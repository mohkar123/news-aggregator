"""Email delivery for the daily news digest.

Required environment variables (set in .env):
    SMTP_HOST       — e.g. smtp.gmail.com
    SMTP_PORT       — e.g. 587
    SMTP_USER       — your Gmail address
    SMTP_PASSWORD   — app password (not your login password)
    EMAIL_FROM      — sender address (usually same as SMTP_USER)
    EMAIL_TO        — comma-separated list of recipients

Gmail setup:
    1. Enable 2-Step Verification on your Google account.
    2. Go to Google Account → Security → App passwords.
    3. Create an app password and paste it as SMTP_PASSWORD.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from collections.abc import Sequence
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from loguru import logger


def _require_env(key: str) -> str:
    value = os.environ.get(key, "")
    if not value:
        raise OSError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return value


def build_html_digest(section_summaries: dict[str, str], date_str: str) -> str:
    """Render section summaries into a simple HTML email body.

    Args:
        section_summaries: Mapping of section name → markdown/plain summary text.
        date_str: Human-readable date string for the email heading.

    Returns:
        HTML string.
    """
    sections_html = ""
    for section, summary in section_summaries.items():
        # Convert basic markdown-style headers to HTML
        html_summary = summary.replace("\n", "<br>")
        sections_html += f"""
        <div style="margin-bottom:2em;">
            <h2 style="color:#1a1a2e;border-bottom:2px solid #e74c3c;padding-bottom:6px;">
                {section.title()}
            </h2>
            <p style="color:#2c3e50;line-height:1.7;">{html_summary}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 720px; margin: 0 auto;
          padding: 2em; background: #fafafa; }}
  h1   {{ color: #1a1a2e; }}
  .footer {{ color: #888; font-size: 0.85em; margin-top: 3em;
             border-top: 1px solid #ddd; padding-top: 1em; }}
</style>
</head>
<body>
  <h1>NYTimes Daily Digest — {date_str}</h1>
  {sections_html}
  <div class="footer">
    Powered by NYTimes API + Claude AI &middot; Generated automatically by Airflow
  </div>
</body>
</html>"""


def send_digest(
    subject: str,
    html_body: str,
    recipients: Sequence[str] | None = None,
) -> None:
    """Send the digest email via SMTP (Gmail TLS).

    Reads connection settings from environment variables.

    Args:
        subject: Email subject line.
        html_body: Full HTML body produced by :func:`build_html_digest`.
        recipients: Override the EMAIL_TO env var with an explicit list.

    Raises:
        EnvironmentError: If any required env var is missing.
        smtplib.SMTPException: On SMTP errors.
    """
    smtp_host = _require_env("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = _require_env("SMTP_USER")
    smtp_password = _require_env("SMTP_PASSWORD")
    email_from = os.environ.get("EMAIL_FROM") or smtp_user

    if recipients:
        to_list = list(recipients)
    else:
        raw_to = _require_env("EMAIL_TO")
        to_list = [addr.strip() for addr in raw_to.split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(email_from, to_list, msg.as_string())

    logger.info("Digest email sent to: {}", ", ".join(to_list))


def test_email_config() -> dict[str, Any]:
    """Check whether all email environment variables are present.

    Returns:
        Dict with ``configured`` (bool), ``from_email``, and ``recipients`` keys.
    """
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"]
    configured = all(os.environ.get(k) for k in required)
    recipients = [
        addr.strip() for addr in os.environ.get("EMAIL_TO", "").split(",") if addr.strip()
    ]
    return {
        "configured": configured,
        "from_email": os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_USER", ""),
        "recipients": recipients,
    }


def send_digest_from_env(
    section_summaries: dict[str, str],
    date_str: str,
) -> None:
    """Convenience wrapper: build HTML and send in one call.

    Args:
        section_summaries: Mapping of section name → summary text.
        date_str: Date string used in the email subject and heading.
    """
    html_body = build_html_digest(section_summaries, date_str)
    subject = f"NYTimes Daily Digest — {date_str}"
    send_digest(subject, html_body)
