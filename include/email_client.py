"""
Email Client for News Digest Delivery
======================================

This module handles sending the daily news digest via email.

SETUP OPTIONS:

1. Gmail (recommended for personal use):
   - Enable 2FA on your Google account
   - Generate an App Password: https://myaccount.google.com/apppasswords
   - Use your email as SMTP_USERNAME and App Password as SMTP_PASSWORD

2. SendGrid (recommended for production):
   - Sign up at https://sendgrid.com/
   - Create an API key
   - Use apikey as SMTP_USERNAME and your API key as SMTP_PASSWORD

3. Amazon SES:
   - Set up SES in AWS Console
   - Use your SES SMTP credentials

CONFIGURATION:
Set these in your .env file:
- SMTP_HOST: SMTP server hostname
- SMTP_PORT: SMTP port (587 for TLS, 465 for SSL)
- SMTP_USERNAME: Your email/username
- SMTP_PASSWORD: Your password/app password
- SMTP_FROM_EMAIL: Sender email address
- EMAIL_RECIPIENTS: Comma-separated list of recipient emails
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import Optional


class EmailClient:
    """Client for sending emails via SMTP."""

    # Common SMTP configurations
    SMTP_CONFIGS = {
        "gmail": {
            "host": "smtp.gmail.com",
            "port": 587,
            "use_tls": True
        },
        "sendgrid": {
            "host": "smtp.sendgrid.net",
            "port": 587,
            "use_tls": True
        },
        "ses": {
            "host": "email-smtp.us-east-1.amazonaws.com",
            "port": 587,
            "use_tls": True
        },
        "outlook": {
            "host": "smtp-mail.outlook.com",
            "port": 587,
            "use_tls": True
        }
    }

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email client.

        Args:
            host: SMTP server hostname (or set SMTP_HOST env var)
            port: SMTP port (or set SMTP_PORT env var)
            username: SMTP username (or set SMTP_USERNAME env var)
            password: SMTP password (or set SMTP_PASSWORD env var)
            from_email: Sender email (or set SMTP_FROM_EMAIL env var)
            use_tls: Use TLS encryption
        """
        self.host = host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.port = port or int(os.environ.get("SMTP_PORT", "587"))
        self.username = username or os.environ.get("SMTP_USERNAME", "")
        self.password = password or os.environ.get("SMTP_PASSWORD", "")
        self.from_email = from_email or os.environ.get("SMTP_FROM_EMAIL", self.username)
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        required = [self.host, self.username, self.password, self.from_email]
        return all(required) and self.password not in ["your_smtp_password_here", ""]

    def send_email(
        self,
        to_emails: list[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[list[str]] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML body of the email
            text_content: Plain text alternative (optional)
            attachments: List of file paths to attach (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            print("❌ Email not configured. Set SMTP credentials in .env")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = ", ".join(to_emails)

            # Add plain text version
            if text_content:
                part1 = MIMEText(text_content, "plain")
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, "html")
            msg.attach(part2)

            # Add attachments
            if attachments:
                for filepath in attachments:
                    path = Path(filepath)
                    if path.exists():
                        with open(path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={path.name}"
                            )
                            msg.attach(part)

            # Send email
            context = ssl.create_default_context()

            if self.use_tls:
                with smtplib.SMTP(self.host, self.port) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.sendmail(self.from_email, to_emails, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.from_email, to_emails, msg.as_string())

            print(f"✅ Email sent to {len(to_emails)} recipient(s)")
            return True

        except smtplib.SMTPAuthenticationError as e:
            error_msg = (
                f"SMTP Authentication failed: {e}\n"
                "Check your username and password.\n"
                "For Gmail, use an App Password: https://myaccount.google.com/apppasswords"
            )
            print(f"❌ {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to send email: {e}"
            print(f"❌ {error_msg}")
            raise RuntimeError(error_msg) from e

    def send_news_digest(
        self,
        to_emails: list[str],
        html_digest_path: str,
        include_attachment: bool = False
    ) -> bool:
        """
        Send the news digest email.

        Args:
            to_emails: List of recipient emails
            html_digest_path: Path to the HTML digest file
            include_attachment: Also attach the HTML file

        Returns:
            True if sent successfully
        """
        today = datetime.now().strftime("%B %d, %Y")
        subject = f"📰 Your Daily News Digest - {today}"

        # Read HTML content
        with open(html_digest_path, "r") as f:
            html_content = f.read()

        # Create plain text version
        text_content = f"""
Your Daily News Digest - {today}

View this email in HTML for the best experience.

Generated by Airflow News Aggregator
        """

        attachments = [html_digest_path] if include_attachment else None

        return self.send_email(
            to_emails=to_emails,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            attachments=attachments
        )


def get_email_recipients() -> list[str]:
    """Get email recipients from environment variable."""
    recipients_str = os.environ.get("EMAIL_RECIPIENTS", "")
    if not recipients_str:
        return []
    return [email.strip() for email in recipients_str.split(",") if email.strip()]


def test_email_config() -> dict:
    """Test email configuration and return status."""
    client = EmailClient()

    result = {
        "configured": client.is_configured(),
        "host": client.host,
        "port": client.port,
        "from_email": client.from_email,
        "recipients": get_email_recipients()
    }

    if not result["configured"]:
        result["error"] = "SMTP credentials not set"
    elif not result["recipients"]:
        result["warning"] = "No recipients configured (set EMAIL_RECIPIENTS)"

    return result
