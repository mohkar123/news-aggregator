"""
DAG 05: NYTimes News Aggregator - Full Featured Pipeline
==========================================================

Production-ready news aggregation with:
- Multiple news sections including ESG/Sustainability
- AI-powered summarization via LLM
- Beautiful HTML digest with professional theme
- Daily email delivery

SECTIONS:
- Home, World, Technology, Science
- ESG/Sustainability (via Article Search)
- Most Popular

SCHEDULE:
- Runs daily at 7 AM

EMAIL SETUP:
Set in .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
EMAIL_FROM, EMAIL_TO
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow.sdk import dag, task
from airflow.providers.standard.operators.empty import EmptyOperator

# Make the src package importable within Airflow workers
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

# Project paths
PROJECT_ROOT = Path(__file__).parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "articles"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Section colours for the HTML theme
SECTION_COLORS = {
    "home": "#1a1a2e",
    "world": "#16213e",
    "technology": "#0f3460",
    "science": "#533483",
    "esg": "#2d6a4f",
    "popular": "#e94560",
}


@dag(
    dag_id="05_nytimes_aggregator",
    schedule="0 7 * * *",  # Daily at 7 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["news", "nytimes", "production", "llm", "esg", "email"],
    default_args={
        "owner": "news-aggregator",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    doc_md=__doc__,
)
def nytimes_aggregator() -> None:
    """Main NYTimes news aggregation pipeline."""

    # =========================================================================
    # VALIDATION TASKS
    # =========================================================================

    @task
    def check_api_key() -> bool:
        """Verify the NYTimes API key is configured."""
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        api_key = os.environ.get("NYT_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            raise ValueError("NYT_API_KEY not configured — add it to .env")
        print(f"NYTimes API key found (ends …{api_key[-4:]})")
        return True

    @task
    def check_llm_availability() -> dict[str, Any]:
        """Check which LLM providers are available."""
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.llm_client import LLMClient

        result: dict[str, Any] = {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "ollama": False,
            "selected": None,
            "llm_available": False,
        }

        try:
            import requests as _req
            resp = _req.get("http://localhost:11434/api/tags", timeout=2)
            result["ollama"] = resp.status_code == 200
        except Exception:
            pass

        client = LLMClient()
        result["selected"] = client.provider_name
        result["llm_available"] = client.is_available()

        if result["llm_available"]:
            print(f"LLM available: {result['selected']}")
        else:
            print("No LLM available. Summaries will be skipped.")

        return result

    @task
    def check_email_config() -> dict[str, Any]:
        """Check whether SMTP credentials are present in the environment."""
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.email.sender import test_email_config

        config = test_email_config()
        if config["configured"]:
            print(f"Email configured: {config['from_email']} -> {config['recipients']}")
        else:
            print("Email not configured. Digest will be saved locally but not sent.")
        return config

    # =========================================================================
    # FETCH TASKS
    # =========================================================================

    @task
    def fetch_top_stories(section: str) -> dict[str, Any]:
        """Fetch top stories for *section* and persist them to disk.

        Args:
            section: NYT section name (e.g. ``"world"``).

        Returns:
            Metadata dict with ``section``, ``count``, and ``filepath``.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.nyt_client import NYTimesClient, save_articles

        client = NYTimesClient()
        articles = client.get_top_stories(section, today_only=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filepath = DATA_DIR / f"top_stories_{section}_{today}.json"
        save_articles(articles, str(filepath))

        print(f"Fetched {len(articles)} articles from {section}")
        return {
            "section": section,
            "count": len(articles),
            "filepath": str(filepath),
            "fetched_at": datetime.now().isoformat(),
        }

    @task
    def fetch_most_popular() -> dict[str, Any]:
        """Fetch the most-viewed articles.

        Returns:
            Metadata dict with ``section``, ``count``, and ``filepath``.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.nyt_client import NYTimesClient, save_articles

        client = NYTimesClient()
        articles = client.get_most_popular("viewed", period=1, today_only=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filepath = DATA_DIR / f"most_popular_{today}.json"
        save_articles(articles, str(filepath))

        print(f"Fetched {len(articles)} popular articles")
        return {
            "section": "popular",
            "count": len(articles),
            "filepath": str(filepath),
        }

    @task
    def fetch_esg_articles() -> dict[str, Any]:
        """Fetch ESG/Sustainability articles via the Article Search API.

        Returns:
            Metadata dict with ``section``, ``count``, and ``filepath``.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.nyt_client import NYTimesClient, save_articles

        client = NYTimesClient()
        articles = client.get_esg_articles(days_back=3, max_articles=15)

        today = datetime.now().strftime("%Y-%m-%d")
        filepath = DATA_DIR / f"esg_{today}.json"
        save_articles(articles, str(filepath))

        print(f"Fetched {len(articles)} ESG/Sustainability articles")
        return {
            "section": "esg",
            "count": len(articles),
            "filepath": str(filepath),
        }

    # =========================================================================
    # LLM SUMMARIZATION TASKS
    # =========================================================================

    @task
    def summarize_section(
        fetch_result: dict[str, Any],
        llm_status: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate an LLM summary for the articles in *fetch_result*.

        Args:
            fetch_result: Output of a fetch task (contains ``section`` and ``filepath``).
            llm_status: Output of :func:`check_llm_availability`.

        Returns:
            Dict with ``section``, ``summary`` (or ``None``), and ``llm_used``.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.llm_client import summarize_articles
        from news_aggregator.clients.nyt_client import load_articles
        from news_aggregator.models.article import Article

        section: str = fetch_result["section"]
        filepath: str = fetch_result["filepath"]
        raw = load_articles(filepath)

        if not llm_status.get("llm_available"):
            return {"section": section, "summary": None, "llm_used": False}

        try:
            print(f"Generating summary for {section}…")
            articles = [Article(**a) for a in raw]
            summary = summarize_articles(articles, section, style="brief")
            print(f"Summary generated for {section}")
            return {
                "section": section,
                "summary": summary,
                "llm_used": True,
                "provider": llm_status.get("selected"),
            }
        except Exception as exc:
            print(f"LLM summary failed for {section}: {exc}")
            return {"section": section, "summary": None, "llm_used": False, "error": str(exc)}

    @task
    def create_daily_digest(
        summaries: list[dict[str, Any]],
        llm_status: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an overall daily digest from all section summaries.

        Args:
            summaries: List of outputs from :func:`summarize_section`.
            llm_status: Output of :func:`check_llm_availability`.

        Returns:
            Dict with ``digest`` text, ``sections_summarized``, and ``section_summaries``.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.clients.llm_client import LLMClient, create_daily_digest_prompt

        section_texts = {s["section"]: s["summary"] for s in summaries if s.get("summary")}

        if not section_texts:
            return {"digest": None, "sections_summarized": 0, "section_summaries": {}}

        if llm_status.get("llm_available"):
            try:
                print("Generating daily digest…")
                client = LLMClient()
                prompt = create_daily_digest_prompt(section_texts)
                digest_text = client.generate(prompt, max_tokens=800)

                today = datetime.now().strftime("%Y-%m-%d")
                digest_path = DATA_DIR / f"llm_digest_{today}.md"
                digest_path.write_text(f"# Daily News Digest — {today}\n\n{digest_text}")

                return {
                    "digest": digest_text,
                    "digest_path": str(digest_path),
                    "sections_summarized": len(section_texts),
                    "section_summaries": section_texts,
                }
            except Exception as exc:
                print(f"Daily digest generation failed: {exc}")

        return {
            "digest": None,
            "sections_summarized": len(section_texts),
            "section_summaries": section_texts,
        }

    # =========================================================================
    # OUTPUT GENERATION
    # =========================================================================

    @task
    def combine_articles(fetch_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge all per-section article files into a single combined JSON.

        Args:
            fetch_results: List of outputs from fetch tasks.

        Returns:
            Dict with ``combined_path``, ``total_articles``, and ``sections``.
        """
        from news_aggregator.clients.nyt_client import load_articles

        all_articles: dict[str, list[dict[str, Any]]] = {}
        for result in fetch_results:
            section: str = result["section"]
            all_articles[section] = load_articles(result["filepath"])

        today = datetime.now().strftime("%Y-%m-%d")
        combined_path = DATA_DIR / f"combined_{today}.json"
        total_count = sum(len(v) for v in all_articles.values())

        with open(combined_path, "w") as fh:
            json.dump(
                {
                    "generated_at": datetime.now().isoformat(),
                    "total_articles": total_count,
                    "sections": all_articles,
                },
                fh,
                indent=2,
            )

        print(f"Combined {total_count} articles from {len(all_articles)} sections")
        return {
            "combined_path": str(combined_path),
            "total_articles": total_count,
            "sections": list(all_articles.keys()),
        }

    @task
    def generate_html_digest(
        combined_result: dict[str, Any],
        daily_digest: dict[str, Any],
    ) -> str:
        """Render an email-compatible HTML digest.

        Args:
            combined_result: Output of :func:`combine_articles`.
            daily_digest: Output of :func:`create_daily_digest`.

        Returns:
            Path to the generated HTML file.
        """
        try:
            import markdown as _md

            def _to_html(text: str) -> str:
                return _md.markdown(text)
        except ImportError:
            def _to_html(text: str) -> str:  # type: ignore[misc]
                return text.replace("\n", "<br>")

        with open(combined_result["combined_path"]) as fh:
            data: dict[str, Any] = json.load(fh)

        today = datetime.now().strftime("%Y-%m-%d")
        today_formatted = datetime.now().strftime("%B %d, %Y")
        html_path = DATA_DIR / f"digest_{today}.html"

        llm_digest: str | None = daily_digest.get("digest")
        section_summaries: dict[str, str] = daily_digest.get("section_summaries", {})

        section_info: dict[str, dict[str, str]] = {
            "home":       {"name": "Top Stories",         "icon": "&#127968;", "color": "#1a1a2e"},
            "world":      {"name": "World News",           "icon": "&#127757;", "color": "#16213e"},
            "technology": {"name": "Technology",           "icon": "&#128187;", "color": "#0f3460"},
            "science":    {"name": "Science",              "icon": "&#128300;", "color": "#533483"},
            "esg":        {"name": "ESG &amp; Sustainability", "icon": "&#127807;", "color": "#2d6a4f"},
            "popular":    {"name": "Most Popular",         "icon": "&#128293;", "color": "#e94560"},
        }

        ai_badge = "AI-Powered Summaries" if llm_digest else ""

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily News Digest - {today_formatted}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:Georgia,'Times New Roman',serif;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background-color:#f5f5f5;">
  <tr><td align="center" style="padding:20px 10px;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;background-color:#ffffff;">

      <!-- Header -->
      <tr><td style="background-color:#1a1a2e;padding:30px 20px;text-align:center;border-bottom:4px solid #e94560;">
        <h1 style="margin:0;font-size:32px;color:#ffffff;font-family:Georgia,serif;">The Daily Digest</h1>
        <p style="margin:10px 0 0;font-size:16px;color:#cccccc;">{today_formatted}</p>
        <p style="margin:10px 0 0;font-size:14px;color:#999999;">{ai_badge}</p>
      </td></tr>

      <!-- Stats bar -->
      <tr><td style="padding:15px 20px;border-bottom:1px solid #eeeeee;">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>
          <td align="center" width="33%" style="padding:10px;">
            <span style="font-size:24px;font-weight:bold;color:#e94560;">{data['total_articles']}</span><br>
            <span style="font-size:12px;color:#888888;">Articles</span>
          </td>
          <td align="center" width="33%" style="padding:10px;">
            <span style="font-size:24px;font-weight:bold;color:#e94560;">{len(data['sections'])}</span><br>
            <span style="font-size:12px;color:#888888;">Sections</span>
          </td>
          <td align="center" width="33%" style="padding:10px;">
            <span style="font-size:24px;font-weight:bold;color:#e94560;">{len(section_summaries)}</span><br>
            <span style="font-size:12px;color:#888888;">AI Summaries</span>
          </td>
        </tr></table>
      </td></tr>
"""

        # AI daily digest block
        if llm_digest:
            html_content += f"""
      <!-- AI Digest -->
      <tr><td style="padding:20px;">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background-color:#667eea;border-radius:8px;">
          <tr><td style="padding:25px;">
            <h2 style="margin:0 0 15px;font-size:22px;color:#ffffff;font-family:Georgia,serif;">Today's AI Briefing</h2>
            <div style="background-color:rgba(255,255,255,0.15);padding:20px;border-radius:6px;color:#ffffff;font-size:15px;line-height:1.7;">
              {_to_html(llm_digest)}
            </div>
          </td></tr>
        </table>
      </td></tr>
"""

        # Per-section content
        for section, articles in data["sections"].items():
            info = section_info.get(
                section, {"name": section.title(), "icon": "&#128240;", "color": "#666"}
            )
            summary_html = _to_html(section_summaries[section]) if section in section_summaries else ""

            html_content += f"""
      <!-- Section: {info['name']} -->
      <tr><td style="padding:20px 20px 0 20px;">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
          <tr><td style="background-color:{info['color']};padding:15px 20px;border-radius:8px 8px 0 0;">
            <span style="font-size:20px;">{info['icon']}</span>
            <span style="font-size:20px;font-weight:bold;color:#ffffff;font-family:Georgia,serif;margin-left:10px;">{info['name']}</span>
            <span style="float:right;background-color:rgba(255,255,255,0.2);padding:4px 12px;border-radius:15px;font-size:13px;color:#ffffff;">{len(articles)} articles</span>
          </td></tr>
        </table>
"""

            if summary_html:
                html_content += f"""
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
          <tr><td style="background-color:#f8f9fa;border-left:4px solid {info['color']};padding:15px 20px;">
            <p style="margin:0 0 8px;font-size:13px;font-weight:bold;color:#333333;">AI Summary</p>
            <div style="font-size:14px;color:#666666;font-style:italic;line-height:1.6;">{summary_html}</div>
          </td></tr>
        </table>
"""

            html_content += """
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background-color:#ffffff;border:1px solid #eeeeee;border-top:none;border-radius:0 0 8px 8px;">
"""
            for idx, article in enumerate(articles[:8]):
                title = article.get("title") or article.get("headline", {}).get("main", "No title")
                abstract = article.get("abstract") or article.get("snippet", "")
                url = article.get("url") or article.get("web_url", "#")
                pub_date = (article.get("published_date", "") or article.get("pub_date", ""))[:10]
                byline = article.get("byline", "")
                if isinstance(byline, dict):
                    byline = byline.get("original", "")
                border = "border-bottom:1px solid #eeeeee;" if idx < min(len(articles), 8) - 1 else ""

                html_content += f"""
          <tr><td style="padding:20px;{border}">
            <h3 style="margin:0 0 8px;font-size:17px;font-weight:bold;line-height:1.4;">
              <a href="{url}" target="_blank" style="color:#2c3e50;text-decoration:none;">{title}</a>
            </h3>
            <p style="margin:0 0 10px;font-size:14px;color:#666666;line-height:1.6;">{abstract}</p>
            <p style="margin:0;font-size:12px;color:#999999;">{pub_date}{f'  {byline}' if byline else ''}</p>
          </td></tr>
"""

            html_content += """
        </table>
      </td></tr>
"""

        html_content += f"""
      <!-- Footer -->
      <tr><td style="background-color:#1a1a2e;padding:30px 20px;text-align:center;">
        <p style="margin:0;font-size:16px;font-weight:bold;color:#ffffff;">The Daily Digest</p>
        <p style="margin:5px 0 0;font-size:14px;color:#cccccc;">Your personalized news briefing</p>
        <p style="margin:15px 0 0;font-size:12px;color:#888888;">Powered by Apache Airflow &amp; Claude AI</p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

        html_path.write_text(html_content)
        print(f"Generated HTML digest: {html_path}")
        return str(html_path)

    @task
    def send_email_digest(
        html_path: str,
        email_config: dict[str, Any],
    ) -> bool:
        """Send the HTML digest to all configured recipients.

        Args:
            html_path: Path to the HTML file generated by :func:`generate_html_digest`.
            email_config: Output of :func:`check_email_config`.

        Returns:
            ``True`` if email was sent, ``False`` if skipped.
        """
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")

        from news_aggregator.email.sender import send_digest

        if not email_config.get("configured"):
            print("Email not configured — skipping send")
            return False

        recipients: list[str] = email_config.get("recipients", [])
        if not recipients:
            print("No email recipients — skipping send")
            return False

        today_formatted = datetime.now().strftime("%B %d, %Y")
        subject = f"NYTimes Daily Digest — {today_formatted}"
        html_body = Path(html_path).read_text()
        send_digest(subject, html_body, recipients)
        print(f"Email sent to {len(recipients)} recipient(s)")
        return True

    @task(trigger_rule="all_done")
    def cleanup_old_files(days_to_keep: int = 7) -> int:
        """Remove data files older than *days_to_keep* days.

        Always runs (``trigger_rule="all_done"``) so old files are cleaned
        even when earlier tasks fail.

        Args:
            days_to_keep: Files older than this are deleted.

        Returns:
            Number of files removed.
        """
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        removed = 0

        for pattern in ["*.json", "*.html", "*.md"]:
            for filepath in DATA_DIR.glob(pattern):
                if filepath.stat().st_mtime < cutoff.timestamp():
                    filepath.unlink()
                    removed += 1

        print(f"Cleaned up {removed} old file(s)")
        return removed

    # =========================================================================
    # DAG FLOW
    # =========================================================================

    start = EmptyOperator(task_id="start")

    # Validation (run in parallel)
    api_check = check_api_key()
    llm_check = check_llm_availability()
    email_check = check_email_config()

    # Fetch all sections (run in parallel after api_check passes)
    home_stories   = fetch_top_stories.override(task_id="fetch_home")("home")
    world_stories  = fetch_top_stories.override(task_id="fetch_world")("world")
    tech_stories   = fetch_top_stories.override(task_id="fetch_technology")("technology")
    sci_stories    = fetch_top_stories.override(task_id="fetch_science")("science")
    esg_stories    = fetch_esg_articles()
    popular        = fetch_most_popular()

    # Summarize each section
    home_sum    = summarize_section.override(task_id="summarize_home")(home_stories, llm_check)
    world_sum   = summarize_section.override(task_id="summarize_world")(world_stories, llm_check)
    tech_sum    = summarize_section.override(task_id="summarize_technology")(tech_stories, llm_check)
    sci_sum     = summarize_section.override(task_id="summarize_science")(sci_stories, llm_check)
    esg_sum     = summarize_section.override(task_id="summarize_esg")(esg_stories, llm_check)
    popular_sum = summarize_section.override(task_id="summarize_popular")(popular, llm_check)

    all_summaries = [home_sum, world_sum, tech_sum, sci_sum, esg_sum, popular_sum]

    # Create overall digest
    daily_digest = create_daily_digest(all_summaries, llm_check)

    # Combine raw articles
    combined = combine_articles([home_stories, world_stories, tech_stories, sci_stories, esg_stories, popular])

    # Render HTML
    html_digest = generate_html_digest(combined, daily_digest)

    # Send email
    email_sent = send_email_digest(html_digest, email_check)

    # Cleanup (always runs)
    cleanup = cleanup_old_files(days_to_keep=7)

    end = EmptyOperator(task_id="end", trigger_rule="all_done")

    # Explicit upstream dependencies that TaskFlow can't infer
    start >> [api_check, llm_check, email_check]
    api_check >> [home_stories, world_stories, tech_stories, sci_stories, esg_stories, popular]
    email_sent >> cleanup >> end


nytimes_dag = nytimes_aggregator()
