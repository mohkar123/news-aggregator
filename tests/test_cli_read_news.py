"""Tests for news_aggregator.cli.read_news."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from news_aggregator.cli.read_news import (
    display_article_plain,
    get_latest_digest,
    get_latest_html,
    list_sections,
    read_section,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_digest(path: Path, name: str, data: dict) -> Path:
    """Write a JSON digest file and return its path."""
    p = path / name
    p.write_text(json.dumps(data))
    return p


SAMPLE_DIGEST = {
    "generated_at": "2026-04-04T07:00:00",
    "total_articles": 3,
    "sections": {
        "world": [
            {
                "title": "World Headline",
                "abstract": "World abstract.",
                "url": "https://nytimes.com/world",
                "published_date": "2026-04-04",
                "byline": "By World Author",
            }
        ],
        "technology": [
            {
                "title": "Tech Headline",
                "abstract": "Tech abstract.",
                "url": "https://nytimes.com/tech",
                "published_date": "2026-04-04",
                "byline": "By Tech Author",
            },
            {
                "title": "Tech Headline 2",
                "abstract": "Tech abstract 2.",
                "url": "https://nytimes.com/tech2",
                "published_date": "2026-04-04",
                "byline": "",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# get_latest_digest
# ---------------------------------------------------------------------------

class TestGetLatestDigest:
    def test_returns_none_when_no_files(self, tmp_path: Path) -> None:
        with patch("news_aggregator.cli.read_news.DATA_DIR", tmp_path):
            result = get_latest_digest()
        assert result is None

    def test_returns_most_recent_file(self, tmp_path: Path) -> None:
        _write_digest(tmp_path, "combined_2026-04-03.json", {})
        _write_digest(tmp_path, "combined_2026-04-04.json", {})
        with patch("news_aggregator.cli.read_news.DATA_DIR", tmp_path):
            result = get_latest_digest()
        assert result is not None
        assert "2026-04-04" in result.name

    def test_ignores_non_matching_files(self, tmp_path: Path) -> None:
        (tmp_path / "digest_2026-04-04.html").write_text("<html/>")
        with patch("news_aggregator.cli.read_news.DATA_DIR", tmp_path):
            result = get_latest_digest()
        assert result is None


# ---------------------------------------------------------------------------
# get_latest_html
# ---------------------------------------------------------------------------

class TestGetLatestHtml:
    def test_returns_none_when_no_files(self, tmp_path: Path) -> None:
        with patch("news_aggregator.cli.read_news.DATA_DIR", tmp_path):
            result = get_latest_html()
        assert result is None

    def test_returns_most_recent_html(self, tmp_path: Path) -> None:
        (tmp_path / "digest_2026-04-03.html").write_text("<html/>")
        (tmp_path / "digest_2026-04-04.html").write_text("<html/>")
        with patch("news_aggregator.cli.read_news.DATA_DIR", tmp_path):
            result = get_latest_html()
        assert result is not None
        assert "2026-04-04" in result.name


# ---------------------------------------------------------------------------
# display_article_plain
# ---------------------------------------------------------------------------

class TestDisplayArticlePlain:
    def test_prints_title_and_url(self, capsys: pytest.CaptureFixture) -> None:
        article = {"title": "My Title", "url": "https://example.com", "abstract": "Summary.", "published_date": "2026-04-04"}
        display_article_plain(article)
        out = capsys.readouterr().out
        assert "My Title" in out
        assert "https://example.com" in out

    def test_truncates_date_to_10_chars(self, capsys: pytest.CaptureFixture) -> None:
        article = {"title": "T", "url": "", "abstract": "", "published_date": "2026-04-04T12:00:00-05:00"}
        display_article_plain(article)
        out = capsys.readouterr().out
        assert "2026-04-04" in out
        assert "T12:00:00" not in out

    def test_falls_back_headline_key(self, capsys: pytest.CaptureFixture) -> None:
        article = {"headline": {"main": "Search Title"}, "snippet": "Snip.", "web_url": "https://nyt.com/s", "pub_date": "2026-04-04"}
        display_article_plain(article)
        out = capsys.readouterr().out
        assert "Search Title" in out

    def test_no_title_shows_fallback(self, capsys: pytest.CaptureFixture) -> None:
        display_article_plain({})
        out = capsys.readouterr().out
        assert "No title" in out


# ---------------------------------------------------------------------------
# list_sections
# ---------------------------------------------------------------------------

class TestListSections:
    def test_plain_output_contains_section_names(self, capsys: pytest.CaptureFixture) -> None:
        with patch("news_aggregator.cli.read_news._RICH", False):
            list_sections(SAMPLE_DIGEST, console=None)
        out = capsys.readouterr().out
        assert "World" in out
        assert "Technology" in out

    def test_plain_output_shows_article_counts(self, capsys: pytest.CaptureFixture) -> None:
        with patch("news_aggregator.cli.read_news._RICH", False):
            list_sections(SAMPLE_DIGEST, console=None)
        out = capsys.readouterr().out
        assert "1" in out  # world has 1 article
        assert "2" in out  # technology has 2 articles

    def test_empty_sections(self, capsys: pytest.CaptureFixture) -> None:
        with patch("news_aggregator.cli.read_news._RICH", False):
            list_sections({"sections": {}}, console=None)
        out = capsys.readouterr().out
        assert "Available Sections" in out


# ---------------------------------------------------------------------------
# read_section
# ---------------------------------------------------------------------------

class TestReadSection:
    def test_missing_section_prints_not_found(self, capsys: pytest.CaptureFixture) -> None:
        with patch("news_aggregator.cli.read_news._RICH", False):
            read_section(SAMPLE_DIGEST, "sports", console=None)
        out = capsys.readouterr().out
        assert "not found" in out

    def test_valid_section_prints_articles(self, capsys: pytest.CaptureFixture) -> None:
        with patch("news_aggregator.cli.read_news._RICH", False):
            read_section(SAMPLE_DIGEST, "world", console=None)
        out = capsys.readouterr().out
        assert "World Headline" in out

    def test_limit_is_respected(self, capsys: pytest.CaptureFixture) -> None:
        big_section = {
            "sections": {
                "world": [{"title": f"Article {i}", "url": "", "abstract": "", "published_date": ""} for i in range(10)]
            }
        }
        with patch("news_aggregator.cli.read_news._RICH", False):
            read_section(big_section, "world", limit=3, console=None)
        out = capsys.readouterr().out
        assert "Article 0" in out
        assert "Article 3" not in out
