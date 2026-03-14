from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib.staticfiles import finders
from accounts.permissions import role_required
from .models import TherapyGame

@login_required
@role_required(["CAREGIVER", "ADMIN"])
def game_list(request):
    games = TherapyGame.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'games/game_list.html', {'games': games})

@login_required
@role_required(["CAREGIVER", "ADMIN"])
def game_detail(request, slug):
    game = get_object_or_404(TherapyGame, slug=slug, is_active=True)
    return render(request, 'games/game_detail.html', {'game': game})

@user_passes_test(lambda u: u.is_superuser)
def static_check(request):
    games = TherapyGame.objects.filter(embed_type='LOCAL')
    results = {}
    for g in games:
        if g.local_embed_path:
            absolute_path = finders.find(g.local_embed_path)
            results[g.slug] = {
                'expected_static_path': g.local_embed_path,
                'resolved_absolute_path': absolute_path if absolute_path else 'NOT FOUND'
            }
    return JsonResponse({'local_h5p_games_check': results})
