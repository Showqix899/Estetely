from django.urls import path

from .views import (
    ForgotPasswordView,
    LoginView,
    MeView,
    RefreshTokenView,
    RegisterView,
    ResetPasswordView,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("token/refresh/", RefreshTokenView.as_view()),
    path("me/", MeView.as_view()),
    path("forgot-password/", ForgotPasswordView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),
]
