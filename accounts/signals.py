from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to automatically create a Profile when a new User is created.
    Default role is 'caregiver' for self-registered users.
    """
    if created:
        Profile.objects.create(user=instance, role="caregiver")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal to save the Profile whenever the User is saved.
    """
    instance.profile.save()
