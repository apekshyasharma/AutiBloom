from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
import datetime

from .models import ChildProfile, CaregiverChild, WeeklyWellbeingEntry, WeeklyWellbeingAnswer, WellbeingQuestion, PredictionResult
from .forms import ChildProfileForm, WeeklyAnswerFormSet
from .services.prediction import build_payload_from_entry, validate_payload
from .services.explainability import build_explanation
from .services.narrative import build_narrative, build_soap_note
from ml.inference import run_inference, ModelNotReadyError

def is_caregiver(user):
    return user.role == 'CAREGIVER' or user.is_superuser


# ──────────────────────────────────────────────────────────
#  Weekly Tracking Helper
# ──────────────────────────────────────────────────────────

def compute_weekly_stats(user, entries):
    """
    Returns weekly tracking stats anchored to the user's tracking_start_date.

    Logic:
    - anchor = user.tracking_start_date  (set once on first child creation)
    - Falls back to the earliest week_start in entries if anchor is not yet set
    - Counts how many 7-day windows from anchor → today have ≥1 SUBMITTED entry
    - Returns dict with:
        submitted_count      – total submitted entries
        weeks_since_signup   – full weeks elapsed since anchor
        weeks_with_entries   – how many of those windows have a submission
        consistency_pct      – int 0-100
        last_submitted_at    – datetime or None
        tracking_start_date  – the anchor date used
    """
    submitted_count = entries.count()
    last_entry = entries.last()
    last_submitted_at = last_entry.submitted_at if last_entry else None

    # Determine anchor
    anchor = user.tracking_start_date if hasattr(user, 'tracking_start_date') else None
    if not anchor:
        if entries.exists():
            anchor = entries.order_by('week_start').first().week_start
        else:
            anchor = timezone.localdate()

    # Normalise anchor to the Monday of its week
    anchor_monday = anchor - datetime.timedelta(days=anchor.weekday())

    # How many full weeks have passed since anchor (inclusive of current week)
    today = timezone.localdate()
    days_elapsed = (today - anchor_monday).days
    weeks_since_signup = max(1, days_elapsed // 7 + 1)  # at least 1

    # Which calendar Mondays correspond to each signup-relative window?
    submitted_week_starts = set(entries.values_list('week_start', flat=True))

    weeks_with_entries = 0
    for w in range(weeks_since_signup):
        window_monday = anchor_monday + datetime.timedelta(weeks=w)
        if window_monday in submitted_week_starts:
            weeks_with_entries += 1

    consistency_pct = int((weeks_with_entries / weeks_since_signup) * 100) if weeks_since_signup else 0

    return {
        'submitted_count':    submitted_count,
        'weeks_since_signup': weeks_since_signup,
        'weeks_tracked':      weeks_with_entries,   # kept for template compatibility
        'consistency_pct':    consistency_pct,
        'last_submitted_at':  last_submitted_at,
        'tracking_start_date': anchor_monday,
    }


# ──────────────────────────────────────────────────────────
#  Dashboard Data Helper
# ──────────────────────────────────────────────────────────

def get_dashboard_data(user, child_id=None):
    """Fetch analytics data for the dashboard."""
    if user.is_superuser:
        if child_id:
            child = get_object_or_404(ChildProfile, id=child_id)
        else:
            child = ChildProfile.objects.first()
    else:
        relationships = CaregiverChild.objects.filter(caregiver=user).select_related('child')
        if not relationships.exists():
            return None, None  # Signal redirect to onboarding

        if child_id:
            relationship = get_object_or_404(CaregiverChild, caregiver=user, child_id=child_id)
            child = relationship.child
        else:
            child = relationships.order_by('-created_at').first().child  # newest child by default

    # Dataset – only SUBMITTED entries, ordered oldest→newest
    entries = WeeklyWellbeingEntry.objects.filter(
        child=child,
        status='SUBMITTED'
    ).order_by('week_start')

    stats = compute_weekly_stats(user, entries)

    # Time series (last 12 entries, chronological)
    chart_entries = entries.order_by('-week_start')[:12][::-1]
    chart_data = {
        'labels':        [e.week_start.strftime("%b %d") for e in chart_entries],
        'overall':       [e.overall_score        for e in chart_entries],
        'communication': [e.communication_score  for e in chart_entries],
        'routines':      [e.routines_score        for e in chart_entries],
        'emotional':     [e.emotional_score       for e in chart_entries],
        'sensory':       [e.sensory_score         for e in chart_entries],
    }

    return child, {
        'stats':            stats,
        'chart_data':       chart_data,
        'selected_child_id': child.id if child else None,
    }


# ──────────────────────────────────────────────────────────
#  Views
# ──────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_caregiver)
def child_list(request):
    """List all children linked to the logged-in caregiver."""
    relationships = CaregiverChild.objects.filter(caregiver=request.user).select_related('child')
    children = [rel.child for rel in relationships]
    return render(request, 'wellbeing/child_list.html', {'children': children})


@login_required
@user_passes_test(is_caregiver)
def wellbeing_dashboard(request):
    """Enhanced dashboard with analytics."""
    child_id = request.GET.get('child_id')
    child, data = get_dashboard_data(request.user, child_id)

    if child is None and not request.user.is_superuser:
        return redirect('wellbeing_child_create')

    # All children for profile switcher
    if request.user.is_superuser:
        all_children = ChildProfile.objects.all()
    else:
        all_children = [
            rel.child
            for rel in CaregiverChild.objects.filter(
                caregiver=request.user
            ).select_related('child').order_by('-created_at')
        ]

    # ── Missed weeks for the selected child ───────────────────────────────────
    missed_weeks = []
    if child and not request.user.is_superuser:
        today = timezone.localdate()
        current_week_start = today - datetime.timedelta(days=today.weekday())

        try:
            rel = CaregiverChild.objects.filter(caregiver=request.user, child=child).first()
            if rel:
                earliest = rel.created_at.date()
                scan_start = earliest - datetime.timedelta(days=earliest.weekday())

                # Batch fetch all submitted week_starts for this child
                submitted = set(
                    WeeklyWellbeingEntry.objects.filter(
                        caregiver=request.user,
                        child=child,
                        status='SUBMITTED',
                        week_start__gte=scan_start,
                        week_start__lte=current_week_start,
                    ).values_list('week_start', flat=True)
                )

                week = scan_start
                while week <= current_week_start:
                    if week not in submitted:
                        week_end = week + datetime.timedelta(days=6)
                        is_current = (week == current_week_start)
                        days_left = 6 - today.weekday() if is_current else 0
                        missed_weeks.append({
                            'week_start': week,
                            'week_end': week_end,
                            'is_current_week': is_current,
                            'days_left': days_left,
                            'label': (
                                f"This week ({week.strftime('%b %d')} – {week_end.strftime('%b %d')})"
                                if is_current else
                                f"Week of {week.strftime('%b %d, %Y')}"
                            ),
                        })
                    week += datetime.timedelta(weeks=1)
        except Exception:
            pass

    context = {
        'child':        child,
        'all_children': all_children,
        'title':        f"Dashboard: {child.name}" if child else "Wellbeing Dashboard",
        'missed_weeks': missed_weeks,
    }
    if data:
        context.update(data)

    return render(request, 'wellbeing/dashboard.html', context)


@login_required
@user_passes_test(is_caregiver)
def dashboard_api(request, child_id):
    """JSON endpoint for dashboard data (used by profile switcher AJAX)."""
    child, data = get_dashboard_data(request.user, child_id)
    if not child:
        return JsonResponse({'error': 'Child not found or access denied'}, status=404)

    # Serialise all date/datetime objects for JSON safely
    if data and 'stats' in data:
        s = data['stats']
        for key in ['last_submitted_at', 'tracking_start_date']:
            val = s.get(key)
            if val and hasattr(val, 'isoformat'):
                s[key] = val.isoformat()
    
    # Add child name for UI updates
    data['child_name'] = child.name

    return JsonResponse(data)


@login_required
@user_passes_test(is_caregiver)
def child_create(request):
    """Create a new child profile and link it to the caregiver."""
    is_onboarding = not CaregiverChild.objects.filter(caregiver=request.user).exists()

    if request.method == 'POST':
        form = ChildProfileForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                child = form.save()
                CaregiverChild.objects.create(caregiver=request.user, child=child)

                # Set tracking_start_date ONCE on first child creation
                if not request.user.tracking_start_date:
                    request.user.tracking_start_date = timezone.localdate()
                    request.user.save(update_fields=['tracking_start_date'])

            messages.success(request, f"Added profile for {child.name}! 🌟")
            # Redirect specifically to the new child so dashboard reflects it immediately
            dashboard_url = reverse('wellbeing_dashboard')
            return redirect(f"{dashboard_url}?child_id={child.id}&event=child_created")
    else:
        form = ChildProfileForm()

    return render(request, 'wellbeing/child_form.html', {
        'form':         form,
        'title':        "Welcome! Let's set up your child's profile" if is_onboarding else 'Add New Child',
        'is_onboarding': is_onboarding,
    })


@login_required
@user_passes_test(is_caregiver)
def child_edit(request, child_id):
    """Edit an existing child profile."""
    if request.user.is_superuser:
        child = get_object_or_404(ChildProfile, id=child_id)
    else:
        relationship = get_object_or_404(CaregiverChild, caregiver=request.user, child_id=child_id)
        child = relationship.child

    if request.method == 'POST':
        form = ChildProfileForm(request.POST, request.FILES, instance=child)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated profile for {child.name}")
            return redirect(f"{reverse('wellbeing_child_detail', args=[child.id])}?event=child_updated")
    else:
        form = ChildProfileForm(instance=child)

    return render(request, 'wellbeing/child_form.html', {'form': form, 'title': f'Edit {child.name}'})


@login_required
@user_passes_test(is_caregiver)
def child_detail(request, child_id):
    """Show child details and their weekly entry history."""
    if request.user.is_superuser:
        child = get_object_or_404(ChildProfile, id=child_id)
    else:
        relationship = get_object_or_404(CaregiverChild, caregiver=request.user, child_id=child_id)
        child = relationship.child

    entries = WeeklyWellbeingEntry.objects.filter(child=child).order_by('-week_start')

    return render(request, 'wellbeing/child_detail.html', {
        'child':   child,
        'entries': entries,
    })


@login_required
@user_passes_test(is_caregiver)
def entry_start(request, child_id):
    """Start or retrieve a draft entry for a specific week."""
    if request.user.is_superuser:
        child = get_object_or_404(ChildProfile, id=child_id)
    else:
        relationship = get_object_or_404(CaregiverChild, caregiver=request.user, child_id=child_id)
        child = relationship.child

    # Determine week_start (Monday of the target week)
    week_start_str = request.GET.get('week_start')
    if week_start_str:
        try:
            target_date = datetime.datetime.strptime(week_start_str, "%Y-%m-%d").date()
            week_start = target_date - datetime.timedelta(days=target_date.weekday())
        except ValueError:
            return HttpResponseBadRequest("Invalid date format")
    else:
        today = timezone.localdate()
        week_start = today - datetime.timedelta(days=today.weekday())

    week_end = week_start + datetime.timedelta(days=6)

    with transaction.atomic():
        entry, created = WeeklyWellbeingEntry.objects.get_or_create(
            caregiver=request.user,
            child=child,
            week_start=week_start,
            defaults={'week_end': week_end}
        )

        questions = WellbeingQuestion.objects.filter(is_active=True)
        existing_q_ids = set(entry.answers.values_list('question_id', flat=True))
        answers_to_create = [
            WeeklyWellbeingAnswer(entry=entry, question=q)
            for q in questions if q.id not in existing_q_ids
        ]
        if answers_to_create:
            WeeklyWellbeingAnswer.objects.bulk_create(answers_to_create)

    return redirect('wellbeing_entry_edit', entry_id=entry.id)


@login_required
@user_passes_test(is_caregiver)
def entry_edit(request, entry_id):
    """Edit answers for a weekly entry with strict integrity."""
    if request.user.is_superuser:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)
    else:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id, caregiver=request.user)

    # Constraint 3: Submitted entry immutability
    if entry.status == 'SUBMITTED' and request.method == 'POST':
        return HttpResponseForbidden("This entry has already been submitted and cannot be edited.")

    if request.method == 'POST':
        formset = WeeklyAnswerFormSet(request.POST, instance=entry)
        if formset.is_valid():
            with transaction.atomic():
                # Constraint 4: Slider integrity (NULL unless touched)
                for form in formset.forms:
                    score = form.cleaned_data.get('slider_score')
                    touched = form.cleaned_data.get('touched') == '1'
                    
                    # If incoming score is presented but user didn't explicitly touch it
                    # AND it was previously NULL, force it back to NULL.
                    if score is not None and not touched:
                        # Check previous state
                        if form.instance.pk:
                            was_none = WeeklyWellbeingAnswer.objects.filter(
                                pk=form.instance.pk, slider_score__isnull=True
                            ).exists()
                            if was_none:
                                form.instance.slider_score = None

                formset.save()
                entry.recompute_metrics()
                entry.save()

            if 'submit_action' in request.POST:
                answers = entry.answers.all()
                unanswered_sliders = answers.filter(slider_score__isnull=True).count()
                unanswered_binary = answers.filter(binary_flag__isnull=True).count()
                total_unanswered = unanswered_sliders + unanswered_binary

                if total_unanswered > 0:
                    messages.error(request, f"You still have {total_unanswered} unanswered question{'s' if total_unanswered > 1 else ''}.")
                    return redirect(f"{reverse('wellbeing_entry_edit', args=[entry.id])}?event=submit_blocked")
                else:
                    entry.status = 'SUBMITTED'
                    entry.submitted_at = timezone.now()
                    entry.save(update_fields=['status', 'submitted_at', 'updated_at'])
                    # Redirect with the Universal Event Modal trigger
                    return redirect(f"{reverse('wellbeing_entry_report', args=[entry.id])}?event=entry_submitted")

            messages.success(request, "Progress saved.")
            return redirect(f"{reverse('wellbeing_entry_edit', args=[entry.id])}?event=entry_saved")
    else:
        formset = WeeklyAnswerFormSet(instance=entry)

    return render(request, 'wellbeing/entry_edit.html', {
        'entry':   entry,
        'formset': formset,
    })


