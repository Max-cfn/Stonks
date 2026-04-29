"""Client LLM unifié (OpenRouter via API OpenAI-compatible).

Documentation OpenRouter : https://openrouter.ai/docs
DeepSeek V4 Pro : https://openrouter.ai/deepseek/deepseek-v4-pro

Ce module ajoute 3 couches de résilience face aux rate limits / 5xx upstream :

1. **Provider routing** : OpenRouter route DeepSeek V4 Pro vers 6 providers
   (DeepSeek officiel, GMICloud, AtlasCloud, SiliconFlow, Novita, Together).
   On force l'ordre de préférence via `provider.order` pour éviter Together
   (le plus cher : $2.10/M in vs $0.435 chez DeepSeek officiel) et tomber
   sur les providers les moins saturés.

2. **Retry exponentiel** : `max_retries` du client OpenAI (gère 429 + 5xx).
   Backoff avec jitter par défaut.

3. **Fallback model** : via `Runnable.with_fallbacks([flash])`. Si Pro est
   indisponible même après tous les retries, le graph bascule
   automatiquement sur DeepSeek V4 Flash (5× moins cher, plus dispo) sans
   perdre la conversation.

Tous les appels sont loggés dans execution_log.txt et les coûts sont
trackés contre `orchestrator_token_budget`.
"""
from __future__ import annotations

from typing import Any

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from ..journal import log_event
from .config import OrchestratorSettings, get_settings


# Tarifs OpenRouter pour DeepSeek V4 (au 28 avril 2026, vérifier régulièrement).
# Source : https://openrouter.ai/api/v1/models/<slug>/endpoints
# Note : DeepSeek officiel est le provider le moins cher pour ces modèles.
_PRICING_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    # model_slug : (input_price, output_price) chez le provider le moins cher
    "deepseek/deepseek-v4-pro": (0.435, 0.870),
    "deepseek/deepseek-v4-flash": (0.140, 0.280),
    "deepseek/deepseek-v3.2-speciale": (0.400, 1.200),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estime le coût d'un appel en USD (au prix du provider le moins cher)."""
    if model not in _PRICING_USD_PER_1M_TOKENS:
        return 0.0
    p_in, p_out = _PRICING_USD_PER_1M_TOKENS[model]
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000


def _build_provider_routing(s: OrchestratorSettings) -> dict[str, Any]:
    """Construit le dict `provider` envoyé à OpenRouter dans extra_body.

    Doc : https://openrouter.ai/docs/features/provider-routing

    Champs supportés :
    - `order` : liste ordonnée de providers à essayer en premier
    - `ignore` : providers à totalement exclure
    - `allow_fallbacks` : si True, OpenRouter peut router vers d'autres
      providers que ceux de `order` si les premiers sont indispos
    - `require_parameters` : exige que le provider supporte les params
      demandés (reasoning, tool_calling, etc.)
    """
    routing: dict[str, Any] = {
        "allow_fallbacks": s.openrouter_allow_fallbacks,
        "require_parameters": s.openrouter_provider_require_parameters,
    }
    if s.provider_order_list:
        routing["order"] = s.provider_order_list
    if s.provider_ignore_list:
        routing["ignore"] = s.provider_ignore_list
    return routing


def make_chat_model(
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
    enable_provider_routing: bool = True,
) -> ChatOpenAI:
    """Construit un client ChatOpenAI configuré pour OpenRouter.

    OpenRouter expose une API OpenAI-compatible sur https://openrouter.ai/api/v1.
    Le `reasoning_effort` et le `provider routing` sont passés via `extra_body`
    (paramètres OpenRouter, pas OpenAI standard).

    Le client OpenAI gère automatiquement le retry sur 429 et 5xx avec backoff
    exponentiel + jitter (paramètre `max_retries`).
    """
    s = get_settings()

    body: dict[str, Any] = {"reasoning": {"effort": s.openrouter_reasoning_effort}}
    if enable_provider_routing:
        body["provider"] = _build_provider_routing(s)
    if extra_body:
        body.update(extra_body)

    return ChatOpenAI(
        model=model or s.openrouter_model,
        api_key=s.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature if temperature is not None else s.openrouter_temperature,
        max_tokens=max_tokens or s.openrouter_max_tokens,
        max_retries=s.openrouter_max_retries,
        timeout=s.openrouter_request_timeout_s,
        default_headers={
            "HTTP-Referer": s.openrouter_http_referer,
            "X-Title": s.openrouter_x_title,
        },
        extra_body=body,
    )


def make_orchestrator_model() -> Runnable:
    """Modèle principal pour l'orchestrateur.

    Configuration appliquée :
    - DeepSeek V4 Pro avec reasoning='high' (configurable via .env)
    - Provider routing : DeepSeek officiel en 1er, Together exclu par défaut
    - max_retries=6 sur 429/5xx avec backoff exponentiel
    - Fallback automatique sur DeepSeek V4 Flash si Pro indispo après retries
      (activable/désactivable via OPENROUTER_ENABLE_MODEL_FALLBACK)

    Returns:
        Un Runnable LangChain (compatible avec create_react_agent).
    """
    s = get_settings()
    primary = make_chat_model()

    if not s.openrouter_enable_model_fallback:
        log_event(
            agent="orchestrator",
            phase="bootstrap",
            action="llm_configured",
            output_summary=f"primary={s.openrouter_model} no_fallback "
            f"providers_order={s.provider_order_list} "
            f"providers_ignore={s.provider_ignore_list} max_retries={s.openrouter_max_retries}",
        )
        return primary

    # Fallback sur le light model (V4 Flash) si Pro est complètement KO
    fallback = make_chat_model(
        model=s.openrouter_fallback_model,
        temperature=0.1,  # plus déterministe pour le fallback
    )

    log_event(
        agent="orchestrator",
        phase="bootstrap",
        action="llm_configured",
        output_summary=(
            f"primary={s.openrouter_model} fallback={s.openrouter_fallback_model} "
            f"providers_order={s.provider_order_list} "
            f"providers_ignore={s.provider_ignore_list} max_retries={s.openrouter_max_retries}"
        ),
    )

    # with_fallbacks : si primary lève une exception (après ses retries internes),
    # bascule automatiquement sur fallback. La conversation continue sans interruption.
    return primary.with_fallbacks(
        [fallback],
        # Tous les types d'erreurs où on bascule (429, timeout, 5xx, etc.)
        # On laisse en None = on bascule sur toute Exception, ce qui couvre
        # RateLimitError, APITimeoutError, APIError, InternalServerError…
        exceptions_to_handle=(Exception,),
    )


def make_light_model() -> ChatOpenAI:
    """Modèle léger pour sous-tâches (DeepSeek V4 Flash par défaut).

    Pas de fallback : si Flash est down, on remonte l'erreur (le subagent
    décidera s'il escalade à l'orchestrateur ou retry plus tard).
    """
    s = get_settings()
    return make_chat_model(model=s.openrouter_model_light, temperature=0.1)
