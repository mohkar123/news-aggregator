#!/usr/bin/env python3
"""
Test LLM Provider Availability and Connection

Run this to verify your LLM configuration before using the news summarization.

Usage:
    python scripts/test_llm.py
    python scripts/test_llm.py --provider anthropic
    python scripts/test_llm.py --provider openai
    python scripts/test_llm.py --provider ollama
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add the src package to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_anthropic() -> bool:
    """Test Anthropic Claude connection."""
    print("\n🔍 Testing Anthropic Claude...")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your_anthropic_key_here":
        print("   ❌ ANTHROPIC_API_KEY not configured")
        print("   Get your key from: https://console.anthropic.com/")
        return False

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Hello from Claude!' in exactly those words."}]
        )
        response = message.content[0].text
        print(f"   ✅ Anthropic working: {response}")
        return True
    except Exception as e:
        print(f"   ❌ Anthropic error: {e}")
        return False


def test_openai() -> bool:
    """Test OpenAI GPT connection."""
    print("\n🔍 Testing OpenAI GPT...")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "your_openai_key_here":
        print("   ❌ OPENAI_API_KEY not configured")
        print("   Get your key from: https://platform.openai.com/api-keys")
        return False

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'Hello from GPT!' in exactly those words."}]
        )
        text = response.choices[0].message.content
        print(f"   ✅ OpenAI working: {text}")
        return True
    except Exception as e:
        print(f"   ❌ OpenAI error: {e}")
        return False


def test_ollama() -> bool:
    """Test Ollama local connection."""
    print("\n🔍 Testing Ollama (local)...")

    try:
        import requests

        # Check if Ollama is running
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code != 200:
                print("   ❌ Ollama not running")
                print("   Install: curl -fsSL https://ollama.ai/install.sh | sh")
                return False
        except requests.exceptions.ConnectionError:
            print("   ❌ Ollama not running (connection refused)")
            print("   Start Ollama or install from: https://ollama.ai/")
            return False

        # Get available models
        models = resp.json().get("models", [])
        if not models:
            print("   ⚠️  Ollama running but no models installed")
            print("   Run: ollama pull llama3.2")
            return False

        model_names = [m["name"] for m in models]
        print(f"   📦 Available models: {', '.join(model_names)}")

        # Test generation with first available model
        model = model_names[0].split(":")[0]  # Remove tag
        print(f"   🔄 Testing with model: {model}")

        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": "Say 'Hello from Ollama!' in exactly those words.",
                "stream": False
            },
            timeout=60
        )
        text = resp.json().get("response", "").strip()
        print(f"   ✅ Ollama working: {text[:50]}...")
        return True

    except Exception as e:
        print(f"   ❌ Ollama error: {e}")
        return False


def test_auto_selection() -> bool:
    """Test automatic provider selection."""
    print("\n🔍 Testing auto-selection...")

    try:
        from news_aggregator.clients.llm_client import LLMClient

        client = LLMClient()

        if client.is_available():
            print(f"   ✅ Auto-selected provider: {client.provider_name}")

            # Test generation
            print("   🔄 Testing text generation...")
            response = client.generate("In one sentence, what is Apache Airflow?", max_tokens=100)
            print(f"   ✅ Response: {response[:100]}...")
            return True
        else:
            print("   ⚠️  No LLM provider available")
            print("   The DAG will work but summaries will be skipped")
            return False

    except Exception as e:
        print(f"   ❌ Auto-selection error: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Test LLM provider connectivity")
    parser.add_argument("--provider", "-p", choices=["anthropic", "openai", "ollama", "all"],
                        default="all", help="Which provider to test")
    args = parser.parse_args()

    print("=" * 50)
    print("LLM Provider Test")
    print("=" * 50)

    results = {}

    if args.provider in ["anthropic", "all"]:
        results["anthropic"] = test_anthropic()

    if args.provider in ["openai", "all"]:
        results["openai"] = test_openai()

    if args.provider in ["ollama", "all"]:
        results["ollama"] = test_ollama()

    if args.provider == "all":
        results["auto"] = test_auto_selection()

    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    any_working = False
    for provider, success in results.items():
        status = "✅ Working" if success else "❌ Not available"
        print(f"  {provider.capitalize()}: {status}")
        if success:
            any_working = True

    if any_working:
        print("\n✅ At least one LLM provider is working!")
        print("   Your news summaries will be AI-generated.")
    else:
        print("\n⚠️  No LLM providers available.")
        print("   The DAG will still work, but summaries will be skipped.")
        print("\n   To enable AI summaries, either:")
        print("   1. Set ANTHROPIC_API_KEY in .env")
        print("   2. Set OPENAI_API_KEY in .env")
        print("   3. Install and run Ollama locally")


if __name__ == "__main__":
    main()