@login_required
@user_passes_test(is_caregiver)
def entry_submit(request, entry_id):
    """Finalize submission of a weekly entry. Blocks if incomplete."""
    if request.user.is_superuser:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)
    else:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id, caregiver=request.user)

    if entry.status == 'SUBMITTED':
        return HttpResponseForbidden("Already submitted.")

    if request.method != 'POST':
        return redirect('wellbeing_entry_edit', entry_id=entry_id)

    # Constraint 2 & Submission Block
    answers = entry.answers.all()
    incomplete = (
        answers.filter(slider_score__isnull=True).exists()
        or answers.filter(binary_flag__isnull=True).exists()
    )
    
    if incomplete:
        messages.error(request, "All 10 questions must be answered before submitting.")
        return redirect(f"{reverse('wellbeing_entry_edit', args=[entry_id])}?event=submit_blocked")

    entry.status = 'SUBMITTED'
    entry.submitted_at = timezone.now()
    entry.save()
    # Redirect with the Universal Event Modal trigger
    return redirect(f"{reverse('wellbeing_entry_report', args=[entry.id])}?event=entry_submitted")


@login_required
@user_passes_test(is_caregiver)
def child_report(request, child_id):
    """Show a trend report of all submitted entries for a child."""
    if request.user.is_superuser:
        child = get_object_or_404(ChildProfile, id=child_id)
    else:
        relationship = get_object_or_404(CaregiverChild, caregiver=request.user, child_id=child_id)
        child = relationship.child

    entries = WeeklyWellbeingEntry.objects.filter(
        child=child,
        status='SUBMITTED'
    ).order_by('-week_start').prefetch_related('predictions')

    # Build a mapping: entry_id -> latest PredictionResult (or None)
    predictions_by_entry_id = {}
    for entry in entries:
        pred = entry.predictions.order_by('-created_at').first()
        if pred:
            predictions_by_entry_id[entry.id] = pred

    return render(request, 'wellbeing/child_report.html', {
        'child':   child,
        'entries': entries,
        'predictions_by_entry_id': predictions_by_entry_id,
    })


