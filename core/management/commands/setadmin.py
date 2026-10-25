from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Make USERNAME the only admin of falcondatabase (removes admin from everyone else)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, username, **options):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"User “{username}” does not exist.")
        User.objects.exclude(pk=user.pk).filter(is_superuser=True).update(is_superuser=False, is_staff=False)
        user.is_superuser = user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])
        self.stdout.write(self.style.SUCCESS(f"“{username}” is now the only admin."))
