from django.db import models

class TherapyGame(models.Model):
    EMBED_CHOICES = [
        ('URL', 'Remote URL'),
        ('LOCAL', 'Local HTML Package'),
    ]
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    goal = models.CharField(max_length=200)
    age_range = models.CharField(max_length=50)
    description = models.TextField()
    embed_type = models.CharField(max_length=10, choices=EMBED_CHOICES, default='URL')
    embed_url = models.URLField(blank=True, null=True)
    local_embed_path = models.CharField(max_length=255, blank=True, help_text="Path relative to static/, e.g., h5p/emotion-match/index.html")
    h5p_file_path = models.CharField(max_length=255, blank=True, help_text="Path relative to static/, e.g., h5p_packages/emotion-match.h5p")
    thumbnail_url = models.URLField(blank=True, null=True)
    provider_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
