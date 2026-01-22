from django.contrib.auth.models import AbstractUser
from django.db import models


def avatar_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    return f"avatars/user_{instance.id or 'new'}/{instance.username}.{ext}"


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        CAREGIVER = "CAREGIVER", "Caregiver"
        CLINICIAN = "CLINICIAN", "Clinician"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CAREGIVER,
    )

    # Clinicians must be created/verified by Admin
    clinician_verified = models.BooleanField(default=False)

    # Date from which weekly tracking intervals are calculated.
    # Set once on first child creation; never overwritten.
    tracking_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Anchor date for weekly tracking intervals (set on first child creation).",
    )

    # ---------- Shared profile fields ---------- #
    avatar = models.ImageField(upload_to=avatar_upload_path, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    bio = models.TextField(blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True, default='')

    # ---------- Clinician-only fields (unused for caregivers/admins) ---------- #
    specialization = models.CharField(max_length=120, blank=True, default='')
    license_number = models.CharField(max_length=80, blank=True, default='')
    years_of_experience = models.PositiveIntegerField(null=True, blank=True)
    qualifications = models.TextField(blank=True, default='')

    # ---------- Settings / preferences ---------- #
    notify_email = models.BooleanField(
        default=True,
        help_text="Receive transactional emails (appointment updates, support plans).",
    )
    notify_appointments = models.BooleanField(
        default=True,
        help_text="Receive in-app reminders for upcoming appointments.",
    )
    notify_community_digest = models.BooleanField(
        default=False,
        help_text="Weekly digest of community posts and unread thread messages.",
    )
    preferred_timezone = models.CharField(max_length=64, blank=True, default='UTC')

    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def is_caregiver(self) -> bool:
        return self.role == self.Role.CAREGIVER

    def is_clinician(self) -> bool:
        return self.role == self.Role.CLINICIAN

    @property
    def initials(self) -> str:
        name = (self.get_full_name() or self.username or '').strip()
        parts = [p for p in name.split() if p]
        if not parts:
            return '?'
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username
