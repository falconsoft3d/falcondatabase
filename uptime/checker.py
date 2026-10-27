"""Requests the monitors' URLs and records the result.

A failed request is retried once before it counts as down. When a monitor changes
from up to down an incident opens (and the owner is notified); the next successful
check closes it.
"""

import datetime
import logging
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from . import notify
from .models import Check, Incident, Monitor
from .net import USER_AGENT, BlockedAddress, guard, opener

logger = logging.getLogger(__name__)

RETRY_DELAY = 2  # seconds before retrying a failed request
MAX_PARALLEL = 10


@dataclass
class Result:
    ok: bool
    status_code: int | None = None
    response_ms: int | None = None
    error: str = ""
    retry: bool = True  # False when retrying can't help (blocked or invalid address)


def request_once(url, timeout):
    started = time.monotonic()
    elapsed = lambda: round((time.monotonic() - started) * 1000)  # noqa: E731
    try:
        guard(url)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with opener.open(request, timeout=timeout) as response:
            return Result(ok=response.status < 400, status_code=response.status, response_ms=elapsed())
    except urllib.error.HTTPError as exc:
        return Result(ok=False, status_code=exc.code, response_ms=elapsed(), error=f"HTTP {exc.code} {exc.reason}")
    except BlockedAddress as exc:
        return Result(ok=False, error=str(exc), retry=False)
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return Result(ok=False, error=f"Timeout after {timeout} s")
        return Result(ok=False, error=str(reason)[:255])
    except TimeoutError:
        return Result(ok=False, error=f"Timeout after {timeout} s")
    except Exception as exc:  # broken TLS, bad status line, reset connection…
        return Result(ok=False, error=f"{type(exc).__name__}: {exc}"[:255])


def probe(url, timeout=None, retry_delay=RETRY_DELAY):
    timeout = timeout or settings.FALCONDB_UPTIME_TIMEOUT
    result = request_once(url, timeout)
    if not result.ok and result.retry:
        time.sleep(retry_delay)
        result = request_once(url, timeout)
    return result


def record(monitor, result, now=None):
    """Save the check, update the monitor's status and open or close its incident."""
    now = now or timezone.now()
    previous = monitor.status
    with transaction.atomic():
        Check.objects.create(monitor=monitor, created_at=now, ok=result.ok, status_code=result.status_code,
                             response_ms=result.response_ms, error=result.error[:255])
        monitor.status = Monitor.UP if result.ok else Monitor.DOWN
        if monitor.status != previous:
            monitor.status_since = now
        monitor.last_checked_at = now
        monitor.last_response_ms = result.response_ms
        monitor.last_error = result.error[:255]
        Monitor.objects.filter(pk=monitor.pk).update(
            status=monitor.status, status_since=monitor.status_since, last_checked_at=now,
            last_response_ms=result.response_ms, last_error=monitor.last_error,
        )
        incident = monitor.incidents.filter(ended_at__isnull=True).first()
        event = None
        if not result.ok and incident is None:
            incident = Incident.objects.create(monitor=monitor, started_at=now, error=result.error[:255])
            event = notify.DOWN
        elif result.ok and incident is not None:
            incident.ended_at = now
            incident.save(update_fields=["ended_at"])
            event = notify.UP
    if event:
        notify.send(monitor, event, incident, result)
    return event


def check(monitor):
    result = probe(monitor.url)
    record(monitor, result)
    return result


def claim_due(now=None, limit=200):
    """Monitors whose check is due, already rescheduled so another worker won't take them."""
    now = now or timezone.now()
    with transaction.atomic():
        due = list(Monitor.objects.select_for_update(skip_locked=True)
                   .filter(enabled=True, next_check_at__lte=now).order_by("next_check_at")[:limit])
        for monitor in due:
            monitor.schedule_next(now)
        Monitor.objects.bulk_update(due, ["next_check_at"])
    return due


def _check_in_thread(monitor):
    try:
        return check(monitor)
    except Exception:
        logger.exception("Uptime check of %s failed", monitor.url)
    finally:
        connection.close()  # each thread has its own database connection


def run_due(now=None, parallel=None):
    """Check every due monitor, ``parallel`` at a time. Returns how many were checked."""
    due = claim_due(now)
    if not due:
        return 0
    due = list(Monitor.objects.filter(pk__in=[m.pk for m in due]).select_related("project__owner"))
    workers = min(parallel or MAX_PARALLEL, len(due))
    if workers == 1:
        for monitor in due:
            check(monitor)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_check_in_thread, due))
    return len(due)


def prune(now=None):
    """Delete checks older than the retention period."""
    cutoff = (now or timezone.now()) - datetime.timedelta(days=settings.FALCONDB_UPTIME_RETENTION_DAYS)
    deleted, _ = Check.objects.filter(created_at__lt=cutoff).delete()
    return deleted
