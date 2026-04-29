"""Health check endpoint — GET /health."""
from importlib.metadata import version

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Renvoie le statut de l'API et sa version."""
    try:
        app_version = version("stonks-backend")
    except Exception:
        app_version = "0.1.0"
    return {"status": "ok", "version": app_version}
