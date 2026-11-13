"""
Views for the accounts app. Every view is an APIView class:
one method per HTTP verb (get, post, put ...).
"""
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    AccessTokenSerializer,
    ErrorSerializer,
    ForgotPasswordSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    MessageSerializer,
    RefreshRequestSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from .tasks import send_password_reset_email, send_welcome_email


class RegisterView(APIView):
    """POST /api/auth/register/  -> create a new account."""

    permission_classes = [AllowAny]  # no login needed to register

    @extend_schema(tags=["Auth"], auth=[], request=RegisterSerializer, responses={201: RegisterResponseSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # returns 400 with errors if the data is bad
        user = serializer.save()

        send_welcome_email.delay(user.id)  # sent later by the Celery worker

        return Response(
            {"message": "Account created successfully.", "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/auth/login/  -> check email + password and return JWT tokens."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Auth"], auth=[], request=LoginSerializer, responses={200: LoginResponseSerializer, 401: ErrorSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # authenticate() returns the user if the password is right, otherwise None
        user = authenticate(
            request=request,
            email=serializer.validated_data["email"].lower(),
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),  # short life (30 min): sent with every request
                "refresh": str(refresh),              # long life (7 days): used to get a new access token
                "user": UserSerializer(user).data,
            }
        )


class RefreshTokenView(APIView):
    """POST /api/auth/token/refresh/  -> send the refresh token, get a new access token."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Auth"], auth=[], request=RefreshRequestSerializer, responses={200: AccessTokenSerializer, 401: ErrorSerializer})
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(refresh_token)  # raises TokenError if expired / invalid
        except TokenError:
            return Response({"error": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"access": str(refresh.access_token)})


class MeView(APIView):
    """
    GET   /api/auth/me/  -> see my account + profile
    PATCH /api/auth/me/  -> update my full_name and profile (phone, address, city)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Auth"], responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(tags=["Auth"], request=UserSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data)


class ForgotPasswordView(APIView):
    """POST /api/auth/forgot-password/  -> email a password reset link."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Auth"], auth=[], request=ForgotPasswordSerializer, responses=MessageSerializer)
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))  # the user id, made safe for a URL
            token = default_token_generator.make_token(user)   # one-time token tied to the old password
            send_password_reset_email.delay(user.id, uid, token)

        # Same answer whether the email exists or not, so nobody can find out who is registered
        return Response({"message": "If this email is registered, a reset link has been sent."})


class ResetPasswordView(APIView):
    """POST /api/auth/reset-password/  -> set a new password using the uid + token from the email."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Auth"], auth=[], request=ResetPasswordSerializer, responses={200: MessageSerializer, 400: ErrorSerializer})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Turn the uid back into a user
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data["uid"])))
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            user = None

        # Check the token (it is invalid if expired, or if the password was already changed)
        if user is None or not default_token_generator.check_token(user, data["token"]):
            return Response({"error": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(data["new_password"])
        user.save()
        return Response({"message": "Password has been reset. You can log in now."})
