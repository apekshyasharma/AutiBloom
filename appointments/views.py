from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import (
    JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, FileResponse, Http404,
)
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings

from .models import (
    Appointment, ClinicianReview, SupportPlan, AppointmentMessage,
    MedicalReport, AppointmentAuditLog,
)
from .forms import AppointmentRequestForm, ClinicianReviewForm, SupportPlanForm, validate_pdf_upload
from wellbeing.models import CaregiverChild, WeeklyWellbeingEntry
from accounts.models import User


# ---------- Role helpers ---------- #

def is_caregiver(user):
    return user.role == 'CAREGIVER' or user.is_superuser


def is_verified_clinician(user):
    return (
        user.role == 'CLINICIAN'
        and getattr(user, 'clinician_verified', False)
        and user.is_active
    )


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _audit(appointment, actor, action, request=None, from_status='', to_status='', **metadata):
    AppointmentAuditLog.objects.create(
        appointment=appointment,
        actor=actor if (actor and actor.is_authenticated) else None,
        action=action,
        from_status=from_status or '',
        to_status=to_status or '',
        metadata=metadata or {},
        ip_address=_client_ip(request) if request else None,
    )


# ----------------- CAREGIVER VIEWS ----------------- #

@login_required
@user_passes_test(is_caregiver)
def caregiver_appointment_list(request):
    appointments = Appointment.objects.filter(caregiver=request.user).order_by('-created_at')
    return render(request, 'appointments/caregiver_list.html', {'appointments': appointments})


@login_required
@user_passes_test(is_caregiver)
def caregiver_request_appointment(request):
    latest_appt = Appointment.objects.filter(
        caregiver=request.user, clinician__isnull=False
    ).order_by('-created_at').first()
    suggested_clinician = latest_appt.clinician if latest_appt else User.objects.filter(
        role='CLINICIAN', clinician_verified=True, is_active=True
    ).first()

    child_rels = CaregiverChild.objects.filter(caregiver=request.user)
    if not child_rels.exists():
        messages.error(request, "You must add a child profile before requesting an appointment.")
        return redirect('dashboard')

    first_child = child_rels.first().child
    suggested_entry = WeeklyWellbeingEntry.objects.filter(
        child=first_child, caregiver=request.user, status='SUBMITTED'
    ).order_by('-week_start').first()

    initial_data = {}
    if suggested_clinician:
        initial_data['clinician'] = suggested_clinician
    if suggested_entry:
        initial_data['entry'] = suggested_entry
        initial_data['child'] = first_child

    if request.method == 'POST':
        form = AppointmentRequestForm(request.POST, request.FILES, caregiver=request.user)
        uploaded_files = request.FILES.getlist('medical_report_files')

        # Require at least one PDF OR a linked wellbeing entry. A caregiver
        # who already has a submitted weekly entry should not be forced to
        # re-upload the same thing as a PDF.
        has_entry = bool(request.POST.get('entry'))
        if not uploaded_files and not has_entry:
            form.add_error(None, "Attach at least one medical report (PDF) or link a wellbeing report.")

        # Pre-validate each uploaded PDF before touching the DB.
        for f in uploaded_files:
            try:
                validate_pdf_upload(f)
            except ValidationError as e:
                form.add_error(None, e.messages[0])

        if form.is_valid():
            with transaction.atomic():
                appt = form.save(commit=False)
                appt.caregiver = request.user
                appt.save()

                created_reports = []
                for f in uploaded_files:
                    report = MedicalReport(
                        appointment=appt,
                        uploaded_by=request.user,
                        file=f,
                        original_filename=f.name,
                        content_type=f.content_type or 'application/pdf',
                        size_bytes=f.size,
                    )
                    report.save()
                    try:
                        report.sha256 = report.compute_sha256()
                        report.save(update_fields=['sha256'])
                    except Exception:
                        pass
                    created_reports.append(report)

                week_str = (
                    f"the week of {appt.entry.week_start.strftime('%b %d')}"
                    if appt.entry else "no specific week"
                )
                attached_bits = []
                if created_reports:
                    attached_bits.append(
                        f"{len(created_reports)} medical report(s): "
                        + ", ".join(r.original_filename for r in created_reports)
                    )
                if appt.entry:
                    attached_bits.append(f"wellbeing report ({week_str})")

                sys_msg = (
                    f"A new appointment request was created. "
                    f"Attached: {'; '.join(attached_bits) if attached_bits else 'no reports'}. "
                    f"Reason: {appt.get_reason_type_display()}."
                )
                AppointmentMessage.objects.create(appointment=appt, sender=request.user, body=sys_msg)

                _audit(
                    appt, request.user, AppointmentAuditLog.Action.BOOKED, request=request,
                    to_status=appt.status,
                    report_count=len(created_reports),
                    report_filenames=[r.original_filename for r in created_reports],
                    wellbeing_entry_id=appt.entry_id,
                )
                for r in created_reports:
                    _audit(
                        appt, request.user, AppointmentAuditLog.Action.REPORT_UPLOADED, request=request,
                        report_id=r.id,
                        report_filename=r.original_filename,
                    )

            if getattr(settings, 'EMAIL_HOST', None) and appt.clinician and appt.clinician.email:
                try:
                    send_mail(
                        subject=f"AutiBloom Consultation Request: {appt.child.name}",
                        message=(
                            f"You have a new '{appt.get_reason_type_display()}' consultation request "
                            f"from {request.user.get_full_name() or request.user.username}.\n\n"
                            f"A medical report has been attached. You will be able to view it once "
                            f"you confirm the appointment.\n\n"
                            f"Log in to review: AutiBloom dashboard."
                        ),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@autibloom.com'),
                        recipient_list=[appt.clinician.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"SMTP Error handled safely: {e}")

            messages.success(
                request,
                f"Appointment requested with {appt.clinician.get_full_name() or appt.clinician.username} for {appt.child.name}."
            )
            return redirect('caregiver_appointment_list')
    else:
        form = AppointmentRequestForm(initial=initial_data, caregiver=request.user)

    no_clinicians = not User.objects.filter(
        role='CLINICIAN', clinician_verified=True, is_active=True
    ).exists()

    return render(request, 'appointments/caregiver_request.html', {
        'form': form,
        'no_clinicians': no_clinicians,
    })


@login_required
@user_passes_test(is_caregiver)
def caregiver_appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, caregiver=request.user)
    return render(request, 'appointments/caregiver_detail.html', {'appointment': appointment})