@login_required
@user_passes_test(is_caregiver)
def _removed_json_export():
    pass
    
# def entry_export_json(request, entry_id):
    """
    Export submitted entry as JSON matching Feature 3 ML Contract.
    """
    if request.user.is_superuser:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)
    else:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id, caregiver=request.user)

    if entry.status != 'SUBMITTED':
        return HttpResponseBadRequest("Entry must be submitted before export.")

    child = entry.child

    missing_fields = []
    if not child.sex:          missing_fields.append('sex')
    if not child.jaundice:     missing_fields.append('jaundice')
    if not child.family_asd:   missing_fields.append('family_asd')
    if not child.date_of_birth: missing_fields.append('date_of_birth')

    if missing_fields:
        missing_str = ",".join(missing_fields)
        return redirect(f"{reverse('wellbeing_child_detail', args=[child.id])}?event=export_blocked&missing={missing_str}")

    today = timezone.localdate()
    age_years = today.year - child.date_of_birth.year - (
        (today.month, today.day) < (child.date_of_birth.month, child.date_of_birth.day)
    )

    payload = {
        "age_years":   age_years,
        "sex":         child.sex,
        "jaundice":    child.jaundice,
        "family_asd":  child.family_asd,
    }

    answers = entry.answers.all()
    answer_map = {ans.question.code.lower(): ans for ans in answers}
    expected_codes = [f"a{i}" for i in range(1, 11)]
    missing_flags = []

    for code in expected_codes:
        if code not in answer_map:
            missing_flags.append(code)
        else:
            ans = answer_map[code]
            if ans.binary_flag is None:
                missing_flags.append(code)
            else:
                payload[code] = ans.binary_flag

    if missing_flags:
        return JsonResponse({
            "error":          "Missing answer binary flags required for export.",
            "missing_fields": missing_flags,
        }, status=400)

    return JsonResponse(payload)


