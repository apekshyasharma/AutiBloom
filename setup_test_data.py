"""
AutiBloom — Test data setup for Postman endpoint testing.

Run from the project root (same folder as manage.py):

    python manage.py shell < setup_test_data.py

What it creates:
  Users (all passwords are in the printed output):
    admin_test                       — ADMIN
    caregiver_test                   — CAREGIVER (with seeded child + entries + appointment)
    caregiver_fresh                  — CAREGIVER (no children — for onboarding test)
    caregiver_peer                   — CAREGIVER (for community messaging tests)
    clinician_verified_test          — CLINICIAN, verified=True
    clinician_unverified_test        — CLINICIAN, verified=False

  Data for caregiver_test:
    - One ChildProfile ("Test Child") linked via CaregiverChild
    - One DRAFT WeeklyWellbeingEntry (current week) with empty answers
    - One SUBMITTED WeeklyWellbeingEntry (previous week) with answers
    - One Appointment assigned to clinician_verified_test
    - CaregiverCommunityProfile (opted in, city=Kathmandu, postal=44600)
    - A Thread with caregiver_peer + one seed message

  Plus: a minimum of 10 WellbeingQuestion rows if the table is empty.

At the end, an "IDS FOR POSTMAN" block is printed — copy those values into
the Postman environment variables (child_id, draft_entry_id, etc.).

Safe to re-run: uses get_or_create everywhere.
"""
import datetime
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from wellbeing.models import (
    ChildProfile, CaregiverChild, WellbeingQuestion,
    WeeklyWellbeingEntry, WeeklyWellbeingAnswer,
)
from community.models import CaregiverCommunityProfile, Thread, Message

User = get_user_model()

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def make_user(username, password, role, verified=True, active=True, email=None):
    email = email or f"{username}@test.local"
    u, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "role": role},
    )
    if created:
        u.set_password(password)
    else:
        u.set_password(password)
    u.email = email
    u.role = role
    if role == "CLINICIAN":
        u.clinician_verified = verified
    if role == "ADMIN":
        u.is_staff = True
        u.is_superuser = True
    u.is_active = active
    u.save()
    print(f"  {'created' if created else 'updated'}: {username}  (role={role}, id={u.id})")
    return u

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
with transaction.atomic():
    print("\n=== Creating test users ===")
    admin       = make_user("admin_test",                "AdminPass123!",       "ADMIN")
    caregiver   = make_user("caregiver_test",            "CaregiverPass123!",   "CAREGIVER")
    cg_fresh    = make_user("caregiver_fresh",           "CaregiverPass123!",   "CAREGIVER")
    cg_peer     = make_user("caregiver_peer",            "CaregiverPass123!",   "CAREGIVER")
    clin_v      = make_user("clinician_verified_test",   "ClinicianPass123!",   "CLINICIAN", verified=True)
    clin_u      = make_user("clinician_unverified_test", "ClinicianPass123!",   "CLINICIAN", verified=False)

    # Set tracking_start_date so dashboard logic works cleanly
    today = timezone.localdate()
    last_monday = today - datetime.timedelta(days=today.weekday())
    if not caregiver.tracking_start_date:
        caregiver.tracking_start_date = last_monday - datetime.timedelta(weeks=2)
        caregiver.save(update_fields=["tracking_start_date"])

    # ------------------------------------------------------------------
    print("\n=== Seeding wellbeing questions (if empty) ===")
    if WellbeingQuestion.objects.count() == 0:
        for i in range(1, 11):
            WellbeingQuestion.objects.create(
                code=f"a{i}",
                text=f"Question A{i} — placeholder text.",
                is_active=True,
            )
        print(f"  created 10 questions (a1..a10)")
    else:
        print(f"  already has {WellbeingQuestion.objects.count()} questions")

    # ------------------------------------------------------------------
    print("\n=== Creating child profile for caregiver_test ===")
    child, _ = ChildProfile.objects.get_or_create(
        name="Test Child",
        defaults={
            "date_of_birth": datetime.date(2019, 5, 15),
            "sex": "m",
            "jaundice": "no",
            "family_asd": "no",
        },
    )
    # Backfill valid values in case a previous run saved uppercase "M"
    if child.sex not in ("m", "f"):
        child.sex = "m"
    if child.jaundice not in ("yes", "no"):
        child.jaundice = "no"
    if child.family_asd not in ("yes", "no"):
        child.family_asd = "no"
    child.save()
    print(f"  child: {child.name} (id={child.id})")

    CaregiverChild.objects.get_or_create(caregiver=caregiver, child=child)

    # ------------------------------------------------------------------
    print("\n=== Creating weekly entries ===")
    # SUBMITTED entry (previous week)
    prev_monday = last_monday - datetime.timedelta(weeks=1)
    submitted_entry, created = WeeklyWellbeingEntry.objects.get_or_create(
        caregiver=caregiver,
        child=child,
        week_start=prev_monday,
        defaults={
            "week_end": prev_monday + datetime.timedelta(days=6),
            "status": "SUBMITTED",
            "submitted_at": timezone.now() - datetime.timedelta(days=2),
        },
    )
    if created:
        submitted_entry.status = "SUBMITTED"
        submitted_entry.submitted_at = timezone.now() - datetime.timedelta(days=2)
        submitted_entry.save()
    # Fill answers with binary_flag
    for q in WellbeingQuestion.objects.filter(is_active=True):
        WeeklyWellbeingAnswer.objects.get_or_create(
            entry=submitted_entry,
            question=q,
            defaults={"slider_score": 4, "binary_flag": 0, "comment": ""},
        )
    print(f"  submitted entry id={submitted_entry.id} (week_start={prev_monday})")

    # DRAFT entry (current week)
    draft_entry, _ = WeeklyWellbeingEntry.objects.get_or_create(
        caregiver=caregiver,
        child=child,
        week_start=last_monday,
        defaults={
            "week_end": last_monday + datetime.timedelta(days=6),
            "status": "DRAFT",
        },
    )
    for q in WellbeingQuestion.objects.filter(is_active=True):
        WeeklyWellbeingAnswer.objects.get_or_create(
            entry=draft_entry, question=q,
            defaults={"slider_score": None, "binary_flag": None},
        )
    print(f"  draft entry id={draft_entry.id} (week_start={last_monday})")

    # Entry with an "incomplete" child (for test 47: missing vitals)
    incomplete_child, _ = ChildProfile.objects.get_or_create(
        name="Incomplete Child",
        defaults={"date_of_birth": datetime.date(2020, 1, 1)},  # deliberately missing sex/jaundice/family_asd
    )
    # wipe the vital fields if they got set
    if incomplete_child.sex or incomplete_child.jaundice or incomplete_child.family_asd:
        ChildProfile.objects.filter(id=incomplete_child.id).update(sex="", jaundice="", family_asd="")
        incomplete_child.refresh_from_db()

    CaregiverChild.objects.get_or_create(caregiver=caregiver, child=incomplete_child)
    incomplete_entry, _ = WeeklyWellbeingEntry.objects.get_or_create(
        caregiver=caregiver,
        child=incomplete_child,
        week_start=prev_monday,
        defaults={
            "week_end": prev_monday + datetime.timedelta(days=6),
            "status": "SUBMITTED",
            "submitted_at": timezone.now(),
        },
    )
    print(f"  incomplete entry id={incomplete_entry.id}")

    # ------------------------------------------------------------------
    print("\n=== Creating community profiles + thread ===")
    CaregiverCommunityProfile.objects.update_or_create(
        user=caregiver,
        defaults={"opt_in": True, "city": "Kathmandu", "postal_code": "44600"},
    )
    CaregiverCommunityProfile.objects.update_or_create(
        user=cg_peer,
        defaults={"opt_in": True, "city": "Kathmandu", "postal_code": "44600"},
    )

    thread = Thread.objects.filter(participants=caregiver).filter(participants=cg_peer).first()
    if not thread:
        thread = Thread.objects.create()
        thread.participants.add(caregiver, cg_peer)
    if thread.messages.count() == 0:
        Message.objects.create(thread=thread, sender=cg_peer, body="Hi there — seed message from peer.")
    print(f"  thread id={thread.id}")

    # ------------------------------------------------------------------
    print("\n=== Creating an appointment (optional) ===")
    try:
        from appointments.models import Appointment
        appt, _ = Appointment.objects.get_or_create(
            caregiver=caregiver,
            clinician=clin_v,
            child=child,
            defaults={"entry": submitted_entry, "reason_type": "GENERAL", "status": "PENDING"},
        )
        print(f"  appointment id={appt.id}")
        appt_id = appt.id
    except Exception as e:
        print(f"  (skipped — {type(e).__name__}: {e})")
        appt_id = None

