"""Tests for news_aggregator.email.sender."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from news_aggregator.email.sender import (
    build_html_digest,
    send_digest,
    test_email_config as get_email_config,
)


# ---------------------------------------------------------------------------
# build_html_digest
# ---------------------------------------------------------------------------

class TestBuildHtmlDigest:
    def test_contains_date(self, section_summaries: dict[str, str]) -> None:
        html = build_html_digest(section_summaries, "2026-04-04")
        assert "2026-04-04" in html

    def test_contains_section_names(self, section_summaries: dict[str, str]) -> None:
        html = build_html_digest(section_summaries, "2026-04-04")
        assert "World" in html
        assert "Technology" in html

    def test_contains_summary_text(self, section_summaries: dict[str, str]) -> None:
        html = build_html_digest(section_summaries, "2026-04-04")
        assert "Key events today." in html

    def test_is_valid_html_skeleton(self, section_summaries: dict[str, str]) -> None:
        html = build_html_digest(section_summaries, "2026-04-04")
        assert html.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_empty_summaries(self) -> None:
        html = build_html_digest({}, "2026-04-04")
        assert "2026-04-04" in html


# ---------------------------------------------------------------------------
# test_email_config
# ---------------------------------------------------------------------------

class TestEmailConfig:
    def test_configured_when_all_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_USER", "test@gmail.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_TO", "a@example.com,b@example.com")
        cfg = get_email_config()
        assert cfg["configured"] is True
        assert cfg["recipients"] == ["a@example.com", "b@example.com"]

    def test_not_configured_when_missing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        monkeypatch.delenv("EMAIL_TO", raising=False)
        cfg = get_email_config()
        assert cfg["configured"] is False
        assert cfg["recipients"] == []

    def test_from_email_falls_back_to_smtp_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SMTP_USER", "user@gmail.com")
        monkeypatch.delenv("EMAIL_FROM", raising=False)
        cfg = get_email_config()
        assert cfg["from_email"] == "user@gmail.com"

    def test_from_email_uses_email_from_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EMAIL_FROM", "sender@example.com")
        monkeypatch.setenv("SMTP_USER", "user@gmail.com")
        cfg = get_email_config()
        assert cfg["from_email"] == "sender@example.com"


# ---------------------------------------------------------------------------
# send_digest
# ---------------------------------------------------------------------------

class TestSendDigest:
    def _set_smtp_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "sender@gmail.com")
        monkeypatch.setenv("SMTP_PASSWORD", "apppassword")
        monkeypatch.setenv("EMAIL_FROM", "sender@gmail.com")
        monkeypatch.setenv("EMAIL_TO", "recipient@example.com")

    def test_calls_sendmail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_smtp_env(monkeypatch)
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp):
            send_digest("Test Subject", "<html>body</html>")

        mock_smtp.sendmail.assert_called_once()
        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][0] == "sender@gmail.com"
        assert "recipient@example.com" in call_args[0][1]

    def test_explicit_recipients_override_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._set_smtp_env(monkeypatch)
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp):
            send_digest("Subj", "<html/>", recipients=["override@example.com"])

        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][1] == ["override@example.com"]

    def test_raises_on_missing_smtp_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        with pytest.raises(EnvironmentError, match="SMTP_HOST"):
            send_digest("Subj", "<html/>")
