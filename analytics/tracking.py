"""Turn a raw hit from the tracking script into a privacy-friendly PageView.

* The visitor id is an HMAC of (day, project, IP, user agent): it can't be
  reversed and changes every day, so no cookie or personal data is stored.
* A session is a visitor's page views with gaps under 30 minutes. Its source and
  medium come from the first page view (UTM parameters or the referrer).
* The country comes from a CDN header if present, else the browser time zone,
  else the region in Accept-Language.
"""

import datetime
import hashlib
import hmac
import json
import re
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.utils import timezone

from .models import PageView

SESSION_TIMEOUT = datetime.timedelta(minutes=30)

BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|python|curl|wget|httpclient|monitor", re.I)

SEARCH_ENGINES = {
    "google": "Google", "bing": "Bing", "duckduckgo": "DuckDuckGo", "yahoo": "Yahoo",
    "yandex": "Yandex", "baidu": "Baidu", "ecosia": "Ecosia", "startpage": "Startpage", "qwant": "Qwant",
}
SOCIAL_NETWORKS = {
    "facebook.com": "Facebook", "fb.com": "Facebook", "instagram.com": "Instagram", "t.co": "X (Twitter)",
    "twitter.com": "X (Twitter)", "x.com": "X (Twitter)", "linkedin.com": "LinkedIn", "lnkd.in": "LinkedIn",
    "youtube.com": "YouTube", "youtu.be": "YouTube", "reddit.com": "Reddit", "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest", "whatsapp.com": "WhatsApp", "t.me": "Telegram", "telegram.org": "Telegram",
    "threads.net": "Threads", "bsky.app": "Bluesky", "mastodon.social": "Mastodon",
}


@lru_cache(maxsize=1)
def timezones():
    """IANA time zone -> ISO country code (generated from tzdata's zone.tab)."""
    return json.loads((Path(__file__).with_name("timezones.json")).read_text())


def is_bot(user_agent):
    return not user_agent or bool(BOT_RE.search(user_agent))


def client_ip(request):
    if settings.FALCONDB_TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # The last entry is the one added by our own proxy; earlier ones can be forged.
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def visitor_id(project_ref, ip, user_agent, day):
    message = f"{day.isoformat()}|{project_ref}|{ip}|{user_agent}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:32]


def device_for(user_agent):
    if re.search(r"iPad|Tablet|Android(?!.*Mobile)", user_agent):
        return "tablet"
    if re.search(r"Mobi|iPhone|iPod|Android", user_agent):
        return "mobile"
    return "desktop"


def browser_for(user_agent):
    for pattern, name in [
        (r"Edg/|EdgiOS|EdgA", "Edge"), (r"OPR/|Opera", "Opera"), (r"SamsungBrowser", "Samsung Internet"),
        (r"Firefox|FxiOS", "Firefox"), (r"CriOS|Chrome|Chromium", "Chrome"), (r"Safari", "Safari"),
    ]:
        if re.search(pattern, user_agent):
            return name
    return "Other"


def os_for(user_agent):
    for pattern, name in [
        (r"Windows", "Windows"), (r"iPhone|iPad|iPod", "iOS"), (r"Android", "Android"),
        (r"CrOS", "ChromeOS"), (r"Mac OS X|Macintosh", "macOS"), (r"Linux", "Linux"),
    ]:
        if re.search(pattern, user_agent):
            return name
    return "Other"


def country_for(request, tz):
    for header in ("CF-IPCountry", "X-Country-Code"):
        code = request.headers.get(header, "").upper()
        if len(code) == 2 and code.isalpha() and code not in ("XX", "T1"):
            return code
    code = timezones().get(tz or "")
    if code:
        return code
    match = re.search(r"\b[a-zA-Z]{2,3}[-_]([A-Za-z]{2})\b", request.headers.get("Accept-Language", ""))
    return match.group(1).upper() if match else ""


def domain_of(url):
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def classify_source(referrer, page_host, query):
    """Return ``(source, medium, campaign, referrer_domain)`` for a new session."""
    utm = {key: values[0].strip()[:100] for key, values in query.items() if key.startswith("utm_") and values}
    ref_domain = domain_of(referrer) if referrer else ""
    if ref_domain and ref_domain == domain_of(f"//{page_host}"):
        ref_domain = ""  # navigation inside the same site
    campaign = utm.get("utm_campaign", "")
    if utm.get("utm_source") or utm.get("utm_medium"):
        medium = (utm.get("utm_medium") or "referral").lower()[:50]
        return utm.get("utm_source") or ref_domain or "(not set)", medium, campaign, ref_domain
    if not ref_domain:
        return "Direct", "direct", campaign, ""
    for name, label in SEARCH_ENGINES.items():
        if name in ref_domain.split("."):
            return label, "organic", campaign, ref_domain
    for domain, label in SOCIAL_NETWORKS.items():
        if ref_domain == domain or ref_domain.endswith("." + domain):
            return label, "social", campaign, ref_domain
    return ref_domain, "referral", campaign, ref_domain


def host_allowed(project, host):
    allowed = project.analytics_hosts()
    return not allowed or any(host == domain or host.endswith("." + domain) for domain in allowed)


def record(project, request, payload, now=None):
    """Store a page view. Returns the PageView, or None if the hit is ignored."""
    user_agent = request.headers.get("User-Agent", "")[:500]
    if is_bot(user_agent):
        return None
    url = urlsplit(str(payload.get("u", ""))[:2000])
    host = (url.hostname or "").lower()
    if url.scheme not in ("http", "https") or not host or not host_allowed(project, host):
        return None

    now = now or timezone.now()
    visitor = visitor_id(project.ref, client_ip(request), user_agent, now.date())
    previous = (PageView.objects.filter(project=project, visitor=visitor, created_at__gte=now - SESSION_TIMEOUT)
                .order_by("-created_at").only("session", "source", "medium", "campaign", "referrer").first())
    if previous:
        session = previous.session
        source, medium, campaign, referrer = previous.source, previous.medium, previous.campaign, previous.referrer
    else:
        session = uuid.uuid4().hex
        source, medium, campaign, referrer = classify_source(
            str(payload.get("r", ""))[:2000], host, parse_qs(url.query))

    return PageView.objects.create(
        project=project, created_at=now, visitor=visitor, session=session,
        hostname=host[:255], path=(url.path or "/")[:512], referrer=referrer[:255],
        source=source[:100], medium=medium[:50], campaign=campaign[:100],
        country=country_for(request, str(payload.get("tz", ""))[:64]),
        device=device_for(user_agent), browser=browser_for(user_agent), os=os_for(user_agent),
    )