# ------------------------------------------------------------------
# Final block — COPY THESE INTO POSTMAN ENVIRONMENT
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("  IDS FOR POSTMAN ENVIRONMENT — copy the values on the right")
print("=" * 60)
print(f"  child_id               = {child.id}")
print(f"  draft_entry_id         = {draft_entry.id}")
print(f"  submitted_entry_id     = {submitted_entry.id}")
print(f"  incomplete_entry_id    = {incomplete_entry.id}")
# prediction_id: create a placeholder only if predictions app exists
try:
    from wellbeing.models import PredictionResult
    pred = PredictionResult.objects.filter(entry=submitted_entry).first()
    if pred:
        print(f"  prediction_id          = {pred.id}")
    else:
        print(f"  prediction_id          = (run test 46 first to create one)")
except Exception:
    pass
print(f"  thread_id              = {thread.id}")
print(f"  caregiver2_id          = {cg_peer.id}")
print(f"  clinician_v_id         = {clin_v.id}")
print(f"  clinician_u_id         = {clin_u.id}")
# Pick first game slug if games exist
try:
    from games.models import TherapyGame
    g = TherapyGame.objects.filter(is_active=True).first()
    print(f"  game_slug              = {g.slug if g else '(no games seeded; test 68 may 404)'}")
except Exception:
    pass
if appt_id:
    print(f"  appointment_id         = {appt_id}")
print("=" * 60)
print("\nDone.  You can now log in at http://127.0.0.1:8000/ with any of:")
print("   admin_test / AdminPass123!")
print("   caregiver_test / CaregiverPass123!")
print("   caregiver_fresh / CaregiverPass123!")
print("   clinician_verified_test / ClinicianPass123!")
print("   clinician_unverified_test / ClinicianPass123!")