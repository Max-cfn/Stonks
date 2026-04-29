"""Client LLM unifié (OpenRouter via API OpenAI-compatible).

Documentation OpenRouter : https://openrouter.ai/docs
DeepSeek V4 Pro : https://openrouter.ai/deepseek/deepseek-v4-pro

Tous les appels sont loggés dans execution_log.txt et les coûts sont
trackés contre `orchestrator_token_budget`.
"""
from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from .config import get_settings


# Tarifs OpenRouter pour DeepSeek V4 (au 28 avril 2026, vérifier régulièrement).
_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    # model_slug : (input_price, output_price)
    "deepseek/deepseek-v4-pro": (0.435, 0.870),
    "deepseek/deepseek-v4-flash": (0.140, 0.280),
    "deepseek/deepseek-v3.2-speciale": (0.400, 1.200),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estime le coût d'un appel en USD."""
    if model not in _PRICING_USD_PER_1M_TOKENS:
        return 0.0
    p_in, p_out = _PRICING_USD_PER_1M_TOKENS[model]
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000


def make_chat_model(
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
) -> ChatOpenAI:
    """Construit un client ChatOpenAI configuré pour OpenRouter.

    OpenRouter expose une API OpenAI-compatible sur https://openrouter.ai/api/v1.
    Le `reasoning_effort` est passé via `extra_body` (paramètre OpenRouter).
    """
    s = get_settings()

    body: dict[str, Any] = {"reasoning": {"effort": s.openrouter_reasoning_effort}}
    if extra_body:
        body.update(extra_body)

    return ChatOpenAI(
        model=model or s.openrouter_model,
        api_key=s.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature if temperature is not None else s.openrouter_temperature,
        max_tokens=max_tokens or s.openrouter_max_tokens,
        default_headers={
            "HTTP-Referer": s.openrouter_http_referer,
            "X-Title": s.openrouter_x_title,
        },
        model_kwargs={"extra_body": body},
    )


def make_orchestrator_model() -> ChatOpenAI:
    """Modèle principal (DeepSeek V4 Pro par défaut, reasoning high)."""
    return make_chat_model()


def make_light_model() -> ChatOpenAI:
    """Modèle léger pour sous-tâches (DeepSeek V4 Flash par défaut)."""
    s = get_settings()
    return make_chat_model(model=s.openrouter_model_light, temperature=0.1)
