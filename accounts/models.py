from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extends Django's built-in User model with app-specific profile data.

    Important:
    - Django's built-in User handles username, password, email, superuser, and staff.
    - This UserProfile handles app roles like admin and technician.
    - The project owner/super admin should be created using:
        python manage.py createsuperuser
    """

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("technician", "Technician"),
    ]

    # Every profile belongs to exactly one Django user.
    # If the user is deleted, the profile is deleted too.
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # App role used by Flutter to decide which dashboard to open.
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="technician",
    )

    # Optional phone number for admins/technicians.
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    # Optional department/team name.
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    # Useful mainly for technicians.
    # Example: unavailable technicians should not receive new tasks.
    is_available = models.BooleanField(
        default=True,
        help_text="Indicates if a technician can respond to leakage alerts.",
    )

    # Automatically records when profile was created.
    created_at = models.DateTimeField(auto_now_add=True)

    # Automatically updates whenever profile is saved.
    updated_at = models.DateTimeField(auto_now=True)

    def is_admin(self):
        """
        Returns True if the user is an app admin.

        Note:
        Super admin is checked using user.is_superuser,
        not with this role field.
        """
        return self.role == "admin"

    def is_technician(self):
        """
        Returns True if the user is a technician.
        """
        return self.role == "technician"

    def __str__(self):
        return f"{self.user.username} ({self.role})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile whenever a Django User is created.

    This prevents errors like:
    user has no profile
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the profile whenever the related User is saved.

    This keeps profile data synchronized with the user.
    """
    if hasattr(instance, "profile"):
        instance.profile.save()