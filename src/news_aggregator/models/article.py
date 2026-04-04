"""Pydantic models for NYT article data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


class Article(BaseModel):
    """Unified article model covering both NYT Top Stories and Article Search formats."""

    title: str
    abstract: str = ""
    url: str = ""
    published_date: str = ""
    byline: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Article:
        """Parse either Top Stories or Article Search API response format."""
        title = raw.get("title") or raw.get("headline", {}).get("main", "No title")
        abstract = raw.get("abstract") or raw.get("snippet", "")
        url = raw.get("url") or raw.get("web_url", "")
        published_date = raw.get("published_date", "") or raw.get("pub_date", "")
        byline_raw = raw.get("byline", "")
        if isinstance(byline_raw, dict):
            byline = byline_raw.get("original", "")
        else:
            byline = byline_raw or ""
        return cls(
            title=title,
            abstract=abstract,
            url=url,
            published_date=published_date,
            byline=byline,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict for XCom / JSON serialization."""
        return self.model_dump()


class DigestSection(BaseModel):
    """One section of the daily digest (e.g. 'world', 'technology')."""

    section: str
    articles: list[Article]
    summary: str = ""


class Digest(BaseModel):
    """Full daily news digest combining all sections."""

    generated_at: str
    total_articles: int
    sections: dict[str, list[dict[str, Any]]]

    @model_validator(mode="before")
    @classmethod
    def _coerce_total(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "total_articles" not in values:
            sections = values.get("sections", {})
            values["total_articles"] = sum(len(v) for v in sections.values())
        return values
