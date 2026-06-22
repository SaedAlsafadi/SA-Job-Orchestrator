"""FastAPI application factory and lifespan management."""

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.router import v1_router
from app.api.websocket.endpoint import router as ws_router
from app.config.constants import API_V1_PREFIX, APP_TITLE, APP_VERSION
from app.config.settings import Environment, get_settings
from app.core.exceptions import AutoApplyError, RecordNotFoundError
from app.db import tenant as _tenant_filter  # noqa: F401  # registers do_orm_execute
from app.db.arq import close_arq_pool, init_arq_pool
from app.db.redis import close_redis_pool, init_redis_pool
from app.db.session import engine
from app.observability.logging import configure_logging

logger = structlog.get_logger(__name__)
settings = get_settings()


def metrics_authorized(cfg: object, authorization: str | None) -> bool:
    """Open in non-production; in production require a matching bearer token (fail-closed)."""
    if cfg.environment != Environment.PRODUCTION:  # type: ignore[attr-defined]
        return True
    token = cfg.metrics_token.get_secret_value()  # type: ignore[attr-defined]
    # Constant-time compare — the token is the only thing guarding /metrics in prod.
    return bool(token) and hmac.compare_digest(authorization or "", f"Bearer {token}")


def validate_production_settings(cfg: object) -> None:
    """Fail-closed at startup if production is misconfigured with insecure defaults.

    Mirrors the secrets-factory guard so a forgotten/placeholder secret can't silently ship
    (a default JWT key = trivial token forgery; a '*' credentialed CORS = any-origin access).
    """
    if cfg.environment != Environment.PRODUCTION:  # type: ignore[attr-defined]
        return
    problems: list[str] = []
    secret = cfg.auth.secret_key.get_secret_value()  # type: ignore[attr-defined]
    if secret in ("", "dev-insecure-change-me") or len(secret) < 16:
        problems.append("AUTH__SECRET_KEY must be a strong, non-default secret")
    if "*" in cfg.cors_origins:  # type: ignore[attr-defined]
        problems.append("CORS_ORIGINS must not contain '*' with credentialed CORS")
    storage = cfg.storage  # type: ignore[attr-defined]
    if storage.provider == "local" and storage.url_signing_secret.get_secret_value() == (
        "dev-insecure-change-me"
    ):
        problems.append("STORAGE__URL_SIGNING_SECRET must be set for local storage")
    if problems:
        raise RuntimeError("Invalid production configuration: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    # Startup
    configure_logging(settings.log_level, settings.environment.value)
    validate_production_settings(settings)  # fail fast on insecure prod config
    logger.info(
        "app_starting",
        version=APP_VERSION,
        environment=settings.environment.value,
    )

    # Schema is owned by Alembic — run `alembic upgrade head` before starting.
    logger.info("database_ready")

    await init_redis_pool(settings.redis_url)
    await init_arq_pool()

    yield

    # Shutdown
    await close_arq_pool()
    await close_redis_pool()
    await engine.dispose()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != Environment.PRODUCTION else None,
        redoc_url="/redoc" if settings.environment != Environment.PRODUCTION else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics: open in non-prod; in production require a bearer token
    # (fail-closed if METRICS_TOKEN is unset) so it isn't a public data leak.
    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if not metrics_authorized(settings, request.headers.get("authorization")):
            return Response(status_code=401)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Exception handlers
    @app.exception_handler(AutoApplyError)
    async def autoapply_error_handler(
        request: Request,
        exc: AutoApplyError,
    ) -> JSONResponse:
        """Convert domain exceptions to JSON error responses."""
        status_code = 500
        if isinstance(exc, RecordNotFoundError):
            status_code = 404
        elif exc.code.endswith("AUTH_ERROR"):
            status_code = 401
        elif exc.code.endswith("FORBIDDEN_ERROR"):
            status_code = 403
        elif exc.code.endswith("RATE_LIMIT"):
            status_code = 429
        elif exc.code.endswith("INTEGRITY_ERROR"):
            status_code = 409

        logger.warning(
            "domain_error",
            error_code=exc.code,
            message=exc.message,
            path=str(request.url),
        )

        return JSONResponse(
            status_code=status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    # Routes
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    app.include_router(ws_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "version": APP_VERSION}

    return app


app = create_app()
