from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from accounts.permissions import role_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField, Q
from django.http import Http404, JsonResponse

from accounts.models import User
from .models import CaregiverCommunityProfile, BlockedUser, Thread, Message
from .forms import CommunityOptInForm

@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_home(request):
    profile, _ = CaregiverCommunityProfile.objects.get_or_create(user=request.user)
    
    form_success = None
    form_error = None

    if request.method == 'POST':
        form = CommunityOptInForm(request.POST, instance=profile)
        if form.is_valid():
            saved = form.save(commit=False)
            # Normalize city casing for consistent matching
            if saved.city:
                saved.city = saved.city.strip().title()
            try:
                saved.save()
                form_success = "Your community profile has been updated."
                profile.refresh_from_db()
            except Exception as e:
                form_error = str(e)
        else:
            # Collect all form errors into a readable string
            errors = []
            for field, errs in form.errors.items():
                label = form.fields[field].label or field
                errors.append(f"{label}: {', '.join(errs)}")
            form_error = " | ".join(errors) if errors else "There was an error updating your profile."
    else:
        form = CommunityOptInForm(instance=profile)

    nearby_caregivers = []
    if profile.opt_in and profile.city:
        # Exclude self and blocked users
        blocked_by_me = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
        blocked_me = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
        excluded_ids = set(list(blocked_by_me) + list(blocked_me) + [request.user.id])

        # Find other opted in users
        candidates = CaregiverCommunityProfile.objects.filter(
            opt_in=True
        ).exclude(user_id__in=excluded_ids)
        
        # Match by postal code first (if provided), then by city (case-insensitive)
        if profile.postal_code:
            candidates = candidates.filter(
                Q(postal_code=profile.postal_code) | Q(city__iexact=profile.city)
            ).annotate(
                is_same_postal=Case(
                    When(postal_code=profile.postal_code, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-is_same_postal', 'user__username')
        else:
            candidates = candidates.filter(city__iexact=profile.city).order_by('user__username')
        
        nearby_caregivers = list(candidates)
        
    context = {
        'form': form,
        'profile': profile,
        'nearby_caregivers': nearby_caregivers,
        'form_success': form_success,
        'form_error': form_error,
    }
    return render(request, 'community/community_home.html', context)



@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_inbox(request):
    threads = Thread.objects.filter(participants=request.user)
    
    blocked_by_me = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
    blocked_me = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
    excluded_ids = set(list(blocked_by_me) + list(blocked_me))

    active_threads = []
    for t in threads:
        other_user = t.other_user(request.user)
        if other_user and other_user.id not in excluded_ids:
            # get last message
            last_msg = t.messages.order_by('-created_at').first()
            unread_count = t.messages.filter(is_read=False).exclude(sender=request.user).count()
            active_threads.append({
                'thread': t,
                'other_user': other_user,
                'last_message': last_msg,
                'unread_count': unread_count
            })
    
    # Sort threads by last message created_at dict
    active_threads.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else t.created_at, 
        reverse=True
    )
            
    context = {
        'active_threads': active_threads
    }
    return render(request, 'community/community_inbox.html', context)


@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_start_thread(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    if target_user == request.user:
        messages.error(request, "You cannot message yourself.")
        return redirect('community_home')

    # check blocked
    is_blocked = BlockedUser.objects.filter(
        Q(blocker=request.user, blocked=target_user) | 
        Q(blocker=target_user, blocked=request.user)
    ).exists()
    
    if is_blocked:
        messages.error(request, "You cannot start a thread with this user.")
        return redirect('community_home')

    # check opt-in
    my_profile = CaregiverCommunityProfile.objects.filter(user=request.user, opt_in=True).first()
    target_profile = CaregiverCommunityProfile.objects.filter(user=target_user, opt_in=True).first()
    
    if not my_profile or not target_profile:
        messages.error(request, "Both users must be opted-in to the community.")
        return redirect('community_home')

    # Find existing thread
    my_threads = request.user.community_threads.all()
    thread = None
    for t in my_threads:
        if t.participants.count() == 2 and t.has_user(target_user):
            thread = t
            break
            
    if not thread:
        thread = Thread.objects.create()
        thread.participants.add(request.user, target_user)
        
    return redirect('community_thread', thread_id=thread.id)


@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_thread(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    
    if not thread.has_user(request.user):
        raise Http404("You do not have access to this thread.")
        
    other_user = thread.other_user(request.user)
    
    # Check block status
    is_blocked = BlockedUser.objects.filter(
        Q(blocker=request.user, blocked=other_user) | 
        Q(blocker=other_user, blocked=request.user)
    ).exists()

    if request.method == "POST":
        if is_blocked:
            messages.error(request, "You cannot send messages in this thread.")
        else:
            body = request.POST.get('body', '').strip()
            if body and len(body) <= 1000:
                Message.objects.create(
                    thread=thread,
                    sender=request.user,
                    body=body
                )
            elif len(body) > 1000:
                messages.error(request, "Message is too long (max 1000 characters).")
            else:
                messages.error(request, "Message cannot be empty.")
        return redirect('community_thread', thread_id=thread.id)
        
    messages_query = thread.messages.order_by('created_at')
    
    # Mark unread messages as read
    unread_msgs = thread.messages.filter(is_read=False).exclude(sender=request.user)
    if unread_msgs.exists():
        unread_msgs.update(is_read=True, read_at=timezone.now())
    
    context = {
        'thread': thread,
        'msgs': messages_query,
        'other_user': other_user,
        'is_blocked': is_blocked,
    }
    return render(request, 'community/community_thread.html', context)


@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_block_user(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        if target_user != request.user:
            BlockedUser.objects.get_or_create(blocker=request.user, blocked=target_user)
            messages.success(request, f"You have blocked {target_user.username}.")
    return redirect('community_home')

@login_required
@role_required(["CAREGIVER", "ADMIN"])
def community_unblock_user(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        qs = BlockedUser.objects.filter(blocker=request.user, blocked=target_user)
        if qs.exists():
            qs.delete()
            messages.success(request, f"You have unblocked {target_user.username}.")
    return redirect('community_home')


# ─────────────────────────────────────────────
#  Read-Receipt API Endpoints
# ─────────────────────────────────────────────

@login_required
@role_required(["CAREGIVER", "ADMIN"])
def mark_messages_read(request, thread_id):
    """
    POST: Mark all unread messages in a thread as read for the current user.
    Called by the RECIPIENT's browser on page load / focus.
    """
    thread = get_object_or_404(Thread, id=thread_id)
    if not thread.has_user(request.user):
        raise Http404()

    # Only mark messages NOT sent by the current user
    updated = thread.messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True, read_at=timezone.now())

    return JsonResponse({'ok': True, 'marked_read': updated})


@login_required
@role_required(["CAREGIVER", "ADMIN"])
def thread_read_status(request, thread_id):
    """
    GET: Return IDs of messages sent by the current user that are now marked read.
    Polled by the SENDER's browser to upgrade single tick → blue double tick.
    """
    thread = get_object_or_404(Thread, id=thread_id)
    if not thread.has_user(request.user):
        raise Http404()

    read_ids = list(
        thread.messages
        .filter(sender=request.user, is_read=True)
        .values_list('id', flat=True)
    )
    return JsonResponse({'read_message_ids': read_ids})
