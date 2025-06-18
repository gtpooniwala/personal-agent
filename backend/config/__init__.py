from pydantic_settings import BaseSettings
from typing import Optional
import os
import yaml


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

# Load LLM config as a separate global variable (not as a field on settings)
LLM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "llm_config.yaml")

def load_llm_config():
    if os.path.exists(LLM_CONFIG_PATH):
        with open(LLM_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    return {}

llm_config = load_llm_config()

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
