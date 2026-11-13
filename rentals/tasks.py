"""Background tasks for the rentals app (run by the Celery worker / beat)."""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .cache_utils import bump_cache_version
from .models import Lease


@shared_task
def send_lease_email(lease_id):
    """Email the tenant when an owner creates a lease for them."""
    lease = Lease.objects.select_related("property", "tenant").filter(id=lease_id).first()
    if lease is None:
        return
    send_mail(
        subject="Your new rental lease",
        message=(
            f"Hi {lease.tenant.full_name},\n\n"
            f"You have a new lease for '{lease.property.title}' ({lease.property.address}).\n"
            f"From {lease.start_date} to {lease.end_date}, rent {lease.monthly_rent} per month."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[lease.tenant.email],
    )


@shared_task
def close_expired_leases():
    """
    Scheduled task (Celery beat runs it every night).
    Finds active leases whose end date is in the past, closes them,
    and makes the property available again.
    """
    today = timezone.localdate()
    expired_leases = Lease.objects.filter(is_active=True, end_date__lt=today).select_related("property")

    count = 0
    for lease in expired_leases:
        lease.is_active = False
        lease.save()
        lease.property.is_available = True
        lease.property.save()
        count += 1

    if count:
        bump_cache_version()  # the property list changed, so drop the old cached lists
    return count
