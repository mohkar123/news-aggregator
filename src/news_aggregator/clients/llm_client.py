"""LLM Client — multi-provider language model integration.

Supported providers (in auto-selection order):
1. Anthropic Claude  — best for nuanced summarization
2. OpenAI GPT        — good general-purpose performance
3. Ollama            — free, local, no API key required

Usage::

    from news_aggregator.clients.llm_client import LLMClient, summarize_articles

    client = LLMClient(provider="anthropic")
    summary = client.generate("Summarize this text...")

    summary = summarize_articles(articles, section="technology")
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from news_aggregator.models.article import Article

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseLLMProvider(ABC):
    """Common interface all providers must implement."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the provider is configured and reachable."""
        ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client: Any = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self.is_available():
            raise ValueError("Anthropic API key not configured")
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key)

        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT API provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self._client: Any = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        if not self.is_available():
            raise ValueError("OpenAI API key not configured")
        try:
            import openai
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        if self._client is None:
            self._client = openai.OpenAI(api_key=self.api_key)

        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider (free, no API key required)."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url

    def is_available(self) -> bool:
        try:
            import requests

            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        import requests

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Unified client
# ---------------------------------------------------------------------------


class LLMClient:
    """Unified LLM client with automatic provider selection.

    Priority: Anthropic → OpenAI → Ollama → extractive fallback.
    """

    PROVIDERS: dict[str, type[BaseLLMProvider]] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    def __init__(self, provider: str | None = None, **kwargs: object) -> None:
        self.provider_name: str = provider or "none"
        self.provider: BaseLLMProvider | None = None
        self.kwargs = kwargs

        if provider:
            if provider not in self.PROVIDERS:
                raise ValueError(
                    f"Unknown provider: {provider}. Choose from: {list(self.PROVIDERS)}"
                )
            self.provider = self.PROVIDERS[provider](**kwargs)
            if not self.provider.is_available():
                raise ValueError(
                    f"Provider '{provider}' is not available "
                    "(missing API key or server not running)"
                )
        else:
            self._auto_select_provider()

    def _auto_select_provider(self) -> None:
        """Select the first available provider."""
        for name, cls in [
            ("anthropic", AnthropicProvider),
            ("openai", OpenAIProvider),
            ("ollama", OllamaProvider),
        ]:
            try:
                candidate = cls(**self.kwargs)
                if candidate.is_available():
                    self.provider = candidate
                    self.provider_name = name
                    logger.info("Using LLM provider: {}", name)
                    return
            except Exception:
                continue

        self.provider = None
        self.provider_name = "fallback"
        logger.warning(
            "No LLM provider available. "
            "Set ANTHROPIC_API_KEY or OPENAI_API_KEY, or run Ollama locally."
        )

    def generate(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text, falling back gracefully if the provider fails."""
        if self.provider:
            try:
                return self.provider.generate(prompt, max_tokens)
            except Exception as exc:
                logger.warning("LLM generation failed: {}. Using fallback.", exc)

        return (
            "[LLM summarization not available. "
            "Configure ANTHROPIC_API_KEY or OPENAI_API_KEY, or install Ollama.]"
        )

    def is_available(self) -> bool:
        """Return True if a working provider is configured."""
        return self.provider is not None and self.provider.is_available()


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def create_summary_prompt(
    articles: list[Article],
    section: str,
    style: str = "brief",
) -> str:
    """Build a structured summarization prompt.

    Args:
        articles: Articles to summarize (capped at 10).
        section: Section name used for context headings.
        style: ``"brief"`` (default), ``"detailed"``, or ``"bullet"``.

    Returns:
        Prompt string ready to send to an LLM.
    """
    article_texts = []
    for i, article in enumerate(articles[:10], 1):
        article_texts.append(f"{i}. {article.title}\n   {article.abstract}")
    articles_block = "\n\n".join(article_texts)

    if style == "brief":
        return f"""You are a professional news editor creating a daily briefing.

Summarize the following {section.upper()} news articles into a concise briefing.

ARTICLES:
{articles_block}

INSTRUCTIONS:
1. Write a 2-3 paragraph executive summary of the key themes and stories
2. Highlight the most important 3-5 stories
3. Note any connecting themes or trends
4. Keep the tone professional and objective
5. Total length: 200-300 words

FORMAT your response as:
## {section.title()} News Summary

[Your summary paragraphs]

### Key Stories
- [Story 1]
- [Story 2]
- [Story 3]

### Themes
[Brief note on connecting themes]
"""

    if style == "detailed":
        return f"""You are a professional news analyst creating an in-depth briefing.

Analyze the following {section.upper()} news articles.

ARTICLES:
{articles_block}

INSTRUCTIONS:
1. Provide a comprehensive summary of each major story
2. Analyze the significance and implications
3. Identify connections between stories
4. Note what to watch for in coming days
5. Total length: 400-600 words

FORMAT your response as:
## {section.title()} News Analysis

### Overview
[2-3 paragraph overview]

### Major Stories
[Detailed coverage of top 3-5 stories]

### Analysis
[Your analysis of trends and implications]

### What to Watch
[Forward-looking points]
"""

    # bullet
    return f"""Summarize these {section.upper()} news headlines into bullet points.

ARTICLES:
{articles_block}

Create a bullet-point summary with:
- One line per major story
- Key facts only
- 5-8 bullets total

## {section.title()} Headlines
"""


def create_daily_digest_prompt(section_summaries: dict[str, str]) -> str:
    """Build a prompt that combines per-section summaries into one daily digest.

    Args:
        section_summaries: Mapping of section name → per-section summary text.

    Returns:
        Prompt string.
    """
    sections_text = "\n\n".join(
        f"### {section.upper()}\n{summary}" for section, summary in section_summaries.items()
    )

    return f"""You are creating a daily news digest combining multiple sections.

SECTION SUMMARIES:
{sections_text}

Create a unified daily digest that:
1. Opens with the single most important story of the day
2. Briefly covers key themes across all sections
3. Highlights any cross-section connections
4. Ends with a forward-looking note

Keep it concise (300-400 words) and engaging.

## Today's News Digest
"""


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------


def summarize_articles(
    articles: list[Article],
    section: str,
    style: str = "brief",
    provider: str | None = None,
) -> str:
    """Summarize a list of articles using an LLM.

    Args:
        articles: Articles to summarize.
        section: Section name (used for headings / context).
        style: ``"brief"``, ``"detailed"``, or ``"bullet"``.
        provider: Force a specific provider; ``None`` for auto-selection.

    Returns:
        Summary text.
    """
    if not articles:
        return f"No articles available for {section}."

    prompt = create_summary_prompt(articles, section, style)
    client = LLMClient(provider=provider)
    return client.generate(prompt, max_tokens=1000)


def generate_with_retry(
    client: LLMClient,
    prompt: str,
    max_retries: int = 3,
    delay: float = 1.0,
) -> str:
    """Generate text with exponential-backoff retry logic.

    Args:
        client: An initialised :class:`LLMClient`.
        prompt: Prompt to send.
        max_retries: Maximum number of attempts.
        delay: Base delay in seconds (doubles each retry).

    Returns:
        Generated text, or a failure notice after all retries are exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return client.generate(prompt)
        except Exception as exc:
            last_error = exc
            logger.warning("Attempt {}/{} failed: {}", attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                sleep_time = delay * (2**attempt)
                logger.info("Retrying in {}s…", sleep_time)
                time.sleep(sleep_time)

    logger.error("All {} attempts failed. Last error: {}", max_retries, last_error)
    return f"[Summary generation failed after {max_retries} attempts]"
