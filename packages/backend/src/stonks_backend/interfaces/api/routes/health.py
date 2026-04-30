"""Health check endpoints — GET /health (liveness) + GET /ready (DB + Vault)."""
from importlib.metadata import version
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — renvoie le statut de l'API."""
    try:
        app_version = version("stonks-backend")
    except Exception:
        app_version = "0.1.0"
    return {"status": "ok", "version": app_version, "service": "stonks-backend"}


@router.get("/ready")
async def ready() -> dict[str, Any]:
    """Readiness probe — vérifie que DB + Vault sont accessibles.

    Cette sonde est appelée par Kubernetes/docker-compose pour savoir si le
    conteneur est prêt à recevoir du trafic.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # --- DB check ---
    try:
        from stonks_backend.infrastructure.database import engine

        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        all_ok = False

    # --- Vault check ---
    try:
        from stonks_backend.infrastructure.config import get_settings
        from stonks_backend.infrastructure.security.vault_client import VaultClient

        settings = get_settings()
        vault = VaultClient.from_settings(settings)
        await vault.health_check()
        checks["vault"] = "ok"
    except Exception as exc:
        checks["vault"] = f"error: {exc}"
        all_ok = False

    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }
