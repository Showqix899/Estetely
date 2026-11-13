from rest_framework.permissions import BasePermission


class IsOwnerRole(BasePermission):
    """Allows only users whose role is 'owner' (people who rent out properties)."""

    message = "Only property owners can do this."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "owner"
