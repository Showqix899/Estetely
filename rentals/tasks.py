"""Background tasks for the rentals app (run by the Celery worker / beat)."""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .cache_utils import bump_cache_version
from .models import Lease,LeaseRequest


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


@shared_task
def send_request_status_email(request_id):
    """
    Email about a lease request:
      * a NEW (pending) request  -> email goes to the property owner
      * approved / rejected      -> email goes to the tenant
    """
    lease_request = LeaseRequest.objects.select_related("property__owner", "tenant").filter(id=request_id).first()
    if lease_request is None:
        return

    rental = lease_request.property
    if lease_request.status == "pending":
        recipient = rental.owner.email
        subject = "New lease request"
        message = (
            f"{lease_request.tenant.full_name} wants to rent '{rental.title}' "
            f"from {lease_request.start_date} to {lease_request.end_date}.\n\n"
            f"Message: {lease_request.message or '-'}\n\n"
            f"Log in to approve or reject it."
        )
    else:
        recipient = lease_request.tenant.email
        subject = f"Your lease request was {lease_request.status}"
        message = f"Your request to rent '{rental.title}' was {lease_request.status} by the owner."

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
    )