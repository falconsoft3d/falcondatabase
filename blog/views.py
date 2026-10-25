from collections import Counter

from django.http import Http404
from django.shortcuts import render
from django.utils.translation import get_language

from . import posts as blog_posts


def base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def index(request):
    """Articles filtered by category, tag and a text search (all optional, combinable)."""
    lang = get_language()
    everything = blog_posts.posts_for(lang)
    category = request.GET.get("category")
    if category not in blog_posts.CATEGORIES:
        category = None
    tag = request.GET.get("tag", "").strip()
    query = request.GET.get("q", "").strip()[:100]

    posts = [p for p in everything if (not category or p.category == category) and (not tag or tag in p.tags)]
    posts = blog_posts.search(posts, query)

    counts = Counter(p.category for p in everything)
    tags = Counter(t for p in everything for t in p.tags).most_common(16)
    return render(request, "blog/index.html", {
        "posts": posts, "category": category, "tag": tag, "query": query,
        "categories": [(c, counts.get(c, 0)) for c in blog_posts.CATEGORIES],
        "total": len(everything), "tags": tags, "filtered": bool(category or tag or query),
    })


def detail(request, slug):
    lang = get_language()
    post = blog_posts.get_post(slug, lang)
    if post is None:
        raise Http404
    html, toc = post.render(base_url(request))
    ordered = blog_posts.posts_for(lang)
    position = next(i for i, p in enumerate(ordered) if p.slug == slug)
    newer = ordered[position - 1] if position > 0 else None
    older = ordered[position + 1] if position + 1 < len(ordered) else None
    return render(request, "blog/detail.html", {
        "post": post, "body": html, "toc": toc, "newer": newer, "older": older,
        "translated": post.lang == lang,
    })
