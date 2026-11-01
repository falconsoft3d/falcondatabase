"""Calls the cron jobs' URLs on schedule and records each run.

Each job is called once per turn. Unlike an uptime check, a failed call is not retried:
the app may have done the work before failing, and the next turn comes soon anyway.
Redirects are not followed either, because they would carry the job's secret header
to another address.
"""

import datetime
import logging
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from uptime.checker import Result
from uptime.net import BlockedAddress, guard

from .models import CronJob, CronRun

logger = logging.getLogger(__name__)

USER_AGENT = "falcondatabase-cron/1.0"
MAX_PARALLEL = 10


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = urllib.request.build_opener(NoRedirects)


def call(job):
    timeout = settings.FALCONDB_CRON_TIMEOUT
    started = time.monotonic()
    elapsed = lambda: round((time.monotonic() - started) * 1000)  # noqa: E731
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if job.header_name:
        headers[job.header_name] = job.header_value
    try:
        guard(job.url)
        request = urllib.request.Request(job.url, data=b"" if job.method == CronJob.POST else None,
                                         method=job.method, headers=headers)
        with opener.open(request, timeout=timeout) as response:
            return Result(ok=response.status < 400, status_code=response.status, response_ms=elapsed())
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location")
        error = f"HTTP {exc.code}: redirects to {location}" if location else f"HTTP {exc.code} {exc.reason}"
        return Result(ok=False, status_code=exc.code, response_ms=elapsed(), error=error[:255])
    except BlockedAddress as exc:
        return Result(ok=False, error=str(exc)[:255])
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return Result(ok=False, error=f"Timeout after {timeout} s")
        return Result(ok=False, error=str(exc.reason)[:255])
    except TimeoutError:
        return Result(ok=False, error=f"Timeout after {timeout} s")
    except Exception as exc:  # broken TLS, bad status line, reset connection…
        return Result(ok=False, error=f"{type(exc).__name__}: {exc}"[:255])


def record(job, result, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        CronRun.objects.create(job=job, created_at=now, ok=result.ok, status_code=result.status_code,
                               response_ms=result.response_ms, error=result.error)
        job.last_run_at = now
        job.last_ok = result.ok
        job.last_status_code = result.status_code
        job.last_response_ms = result.response_ms
        job.last_error = result.error
        CronJob.objects.filter(pk=job.pk).update(
            last_run_at=now, last_ok=result.ok, last_status_code=result.status_code,
            last_response_ms=result.response_ms, last_error=result.error,
        )


def run(job):
    result = call(job)
    record(job, result)
    return result


def claim_due(now=None, limit=200):
    """Jobs whose turn has come, already rescheduled so another worker won't take them."""
    now = now or timezone.now()
    with transaction.atomic():
        due = list(CronJob.objects.select_for_update(skip_locked=True)
                   .filter(enabled=True, next_run_at__lte=now).order_by("next_run_at")[:limit])
        for job in due:
            job.schedule_next(now)
        CronJob.objects.bulk_update(due, ["next_run_at"])
    return due


def _run_in_thread(job):
    try:
        return run(job)
    except Exception:
        logger.exception("Cron job %s failed", job.pk)
    finally:
        connection.close()  # each thread has its own database connection


def run_due(now=None):
    """Call every due job. Returns how many were called."""
    due = claim_due(now)
    if not due:
        return 0
    workers = min(MAX_PARALLEL, len(due))
    if workers <= 1:
        for job in due:
            run(job)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_run_in_thread, due))
    return len(due)


def prune(now=None):
    """Delete runs older than the retention period."""
    cutoff = (now or timezone.now()) - datetime.timedelta(days=settings.FALCONDB_CRON_RETENTION_DAYS)
    deleted, _ = CronRun.objects.filter(created_at__lt=cutoff).delete()
    return deleted
