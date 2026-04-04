"""Tests for news_aggregator.clients.llm_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from news_aggregator.clients.llm_client import (
    LLMClient,
    create_daily_digest_prompt,
    create_summary_prompt,
    generate_with_retry,
    summarize_articles,
)
from news_aggregator.models.article import Article


# ---------------------------------------------------------------------------
# LLMClient initialisation
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClient(provider="nonexistent")

    def test_unavailable_explicit_provider_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="not available"):
            LLMClient(provider="anthropic")

    def test_auto_select_falls_back_when_no_providers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch(
            "news_aggregator.clients.llm_client.OllamaProvider.is_available",
            return_value=False,
        ):
            client = LLMClient()
        assert client.provider_name == "fallback"
        assert not client.is_available()

    def test_auto_select_picks_anthropic_when_key_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        client = LLMClient()
        assert client.provider_name == "anthropic"
        assert client.is_available()

    def test_auto_select_skips_anthropic_picks_openai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        with patch(
            "news_aggregator.clients.llm_client.OllamaProvider.is_available",
            return_value=False,
        ):
            client = LLMClient()
        assert client.provider_name == "openai"


# ---------------------------------------------------------------------------
# LLMClient.generate
# ---------------------------------------------------------------------------

class TestLLMClientGenerate:
    def test_returns_placeholder_when_no_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch(
            "news_aggregator.clients.llm_client.OllamaProvider.is_available",
            return_value=False,
        ):
            client = LLMClient()
        result = client.generate("hello")
        assert "not available" in result.lower()

    def test_delegates_to_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        client = LLMClient()
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Great summary"
        client.provider = mock_provider
        assert client.generate("prompt") == "Great summary"

    def test_falls_back_on_provider_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        client = LLMClient()
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = RuntimeError("API down")
        mock_provider.is_available.return_value = True
        client.provider = mock_provider
        result = client.generate("prompt")
        assert "not available" in result.lower()


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

class TestCreateSummaryPrompt:
    def test_brief_contains_required_sections(self, articles: list[Article]) -> None:
        prompt = create_summary_prompt(articles, "technology", style="brief")
        assert "ARTICLES:" in prompt
        assert "INSTRUCTIONS:" in prompt
        assert "technology" in prompt.lower()

    def test_detailed_style(self, articles: list[Article]) -> None:
        prompt = create_summary_prompt(articles, "world", style="detailed")
        assert "Analysis" in prompt

    def test_bullet_style(self, articles: list[Article]) -> None:
        prompt = create_summary_prompt(articles, "science", style="bullet")
        assert "bullet" in prompt.lower() or "Headlines" in prompt

    def test_capped_at_10_articles(self) -> None:
        many = [Article(title=f"Article {i}") for i in range(20)]
        prompt = create_summary_prompt(many, "home")
        # Only articles 1-10 should appear (numbered list)
        assert "10." in prompt
        assert "11." not in prompt

    def test_article_titles_appear_in_prompt(self, articles: list[Article]) -> None:
        prompt = create_summary_prompt(articles, "world")
        assert articles[0].title in prompt


class TestCreateDailyDigestPrompt:
    def test_contains_all_sections(self, section_summaries: dict[str, str]) -> None:
        prompt = create_daily_digest_prompt(section_summaries)
        assert "WORLD" in prompt
        assert "TECHNOLOGY" in prompt

    def test_contains_section_text(self, section_summaries: dict[str, str]) -> None:
        prompt = create_daily_digest_prompt(section_summaries)
        assert "Key events today." in prompt


# ---------------------------------------------------------------------------
# summarize_articles
# ---------------------------------------------------------------------------

class TestSummarizeArticles:
    def test_empty_list_returns_no_articles_message(self) -> None:
        result = summarize_articles([], "world")
        assert "No articles" in result

    def test_calls_llm_client(
        self, articles: list[Article], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        mock_client = MagicMock()
        mock_client.generate.return_value = "Mock summary"
        with patch("news_aggregator.clients.llm_client.LLMClient", return_value=mock_client):
            result = summarize_articles(articles, "technology")
        assert result == "Mock summary"
        mock_client.generate.assert_called_once()


# ---------------------------------------------------------------------------
# generate_with_retry
# ---------------------------------------------------------------------------

class TestGenerateWithRetry:
    def test_returns_on_first_success(self) -> None:
        client = MagicMock()
        client.generate.return_value = "ok"
        result = generate_with_retry(client, "prompt", max_retries=3)
        assert result == "ok"
        client.generate.assert_called_once()

    def test_retries_on_exception(self) -> None:
        client = MagicMock()
        client.generate.side_effect = [RuntimeError("fail"), RuntimeError("fail"), "success"]
        with patch("time.sleep"):
            result = generate_with_retry(client, "prompt", max_retries=3, delay=0.0)
        assert result == "success"
        assert client.generate.call_count == 3

    def test_returns_failure_message_after_all_retries(self) -> None:
        client = MagicMock()
        client.generate.side_effect = RuntimeError("always fails")
        with patch("time.sleep"):
            result = generate_with_retry(client, "prompt", max_retries=2, delay=0.0)
        assert "failed" in result.lower()
        assert client.generate.call_count == 2
