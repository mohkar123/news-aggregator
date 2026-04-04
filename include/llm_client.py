"""Backwards-compatibility shim.

The canonical implementation has moved to::

    news_aggregator.clients.llm_client

Import from there in all new code.
"""

from news_aggregator.clients.llm_client import (  # noqa: F401
    AnthropicProvider,
    BaseLLMProvider,
    LLMClient,
    OllamaProvider,
    OpenAIProvider,
    create_daily_digest_prompt,
    create_summary_prompt,
    generate_with_retry,
    summarize_articles,
)
