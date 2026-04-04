"""Tests for news_aggregator.clients.nyt_client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from news_aggregator.clients.nyt_client import (
    NYTimesClient,
    format_article,
    load_articles,
    save_articles,
)
from news_aggregator.models.article import Article


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


TOP_STORIES_PAYLOAD = {
    "results": [
        {
            "title": "Article One",
            "abstract": "Abstract one.",
            "url": "https://nytimes.com/1",
            "published_date": "2026-04-04T12:00:00-05:00",
            "byline": "By Author One",
        },
        {
            "title": "Article Two",
            "abstract": "Abstract two.",
            "url": "https://nytimes.com/2",
            "published_date": "2026-04-04T11:00:00-05:00",
            "byline": "By Author Two",
        },
    ]
}

POPULAR_PAYLOAD = {"results": [{"title": "Popular", "abstract": "Pop abstract.", "url": "https://nytimes.com/pop"}]}

SEARCH_PAYLOAD = {
    "response": {
        "docs": [
            {
                "headline": {"main": "ESG Story"},
                "snippet": "ESG snippet.",
                "web_url": "https://nytimes.com/esg",
                "pub_date": "2026-04-04T00:00:00+0000",
                "byline": {"original": "By ESG Author"},
            }
        ]
    }
}


# ---------------------------------------------------------------------------
# NYTimesClient init
# ---------------------------------------------------------------------------

class TestNYTimesClientInit:
    def test_raises_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NYT_API_KEY", raising=False)
        with pytest.raises(ValueError, match="NYT_API_KEY not set"):
            NYTimesClient()

    def test_accepts_explicit_key(self) -> None:
        client = NYTimesClient(api_key="testkey")
        assert client.api_key == "testkey"

    def test_reads_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "envkey")
        client = NYTimesClient()
        assert client.api_key == "envkey"


# ---------------------------------------------------------------------------
# get_top_stories
# ---------------------------------------------------------------------------

class TestGetTopStories:
    def test_returns_articles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        with patch.object(client._session, "get", return_value=_mock_response(TOP_STORIES_PAYLOAD)):
            articles = client.get_top_stories("home")
        assert len(articles) == 2
        assert articles[0].title == "Article One"
        assert articles[1].url == "https://nytimes.com/2"

    def test_empty_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        with patch.object(client._session, "get", return_value=_mock_response({"results": []})):
            assert client.get_top_stories("world") == []


# ---------------------------------------------------------------------------
# get_most_popular
# ---------------------------------------------------------------------------

class TestGetMostPopular:
    def test_returns_articles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        with patch.object(client._session, "get", return_value=_mock_response(POPULAR_PAYLOAD)):
            articles = client.get_most_popular("viewed", period=1)
        assert articles[0].title == "Popular"


# ---------------------------------------------------------------------------
# get_esg_articles — including the null-docs regression
# ---------------------------------------------------------------------------

class TestGetEsgArticles:
    def test_returns_articles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        with patch.object(client._session, "get", return_value=_mock_response(SEARCH_PAYLOAD)):
            articles = client.get_esg_articles()
        assert articles[0].title == "ESG Story"
        assert articles[0].byline == "By ESG Author"

    def test_null_docs_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: NYT API occasionally returns {"response": {"docs": null}}."""
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        payload = {"response": {"docs": None}}
        with patch.object(client._session, "get", return_value=_mock_response(payload)):
            articles = client.get_esg_articles()
        assert articles == []

    def test_missing_response_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        with patch.object(client._session, "get", return_value=_mock_response({})):
            assert client.get_esg_articles() == []

    def test_respects_max_articles(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        many_docs = [{"headline": {"main": f"Doc {i}"}} for i in range(20)]
        payload = {"response": {"docs": many_docs}}
        with patch.object(client._session, "get", return_value=_mock_response(payload)):
            articles = client.get_esg_articles(max_articles=5)
        assert len(articles) == 5


# ---------------------------------------------------------------------------
# Rate-limit retry
# ---------------------------------------------------------------------------

class TestRetryBehaviour:
    def test_retries_on_429(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NYT_API_KEY", "key")
        client = NYTimesClient()
        rate_limited = _mock_response({}, status=429)
        rate_limited.raise_for_status = MagicMock()
        ok = _mock_response({"results": []})

        with patch.object(client._session, "get", side_effect=[rate_limited, ok]):
            with patch("time.sleep"):   # don't actually wait
                articles = client.get_top_stories("home")
        assert articles == []


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

class TestSaveLoadArticles:
    def test_roundtrip(self, tmp_path: Path, article: Article) -> None:
        path = str(tmp_path / "articles.json")
        save_articles([article], path)
        loaded = load_articles(path)
        assert len(loaded) == 1
        assert loaded[0]["title"] == article.title

    def test_creates_parent_dirs(self, tmp_path: Path, article: Article) -> None:
        path = str(tmp_path / "nested" / "dir" / "articles.json")
        save_articles([article], path)
        assert Path(path).exists()

    def test_empty_list(self, tmp_path: Path) -> None:
        path = str(tmp_path / "empty.json")
        save_articles([], path)
        assert load_articles(path) == []


# ---------------------------------------------------------------------------
# format_article
# ---------------------------------------------------------------------------

class TestFormatArticle:
    def test_brief_contains_title(self, article: Article) -> None:
        result = format_article(article, style="brief")
        assert article.title in result
        assert article.url in result

    def test_full_contains_abstract(self, article: Article) -> None:
        result = format_article(article, style="full")
        assert article.abstract in result
        assert "=" * 10 in result

    def test_date_truncated_to_10_chars(self, article: Article) -> None:
        result = format_article(article, style="brief")
        assert "2026-04-04" in result
