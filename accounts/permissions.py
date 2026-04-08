from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    Decorator to restrict access to users with specific roles.
    allowed_roles: list of role strings (e.g., ["ADMIN", "CLINICIAN"])
    """
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.role in allowed_roles:
            return True
        raise PermissionDenied  # Triggers 403

    return user_passes_test(check_role)


def clinician_verified_required(view_func):
    """
    Decorator to ensure a clinician is verified.
    """
    def check_verified(user):
        if not user.is_authenticated:
            return False
        # If not a clinician, this check doesn't apply (or block them if strictly for clinicians)
        # Assuming this decorator is used ON TOP of login_required or role_required usually.
        # But to be safe, if they are a clinician, they must be verified.
        if user.role == "CLINICIAN" and not user.clinician_verified:
            raise PermissionDenied
        return True

    return user_passes_test(check_verified)(view_func)

admin_required = role_required(["ADMIN"])

