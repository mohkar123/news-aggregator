#!/usr/bin/env python3
"""
Test NYTimes API connection and fetch sample articles.

Run this to verify your API key works before using Airflow.

Usage:
    python scripts/test_nytimes.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add the src package to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    print("=" * 50)
    print("NYTimes API Test")
    print("=" * 50)

    api_key = os.environ.get("NYT_API_KEY", "")

    if not api_key or api_key == "your_api_key_here":
        print("\n❌ NYTIMES_API_KEY not set!")
        print("\nTo fix this:")
        print("  1. Go to https://developer.nytimes.com/")
        print("  2. Create an account (free)")
        print("  3. Create a new app")
        print("  4. Enable APIs: Top Stories, Article Search, Most Popular")
        print("  5. Copy your API key")
        print(f"  6. Edit {env_path}")
        print("  7. Set NYTIMES_API_KEY=your_actual_key")
        return

    print(f"\n✅ API key found (ends with ...{api_key[-4:]})")

    try:
        from news_aggregator.clients.nyt_client import NYTimesClient, format_article

        print("\n🔄 Testing API connection...")
        client = NYTimesClient(api_key)

        # Test Top Stories
        print("\n📰 Fetching top stories (home)...")
        articles = client.get_top_stories("home")
        print(f"   Retrieved {len(articles)} articles")

        if articles:
            print("\n   Sample article:")
            print(format_article(articles[0], "brief"))

        # Test Most Popular
        print("📈 Fetching most popular...")
        popular = client.get_most_popular("viewed", period=1)
        print(f"   Retrieved {len(popular)} popular articles")

        print("\n" + "=" * 50)
        print("✅ All tests passed! Your API is working.")
        print("=" * 50)
        print("\nNext steps:")
        print("  1. Start Airflow: ./scripts/start_airflow.sh")
        print("  2. Go to http://localhost:8080")
        print("  3. Enable the '05_nytimes_aggregator' DAG")
        print("  4. Trigger it manually or wait for schedule")
        print("  5. Read your news: python scripts/read_news.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nThis might mean:")
        print("  - Invalid API key")
        print("  - API rate limit exceeded (wait a minute)")
        print("  - Network issue")


if __name__ == "__main__":
    main()