@login_required
@user_passes_test(is_caregiver)
@require_POST
def predict_entry(request, entry_id):
    """Run ML prediction on a submitted entry and store the result."""
    if request.user.is_superuser:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)
    else:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id, caregiver=request.user)

    if entry.status != 'SUBMITTED':
        return JsonResponse({'error': 'Entry must be in SUBMITTED status to run prediction.'}, status=400)

    try:
        payload = build_payload_from_entry(entry)
        validate_payload(payload)
    except ValidationError as e:
        return JsonResponse({'error': str(e.message if hasattr(e, 'message') else e.messages)}, status=400)

    # ── Attempt real model inference ─────────────────────────────────────────
    try:
        result      = run_inference(payload)
        label       = result['label']
        score       = result['score']
        version     = result['model_version']
        explanation = build_explanation(payload, result.get('shap_values'))

    except ModelNotReadyError:
        # Graceful stub fallback — model artefacts not yet deployed
        explanation = build_explanation(payload)
        label       = 'Model not trained yet'
        score       = None
        version     = 'stub-v1'

    # ── Persist / overwrite prediction result ────────────────────────────────
    # update_or_create allows re-running after the real model is loaded
    prediction, _ = PredictionResult.objects.update_or_create(
        entry=entry,
        caregiver=request.user,
        defaults={
            'child':            entry.child,
            'prediction_label': label,
            'prediction_score': score,
            'model_version':    version,
            'explanation_json': explanation,
        }
    )

    return JsonResponse({
        'status':           'ok',
        'prediction_label': prediction.prediction_label,
        'prediction_score': prediction.prediction_score,
        'model_version':    prediction.model_version,
        'created_at':       prediction.created_at.isoformat(),
        'explanation':      prediction.explanation_json,
    })


