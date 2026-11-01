import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from cron import runner

logger = logging.getLogger(__name__)

TICK = 30           # seconds between looks for due jobs
PRUNE_EVERY = 3600  # seconds between deletions of old runs


class Command(BaseCommand):
    help = ("Call the cron jobs whose time has come, forever (every 30 s). "
            "With --once, call the due jobs and exit.")

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one round and exit.")

    def handle(self, *args, once=False, **options):
        if once:
            called = runner.run_due()
            deleted = runner.prune()
            self.stdout.write(f"Called {called} job(s), deleted {deleted} old run(s).")
            return

        stopping = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stopping.append(True))
        self.stdout.write(f"Cron worker started: looking for due jobs every {TICK} s.")
        last_prune = None
        while not stopping:
            started = time.monotonic()
            try:
                called = runner.run_due()
                if called:
                    logger.info("Called %s job(s) at %s", called, timezone.now().isoformat(timespec="seconds"))
                if last_prune is None or started - last_prune >= PRUNE_EVERY:
                    runner.prune()
                    last_prune = started
            except Exception:
                logger.exception("Cron round failed")
            close_old_connections()
            while not stopping and time.monotonic() - started < TICK:
                time.sleep(1)
        self.stdout.write("Cron worker stopped.")
