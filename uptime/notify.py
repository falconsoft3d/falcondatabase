"""Alerts sent when a monitor goes down or comes back: an email to the project owner
(if the monitor has notifications on) and a JSON POST to its webhook (if it has one)."""

import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from .net import USER_AGENT, BlockedAddress, guard, opener

logger = logging.getLogger(__name__)

DOWN = "down"
UP = "up"


def configured():
    """True when emails really leave the server (SMTP), not only the log."""
    return bool(settings.EMAIL_HOST)


def human_duration(delta):
    minutes = max(1, round(delta.total_seconds() / 60))
    if minutes < 60:
        return _("%(n)s min") % {"n": minutes}
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return _("%(h)s h %(m)s min") % {"h": hours, "m": minutes}
    return _("%(d)s days") % {"d": hours // 24}


def message(monitor, event, incident, result):
    """``(subject, body)`` in the site's default language."""
    project = monitor.project
    if event == DOWN:
        subject = _("🔴 Down: %(site)s") % {"site": monitor.label}
        lines = [
            _("%(url)s is not responding.") % {"url": monitor.url},
            _("Error: %(error)s") % {"error": result.error or "—"},
        ]
    else:
        subject = _("🟢 Back up: %(site)s") % {"site": monitor.label}
        lines = [
            _("%(url)s is responding again.") % {"url": monitor.url},
            _("It was down for %(duration)s.") % {"duration": human_duration(incident.duration)},
        ]
    lines += [
        _("Project: %(project)s") % {"project": f"{project.owner.username}/{project.slug}"},
        _("Time: %(time)s UTC") % {"time": timezone.now().strftime("%Y-%m-%d %H:%M")},
    ]
    return subject, "\n".join(lines)


def send(monitor, event, incident, result):
    with translation.override(settings.LANGUAGE_CODE):
        subject, body = message(monitor, event, incident, result)
    if monitor.notify and monitor.project.owner.email:
        try:
            send_mail(f"[falcondatabase] {subject}", body, None, [monitor.project.owner.email])
        except Exception:
            logger.exception("Could not email the uptime alert for %s", monitor.url)
    if monitor.webhook_url:
        post_webhook(monitor, event, incident, result, f"{subject}\n{body}")


def post_webhook(monitor, event, incident, result, text):
    """POST a JSON payload. ``text`` / ``content`` let Slack and Discord show it as is."""
    payload = {
        "event": event,
        "text": text,
        "content": text,
        "url": monitor.url,
        "project": f"{monitor.project.owner.username}/{monitor.project.slug}",
        "status_code": result.status_code,
        "response_ms": result.response_ms,
        "error": result.error,
        "incident_started_at": incident.started_at.isoformat(),
        "incident_ended_at": incident.ended_at.isoformat() if incident.ended_at else None,
    }
    try:
        guard(monitor.webhook_url)
        request = urllib.request.Request(monitor.webhook_url, data=json.dumps(payload).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
        opener.open(request, timeout=settings.FALCONDB_UPTIME_TIMEOUT).close()
    except (BlockedAddress, OSError) as exc:
        logger.warning("Uptime webhook %s failed: %s", monitor.webhook_url, exc)
