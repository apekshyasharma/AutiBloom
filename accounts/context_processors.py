from django.utils import timezone
import datetime
from community.models import Message, BlockedUser
from wellbeing.models import CaregiverChild, WeeklyWellbeingEntry


def _monday_of_week(d):
    """Return the Monday of the week containing date d."""
    return d - datetime.timedelta(days=d.weekday())


def notifications_processor(request):
    if not request.user.is_authenticated:
        return {}

    try:
        if request.user.role != 'CAREGIVER':
            return {}
    except AttributeError:
        return {}

    unread_messages_count = 0
    weekly_checkin_required = False
    missed_weeks_count = 0
    oldest_missed_week_start = None
    days_until_week_end = 0

    try:
        # ── 1. Unread messages (exclude blocked users in both directions) ──────
        blocked_by_me = BlockedUser.objects.filter(
            blocker=request.user
        ).values_list('blocked_id', flat=True)
        blocked_me = BlockedUser.objects.filter(
            blocked=request.user
        ).values_list('blocker_id', flat=True)
        excluded_sender_ids = set(list(blocked_by_me) + list(blocked_me))

        unread_messages_count = (
            Message.objects
            .filter(thread__participants=request.user, is_read=False)
            .exclude(sender=request.user)
            .exclude(sender_id__in=excluded_sender_ids)
            .count()
        )

        # ── 2. Weekly check-in — only count weeks since each child was added ──
        today = timezone.localdate()
        current_week_start = _monday_of_week(today)

        relationships = (
            CaregiverChild.objects
            .filter(caregiver=request.user)
            .select_related('child')
        )

        if relationships.exists():
            child_info = []
            for rel in relationships:
                child_added_monday = _monday_of_week(rel.created_at.date())
                child_info.append({
                    'child_id': rel.child_id,
                    'name': rel.child.name,
                    'start_week': child_added_monday,
                })

            all_child_ids = [c['child_id'] for c in child_info]

            # One query: all (child_id, week_start, status) for this caregiver
            submitted_set = set(
                WeeklyWellbeingEntry.objects
                .filter(
                    caregiver=request.user,
                    status='SUBMITTED',
                    week_start__lte=current_week_start,
                )
                .values_list('child_id', 'week_start')
            )

            # Also track drafts so we don't over-alert
            draft_set = set(
                WeeklyWellbeingEntry.objects
                .filter(
                    caregiver=request.user,
                    status='DRAFT',
                    week_start__lte=current_week_start,
                )
                .values_list('child_id', 'week_start')
            )

            # Walk week by week per child — only count weeks after child was added
            missed_weeks = set()
            children_missing = {}  # child_name -> {'count': N, 'oldest': date}
            week = current_week_start
            # Only scan the last 4 weeks + current week to avoid unbounded alerts
            scan_limit = current_week_start - datetime.timedelta(weeks=4)

            while week >= scan_limit:
                for child in child_info:
                    if week < child['start_week']:
                        continue
                    if (child['child_id'], week) not in submitted_set:
                        missed_weeks.add(week)
                        if oldest_missed_week_start is None or week < oldest_missed_week_start:
                            oldest_missed_week_start = week
                        # Track per-child
                        name = child['name']
                        if name not in children_missing:
                            children_missing[name] = {'count': 0, 'oldest': week}
                        children_missing[name]['count'] += 1
                        if week < children_missing[name]['oldest']:
                            children_missing[name]['oldest'] = week
                week -= datetime.timedelta(weeks=1)

            missed_weeks_count = len(missed_weeks)

            if missed_weeks_count > 0:
                weekly_checkin_required = True

            # Days remaining until Sunday of current week (Monday=0 … Sunday=6)
            days_until_week_end = 6 - today.weekday()

    except Exception:
        pass

    # Build per-child list for template
    children_needing_checkin = []
    if 'children_missing' in dir() or True:
        try:
            for name, info in children_missing.items():
                children_needing_checkin.append({
                    'name': name,
                    'count': info['count'],
                    'oldest': info['oldest'],
                })
        except Exception:
            pass

    return {
        'unread_messages_count': unread_messages_count,
        'weekly_checkin_required': weekly_checkin_required,
        'missed_weeks_count': missed_weeks_count,
        'oldest_missed_week_start': oldest_missed_week_start,
        'days_until_week_end': days_until_week_end,
        'children_needing_checkin': children_needing_checkin,
    }
