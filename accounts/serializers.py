"""
Serializers for the accounts app.

A serializer does two jobs:
  1. Turns a database object into JSON (for responses)
  2. Checks incoming JSON and turns it into a database object (for requests)
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    """Shows / edits the extra details (phone, address, city) of a user."""

    class Meta:
        model = Profile
        fields = ["phone", "address", "city"]


class UserSerializer(serializers.ModelSerializer):
    """
    Shows a user together with their profile.
    The profile is a NESTED serializer: it appears as an object inside the user JSON.
    """

    # required=False: a user without a profile (e.g. created in admin) still works
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "profile"]
        read_only_fields = ["id", "email", "role"]  # these cannot be changed from the API

    def update(self, instance, validated_data):
        """Update the user AND the nested profile """
        profile_data = validated_data.pop("profile", {})

        # 1) update the user table
        instance.full_name = validated_data.get("full_name", instance.full_name)
        instance.save()

        # 2) update the profile table (create it first if it does not exist yet)
        profile, _ = Profile.objects.get_or_create(user=instance)
        for field, value in profile_data.items():
            setattr(profile, field, value)
        profile.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    """Checks the registration form and creates the user + an empty profile."""

    password = serializers.CharField(write_only=True)  # write_only: never sent back in responses
    role = serializers.ChoiceField(choices=["owner", "tenant"], default="tenant")

    class Meta:
        model = User
        fields = ["email", "full_name", "password", "role"]

    def validate_email(self, value):
        """Save emails in lowercase so 'A@x.com' and 'a@x.com' are the same user."""
        return value.lower()

    def validate_password(self, value):
        """Run Django's password rules (min length, not too common, ...)."""
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        Profile.objects.create(user=user)  # every user gets one profile
        return user


class LoginSerializer(serializers.Serializer):
    """Checks that the login form has an email and a password."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ForgotPasswordSerializer(serializers.Serializer):
    """Checks the 'forgot password' form (only an email)."""

    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    """Checks the 'reset password' form: uid + token (from the email) and the new password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


# ---- The serializers below are only used to DESCRIBE responses in the Swagger docs ----
class MessageSerializer(serializers.Serializer):
    """Response like {"message": "..."}"""

    message = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    """Response like {"error": "..."}"""

    error = serializers.CharField()


class RegisterResponseSerializer(serializers.Serializer):
    """Response of the register endpoint."""

    message = serializers.CharField()
    user = UserSerializer()


class LoginResponseSerializer(serializers.Serializer):
    """Response of the login endpoint."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class RefreshRequestSerializer(serializers.Serializer):
    """Body of the token refresh endpoint."""

    refresh = serializers.CharField()


class AccessTokenSerializer(serializers.Serializer):
    """Response of the token refresh endpoint."""

    access = serializers.CharField()
