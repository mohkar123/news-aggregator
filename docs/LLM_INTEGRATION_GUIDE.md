# LLM Integration Guide

A guide to the LLM layer in the NYTimes News Aggregator — how it is structured, how to configure it, and how to extend or harden it for production.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Provider Comparison](#provider-comparison)
4. [Prompt Engineering](#prompt-engineering)
5. [Error Handling & Resilience](#error-handling--resilience)
6. [Cost Management](#cost-management)
7. [Testing Strategies](#testing-strategies)
8. [Production Best Practices](#production-best-practices)

---

## Overview

The LLM layer sits between the data-fetch tasks and the email-delivery task in `dags/05_nytimes_aggregator.py`. It performs two levels of summarization:

1. **Per-section summary** — each news section (world, technology, science, ESG, …) is summarized independently.
2. **Daily digest** — all section summaries are combined into a single briefing.

LLM availability is checked once at DAG startup. Every downstream task receives the result and degrades gracefully when no provider is configured.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                    DAG 05 — nytimes_aggregator                    │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  check_api_key  ──►  fetch_top_stories (×4 sections)             │
│  check_llm      ──►  fetch_esg_articles                          │
│  check_email    ──►  fetch_most_popular                          │
│                           │                                       │
│                    summarize_section (×6, parallel)              │
│                    [uses news_aggregator.clients.llm_client]      │
│                           │                                       │
│                    create_daily_digest                            │
│                           │                                       │
│               ┌───────────┴───────────┐                          │
│         combine_articles       (digest text)                     │
│               │                       │                          │
│         generate_html_digest ◄────────┘                          │
│               │                                                   │
│         send_email_digest                                         │
│               │                                                   │
│         cleanup_old_files  (trigger_rule=all_done)               │
└───────────────────────────────────────────────────────────────────┘
```

### Module layout

```
src/news_aggregator/
└── clients/
    └── llm_client.py
        ├── BaseLLMProvider    (ABC)
        ├── AnthropicProvider  (Claude)
        ├── OpenAIProvider     (GPT)
        ├── OllamaProvider     (local)
        ├── LLMClient          (auto-selects provider)
        ├── create_summary_prompt()
        ├── create_daily_digest_prompt()
        ├── summarize_articles()
        └── generate_with_retry()
```

### Provider selection order

`LLMClient()` without an explicit `provider=` argument tries each in order:

1. **Anthropic** — if `ANTHROPIC_API_KEY` is set
2. **OpenAI** — if `OPENAI_API_KEY` is set
3. **Ollama** — if a server is responding at `localhost:11434`
4. **Fallback** — returns a placeholder string; the DAG continues without summaries

---

## Provider Comparison

### Anthropic Claude

| Aspect | Details |
|---|---|
| **Best for** | Nuanced summarization, complex instructions, consistent tone |
| **Current models** | `claude-haiku-4-5-20251001` (fast/cheap), `claude-sonnet-4-6` (balanced), `claude-opus-4-6` (best) |
| **Pricing** | ~$0.25–15 / M tokens depending on model |
| **Setup** | `poetry add anthropic` + `ANTHROPIC_API_KEY` in `.env` |

```python
import anthropic
from news_aggregator.clients.llm_client import AnthropicProvider

provider = AnthropicProvider(model="claude-haiku-4-5-20251001")
summary = provider.generate("Summarize this article…")
```

### OpenAI GPT

| Aspect | Details |
|---|---|
| **Best for** | General purpose, wide ecosystem |
| **Models** | `gpt-4o-mini` (fast/cheap), `gpt-4o` (capable) |
| **Pricing** | ~$0.15–30 / M tokens |
| **Setup** | `poetry add openai` (optional dep) + `OPENAI_API_KEY` in `.env` |

```python
from news_aggregator.clients.llm_client import OpenAIProvider

provider = OpenAIProvider(model="gpt-4o-mini")
summary = provider.generate("Summarize this article…")
```

### Ollama (Local)

| Aspect | Details |
|---|---|
| **Best for** | Development, privacy, air-gapped environments |
| **Models** | `llama3.2`, `mistral`, `phi3`, `gemma2`, … |
| **Pricing** | Free — runs on your CPU/GPU |
| **Setup** | Install from <https://ollama.ai/> then `ollama pull llama3.2` |

```python
from news_aggregator.clients.llm_client import OllamaProvider

provider = OllamaProvider(model="llama3.2")
summary = provider.generate("Summarize this article…")
```

### Decision Matrix

| Scenario | Recommended |
|---|---|
| Local development / testing | Ollama |
| Production — quality focus | Anthropic Claude Sonnet |
| Production — cost focus | Claude Haiku or GPT-4o-mini |
| Sensitive / proprietary data | Ollama |
| High volume | Anthropic or OpenAI with batching |

---

## Prompt Engineering

### The prompts used in this project

`create_summary_prompt()` (in `llm_client.py`) supports three styles:

| Style | Length | Use case |
|---|---|---|
| `"brief"` (default) | 200–300 words | Daily email digest |
| `"detailed"` | 400–600 words | Deep-dive reading |
| `"bullet"` | 5–8 bullets | Quick scan |

`create_daily_digest_prompt()` receives all per-section summaries and asks the model to combine them into one 300–400-word briefing.

### Structure of an effective prompt

```
┌──────────────────────────────────┐
│  ROLE / PERSONA                  │  "You are a professional news editor…"
├──────────────────────────────────┤
│  CONTEXT                         │  What section, what style
├──────────────────────────────────┤
│  INPUT DATA                      │  Numbered list of article titles + abstracts
├──────────────────────────────────┤
│  INSTRUCTIONS                    │  Numbered steps (word count, tone, structure)
├──────────────────────────────────┤
│  OUTPUT FORMAT                   │  Exact Markdown headings to use
└──────────────────────────────────┘
```

### Using `Article` models in prompts

The prompt builder takes `list[Article]` — Pydantic objects, not raw dicts:

```python
from news_aggregator.clients.nyt_client import NYTimesClient
from news_aggregator.clients.llm_client import create_summary_prompt, LLMClient

client = NYTimesClient()
articles = client.get_top_stories("technology")   # returns list[Article]

prompt = create_summary_prompt(articles, section="technology", style="brief")
llm = LLMClient()
summary = llm.generate(prompt)
```

### Prompt engineering best practices

1. **Be specific** — "Write 200–300 words" beats "write a summary"
2. **Number your instructions** — models follow numbered lists more reliably
3. **Specify the output format** — exact Markdown headers reduce post-processing
4. **Limit input** — `articles[:10]` prevents prompt bloat
5. **Test iteratively** — run `scripts/test_llm.py` and inspect outputs

---

## Error Handling & Resilience

### How the code handles failures

`LLMClient.generate()` catches provider exceptions and returns a placeholder string rather than raising. The DAG task records `llm_used: False` and continues — the digest is generated without summaries rather than failing.

`generate_with_retry()` adds exponential backoff on top:

```python
from news_aggregator.clients.llm_client import LLMClient, generate_with_retry

client = LLMClient(provider="anthropic")
result = generate_with_retry(client, prompt, max_retries=3, delay=1.0)
# delays: 1s → 2s → 4s
```

### Graceful degradation in a DAG task

```python
from news_aggregator.clients.llm_client import LLMClient
from news_aggregator.models.article import Article

@task
def summarize_section(fetch_result: dict, llm_status: dict) -> dict:
    if not llm_status.get("llm_available"):
        return {"section": fetch_result["section"], "summary": None, "llm_used": False}

    articles = [Article(**a) for a in load_articles(fetch_result["filepath"])]
    try:
        client = LLMClient()
        summary = client.generate(create_summary_prompt(articles, fetch_result["section"]))
        return {"section": fetch_result["section"], "summary": summary, "llm_used": True}
    except Exception as exc:
        logger.warning("LLM summary failed: {}", exc)
        return {"section": fetch_result["section"], "summary": None, "llm_used": False}
```

### Circuit-breaker pattern (optional extension)

```python
import time

class CircuitBreaker:
    """Prevent repeated calls to an unavailable provider."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0) -> None:
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time: float = 0.0
        self.state = "closed"   # closed | open | half-open

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise RuntimeError("Circuit breaker is open — skipping LLM call")

        try:
            result = func(*args, **kwargs)
            self.failures = 0
            self.state = "closed"
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

---

## Cost Management

### Token estimation

```python
def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 characters per token for English text."""
    return len(text) // 4
```

### Model pricing reference (approximate)

| Model | Input / M tokens | Output / M tokens |
|---|---|---|
| `claude-haiku-4-5-20251001` | $0.80 | $4.00 |
| `claude-sonnet-4-6` | $3.00 | $15.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |
| `gpt-4o` | $5.00 | $15.00 |

Prices change frequently — check the provider's pricing page before planning a budget.

### Cost-saving strategies

**1. Use the cheapest model that meets quality requirements**
```python
# In llm_client.py — default is already the cheapest Claude model
provider = AnthropicProvider(model="claude-haiku-4-5-20251001")
```

**2. Limit articles per prompt**
```python
# create_summary_prompt already caps at 10 articles
for i, article in enumerate(articles[:10], 1):
    ...
```

**3. Cache results** (useful if the DAG is re-triggered within the same day)
```python
import hashlib, json
from pathlib import Path

_CACHE_DIR = Path("/tmp/llm_cache")
_CACHE_DIR.mkdir(exist_ok=True)

def cached_generate(client: LLMClient, prompt: str) -> str:
    key = hashlib.md5(prompt.encode()).hexdigest()
    cache_file = _CACHE_DIR / f"{key}.txt"
    if cache_file.exists():
        return cache_file.read_text()
    result = client.generate(prompt)
    cache_file.write_text(result)
    return result
```

**4. Set explicit token limits**
```python
summary = client.generate(prompt, max_tokens=500)   # brief style ≈ 300 words
```

---

## Testing Strategies

### Smoke test (no API key needed)

```bash
poetry run python scripts/test_llm.py --provider ollama
```

### Unit tests (mock the provider)

```python
# tests/test_llm_client.py
from unittest.mock import MagicMock, patch
from news_aggregator.clients.llm_client import summarize_articles
from news_aggregator.models.article import Article

def test_summarize_articles_mock():
    articles = [Article(title="Test", abstract="Content", url="http://example.com")]
    mock_client = MagicMock()
    mock_client.generate.return_value = "Mock summary"

    with patch("news_aggregator.clients.llm_client.LLMClient", return_value=mock_client):
        result = summarize_articles(articles, "technology")

    assert "Mock summary" in result
    mock_client.generate.assert_called_once()

def test_fallback_when_no_provider(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from news_aggregator.clients.llm_client import LLMClient
    client = LLMClient()   # falls back automatically
    result = client.generate("hello")
    assert "not available" in result.lower()
```

### Integration test (real API key)

```python
# tests/test_llm_integration.py
import os
import pytest
from news_aggregator.clients.llm_client import LLMClient

@pytest.mark.integration
def test_anthropic_real_call():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    client = LLMClient(provider="anthropic")
    result = client.generate("Reply with exactly: test successful", max_tokens=20)
    assert "test" in result.lower()
```

Run integration tests separately so they don't hit the API in CI:
```bash
poetry run pytest -m "not integration"           # fast, no API calls
poetry run pytest -m integration --timeout 30    # slow, requires keys
```

### Prompt structure test

```python
def test_prompt_contains_required_sections():
    from news_aggregator.clients.llm_client import create_summary_prompt
    from news_aggregator.models.article import Article

    articles = [Article(title="AI News", abstract="Big developments in AI.")]
    prompt = create_summary_prompt(articles, "technology", style="brief")

    assert "ARTICLES:" in prompt
    assert "INSTRUCTIONS:" in prompt
    assert "technology" in prompt.lower()
    assert estimate_tokens(prompt) < 4_000   # leave room for response
```

---

## Production Best Practices

### 1. Store credentials in Airflow Connections

Instead of `.env`, use the Airflow Connections UI (Admin → Connections):

```python
from airflow.hooks.base import BaseHook

def get_llm_client() -> LLMClient:
    try:
        conn = BaseHook.get_connection("anthropic_api")
        return LLMClient(provider="anthropic", api_key=conn.password)
    except Exception:
        return LLMClient()   # auto-select from env as fallback
```

### 2. Use Airflow Variables for model configuration

```python
from airflow.models import Variable
from news_aggregator.clients.llm_client import AnthropicProvider

model = Variable.get("llm_model", default_var="claude-haiku-4-5-20251001")
provider = AnthropicProvider(model=model)
```

### 3. Structured logging with loguru

All logging in `llm_client.py` uses loguru. Airflow captures stdout/stderr per task, so these logs appear in the task log UI automatically.

```python
from loguru import logger

logger.info("Using LLM provider: {}", client.provider_name)
logger.warning("LLM generation failed: {}. Using fallback.", exc)
logger.error("All {} retries exhausted.", max_retries)
```

### 4. Environment-based model selection

```python
import os
from news_aggregator.clients.llm_client import LLMClient

_MODEL_BY_ENV = {
    "development": "claude-haiku-4-5-20251001",
    "staging":     "claude-haiku-4-5-20251001",
    "production":  "claude-sonnet-4-6",
}

def get_client() -> LLMClient:
    env = os.environ.get("ENVIRONMENT", "development")
    model = _MODEL_BY_ENV.get(env, "claude-haiku-4-5-20251001")
    return LLMClient(provider="anthropic", model=model)
```

### 5. Security checklist

- Never log full prompts — they may contain article text or user data
- Store API keys in Airflow Connections or a secrets backend, not in DAG code
- Add `data/` and `.env` to `.gitignore` (already done)
- Sanitize any user-supplied text before interpolating it into a prompt:

```python
import html
safe_query = html.escape(user_input.strip())
prompt = f"Summarize news about: {safe_query}"
```

---

## Quick Reference

### Install LLM dependencies

```bash
poetry install                  # installs anthropic (in main deps)
poetry install --extras openai  # also installs openai
```

### Test all providers at once

```bash
poetry run python scripts/test_llm.py          # tests all configured providers
poetry run python scripts/test_llm.py --provider anthropic
```

### Common issues

| Issue | Solution |
|---|---|
| Rate limit (429) | `generate_with_retry()` handles this with exponential backoff |
| Token limit exceeded | Reduce `articles[:10]` cap or lower `max_tokens` |
| Slow responses | Switch to a faster model (Haiku vs Sonnet) |
| Inconsistent output format | Tighten the `FORMAT your response as:` section of the prompt |
| High costs | Use `claude-haiku-4-5-20251001` or `gpt-4o-mini`; add caching |

---

*Part of the NYTimes News Aggregator project.*
