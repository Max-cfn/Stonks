"""Client LLM unifié (OpenRouter via API OpenAI-compatible).

Doc OpenRouter : https://openrouter.ai/docs
DeepSeek V4 Pro : https://openrouter.ai/deepseek/deepseek-v4-pro

3 couches de résilience face aux erreurs upstream (429, 402, 5xx, timeouts) :

1. **Provider routing** : OpenRouter route DeepSeek V4 Pro vers 6 providers
   (DeepSeek officiel, GMICloud, AtlasCloud, SiliconFlow, Novita, Together).
   On force l'ordre via `provider.order` pour préférer DeepSeek officiel
   (le moins cher, 1M ctx). Mais maintenant on autorise OpenRouter à fallback
   sur les autres providers si DeepSeek officiel renvoie 402 (insufficient
   balance dans le bucket OpenRouter — fréquent quand pas de BYOK) ou 429.

2. **Retry exponentiel** : `max_retries` du client OpenAI, gère 429+5xx
   avec backoff + jitter.

3. **Fallback model** : `Runnable.with_fallbacks([flash])`. Si le modèle
   principal échoue après tous les retries (toute erreur), bascule sur
   DeepSeek V4 Flash (5x moins cher, plus dispo).
"""
from __future__ import annotations

from typing import Any

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from ..journal import log_event
from .config import OrchestratorSettings, get_settings


def _build_provider_routing(s: OrchestratorSettings) -> dict[str, Any]:
    """Construit le dict `provider` envoyé à OpenRouter dans extra_body.

    Doc : https://openrouter.ai/docs/features/provider-routing

    Champs supportés :
    - `order` : liste ordonnée de providers préférés
    - `ignore` : providers exclus
    - `allow_fallbacks` : si True, OpenRouter peut router ailleurs si
      les providers de `order` sont indispos (recommandé pour la résilience)
    - `require_parameters` : exige le support de tous les params (reasoning,
      tools…). Doit rester False : le client OpenAI envoie
      `max_completion_tokens` qu'aucun provider ne déclare formellement.
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
    """Construit un ChatOpenAI configuré pour OpenRouter.

    Le `reasoning_effort` et le `provider routing` sont passés via `extra_body`
    (paramètres OpenRouter spécifiques). Le client OpenAI gère le retry
    exponentiel + jitter sur 429 et 5xx (param `max_retries`).
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

    Configuration :
    - DeepSeek V4 Pro avec reasoning='high'
    - Provider routing : DeepSeek officiel préféré, mais fallback OpenRouter
      autorisé (gère le 402 "Insufficient Balance" du bucket OpenRouter)
    - max_retries=6 sur 429/5xx
    - Si Pro fail entièrement après retries → bascule auto sur V4 Flash via
      with_fallbacks (toute Exception déclenche)
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

    fallback = make_chat_model(
        model=s.openrouter_fallback_model,
        temperature=0.1,
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

    return primary.with_fallbacks(
        [fallback],
        exceptions_to_handle=(Exception,),
    )


def make_light_model() -> ChatOpenAI:
    """Modèle léger pour sous-tâches (DeepSeek V4 Flash par défaut)."""
    s = get_settings()
    return make_chat_model(model=s.openrouter_model_light, temperature=0.1)
