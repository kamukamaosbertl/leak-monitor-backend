import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Create superuser automatically from environment variables"

    def handle(self, *args, **kwargs):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING("Superuser not created. Missing environment variables.")
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write("Superuser already exists")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS("Superuser created successfully"))