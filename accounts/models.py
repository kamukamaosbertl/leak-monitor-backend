from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extends Django User with system roles and extra info.

    This is the CORE of your permission system.
    Every user MUST have a profile.
    """

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("technician", "Technician"),
        ("worker", "Worker"),
        ("viewer", "Viewer"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="worker",  # 🔥 default safe role
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    is_available = models.BooleanField(
        default=True,
        help_text="Indicates if a technician/worker can respond to alerts.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── ROLE HELPERS ─────────────────────────────────────────

    def is_admin(self):
        return self.role == "admin"

    def is_technician(self):
        return self.role == "technician"

    def is_worker(self):
        return self.role == "worker"

    def is_viewer(self):
        return self.role == "viewer"

    def __str__(self):
        return f"{self.user.username} ({self.role})"


# 🔥 AUTO CREATE PROFILE WHEN USER IS CREATED
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


# 🔥 ENSURE PROFILE ALWAYS EXISTS
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()