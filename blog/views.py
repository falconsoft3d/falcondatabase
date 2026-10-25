from django.http import Http404
from django.shortcuts import render
from django.utils.translation import get_language

from . import posts as blog_posts


def base_url(request):
    return request.build_absolute_uri("/").rstrip("/")


def index(request):
    category = request.GET.get("category")
    if category not in blog_posts.CATEGORIES:
        category = None
    posts = blog_posts.posts_for(get_language(), category)
    return render(request, "blog/index.html", {"posts": posts, "category": category,
                                               "categories": blog_posts.CATEGORIES})


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
