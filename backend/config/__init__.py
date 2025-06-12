from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment-based configuration."""
    
    # MVP settings
    openai_api_key: str
    database_path: str = "data/agent.db"
    log_level: str = "INFO"
    
    # Future settings with defaults for cloud deployment
    environment: str = "local"
    redis_url: Optional[str] = None
    database_url: Optional[str] = None
    jwt_secret: Optional[str] = None
    
    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    # API keys for web search providers (optional)
    bing_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    google_cx: Optional[str] = None
    serpapi_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
