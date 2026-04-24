from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Extends Django's default User model with system roles.

    We keep Django's built-in User for login/authentication,
    then use this profile to control what each user can do.
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
        default="worker",
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
        help_text="Used to know if a worker/technician can respond to alerts.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_admin(self):
        return self.role == "admin"

    def is_technician(self):
        return self.role == "technician"

    def is_worker(self):
        return self.role == "worker"

    def is_viewer(self):
        return self.role == "viewer"

    def __str__(self):
        return f"{self.user.username} - {self.role}"