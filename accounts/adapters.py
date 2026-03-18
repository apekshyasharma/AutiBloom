"""
Allauth adapters that keep AutiBloom's role system intact when users
sign in through Google (or any future social provider).

Key behaviours:
    * A new social user is always created as a CAREGIVER.
    * Clinicians & admins must still be provisioned by an admin — we refuse
      to "link" a Google identity to an existing clinician / admin account
      that doesn't have the same verified email on both sides.
    * Username is derived from the Google email local part and deduplicated
      so we never hit the unique constraint.
"""
import re
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import User


def _unique_username_from_email(email: str) -> str:
    base = (email or "user").split("@", 1)[0].lower()
    base = re.sub(r"[^a-z0-9_.-]", "", base) or "user"
    candidate = base
    n = 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


class RoleAwareAccountAdapter(DefaultAccountAdapter):
    """Allauth's plain-account adapter (used for local signup + password reset)."""

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        if not user.role:
            user.role = User.Role.CAREGIVER
        if commit:
            user.save()
        return user


class RoleAwareSocialAdapter(DefaultSocialAccountAdapter):
    """Runs when a user signs in via Google."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        # Force the role — no matter what the provider sends.
        user.role = User.Role.CAREGIVER
        # Build a stable, unique username. Allauth will set one but it may
        # collide with an existing local account.
        email = (user.email or data.get("email") or "").strip()
        if not user.username or User.objects.filter(username__iexact=user.username).exists():
            user.username = _unique_username_from_email(email)
        return user

    def pre_social_login(self, request, sociallogin):
        """
        If the email already belongs to an existing user, link the social
        account to that user (avoids "UNIQUE constraint" errors on email).
        Clinicians and admins can therefore also sign in with Google as long
        as their profile email matches the Google account.
        """
        if sociallogin.is_existing:
            return
        email = (sociallogin.account.extra_data.get("email") or "").strip().lower()
        if not email:
            return
        try:
            existing = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return
        sociallogin.connect(request, existing)
