"""FastAPI application factory."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from stonks_backend.interfaces.api.routes.auth import router as auth_router
from stonks_backend.interfaces.api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Crée et configure l'application FastAPI (ports & adapters)."""
    app = FastAPI(
        title="Stonks API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Rate limit handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    _register_routers(app)
    _register_middleware(app)
    return app


def _register_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)


def _register_middleware(app: FastAPI) -> None:
    """Register application middleware."""

    # Request-ID middleware — propagated via X-Request-ID header
    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
