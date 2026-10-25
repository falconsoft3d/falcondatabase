import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create the admin account if it doesn't exist and make it the only admin. "
        "Reads FALCONDB_ADMIN_USERNAME, FALCONDB_ADMIN_EMAIL and FALCONDB_ADMIN_PASSWORD "
        "(the password is only used when the account is created)."
    )

    def handle(self, *args, **options):
        username = os.environ.get("FALCONDB_ADMIN_USERNAME", "").strip()
        email = os.environ.get("FALCONDB_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("FALCONDB_ADMIN_PASSWORD", "")
        if not username:
            raise CommandError("FALCONDB_ADMIN_USERNAME is required.")

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            if not email or not password:
                raise CommandError("FALCONDB_ADMIN_EMAIL and FALCONDB_ADMIN_PASSWORD are required to create the admin.")
            if User.objects.filter(email__iexact=email).exists():
                raise CommandError(f"Another account already uses {email}.")
            User.objects.create_user(username=username, email=email, password=password)
            self.stdout.write(f"Created user “{username}”.")
        else:
            self.stdout.write(f"User “{username}” already exists; password unchanged.")
        call_command("setadmin", username, stdout=self.stdout)
