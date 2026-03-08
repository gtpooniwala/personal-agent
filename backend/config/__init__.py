import os
from typing import Optional

import yaml
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE_PATH = os.path.join(PROJECT_ROOT, ".env")


class Settings(BaseSettings):
    """Application settings with environment-based configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        case_sensitive=False,
        # Keep startup resilient when unrelated env vars are present.
        extra="ignore",
    )

    # LLM/provider settings
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGFUSE_ENABLED", "LANGFUSE_TRACING_ENABLED"),
    )
    langfuse_sample_rate: float = 1.0

    # Core application settings
    database_url: str = "postgresql+psycopg://personal_agent:personal_agent@127.0.0.1:5432/personal_agent"
    log_level: str = "INFO"
    debug: bool = False

    # Future settings with defaults for cloud deployment
    environment: str = "local"
    redis_url: Optional[str] = None
    jwt_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY"),
    )

    # API settings
    api_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("API_HOST", "HOST"),
    )
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("API_PORT", "PORT"),
    )
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    frontend_url: Optional[str] = "http://localhost:3000"

    # Optional integration settings
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    todoist_api_token: Optional[str] = None
    google_calendar_credentials: Optional[str] = None

    # Feature flags
    enable_internet_search: bool = True
    enable_document_qa: bool = True
    enable_gmail_integration: bool = True
    enable_calendar_integration: bool = False

    # Performance settings
    max_conversation_history: int = 50
    conversation_summary_threshold: int = 20
    runtime_orchestration_max_workers: int = Field(
        default=4,
        ge=1,
        validation_alias=AliasChoices(
            "RUNTIME_ORCHESTRATION_MAX_WORKERS",
        ),
    )

    # API keys for web search providers (optional)
    bing_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    google_cx: Optional[str] = None
    serpapi_key: Optional[str] = None


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

AGENT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent_config.yaml")


def load_agent_config():
    if os.path.exists(AGENT_CONFIG_PATH):
        with open(AGENT_CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    return {}


agent_config = load_agent_config()

# Ensure local data directory exists for uploads and local tool files.
os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
