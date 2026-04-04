"""NYTimes API client."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from news_aggregator.models.article import Article

_BASE = "https://api.nytimes.com/svc"

# Sections available via the Top Stories API
TOP_STORY_SECTIONS = [
    "arts",
    "automobiles",
    "books",
    "business",
    "fashion",
    "food",
    "health",
    "home",
    "insider",
    "magazine",
    "movies",
    "nyregion",
    "obituaries",
    "opinion",
    "politics",
    "realestate",
    "science",
    "sports",
    "sundayreview",
    "technology",
    "theater",
    "t-magazine",
    "travel",
    "upshot",
    "us",
    "world",
]


class NYTimesClient:
    """Client for the New York Times APIs."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("NYT_API_KEY", "")
        if not self.api_key:
            raise ValueError("NYT_API_KEY not set. Add it to your .env file or pass it explicitly.")
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_top_stories(self, section: str = "home") -> list[Article]:
        """Fetch top stories for a section.

        Args:
            section: One of TOP_STORY_SECTIONS (default ``"home"``).

        Returns:
            List of :class:`Article` objects.
        """
        url = f"{_BASE}/topstories/v2/{section}.json"
        data = self._get(url)
        results: list[dict[str, Any]] = data.get("results", [])
        logger.info("Fetched {} top stories for section '{}'", len(results), section)
        return [Article.from_raw(r) for r in results]

    def get_most_popular(
        self,
        type: str = "viewed",
        period: int = 1,
    ) -> list[Article]:
        """Fetch most popular articles.

        Args:
            type: ``"viewed"``, ``"shared"``, or ``"emailed"``.
            period: Number of days (1, 7, or 30).

        Returns:
            List of :class:`Article` objects.
        """
        url = f"{_BASE}/mostpopular/v2/{type}/{period}.json"
        data = self._get(url)
        results: list[dict[str, Any]] = data.get("results", [])
        logger.info("Fetched {} most-popular ({}) articles", len(results), type)
        return [Article.from_raw(r) for r in results]

    def search(
        self,
        query: str,
        page: int = 0,
        sort: str = "relevance",
    ) -> list[Article]:
        """Search articles via the Article Search API.

        Args:
            query: Full-text search query.
            page: Zero-based page number.
            sort: ``"relevance"`` or ``"newest"`` or ``"oldest"``.

        Returns:
            List of :class:`Article` objects.
        """
        url = f"{_BASE}/search/v2/articlesearch.json"
        data = self._get(url, params={"q": query, "page": page, "sort": sort})
        docs: list[dict[str, Any]] = data.get("response", {}).get("docs") or []
        logger.info("Search '{}' returned {} articles", query, len(docs))
        return [Article.from_raw(d) for d in docs]

    def get_esg_articles(
        self,
        days_back: int = 3,
        max_articles: int = 15,
    ) -> list[Article]:
        """Fetch ESG / sustainability articles via the Article Search API.

        Args:
            days_back: How many days back to search.
            max_articles: Maximum number of results to return.

        Returns:
            List of :class:`Article` objects.
        """
        from datetime import datetime, timedelta, timezone

        begin_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y%m%d")
        query = (
            'ESG OR sustainability OR "climate change" '
            'OR "renewable energy" OR "carbon emissions" OR governance'
        )
        url = f"{_BASE}/search/v2/articlesearch.json"
        data = self._get(
            url,
            params={
                "q": query,
                "begin_date": begin_date,
                "sort": "newest",
                "fl": "headline,abstract,web_url,pub_date,byline",
            },
        )
        docs: list[dict[str, Any]] = (data.get("response", {}).get("docs") or [])[:max_articles]
        logger.info("Fetched {} ESG/sustainability articles", len(docs))
        return [Article.from_raw(d) for d in docs]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        """Perform a GET request with automatic retry and rate-limit handling."""
        all_params: dict[str, Any] = {"api-key": self.api_key}
        if params:
            all_params.update(params)

        for attempt in range(retries):
            try:
                response = self._session.get(url, params=all_params, timeout=15)
                if response.status_code == 429:
                    wait = 10 * (attempt + 1)
                    logger.warning("Rate limited — waiting {}s before retry", wait)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
            except requests.RequestException as exc:
                if attempt == retries - 1:
                    raise
                logger.warning("Request failed (attempt {}/{}): {}", attempt + 1, retries, exc)
                time.sleep(2**attempt)

        return {}  # unreachable, satisfies mypy


# ---------------------------------------------------------------------------
# File I/O helpers (used by Airflow tasks to persist between task boundaries)
# ---------------------------------------------------------------------------


def save_articles(articles: list[Article], filepath: str) -> None:
    """Serialise a list of articles to a JSON file.

    Args:
        articles: Articles to save.
        filepath: Destination file path (parent dirs created if absent).
    """
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as fh:
        json.dump([a.as_dict() for a in articles], fh, indent=2)
    logger.debug("Saved {} articles to {}", len(articles), filepath)


def load_articles(filepath: str) -> list[dict[str, Any]]:
    """Load articles previously saved by :func:`save_articles`.

    Args:
        filepath: Path to the JSON file.

    Returns:
        List of raw article dicts.
    """
    with open(filepath) as fh:
        return json.load(fh)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def format_article(article: Article, style: str = "brief") -> str:
    """Render an :class:`Article` as a human-readable string.

    Args:
        article: The article to format.
        style: ``"brief"`` (default) or ``"full"``.

    Returns:
        Formatted string.
    """
    date = article.published_date[:10] if article.published_date else ""
    by = f"  {article.byline}" if article.byline else ""

    if style == "brief":
        return f"{article.title}\n{date}{by}\n{article.url}"

    return (
        f"{'=' * 60}\n"
        f"{article.title}\n"
        f"{date}{by}\n"
        f"{'=' * 60}\n"
        f"{article.abstract}\n\n"
        f"{article.url}\n"
    )
