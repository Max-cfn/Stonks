"""Configuration centralisée via Pydantic Settings.

Toutes les variables sont lues depuis l'environnement, avec fallback sur le
.env du repo (chargé via python-dotenv). Cf. /opt/stonks/.env.example pour la
liste exhaustive.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_repo_root() -> Path:
    """Trouve la racine du monorepo (où vivent .env, Taskfile.yml, package.json).

    Stratégie :
    1. Si STONKS_REPO_ROOT est défini, l'utiliser.
    2. Sinon, remonter depuis ce fichier jusqu'à trouver un marqueur
       (Taskfile.yml + package.json + agents_core/).
    3. Fallback : 5 niveaux au-dessus (agents_core/src/stonks_core/orchestrator/config.py
       → /opt/stonks/).
    """
    env_root = os.environ.get("STONKS_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    here = Path(__file__).resolve()
    markers = ("Taskfile.yml", "package.json", "agents_core")
    for parent in here.parents:
        if all((parent / m).exists() for m in markers):
            return parent
    # Fallback explicite
    return here.parents[4]


REPO_ROOT = _detect_repo_root()


class OrchestratorSettings(BaseSettings):
    """Settings de l'orchestrateur principal."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── LLM ──────────────────────────────────────────────────────────
    openrouter_api_key: SecretStr = Field(..., description="Clé OpenRouter")
    openrouter_model: str = Field(default="deepseek/deepseek-v4-pro")
    openrouter_model_light: str = Field(default="deepseek/deepseek-v4-flash")
    openrouter_reasoning_effort: str = Field(default="high")
    openrouter_temperature: float = Field(default=0.2)
    openrouter_max_tokens: int = Field(default=32_000)
    openrouter_http_referer: str = Field(default="https://github.com/Max-cfn/Stonks")
    openrouter_x_title: str = Field(default="Stonks-Orchestrator")

    # ─── Repository ───────────────────────────────────────────────────
    target_github_repo: str = Field(default="Max-cfn/Stonks")
    github_default_branch: str = Field(default="main")
    github_token: SecretStr | None = Field(default=None)
    reference_repo_picsou: str = Field(default="Zoeille/picsou-finance")

    # ─── Runtime ──────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    execution_log_path: Path = Field(default=REPO_ROOT / "execution_log.txt")
    orchestrator_token_budget: int = Field(default=10_000_000)
    require_human_confirmation: bool = Field(default=True)
    max_autonomous_iterations: int = Field(default=200)

    # ─── UI ───────────────────────────────────────────────────────────
    streamlit_server_port: int = Field(default=8501)
    streamlit_server_address: str = Field(default="0.0.0.0")

    # ─── Redis ────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ─── GitNexus ─────────────────────────────────────────────────────
    gitnexus_backend_url: str = Field(default="http://localhost:4747")

    # ─── Sandbox ──────────────────────────────────────────────────────
    @property
    def repo_root(self) -> Path:
        """Racine du monorepo (toutes les opérations file/shell sont sandboxées ici)."""
        return REPO_ROOT


@lru_cache(maxsize=1)
def get_settings() -> OrchestratorSettings:
    """Retourne le singleton settings (cached)."""
    return OrchestratorSettings()  # type: ignore[call-arg]
