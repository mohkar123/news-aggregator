"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from news_aggregator.models.article import Article


@pytest.fixture
def raw_top_stories() -> dict:
    """Raw article dict in NYT Top Stories / Most Popular API format."""
    return {
        "title": "Test Headline",
        "abstract": "Test abstract text.",
        "url": "https://www.nytimes.com/test",
        "published_date": "2026-04-04T12:00:00-05:00",
        "byline": "By Test Author",
    }


@pytest.fixture
def raw_search_article() -> dict:
    """Raw article dict in NYT Article Search API format."""
    return {
        "headline": {"main": "Search Headline"},
        "snippet": "Search snippet text.",
        "web_url": "https://www.nytimes.com/search",
        "pub_date": "2026-04-04T12:00:00+0000",
        "byline": {"original": "By Search Author"},
    }


@pytest.fixture
def article() -> Article:
    return Article(
        title="Test Headline",
        abstract="Test abstract text.",
        url="https://www.nytimes.com/test",
        published_date="2026-04-04",
        byline="By Test Author",
    )


@pytest.fixture
def articles(article: Article) -> list[Article]:
    return [article] * 5


@pytest.fixture
def section_summaries() -> dict[str, str]:
    return {
        "world": "## World News Summary\n\nKey events today.",
        "technology": "## Technology News Summary\n\nBig tech news.",
    }
