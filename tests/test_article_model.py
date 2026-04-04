"""Tests for news_aggregator.models.article."""

from __future__ import annotations

import pytest

from news_aggregator.models.article import Article, Digest, DigestSection


class TestArticleFromRaw:
    def test_top_stories_format(self, raw_top_stories: dict) -> None:
        article = Article.from_raw(raw_top_stories)
        assert article.title == "Test Headline"
        assert article.abstract == "Test abstract text."
        assert article.url == "https://www.nytimes.com/test"
        assert article.published_date == "2026-04-04T12:00:00-05:00"
        assert article.byline == "By Test Author"

    def test_article_search_format(self, raw_search_article: dict) -> None:
        article = Article.from_raw(raw_search_article)
        assert article.title == "Search Headline"
        assert article.abstract == "Search snippet text."
        assert article.url == "https://www.nytimes.com/search"
        assert article.byline == "By Search Author"

    def test_byline_dict_extracted(self) -> None:
        raw = {"title": "T", "byline": {"original": "By Dict Author"}}
        assert Article.from_raw(raw).byline == "By Dict Author"

    def test_byline_string_preserved(self) -> None:
        raw = {"title": "T", "byline": "By String Author"}
        assert Article.from_raw(raw).byline == "By String Author"

    def test_missing_fields_default_to_empty(self) -> None:
        article = Article.from_raw({"title": "Minimal"})
        assert article.title == "Minimal"
        assert article.abstract == ""
        assert article.url == ""
        assert article.published_date == ""
        assert article.byline == ""

    def test_completely_empty_dict_uses_fallback_title(self) -> None:
        article = Article.from_raw({})
        assert article.title == "No title"

    def test_headline_preferred_over_title_when_both_present(self) -> None:
        # title takes precedence because it is checked first in from_raw
        raw = {"title": "Top Title", "headline": {"main": "Search Title"}}
        assert Article.from_raw(raw).title == "Top Title"

    def test_web_url_fallback(self) -> None:
        raw = {"title": "T", "web_url": "https://fallback.com"}
        assert Article.from_raw(raw).url == "https://fallback.com"

    def test_pub_date_fallback(self) -> None:
        raw = {"title": "T", "pub_date": "2026-01-01"}
        assert Article.from_raw(raw).published_date == "2026-01-01"


class TestArticleAsDict:
    def test_roundtrip(self, article: Article) -> None:
        d = article.as_dict()
        restored = Article(**d)
        assert restored == article

    def test_returns_plain_dict(self, article: Article) -> None:
        d = article.as_dict()
        assert isinstance(d, dict)
        assert set(d.keys()) == {"title", "abstract", "url", "published_date", "byline"}


class TestDigestModel:
    def test_total_articles_auto_computed(self) -> None:
        digest = Digest(
            generated_at="2026-04-04T07:00:00",
            sections={"world": [{"title": "A"}], "tech": [{"title": "B"}, {"title": "C"}]},
        )
        assert digest.total_articles == 3

    def test_explicit_total_articles_preserved(self) -> None:
        digest = Digest(
            generated_at="2026-04-04T07:00:00",
            total_articles=99,
            sections={},
        )
        assert digest.total_articles == 99


class TestDigestSection:
    def test_defaults(self, article: Article) -> None:
        section = DigestSection(section="world", articles=[article])
        assert section.summary == ""
        assert len(section.articles) == 1
