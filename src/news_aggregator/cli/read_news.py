"""Terminal-based reader for the NYTimes daily digest.

Usage::

    read-news                       # list sections and tips
    read-news --section world       # read a specific section
    read-news --popular             # read popular articles
    read-news --open                # open HTML digest in browser
    read-news --interactive         # interactive menu
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

try:
    from rich.console import Console
    from rich.markdown import Markdown  # noqa: F401 — re-exported for callers
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    Console = None  # type: ignore[assignment,misc]
    _RICH = False

DATA_DIR = Path(__file__).parents[3] / "data" / "articles"


# ---------------------------------------------------------------------------
# Locate digest files
# ---------------------------------------------------------------------------


def get_latest_digest() -> Path | None:
    """Return the most recent combined digest JSON file, or None."""
    files = sorted(DATA_DIR.glob("combined_*.json"), reverse=True)
    return files[0] if files else None


def get_latest_html() -> Path | None:
    """Return the most recent HTML digest file, or None."""
    files = sorted(DATA_DIR.glob("digest_*.html"), reverse=True)
    return files[0] if files else None


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def display_article_rich(article: dict, console: Console) -> None:  # type: ignore[valid-type]
    """Render a single article using Rich formatting."""
    title = article.get("title") or article.get("headline", {}).get("main", "No title")
    abstract = article.get("abstract") or article.get("snippet", "")
    url = article.get("url") or article.get("web_url", "")
    pub_date = (article.get("published_date", "") or article.get("pub_date", ""))[:10]
    byline_raw = article.get("byline", "")
    byline = byline_raw.get("original", "") if isinstance(byline_raw, dict) else byline_raw

    content = (
        f"[bold blue]{title}[/bold blue]\n\n"
        f"{abstract}\n\n"
        f"[dim]  {pub_date}  {'  ' + byline if byline else ''}[/dim]\n"
        f"[link={url}]Read more[/link]"
    )
    console.print(Panel(content, border_style="blue"))
    console.print()


def display_article_plain(article: dict) -> None:
    """Render a single article as plain text."""
    title = article.get("title") or article.get("headline", {}).get("main", "No title")
    abstract = article.get("abstract") or article.get("snippet", "")
    url = article.get("url") or article.get("web_url", "")
    pub_date = (article.get("published_date", "") or article.get("pub_date", ""))[:10]

    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    print(abstract)
    print(f"\n  {pub_date}")
    print(f"  {url}\n")


def list_sections(data: dict, console: Console | None = None) -> None:  # type: ignore[valid-type]
    """Print a table of available sections and their article counts."""
    if _RICH and console:
        table = Table(title="Available Sections")
        table.add_column("Section", style="cyan")
        table.add_column("Articles", justify="right", style="green")
        for section, articles in data.get("sections", {}).items():
            table.add_row(section.title(), str(len(articles)))
        console.print(table)
    else:
        print("\nAvailable Sections:")
        for section, articles in data.get("sections", {}).items():
            print(f"  - {section.title()}: {len(articles)} articles")


def read_section(
    data: dict,
    section: str,
    limit: int = 10,
    console: Console | None = None,  # type: ignore[valid-type]
) -> None:
    """Print articles from a named section."""
    sections = data.get("sections", {})
    if section not in sections:
        print(f"Section '{section}' not found.")
        list_sections(data, console)
        return

    articles = sections[section][:limit]
    if _RICH and console:
        header = f"\n[bold magenta]  {section.upper()} ({len(articles)} articles)[/bold magenta]\n"
        console.print(header)
        for article in articles:
            display_article_rich(article, console)
    else:
        print(f"\n  {section.upper()} ({len(articles)} articles)\n")
        for article in articles:
            display_article_plain(article)


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


def interactive_mode(data: dict, console: Console | None = None) -> None:  # type: ignore[valid-type]
    """Run a simple interactive menu for browsing the digest."""
    sections = list(data.get("sections", {}).keys())

    while True:
        print("\n" + "=" * 40)
        print("NEWS READER — Interactive Mode")
        print("=" * 40)
        for i, section in enumerate(sections, 1):
            count = len(data["sections"][section])
            print(f"  {i}. {section.title()} ({count})")
        print("\n  a — all sections  |  o — open browser  |  q — quit")

        choice = input("\nYour choice: ").strip().lower()

        if choice == "q":
            print("Goodbye!")
            break
        elif choice == "o":
            html_path = get_latest_html()
            if html_path:
                webbrowser.open(f"file://{html_path}")
            else:
                print("No HTML digest found. Run the Airflow DAG first.")
        elif choice == "a":
            for section in sections:
                read_section(data, section, limit=5, console=console)
                input("\nPress Enter for next section…")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(sections):
                read_section(data, sections[idx], limit=10, console=console)
            else:
                print("Invalid section number.")
        else:
            print("Invalid choice.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for ``read-news``."""
    parser = argparse.ArgumentParser(description="Read your NYTimes news digest")
    parser.add_argument("--section", "-s", help="Read a specific section")
    parser.add_argument("--popular", "-p", action="store_true", help="Show popular articles")
    parser.add_argument("--list", "-l", action="store_true", help="List available sections")
    parser.add_argument("--open", "-o", action="store_true", help="Open HTML digest in browser")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Max articles to show")
    args = parser.parse_args()

    console = Console() if _RICH else None  # type: ignore[misc]

    if args.open:
        html_path = get_latest_html()
        if html_path:
            webbrowser.open(f"file://{html_path}")
            print(f"Opened: {html_path}")
        else:
            print("No HTML digest found. Run the Airflow DAG first.")
        return

    digest_path = get_latest_digest()
    if not digest_path:
        print("No digest found.")
        print("  1. Start Airflow and trigger the '05_nytimes_aggregator' DAG.")
        print("  2. Run this command again.")
        return

    with open(digest_path) as f:
        data = json.load(f)

    if _RICH and console:
        console.print("\n[bold green]  NYTimes Digest[/bold green]")
        console.print(f"[dim]Generated: {data['generated_at']}[/dim]")
        console.print(f"[dim]Total articles: {data['total_articles']}[/dim]\n")
    else:
        print("\n  NYTimes Digest")
        print(f"Generated: {data['generated_at']}")
        print(f"Total articles: {data['total_articles']}\n")

    if args.list:
        list_sections(data, console)
    elif args.interactive:
        interactive_mode(data, console)
    elif args.popular:
        read_section(data, "popular", args.limit, console)
    elif args.section:
        read_section(data, args.section.lower(), args.limit, console)
    else:
        list_sections(data, console)
        print("\nTip: Use --interactive for full reading experience")
        print("     Use --open to view in browser")


if __name__ == "__main__":
    main()
