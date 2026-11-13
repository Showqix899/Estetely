"""
Celery setup.

Celery runs "background tasks" (like sending emails) in a separate process
called the worker, so the API can answer the user immediately.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

# Read every setting that starts with CELERY_ from Django's settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Look for a tasks.py file inside every installed app
app.autodiscover_tasks()
