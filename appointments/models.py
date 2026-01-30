import hashlib
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from wellbeing.models import ChildProfile, WeeklyWellbeingEntry


def medical_report_upload_path(instance, filename):
    # Isolate by caregiver and appointment for a predictable, scoped layout.
    caregiver_id = instance.uploaded_by_id or 'anonymous'
    appt_id = instance.appointment_id or 'pending'
    safe_name = f"{uuid.uuid4().hex}.pdf"
    return f"medical_reports/caregiver_{caregiver_id}/appt_{appt_id}/{safe_name}"


class Appointment(models.Model):
    REASON_CHOICES = [
        ('CASUAL', 'Casual check-in'),
        ('SEVERE', 'Urgent concern'),
    ]
    TIME_WINDOW_CHOICES = [
        ('09:00', '9:00 AM'),
        ('09:30', '9:30 AM'),
        ('10:00', '10:00 AM'),
        ('10:30', '10:30 AM'),
        ('11:00', '11:00 AM'),
        ('11:30', '11:30 AM'),
        ('12:00', '12:00 PM'),
        ('12:30', '12:30 PM'),
        ('13:00', '1:00 PM'),
        ('13:30', '1:30 PM'),
        ('14:00', '2:00 PM'),
        ('14:30', '2:30 PM'),
        ('15:00', '3:00 PM'),
        ('15:30', '3:30 PM'),
        ('16:00', '4:00 PM'),
        ('16:30', '4:30 PM'),
        ('17:00', '5:00 PM'),
    ]

    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Requested'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    STATUS_CHOICES = Status.choices

    # Allowed forward transitions. Used by transition_to() to reject illegal moves.
    ALLOWED_TRANSITIONS = {
        Status.REQUESTED: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.COMPLETED, Status.CANCELLED},
        Status.COMPLETED: set(),
        Status.CANCELLED: set(),
    }

    caregiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requested_appointments')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='appointments')
    clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_appointments',
        limit_choices_to={'role': 'CLINICIAN', 'clinician_verified': True, 'is_active': True}
    )
    entry = models.ForeignKey(WeeklyWellbeingEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_appointments')

    reason_type = models.CharField(max_length=15, choices=REASON_CHOICES)
    reason_text = models.TextField()
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time_window = models.CharField(max_length=15, choices=TIME_WINDOW_CHOICES)

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=Status.REQUESTED)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appt: {self.child} ({self.get_status_display()})"

    # ---------- State transitions ---------- #

    def can_transition_to(self, new_status) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        """Raise ValidationError on an illegal transition. Caller is responsible for saving."""
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Illegal transition: {self.get_status_display()} → {new_status}."
            )
        self.status = new_status

    # ---------- Access control helpers ---------- #

    def report_accessible_by(self, user) -> bool:
        """
        Policy gate for the attached medical report (PDF).
          - Caregiver: always may read their own appointment's report.
          - Clinician (assigned + verified): only once status is CONFIRMED or COMPLETED.
          - Superuser: unrestricted (admin oversight).
        """
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.role == 'CAREGIVER' and self.caregiver_id == user.id:
            return True
        if (
            user.role == 'CLINICIAN'
            and getattr(user, 'clinician_verified', False)
            and user.is_active
            and self.clinician_id == user.id
            and self.status in (self.Status.CONFIRMED, self.Status.COMPLETED)
        ):
            return True
        return False


class MedicalReport(models.Model):
    """
    PDF uploaded by the caregiver when booking an appointment.
    Served via an authenticated endpoint — never via a public MEDIA_URL link.
    """
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='medical_reports',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_medical_reports',
    )
    file = models.FileField(
        upload_to=medical_report_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, default='application/pdf')
    size_bytes = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Report({self.original_filename}) for {self.appointment_id}"

    def compute_sha256(self):
        h = hashlib.sha256()
        self.file.open('rb')
        try:
            for chunk in self.file.chunks():
                h.update(chunk)
        finally:
            self.file.close()
        return h.hexdigest()


class ClinicianReview(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='clinician_review')
    clinician_notes = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for {self.appointment}"


class SupportPlan(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='support_plan')
    title = models.CharField(max_length=200, default="Support Plan")
    recommendations = models.TextField()
    follow_up_required = models.BooleanField(default=True)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan for {self.appointment}"

    @property
    def is_complete(self) -> bool:
        return bool(self.recommendations and self.recommendations.strip())


class AppointmentMessage(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message by {self.sender} on {self.appointment}"


class AppointmentAuditLog(models.Model):
    """
    Immutable audit trail of sensitive actions: state transitions, report
    uploads, report access, support-plan issuance. Never mutate rows —
    only insert.
    """
    class Action(models.TextChoices):
        BOOKED = 'BOOKED', 'Appointment booked'
        CONFIRMED = 'CONFIRMED', 'Appointment confirmed'
        COMPLETED = 'COMPLETED', 'Case completed'
        CANCELLED = 'CANCELLED', 'Appointment cancelled'
        REPORT_UPLOADED = 'REPORT_UPLOADED', 'Medical report uploaded'
        REPORT_ACCESSED = 'REPORT_ACCESSED', 'Medical report accessed'
        REPORT_ACCESS_DENIED = 'REPORT_ACCESS_DENIED', 'Medical report access denied'
        PLAN_ISSUED = 'PLAN_ISSUED', 'Support plan issued'

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    from_status = models.CharField(max_length=15, blank=True, default='')
    to_status = models.CharField(max_length=15, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        who = self.actor.username if self.actor else 'system'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {who} · {self.action} · appt={self.appointment_id}"
