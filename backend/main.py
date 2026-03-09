import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure warnings early to suppress known upstream issues
from backend.config.warnings_shim import configure_warnings

configure_warnings()

from backend.api.routes import router as versioned_router
from backend.api.runtime_routes import runtime_router
from backend.api.scheduler_routes import scheduler_router
from backend.config import settings
from backend.observability import configure_logging, langfuse_manager, push_context
from sqlalchemy.engine.url import make_url

# Configure structured logging
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


def _safe_database_url() -> str:
    """Render configured database URL without exposing credentials."""
    try:
        return make_url(settings.database_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid DATABASE_URL>"


def _is_local_environment() -> bool:
    return (settings.environment or "").strip().lower() == "local"


def _configured_agent_api_key() -> str | None:
    if not settings.agent_api_key:
        return None
    token = settings.agent_api_key.strip()
    return token or None


def _auth_is_enabled() -> bool:
    return _configured_agent_api_key() is not None


def _apply_cors_headers(request, response) -> None:
    origin = request.headers.get("Origin")
    if not origin:
        return

    if "*" in allow_origins:
        if allow_credentials:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        return

    if origin not in allow_origins:
        return

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    if allow_credentials:
        response.headers["Access-Control-Allow-Credentials"] = "true"


def _is_authorized_request(request) -> bool:
    expected_token = _configured_agent_api_key()
    if expected_token is None:
        return True

    authorization = request.headers.get("Authorization")
    if not authorization:
        return False

    scheme, _, provided_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not provided_token:
        return False

    return secrets.compare_digest(provided_token, expected_token)


def _authorization_header_present(request) -> bool:
    return bool(request.headers.get("Authorization"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Personal Agent API starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database URL: {_safe_database_url()}")
    if not _is_local_environment() and not _auth_is_enabled():
        raise RuntimeError(
            "AGENT_API_KEY must be configured when ENVIRONMENT is not local."
        )
    if not settings.gemini_api_key and not settings.openai_api_key:
        raise RuntimeError(
            "Either GEMINI_API_KEY or OPENAI_API_KEY must be configured."
        )
    langfuse_manager.initialize()

    from backend.api.state import (
        conversation_maintenance_service,
        heartbeat_service,
        runtime_service,
        scheduler_service,
    )

    await heartbeat_service.start()
    await conversation_maintenance_service.start()
    await scheduler_service.start()

    yield

    # Shutdown
    logger.info("Personal Agent API shutting down...")
    await scheduler_service.stop()
    await conversation_maintenance_service.stop()
    await heartbeat_service.stop()
    await runtime_service.shutdown()
    langfuse_manager.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Personal Agent API",
    description="LangChain-powered personal assistant API",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend
raw_origins = [
    origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()
]
allow_origins = raw_origins or ["*"]
allow_credentials = allow_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request, call_next):
    """Attach request-scoped context and standardized request logs."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = perf_counter()

    with push_context(request_id=request_id, route=request.url.path):
        if request.method != "OPTIONS" and _auth_is_enabled() and not _is_authorized_request(request):
            latency_ms = int((perf_counter() - start) * 1000)
            response = JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "Bearer"},
            )
            _apply_cors_headers(request, response)
            response.headers["X-Request-ID"] = request_id
            logger.warning(
                "Request unauthorized",
                extra={
                    "event": "http.request.unauthorized",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "auth_header_present": _authorization_header_present(request),
                },
            )
        else:
            try:
                response = await call_next(request)
            except Exception:
                latency_ms = int((perf_counter() - start) * 1000)
                logger.exception(
                    "Request failed",
                    extra={
                        "event": "http.request.failed",
                        "method": request.method,
                        "path": request.url.path,
                        "latency_ms": latency_ms,
                    },
                )
                raise

        latency_ms = int((perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "Request completed",
            extra={
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response


# Include API routes
app.include_router(versioned_router, prefix="/api/v1")
app.include_router(runtime_router)
app.include_router(scheduler_router)

# Serve static files (for serving the frontend if needed)
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True if settings.environment == "local" else False,
        log_level=settings.log_level.lower(),
    )
