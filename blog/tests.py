from django.test import TestCase
from django.urls import reverse

from . import posts as blog_posts

LANGUAGES = ("en", "es")


class BlogContentTests(TestCase):
    def test_every_article_is_in_english_and_spanish(self):
        articles = blog_posts.all_posts()
        self.assertGreaterEqual(len(articles), 10)
        for slug, versions in articles.items():
            self.assertEqual(sorted(versions), sorted(LANGUAGES), slug)
            en, es = versions["en"], versions["es"]
            self.assertEqual((en.date, en.category), (es.date, es.category), slug)

    def test_has_tutorials(self):
        tutorials = blog_posts.posts_for("en", "tutorial")
        self.assertGreaterEqual(len(tutorials), 5)

    def test_markdown_renders_with_base_url(self):
        post = blog_posts.get_post("query-tables-with-javascript-sdk", "en")
        html, toc = post.render("https://db.example.com")
        self.assertIn("https://db.example.com/sdk/falcondb.js", html)
        self.assertNotIn("%BASE_URL%", html)
        self.assertTrue(toc)


class BlogViewTests(TestCase):
    def get(self, url, lang):
        return self.client.get(url, headers={"Accept-Language": lang})

    def test_index_in_both_languages(self):
        self.assertContains(self.get(reverse("blog:index"), "en"), "Introducing falcondatabase")
        self.assertContains(self.get(reverse("blog:index"), "es"), "Presentamos falcondatabase")

    def test_category_filter(self):
        response = self.get(reverse("blog:index") + "?category=guide", "en")
        self.assertContains(response, "understanding access rules")
        self.assertNotContains(response, "Introducing falcondatabase")

    def test_every_article_renders(self):
        for slug in blog_posts.all_posts():
            for lang in LANGUAGES:
                response = self.get(reverse("blog:detail", args=[slug]), lang)
                self.assertEqual(response.status_code, 200, (slug, lang))
                self.assertContains(response, blog_posts.get_post(slug, lang).title)

    def test_unknown_article(self):
        self.assertEqual(self.client.get(reverse("blog:detail", args=["nope"])).status_code, 404)

    def test_home_shows_latest_articles(self):
        self.assertContains(self.get(reverse("home"), "en"), "Latest from the blog")


class BlogSearchTests(TestCase):
    def get(self, query, lang="en"):
        return self.client.get(reverse("blog:index") + query, headers={"Accept-Language": lang})

    def slugs(self, response):
        return [p.slug for p in response.context["posts"]]

    def test_search(self):
        self.assertEqual(self.slugs(self.get("?q=install+extension")), ["chrome-extension"])
        self.assertIn("chrome-extension", self.slugs(self.get("?q=EXTENSION")))
        # Accents and case don't matter: "analitica" finds "Analítica".
        spanish = self.slugs(self.get("?q=analitica", "es"))
        self.assertIn("web-analytics-without-cookies", spanish)
        self.assertEqual(self.slugs(self.get("?q=zzzz-nothing")), [])
        self.assertContains(self.get("?q=zzzz-nothing"), "No articles found")

    def test_title_matches_rank_first(self):
        results = self.slugs(self.get("?q=portal"))
        self.assertEqual(results[0], "project-portal")

    def test_tags_and_combined_filters(self):
        tagged = self.get("?tag=docker")
        self.assertEqual(self.slugs(tagged), ["deploy-with-docker"])
        combined = self.slugs(self.get("?category=guide&q=json"))
        self.assertEqual(combined[0], "export-import-projects")  # "JSON" is in its title
        self.assertTrue(all(blog_posts.get_post(s, "en").category == "guide" for s in combined))
        self.assertEqual(self.get("?category=bogus").context["category"], None)

    def test_categories_have_counts(self):
        response = self.get("")
        counts = dict(response.context["categories"])
        self.assertEqual(sum(counts.values()), response.context["total"])
        self.assertGreaterEqual(counts["tutorial"], 5)

    def test_home_links_installation_guide(self):
        self.assertContains(self.client.get(reverse("home")), reverse("blog:detail", args=["chrome-extension"]))