@login_required
@user_passes_test(is_caregiver)
@require_POST
def generate_narrative(request, prediction_id):
    """Generate a template-based parent-friendly summary for a prediction."""
    if request.user.is_superuser:
        prediction = get_object_or_404(PredictionResult, id=prediction_id)
    else:
        prediction = get_object_or_404(PredictionResult, id=prediction_id, caregiver=request.user)

    # 1. Check idempotency
    force = request.POST.get('force') == '1'
    if prediction.narrative_text and not force:
        return JsonResponse({'status': 'ok', 'narrative_text': prediction.narrative_text})

    # 2. Compute trend_summary based on submission history
    child = prediction.child
    
    # Get last up to 4 submitted entries before or matching this prediction's entry week
    past_entries = WeeklyWellbeingEntry.objects.filter(
        child=child, status='SUBMITTED', week_start__lte=prediction.entry.week_start
    ).order_by('-week_start')[:4]
    
    entries_list = list(past_entries)[::-1] # earliest to latest
    
    trend_summary = {'latest_overall': None, 'domain_trends': {}}
    if entries_list:
        latest = entries_list[-1]
        trend_summary['latest_overall'] = latest.overall_score
        
        if len(entries_list) >= 2:
            first = entries_list[0]
            domains = [
                ('communication_score', 'communication'),
                ('routines_score', 'routines'),
                ('emotional_score', 'emotional_responses'),
                ('sensory_score', 'sensory_behaviors')
            ]
            
            for score_field, domain_name in domains:
                first_score = getattr(first, score_field)
                last_score = getattr(latest, score_field)
                if first_score is not None and last_score is not None:
                    diff = last_score - first_score
                    # Higher scores are better (0-4 slider, 0-1 is risk).
                    # 'up' = improvement, 'down' = worsening
                    if diff >= 0.5:
                        trend_summary['domain_trends'][domain_name] = 'up'
                    elif diff <= -0.5:
                        trend_summary['domain_trends'][domain_name] = 'down'
                    else:
                        trend_summary['domain_trends'][domain_name] = 'stable'

    # 3. Build narrative and save
    narrative = build_narrative(trend_summary, prediction)
    
    # 3b. Build SOAP note
    soap_note = build_soap_note(trend_summary, prediction)
    
    prediction.narrative_text = narrative
    # We will pass soap_note down, but let's actually store it if needed. 
    # For now, let's just make the entire narrative be the SOAP note! Wait, user said pdf must be SOAP.
    # Let's add it to the context. Or just replace narrative with SOAP.
    # Let's replace narrative with SOAP note right here for simplicity, OR if we need both, we can store SOAP in narrative_text and narrative somewhere else? No, just store both or pass both.
    
    # Actually, the user says "remove the export json, also the pdf must be generated as SOAP compliant...".
    # Let's just put the SOAP in prediction.narrative_text.
    prediction.narrative_text = soap_note
    prediction.save(update_fields=['narrative_text'])

    return JsonResponse({'status': 'ok', 'narrative_text': narrative})


