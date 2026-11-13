"""
Background tasks for the accounts app.

A task runs inside the Celery worker, NOT inside the API request.
We call them with .delay(...) so the API does not wait for the email to be sent.
We pass only simple values (ids, strings) to a task, never whole objects.
"""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import User


@shared_task
def send_welcome_email(user_id):
    """Send a 'welcome' email right after a user registers."""
    user = User.objects.filter(id=user_id).first()
    if user is None:
        return
    send_mail(
        subject="Welcome to Estately",
        message=f"Hi {user.full_name},\n\nYour account was created successfully. You can log in now.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


@shared_task
def send_password_reset_email(user_id, uid, token):
    """Send the 'reset your password' email that contains the reset link."""
    user = User.objects.filter(id=user_id).first()
    if user is None:
        return
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Reset your Estately password",
        message=(
            f"Hi {user.full_name},\n\n"
            f"Open this link to choose a new password (valid for 1 hour):\n{link}\n\n"
            f"If you are testing the API directly, send these two values to /api/auth/reset-password/:\n"
            f"uid: {uid}\ntoken: {token}\n\n"
            f"If you did not ask for this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
