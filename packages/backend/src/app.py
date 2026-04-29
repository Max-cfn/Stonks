"""FastAPI application factory."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    """Crée et configure l'application FastAPI."""
    app = FastAPI(
        title="Stonks API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    _register_routers(app)
    return app


def _register_routers(app: FastAPI) -> None:
    from src.api.health import router as health_router

    app.include_router(health_router)