@login_required
@user_passes_test(is_caregiver)
def entry_report(request, entry_id):
    """
    Feature 3 Demo Mode: Show a weekly report page after submission.
    Calculates mock prediction, explainability, and narrative on the fly.
    """
    if request.user.is_superuser:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)
    else:
        entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id, caregiver=request.user)

    if entry.status != 'SUBMITTED':
        messages.warning(request, "This entry is not submitted yet.")
        return redirect('wellbeing_entry_edit', entry_id=entry.id)
        
    # 1. Summary, 2. Prediction, & 3. Explainability
    try:
        payload = build_payload_from_entry(entry)
        try:
            result = run_inference(payload)
            explanation = build_explanation(payload, result.get('shap_values'))
            risk_score = explanation.get('risk_count', 0)
            mock_label = result['label']
            mock_confidence = result['score'] * 100
        except ModelNotReadyError:
            explanation = build_explanation(payload)
            risk_score = explanation.get('risk_count', 0)
            # Fallback mock prediction
            if risk_score <= 2:
                mock_label = "Low Probability"
            elif risk_score <= 6:
                mock_label = "Moderate Probability"
            else:
                mock_label = "High Probability"
            mock_confidence = (risk_score / 10.0) * 100
    except ValidationError:
        explanation = {}
        risk_score = entry.answers.filter(binary_flag=1).count()
        # Fallback mock prediction
        if risk_score <= 2:
            mock_label = "Low Probability"
        elif risk_score <= 6:
            mock_label = "Moderate Probability"
        else:
            mock_label = "High Probability"
        mock_confidence = (risk_score / 10.0) * 100
        
    # 4. Parent-friendly narrative
    past_entries = WeeklyWellbeingEntry.objects.filter(
        child=entry.child, status='SUBMITTED', week_start__lte=entry.week_start
    ).order_by('-week_start')[:4]
    
    entries_list = list(past_entries)[::-1]
    trend_summary = {'latest_overall': entry.overall_score, 'domain_trends': {}}
    if len(entries_list) >= 2:
        first = entries_list[0]
        latest = entries_list[-1]
        domains = [
            ('communication_score', 'communication'),
            ('routines_score', 'routines'),
            ('emotional_score', 'emotional_responses'),
            ('sensory_score', 'sensory_behaviors')
        ]
        for f_field, d_name in domains:
            v1 = getattr(first, f_field)
            v2 = getattr(latest, f_field)
            if v1 is not None and v2 is not None:
                diff = v2 - v1
                if diff >= 0.5: trend_summary['domain_trends'][d_name] = 'up'
                elif diff <= -0.5: trend_summary['domain_trends'][d_name] = 'down'
                else: trend_summary['domain_trends'][d_name] = 'stable'
                
    class MockPrediction:
        def __init__(self, exp, label):
            self.explanation_json = exp
            self.prediction_label = label
            self.model_version = 'mock-demo-v1'
    
    mock_pred = MockPrediction(explanation, mock_label)
    narrative = build_narrative(trend_summary, mock_pred)
    soap_note = build_soap_note(trend_summary, mock_pred)

    return render(request, 'wellbeing/entry_report.html', {
        'entry': entry,
        'risk_score': risk_score,
        'mock_label': mock_label,
        'mock_confidence': int(mock_confidence),
        'explanation': explanation,
        'narrative': narrative,
        'soap_note': soap_note
    })


