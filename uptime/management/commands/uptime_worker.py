import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from uptime import checker

logger = logging.getLogger(__name__)

TICK = 30           # seconds between looks for due monitors
PRUNE_EVERY = 3600  # seconds between deletions of old checks


class Command(BaseCommand):
    help = ("Check the uptime monitors whose time has come, forever (every 30 s). "
            "With --once, check the due monitors and exit (for cron).")

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one round and exit.")

    def handle(self, *args, once=False, **options):
        if once:
            checked = checker.run_due()
            deleted = checker.prune()
            self.stdout.write(f"Checked {checked} monitor(s), deleted {deleted} old check(s).")
            return

        stopping = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stopping.append(True))
        self.stdout.write(f"Uptime worker started: looking for due monitors every {TICK} s.")
        last_prune = None
        while not stopping:
            started = time.monotonic()
            try:
                checked = checker.run_due()
                if checked:
                    logger.info("Checked %s monitor(s) at %s", checked, timezone.now().isoformat(timespec="seconds"))
                if last_prune is None or started - last_prune >= PRUNE_EVERY:
                    checker.prune()
                    last_prune = started
            except Exception:
                logger.exception("Uptime round failed")
            while not stopping and time.monotonic() - started < TICK:
                time.sleep(1)
        self.stdout.write("Uptime worker stopped.")
