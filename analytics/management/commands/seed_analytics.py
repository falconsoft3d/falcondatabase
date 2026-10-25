import datetime
import random
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from analytics.models import PageView
from projects.models import Project

COUNTRIES = [("US", 30), ("ES", 18), ("MX", 10), ("CL", 8), ("GB", 7), ("DE", 6), ("AR", 5), ("CU", 4), ("FR", 4), ("CO", 4)]
CHANNELS = [  # (source, medium, referrer, weight)
    ("Direct", "direct", "", 34), ("Google", "organic", "google.com", 30), ("Bing", "organic", "bing.com", 4),
    ("LinkedIn", "social", "linkedin.com", 8), ("X (Twitter)", "social", "x.com", 5),
    ("github.com", "referral", "github.com", 7), ("newsletter", "email", "", 6), ("google", "cpc", "", 6),
]
DEVICES = [("desktop", 58), ("mobile", 36), ("tablet", 6)]
BROWSERS = {"desktop": [("Chrome", 62), ("Safari", 14), ("Firefox", 12), ("Edge", 12)],
            "mobile": [("Safari", 48), ("Chrome", 44), ("Samsung Internet", 8)],
            "tablet": [("Safari", 70), ("Chrome", 30)]}
SYSTEMS = {"desktop": [("Windows", 55), ("macOS", 35), ("Linux", 10)],
           "mobile": [("iOS", 52), ("Android", 48)], "tablet": [("iOS", 75), ("Android", 25)]}
PAGES = [("/", 30), ("/pricing", 12), ("/blog", 10), ("/docs", 9), ("/blog/getting-started", 8),
         ("/login", 7), ("/signup", 6), ("/about", 4), ("/contact", 3), ("/changelog", 2)]


def pick(options):
    values, weights = zip(*options)
    return random.choices(values, weights)[0]


class Command(BaseCommand):
    help = "Fill a project's analytics with realistic sample visits (for demos and testing)."

    def add_arguments(self, parser):
        parser.add_argument("project", help="Project ref (20 letters) or owner/slug")
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--sessions", type=int, default=120, help="Average sessions per day")
        parser.add_argument("--host", default="www.example.com")
        parser.add_argument("--seed", type=int, default=None)

    def handle(self, *args, project, days, sessions, host, seed, **options):
        random.seed(seed)
        if "/" in project:
            owner, slug = project.split("/", 1)
            target = Project.objects.filter(owner__username=owner, slug=slug).first()
        else:
            target = Project.objects.filter(ref=project).first()
        if target is None:
            raise CommandError(f"Project {project!r} not found.")

        now = timezone.now()
        rows = []
        for offset in range(days):
            day = (now - datetime.timedelta(days=offset)).date()
            weekend = day.weekday() >= 5
            growth = 1 + (days - offset) / days * 0.4      # traffic grows over the period
            count = int(random.gauss(sessions * growth * (0.7 if weekend else 1), sessions * 0.08))
            for _ in range(max(count, 0)):
                start = datetime.datetime.combine(day, datetime.time(), tzinfo=datetime.UTC) + datetime.timedelta(
                    seconds=random.randint(0, 86399))
                if start > now:
                    continue
                source, medium, referrer, _w = random.choices(CHANNELS, [c[3] for c in CHANNELS])[0]
                device = pick(DEVICES)
                common = dict(
                    project=target, visitor=uuid.uuid4().hex, session=uuid.uuid4().hex, hostname=host,
                    referrer=referrer, source=source, medium=medium, campaign="", country=pick(COUNTRIES),
                    device=device, browser=pick(BROWSERS[device]), os=pick(SYSTEMS[device]),
                )
                views = 1 if random.random() < 0.42 else random.randint(2, 6)
                for view in range(views):
                    rows.append(PageView(created_at=start + datetime.timedelta(minutes=2 * view), path=pick(PAGES), **common))
        PageView.objects.bulk_create(rows, batch_size=2000)
        target.analytics_enabled = True
        target.save(update_fields=["analytics_enabled"])
        self.stdout.write(self.style.SUCCESS(f"Created {len(rows)} page views for {target} over {days} days."))
