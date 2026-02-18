from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

class CaregiverCommunityProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='community_profile')
    opt_in = models.BooleanField(default=False)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.opt_in and not self.city.strip():
            raise ValidationError("City must be provided if opted in to the community.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Community Profile"

class BlockedUser(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"

class Thread(models.Model):
    participants = models.ManyToManyField(User, related_name='community_threads')
    created_at = models.DateTimeField(auto_now_add=True)

    def has_user(self, user):
        return self.participants.filter(id=user.id).exists()

    def other_user(self, me):
        # Assumes exactly 2 participants, which is enforced by the views
        return self.participants.exclude(id=me.id).first()

    def __str__(self):
        return f"Thread {self.id}"

class Message(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_community_messages')
    body = models.TextField(max_length=1000)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message {self.id} in Thread {self.thread.id}"