@login_required
def entry_export_pdf(request, entry_id):
    """
    Generate a professional clinical PDF report using Playwright.

    Access rules:
      - Superuser:          always allowed.
      - Owning caregiver:   always allowed.
      - Assigned clinician: allowed once any appointment linking this entry
                            reaches CONFIRMED / COMPLETED (same gate used for
                            uploaded medical reports).
    """
    entry = get_object_or_404(WeeklyWellbeingEntry, id=entry_id)

    user = request.user
    allowed = False
    if user.is_superuser:
        allowed = True
    elif entry.caregiver_id == user.id:
        allowed = True
    elif getattr(user, 'role', None) == 'CLINICIAN' and getattr(user, 'clinician_verified', False):
        # Delegate to the appointment policy so there's one source of truth.
        if entry.linked_appointments.filter(
            clinician=user,
            status__in=['CONFIRMED', 'COMPLETED'],
        ).exists():
            allowed = True

    if not allowed:
        return HttpResponseForbidden("You don't have access to this report.")

    if entry.status != 'SUBMITTED':
        messages.warning(request, "This entry is not submitted yet.")
        return redirect('wellbeing_entry_edit', entry_id=entry.id)

    # ── Build the same context as entry_report ──────────────────
    try:
        payload = build_payload_from_entry(entry)
        try:
            result = run_inference(payload)
            explanation = build_explanation(payload, result.get('shap_values'))
            risk_score = explanation.get('risk_count', 0)
            mock_label = result['label']
            mock_confidence = int(result['score'] * 100)
        except ModelNotReadyError:
            explanation = build_explanation(payload)
            risk_score = explanation.get('risk_count', 0)
            if risk_score <= 2:
                mock_label = "Low Probability"
            elif risk_score <= 6:
                mock_label = "Moderate Probability"
            else:
                mock_label = "High Probability"
            mock_confidence = int((risk_score / 10.0) * 100)
    except ValidationError:
        explanation = {}
        risk_score = entry.answers.filter(binary_flag=1).count()
        if risk_score <= 2:
            mock_label = "Low Probability"
        elif risk_score <= 6:
            mock_label = "Moderate Probability"
        else:
            mock_label = "High Probability"
        mock_confidence = int((risk_score / 10.0) * 100)

    # Narrative + SOAP
    past_entries = WeeklyWellbeingEntry.objects.filter(
        child=entry.child, status='SUBMITTED', week_start__lte=entry.week_start
    ).order_by('-week_start')[:4]
    entries_list = list(past_entries)[::-1]
    trend_summary = {'latest_overall': entry.overall_score, 'domain_trends': {}}
    if len(entries_list) >= 2:
        first = entries_list[0]
        latest = entries_list[-1]
        domains = [
            ('communication_score', 'communication'),
            ('routines_score', 'routines'),
            ('emotional_score', 'emotional_responses'),
            ('sensory_score', 'sensory_behaviors')
        ]
        for f_field, d_name in domains:
            v1 = getattr(first, f_field)
            v2 = getattr(latest, f_field)
            if v1 is not None and v2 is not None:
                diff = v2 - v1
                if diff >= 0.5:
                    trend_summary['domain_trends'][d_name] = 'up'
                elif diff <= -0.5:
                    trend_summary['domain_trends'][d_name] = 'down'
                else:
                    trend_summary['domain_trends'][d_name] = 'stable'

    class MockPrediction:
        def __init__(self, exp, label):
            self.explanation_json = exp
            self.prediction_label = label
            self.model_version = 'mock-demo-v1'

    mock_pred = MockPrediction(explanation, mock_label)
    narrative = build_narrative(trend_summary, mock_pred)
    soap_note = build_soap_note(trend_summary, mock_pred)

    # Build safe flags (indicators NOT flagged)
    risk_flags = explanation.get('risk_flags', [])
    safe_flags = [f'a{i}' for i in range(1, 11) if f'a{i}' not in risk_flags]

    # ── Render the standalone PDF template to HTML ──────────────
    html_string = render_to_string('wellbeing/entry_report_pdf.html', {
        'entry': entry,
        'risk_score': risk_score,
        'mock_label': mock_label,
        'mock_confidence': mock_confidence,
        'explanation': explanation,
        'narrative': narrative,
        'soap_note': soap_note,
        'safe_flags': safe_flags,
        'generated_date': timezone.localdate(),
    }, request=request)

    # ── Generate PDF via Playwright ─────────────────────────────
    import logging
    logger = logging.getLogger(__name__)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Load the rendered HTML
            page.set_content(html_string, wait_until='networkidle')

            # Wait for fonts to load
            page.wait_for_timeout(1500)

            # If there's a SHAP chart, wait for it to render
            if explanation.get('top_shap_features'):
                try:
                    page.wait_for_function('window.__chartRendered === true', timeout=5000)
                except Exception:
                    pass  # Chart may not render, continue anyway

            # Generate PDF
            pdf_bytes = page.pdf(
                format='A4',
                print_background=True,
                margin={
                    'top': '20mm',
                    'bottom': '20mm',
                    'left': '18mm',
                    'right': '18mm',
                },
            )

            browser.close()

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        messages.error(request, f"PDF generation failed: {str(e)}. Please use the Print option instead.")
        return redirect('wellbeing_entry_report', entry_id=entry.id)

    # ── Return the PDF ──────────────────────────────────────────
    child_name = entry.child.name.replace(' ', '_')
    week = entry.week_start.strftime('%Y%m%d')
    filename = f'AutiBloom_ClinicalReport_{child_name}_{week}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
