from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = (
        ("caregiver", "Caregiver"),
        ("doctor", "Doctor"),
        ("admin", "Admin"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="caregiver")

    def __str__(self):
        return f"{self.user.username} - {self.role}"
