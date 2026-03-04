from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api import router
from backend.config import settings
import logging
import uvicorn

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Personal Agent API starting up...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database path: {settings.database_path}")
    
    yield
    
    # Shutdown
    logger.info("Personal Agent API shutting down...")

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
