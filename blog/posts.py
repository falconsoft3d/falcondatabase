"""Blog articles stored as Markdown files: ``posts/<slug>.<lang>.md``.

Each file starts with a small front matter block::

    ---
    title: My article
    date: 2026-10-20
    category: tutorial        # tutorial, guide or news
    summary: One sentence for the listing.
    tags: api, javascript
    ---

``%BASE_URL%`` in the body is replaced with the URL of the running server.
"""

import datetime
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import markdown

POSTS_DIR = Path(__file__).resolve().parent / "posts"
FILE_RE = re.compile(r"^(?P<slug>[a-z0-9-]+)\.(?P<lang>[a-z]{2})\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.S)
CATEGORIES = ("tutorial", "guide", "news")
WORDS_PER_MINUTE = 200


@dataclass
class Post:
    slug: str
    lang: str
    title: str
    date: datetime.date
    category: str
    summary: str
    body: str
    tags: list = field(default_factory=list)

    @property
    def reading_minutes(self):
        return max(1, round(len(self.body.split()) / WORDS_PER_MINUTE))

    def render(self, base_url):
        """Return ``(html, toc)`` for the article body."""
        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "sane_lists"],
                               extension_configs={"toc": {"toc_depth": "2-3"}})
        html = md.convert(self.body.replace("%BASE_URL%", base_url))
        return html, md.toc_tokens


def unquote(value):
    """Front matter values may be quoted, e.g. ``title: "Tutorial: x"``."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(path):
    match = FILE_RE.match(path.name)
    content = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match or not content:
        raise ValueError(f"Invalid blog post file: {path.name}")
    meta = dict(
        (key.strip(), unquote(value.strip()))
        for key, _sep, value in (line.partition(":") for line in content["meta"].splitlines() if line.strip())
    )
    category = meta.get("category", "guide")
    if category not in CATEGORIES:
        raise ValueError(f"{path.name}: unknown category {category!r}")
    return Post(
        slug=match["slug"],
        lang=match["lang"],
        title=meta["title"],
        date=datetime.date.fromisoformat(meta["date"]),
        category=category,
        summary=meta.get("summary", ""),
        tags=[tag.strip() for tag in meta.get("tags", "").split(",") if tag.strip()],
        body=content["body"].strip(),
    )


def _signature():
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in POSTS_DIR.glob("*.md")))


@lru_cache(maxsize=4)
def _load(signature):
    posts = {}
    for name, _mtime in signature:
        post = parse(POSTS_DIR / name)
        posts.setdefault(post.slug, {})[post.lang] = post
    return posts


def all_posts():
    """``{slug: {lang: Post}}``, reloaded automatically when a file changes."""
    return _load(_signature())


def pick(versions, lang):
    return versions.get(lang) or versions.get("en") or next(iter(versions.values()))


def posts_for(lang, category=None):
    posts = [pick(versions, lang) for versions in all_posts().values()]
    if category:
        posts = [post for post in posts if post.category == category]
    return sorted(posts, key=lambda post: (post.date, post.slug), reverse=True)


def get_post(slug, lang):
    versions = all_posts().get(slug)
    return pick(versions, lang) if versions else None
