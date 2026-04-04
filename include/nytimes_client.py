"""
NYTimes API Client

This module provides a clean interface to the NYTimes APIs.
Get your API key from: https://developer.nytimes.com/

Available APIs:
- Top Stories: Get current top stories by section
- Article Search: Search articles by keyword, date range, etc.
- Most Popular: Get most viewed/shared/emailed articles
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class NYTimesClient:
    """Client for interacting with NYTimes APIs."""

    BASE_URL = "https://api.nytimes.com/svc"

    # Available sections for Top Stories API
    SECTIONS = [
        "home", "arts", "automobiles", "books", "business", "fashion",
        "food", "health", "insider", "magazine", "movies", "nyregion",
        "obituaries", "opinion", "politics", "realestate", "science",
        "sports", "sundayreview", "technology", "theater", "t-magazine",
        "travel", "upshot", "us", "world"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the NYTimes client.

        Args:
            api_key: NYTimes API key. If not provided, reads from NYTIMES_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("NYTIMES_API_KEY")
        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError(
                "NYTimes API key not found. "
                "Get one from https://developer.nytimes.com/ and set NYTIMES_API_KEY"
            )
        self._last_request_time = 0
        self._rate_limit_delay = 6  # NYTimes allows ~10 requests/minute

    def _rate_limit(self):
        """Ensure we don't exceed API rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the NYTimes API."""
        self._rate_limit()

        params = params or {}
        params["api-key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def get_top_stories(self, section: str = "home") -> list[dict]:
        """
        Get top stories for a section.

        Args:
            section: News section (home, world, science, technology, etc.)

        Returns:
            List of article dictionaries
        """
        if section not in self.SECTIONS:
            raise ValueError(f"Invalid section. Choose from: {self.SECTIONS}")

        data = self._make_request(f"topstories/v2/{section}.json")
        return data.get("results", [])

    def search_articles(
        self,
        query: str,
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort: str = "relevance",
        page: int = 0
    ) -> dict:
        """
        Search for articles.

        Args:
            query: Search query
            begin_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)
            sort: Sort order (newest, oldest, relevance)
            page: Page number (0-indexed, 10 results per page)

        Returns:
            Dictionary with response data including articles
        """
        params = {
            "q": query,
            "sort": sort,
            "page": page
        }

        if begin_date:
            params["begin_date"] = begin_date
        if end_date:
            params["end_date"] = end_date

        data = self._make_request("search/v2/articlesearch.json", params)
        return data.get("response", {})

    def get_most_popular(
        self,
        resource: str = "viewed",
        period: int = 1
    ) -> list[dict]:
        """
        Get most popular articles.

        Args:
            resource: Type of popularity (viewed, shared, emailed)
            period: Time period in days (1, 7, or 30)

        Returns:
            List of popular articles
        """
        if resource not in ["viewed", "shared", "emailed"]:
            raise ValueError("resource must be: viewed, shared, or emailed")
        if period not in [1, 7, 30]:
            raise ValueError("period must be: 1, 7, or 30")

        data = self._make_request(f"mostpopular/v2/{resource}/{period}.json")
        return data.get("results", [])

    def get_esg_articles(self, days_back: int = 7, max_articles: int = 15) -> list[dict]:
        """
        Get ESG (Environmental, Social, Governance) and Sustainability articles.

        Uses Article Search API with ESG-related keywords.

        Args:
            days_back: How many days back to search
            max_articles: Maximum number of articles to return

        Returns:
            List of ESG-related articles
        """
        # ESG/Sustainability search terms
        esg_queries = [
            "ESG investing",
            "sustainability",
            "climate change corporate",
            "renewable energy business",
            "carbon emissions",
            "green energy",
            "corporate governance",
            "social responsibility",
            "environmental policy",
            "net zero"
        ]

        # Calculate date range
        end_date = datetime.now()
        begin_date = end_date - timedelta(days=days_back)

        all_articles = []
        seen_urls = set()

        for query in esg_queries:
            if len(all_articles) >= max_articles:
                break

            try:
                response = self.search_articles(
                    query=query,
                    begin_date=begin_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    sort="newest",
                    page=0
                )

                docs = response.get("docs", [])
                for doc in docs:
                    url = doc.get("web_url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        # Normalize article format to match Top Stories format
                        normalized = {
                            "title": doc.get("headline", {}).get("main", ""),
                            "abstract": doc.get("abstract") or doc.get("snippet", ""),
                            "url": url,
                            "published_date": doc.get("pub_date", ""),
                            "section": doc.get("section_name", "ESG"),
                            "byline": doc.get("byline", {}).get("original", ""),
                            "source": "Article Search",
                            "keywords": [kw.get("value", "") for kw in doc.get("keywords", [])]
                        }
                        all_articles.append(normalized)

                        if len(all_articles) >= max_articles:
                            break

            except Exception as e:
                print(f"Warning: Error searching for '{query}': {e}")
                continue

        # Sort by date (newest first)
        all_articles.sort(
            key=lambda x: x.get("published_date", ""),
            reverse=True
        )

        return all_articles[:max_articles]


def format_article(article: dict, format_type: str = "brief") -> str:
    """
    Format an article for display.

    Args:
        article: Article dictionary from API
        format_type: 'brief' or 'full'

    Returns:
        Formatted string
    """
    title = article.get("title") or article.get("headline", {}).get("main", "No title")
    abstract = article.get("abstract") or article.get("snippet", "")
    url = article.get("url") or article.get("web_url", "")
    section = article.get("section") or article.get("section_name", "")
    pub_date = article.get("published_date") or article.get("pub_date", "")
    byline = article.get("byline") or ""
    if isinstance(byline, dict):
        byline = byline.get("original", "")

    if format_type == "brief":
        return f"📰 {title}\n   {abstract[:100]}...\n   🔗 {url}\n"
    else:
        return f"""
{'='*60}
📰 {title}
{'='*60}
📅 {pub_date}  |  📁 {section}
✍️  {byline}

{abstract}

🔗 {url}
{'='*60}
"""


def save_articles(articles: list[dict], filepath: str):
    """Save articles to a JSON file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(articles),
            "articles": articles
        }, f, indent=2)


def load_articles(filepath: str) -> list[dict]:
    """Load articles from a JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)
        return data.get("articles", [])
