from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api import router
from backend.config import settings
from backend.observability import configure_logging, langfuse_manager, push_context
import logging
import uvicorn
from time import perf_counter
import uuid
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Personal Agent API starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database URL: {_safe_database_url()}")
    if not settings.gemini_api_key:
        logger.warning(
            "GEMINI_API_KEY is not configured; Gemini-backed requests may fail at runtime."
        )
    langfuse_manager.initialize()
    
    yield
    
    # Shutdown
    logger.info("Personal Agent API shutting down...")
    langfuse_manager.shutdown()

# Create FastAPI app
app = FastAPI(
    title="Personal Agent API",
    description="LangChain-powered personal assistant API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend
raw_origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
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
app.include_router(router, prefix="/api/v1")

# Serve static files (for serving the frontend if needed)
# app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True if settings.environment == "local" else False,
        log_level=settings.log_level.lower()
    )
