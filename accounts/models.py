"""
Database tables for users.

Table 1: User     -> a person who can log in (with email + password)
Table 2: Profile  -> extra details of a user (phone, address, city)
                     One User has exactly ONE Profile  (one-to-one relation)
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Tells Django how to create normal users and superusers."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # the password is saved as a hash, never as plain text
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """The user table. Users log in with their email instead of a username."""

    ROLE_CHOICES = [
        ("owner", "Owner"),    # owns properties and rents them out
        ("tenant", "Tenant"),  # rents a property
    ]

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="tenant")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # can log in to /admin/
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"       # the field used to log in
    REQUIRED_FIELDS = ["full_name"]  # asked by "createsuperuser"

    objects = UserManager()

    def __str__(self):
        return self.email


class Profile(models.Model):
    """Extra information about a user. ONE user <-> ONE profile (one-to-one)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Profile of {self.user.email}"
