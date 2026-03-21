"""LLM provider factory with multi-provider fallback support."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings

logger = logging.getLogger(__name__)


def get_groq_llm(**kwargs: Any) -> BaseChatModel:
    """Get Groq LLM (free tier - Llama 3.3 70B)."""
    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model_name,
        temperature=kwargs.get("temperature", 0),
        max_tokens=kwargs.get("max_tokens", 4096),
    )


def get_google_llm(**kwargs: Any) -> BaseChatModel:
    """Get Google Gemini LLM (free tier)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        google_api_key=settings.google_api_key,
        model=settings.google_model_name,
        temperature=kwargs.get("temperature", 0),
        max_output_tokens=kwargs.get("max_tokens", 4096),
    )


def get_openai_compatible_llm(**kwargs: Any) -> BaseChatModel:
    """Get OpenAI-compatible LLM (Ollama, vLLM, etc.)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=settings.openai_api_base,
        api_key=settings.openai_api_key,
        model=settings.openai_model_name,
        temperature=kwargs.get("temperature", 0),
        max_tokens=kwargs.get("max_tokens", 4096),
    )


_PROVIDERS = {
    "groq": get_groq_llm,
    "google": get_google_llm,
    "openai": get_openai_compatible_llm,
}

_FALLBACK_ORDER = ["groq", "google", "openai"]


def get_llm(provider: str | None = None, **kwargs: Any) -> BaseChatModel:
    """Get LLM instance with automatic fallback across providers.

    Tries the requested provider first, then falls back through
    the remaining providers in order.
    """
    primary = provider or settings.primary_model
    providers_to_try = [primary] + [p for p in _FALLBACK_ORDER if p != primary]

    last_error: Exception | None = None
    for p in providers_to_try:
        factory = _PROVIDERS.get(p)
        if factory is None:
            continue
        try:
            llm = factory(**kwargs)
            logger.info("Using LLM provider: %s", p)
            return llm
        except Exception as e:
            logger.warning("Provider %s failed: %s", p, e)
            last_error = e

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def invoke_llm_with_retry(llm: BaseChatModel, messages: list) -> Any:
    """Invoke LLM with exponential backoff retry."""
    return await llm.ainvoke(messages)