# ----------------- CLINICIAN VIEWS ----------------- #

@login_required
@user_passes_test(is_verified_clinician, login_url='/not-authorized/')
def clinician_appointment_list(request):
    appointments = Appointment.objects.filter(clinician=request.user).order_by('-created_at')
    return render(request, 'appointments/clinician_list.html', {'appointments': appointments})


@login_required
@user_passes_test(is_verified_clinician, login_url='/not-authorized/')
def clinician_appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, clinician=request.user)
    return render(request, 'appointments/clinician_detail.html', {'appointment': appointment})


@login_required
@user_passes_test(is_verified_clinician, login_url='/not-authorized/')
def clinician_write_review(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, clinician=request.user)

    review_instance, _ = ClinicianReview.objects.get_or_create(appointment=appointment)
    plan_instance, _ = SupportPlan.objects.get_or_create(appointment=appointment)

    if request.method == 'POST':
        review_form = ClinicianReviewForm(request.POST, instance=review_instance)
        plan_form = SupportPlanForm(request.POST, instance=plan_instance)

        if review_form.is_valid() and plan_form.is_valid():
            review_form.save()
            plan_form.save()

            if 'mark_completed' in request.POST:
                action = 'complete'
            elif 'mark_confirmed' in request.POST:
                action = 'confirm'
            else:
                action = 'draft'

            # -- SAVE DRAFT --
            if action == 'draft':
                messages.success(request, "Draft saved. You can resume this review any time from Assigned Cases.")
                return redirect('clinician_appointment_list')

            # -- CONFIRM --
            if action == 'confirm':
                prev_status = appointment.status
                try:
                    appointment.transition_to(Appointment.Status.CONFIRMED)
                except ValidationError:
                    messages.warning(
                        request,
                        f"Cannot confirm — case is already {appointment.get_status_display().lower()}."
                    )
                    return redirect('clinician_write_review', appointment_id=appointment.id)

                appointment.confirmed_at = timezone.now()
                appointment.save(update_fields=['status', 'confirmed_at', 'updated_at'])

                clinician_name = request.user.get_full_name() or request.user.username

                AppointmentMessage.objects.create(
                    appointment=appointment, sender=request.user,
                    body=(
                        f"Good news! Your appointment for {appointment.child.name} has been confirmed "
                        f"by Dr. {clinician_name}.\n\n"
                        f"The clinician is now reviewing the attached reports and will prepare a "
                        f"personalised support plan. You will be notified once the review is complete."
                    ),
                )
                _audit(
                    appointment, request.user, AppointmentAuditLog.Action.CONFIRMED, request=request,
                    from_status=prev_status, to_status=appointment.status,
                )

                if getattr(settings, 'EMAIL_HOST', None) and appointment.caregiver.email:
                    try:
                        send_mail(
                            subject=f"AutiBloom: Appointment Confirmed for {appointment.child.name}",
                            message=(
                                f"Dear {appointment.caregiver.get_full_name() or appointment.caregiver.username},\n\n"
                                f"Your consultation request for {appointment.child.name} has been confirmed "
                                f"by Dr. {clinician_name}.\n\n"
                                f"The clinician is reviewing the case and will issue a support plan shortly. "
                                f"You can check the status anytime by logging into AutiBloom.\n\n"
                                f"— The AutiBloom Team"
                            ),
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@autibloom.com'),
                            recipient_list=[appointment.caregiver.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"SMTP Error handled safely: {e}")

                messages.success(
                    request,
                    "Appointment confirmed. The caregiver has been notified and the medical report is now unlocked.",
                    extra_tags='dialog dialog-confirmed',
                )
                return redirect('clinician_appointment_detail', appointment_id=appointment.id)

            # -- COMPLETE CASE --
            if action == 'complete':
                if not plan_instance.is_complete:
                    messages.error(
                        request,
                        "You must provide recommendations in the Support Plan before completing a case."
                    )
                    return redirect('clinician_write_review', appointment_id=appointment.id)

                prev_status = appointment.status
                try:
                    appointment.transition_to(Appointment.Status.COMPLETED)
                except ValidationError:
                    if prev_status == Appointment.Status.REQUESTED:
                        messages.warning(
                            request,
                            "You must confirm the appointment before completing the case."
                        )
                    else:
                        messages.warning(
                            request,
                            f"Cannot complete — case is {appointment.get_status_display().lower()}."
                        )
                    return redirect('clinician_write_review', appointment_id=appointment.id)

                appointment.completed_at = timezone.now()
                appointment.save(update_fields=['status', 'completed_at', 'updated_at'])

                clinician_name = request.user.get_full_name() or request.user.username
                plan_title = plan_instance.title or "Support Plan"

                AppointmentMessage.objects.create(
                    appointment=appointment, sender=request.user,
                    body=(
                        f"Your clinical review for {appointment.child.name} is now complete.\n\n"
                        f"Dr. {clinician_name} has issued a support plan: \"{plan_title}\".\n\n"
                        f"Please open your appointment details to view the full recommendations, "
                        f"follow-up instructions, and clinical guidance.\n\n"
                        f"Note: This support plan is based on the information shared through AutiBloom "
                        f"and is intended as guidance. Always consult your child's primary healthcare "
                        f"provider before making significant changes."
                    ),
                )
                _audit(
                    appointment, request.user, AppointmentAuditLog.Action.COMPLETED, request=request,
                    from_status=prev_status, to_status=appointment.status,
                    plan_id=plan_instance.id,
                )
                _audit(
                    appointment, request.user, AppointmentAuditLog.Action.PLAN_ISSUED, request=request,
                    plan_id=plan_instance.id,
                    plan_title=plan_title,
                    follow_up_required=plan_instance.follow_up_required,
                )

                if getattr(settings, 'EMAIL_HOST', None) and appointment.caregiver.email:
                    try:
                        follow_up_text = ""
                        if plan_instance.follow_up_required:
                            follow_up_text = "\n\nA follow-up has been recommended"
                            if plan_instance.follow_up_date:
                                follow_up_text += f" for {plan_instance.follow_up_date.strftime('%B %d, %Y')}"
                            follow_up_text += "."

                        send_mail(
                            subject=f"AutiBloom: Support Plan Ready — {appointment.child.name}",
                            message=(
                                f"Dear {appointment.caregiver.get_full_name() or appointment.caregiver.username},\n\n"
                                f"Dr. {clinician_name} has completed the clinical review for "
                                f"{appointment.child.name} and issued a support plan.\n\n"
                                f"Plan: {plan_title}\n"
                                f"Status: Completed{follow_up_text}\n\n"
                                f"Please log in to AutiBloom to view the full recommendations "
                                f"and personalised guidance.\n\n"
                                f"Important: This plan is intended as clinical guidance based on "
                                f"the information shared. Always consult your child's primary "
                                f"healthcare provider.\n\n"
                                f"— The AutiBloom Clinical Team"
                            ),
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@autibloom.com'),
                            recipient_list=[appointment.caregiver.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"SMTP Error handled safely: {e}")

                messages.success(
                    request,
                    "Case completed and support plan delivered to the caregiver.",
                    extra_tags='dialog dialog-completed',
                )
                return redirect('clinician_appointment_detail', appointment_id=appointment.id)
    else:
        review_form = ClinicianReviewForm(instance=review_instance)
        plan_form = SupportPlanForm(instance=plan_instance)

    return render(request, 'appointments/clinician_review.html', {
        'appointment': appointment,
        'review_form': review_form,
        'plan_form': plan_form,
        'report_accessible': appointment.report_accessible_by(request.user),
    })


@login_required
@user_passes_test(is_verified_clinician, login_url='/not-authorized/')
def clinician_appointment_report_json(request, appointment_id):
    """Wellbeing JSON payload — gated by status so pre-confirmation clinicians can't peek."""
    appointment = get_object_or_404(Appointment, id=appointment_id, clinician=request.user)

    if not appointment.report_accessible_by(request.user):
        _audit(
            appointment, request.user, AppointmentAuditLog.Action.REPORT_ACCESS_DENIED,
            request=request, reason='status_gate_json',
        )
        return HttpResponseForbidden("You must confirm this appointment before accessing reports.")

    if not appointment.entry:
        return HttpResponseBadRequest("No weekly report attached to this appointment.")

    entry = appointment.entry
    child = appointment.child

    missing_fields = []
    if not child.sex:           missing_fields.append('sex')
    if not child.jaundice:      missing_fields.append('jaundice')
    if not child.family_asd:    missing_fields.append('family_asd')
    if not child.date_of_birth: missing_fields.append('date_of_birth')

    if missing_fields:
        return JsonResponse(
            {"error": "Child profile missing vital signs", "missing": ",".join(missing_fields)},
            status=400,
        )

    today = timezone.localdate()
    age_years = today.year - child.date_of_birth.year - (
        (today.month, today.day) < (child.date_of_birth.month, child.date_of_birth.day)
    )

    payload = {
        "age_years":  age_years,
        "sex":        child.sex,
        "jaundice":   child.jaundice,
        "family_asd": child.family_asd,
    }

    answers = entry.answers.all()
    answer_map = {ans.question.code.lower(): ans for ans in answers}
    expected_codes = [f"a{i}" for i in range(1, 11)]

    missing_flags = []
    for code in expected_codes:
        if code in answer_map and answer_map[code].binary_flag is not None:
            payload[code] = answer_map[code].binary_flag
        else:
            missing_flags.append(code)

    if missing_flags:
        return JsonResponse({
            "error": "Missing answer binary flags required for export.",
            "missing_fields": missing_flags,
        }, status=400)

    return JsonResponse(payload)


# ----------------- SECURE FILE ACCESS ----------------- #

@login_required
def appointment_report_download(request, appointment_id, report_id):
    """
    Authenticated, policy-gated download for uploaded medical report PDFs.

    Flow:
      - @login_required → authenticated session required (fixes the spurious
        redirect-to-login when a session was mis-handled).
      - appointment.report_accessible_by() enforces RBAC + state gate
        (caregiver always; clinician only after CONFIRMED).
      - Access (allowed or denied) is recorded in the audit log.
      - PDF is streamed inline via FileResponse — never exposed at MEDIA_URL,
        so copy-pasted links don't leak.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)
    report = get_object_or_404(MedicalReport, id=report_id, appointment=appointment)

    if not appointment.report_accessible_by(request.user):
        _audit(
            appointment, request.user, AppointmentAuditLog.Action.REPORT_ACCESS_DENIED,
            request=request, report_id=report.id, reason='policy_gate',
        )
        return HttpResponseForbidden(
            "You do not have access to this report yet. "
            "Clinicians must confirm the appointment first."
        )

    try:
        response = FileResponse(
            report.file.open('rb'),
            content_type='application/pdf',
            as_attachment=False,
            filename=report.original_filename or 'medical_report.pdf',
        )
    except FileNotFoundError:
        raise Http404("Report file is missing on the server.")

    # Defence-in-depth — prevent caches and framing of PHI.
    response['Cache-Control'] = 'private, no-store, max-age=0, must-revalidate'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Referrer-Policy'] = 'no-referrer'

    _audit(
        appointment, request.user, AppointmentAuditLog.Action.REPORT_ACCESSED,
        request=request, report_id=report.id,
    )
    return response


# ----------------- INLINE CONFIRM (from cases list) ----------------- #

@login_required
@user_passes_test(is_verified_clinician, login_url='/not-authorized/')
@require_POST
def clinician_confirm_appointment(request, appointment_id):
    """
    One-click confirm from the cases list. Flips REQUESTED → CONFIRMED,
    notifies the caregiver, writes the audit entry, and bounces back to
    wherever the clinician clicked from.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id, clinician=request.user)
    prev_status = appointment.status

    try:
        appointment.transition_to(Appointment.Status.CONFIRMED)
    except ValidationError:
        messages.warning(
            request,
            f"Cannot confirm — case is already {appointment.get_status_display().lower()}."
        )
        return redirect(request.META.get('HTTP_REFERER') or 'clinician_appointment_list')

    appointment.confirmed_at = timezone.now()
    appointment.save(update_fields=['status', 'confirmed_at', 'updated_at'])

    clinician_name = request.user.get_full_name() or request.user.username
    AppointmentMessage.objects.create(
        appointment=appointment, sender=request.user,
        body=(
            f"Good news! Your appointment for {appointment.child.name} has been confirmed "
            f"by Dr. {clinician_name}. The clinician is now reviewing the attached reports."
        ),
    )
    _audit(
        appointment, request.user, AppointmentAuditLog.Action.CONFIRMED, request=request,
        from_status=prev_status, to_status=appointment.status,
    )

    if getattr(settings, 'EMAIL_HOST', None) and appointment.caregiver.email:
        try:
            send_mail(
                subject=f"AutiBloom: Appointment Confirmed for {appointment.child.name}",
                message=(
                    f"Dear {appointment.caregiver.get_full_name() or appointment.caregiver.username},\n\n"
                    f"Your consultation request for {appointment.child.name} has been confirmed "
                    f"by Dr. {clinician_name}. A support plan will follow shortly.\n\n"
                    f"— The AutiBloom Team"
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@autibloom.com'),
                recipient_list=[appointment.caregiver.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"SMTP Error handled safely: {e}")

    messages.success(
        request,
        f"Appointment for {appointment.child.name} confirmed. The caregiver has been notified and the medical report is now unlocked.",
        extra_tags='dialog dialog-confirmed',
    )
    return redirect('clinician_appointment_list')


# ----------------- MESSAGES ----------------- #

@login_required
def appointment_messages_page(request, appointment_id):
    """
    Dedicated messaging thread page for an appointment. Shared by caregiver
    and assigned clinician — both roles see the same thread and can post.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # RBAC — the appointment's two authorised roles plus admin.
    user = request.user
    is_authorized = (
        user.is_superuser
        or (user.role == 'CAREGIVER' and appointment.caregiver_id == user.id)
        or (
            user.role == 'CLINICIAN'
            and getattr(user, 'clinician_verified', False)
            and appointment.clinician_id == user.id
        )
    )
    if not is_authorized:
        return HttpResponseForbidden("Not authorized to view this thread.")

    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        if body:
            AppointmentMessage.objects.create(appointment=appointment, sender=user, body=body)
        return redirect('appointment_messages_page', appointment_id=appointment.id)

    return render(request, 'appointments/messages_thread.html', {
        'appointment': appointment,
        'messages_list': appointment.messages.select_related('sender').all(),
    })


@login_required
@require_POST
def add_appointment_message(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    is_authorized = False
    if request.user.role == 'CAREGIVER' and appointment.caregiver == request.user:
        is_authorized = True
    elif (
        request.user.role == 'CLINICIAN'
        and request.user.clinician_verified
        and appointment.clinician == request.user
    ):
        is_authorized = True

    if not is_authorized:
        return HttpResponseForbidden("Not authorized to post to this thread.")

    body = request.POST.get('body', '').strip()
    if body:
        AppointmentMessage.objects.create(appointment=appointment, sender=request.user, body=body)

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('dashboard')
