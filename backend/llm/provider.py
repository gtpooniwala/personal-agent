"""Provider-agnostic chat and embedding model factories."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
except Exception:  # pragma: no cover - optional dependency in some environments
    ChatGoogleGenerativeAI = None
    GoogleGenerativeAIEmbeddings = None

from backend.config import llm_config, settings

DEFAULT_PROVIDER = "gemini"
DEFAULT_CHAT_MODELS: Dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4.1-mini",
}
DEFAULT_EMBEDDING_MODELS: Dict[str, str] = {
    "gemini": "models/text-embedding-004",
    "openai": "text-embedding-3-small",
}


class MissingProviderKeyError(RuntimeError):
    """Raised when the selected LLM provider key is missing."""


class MissingModelDependencyError(RuntimeError):
    """Raised when the selected provider package is missing."""


def _config_default_provider() -> str:
    providers = llm_config.get("providers", {}) if isinstance(llm_config, dict) else {}
    configured = str(providers.get("default", DEFAULT_PROVIDER)).strip().lower()
    return configured if configured in {"gemini", "openai"} else DEFAULT_PROVIDER


def _resolve_model_name(tool_name: str, model_override: Optional[str] = None) -> str:
    if model_override:
        return model_override

    llms = llm_config.get("llms", {}) if isinstance(llm_config, dict) else {}
    configured = llms.get(tool_name) or llms.get("default")
    if configured == "default":
        configured = llms.get("default")

    if configured:
        return str(configured).strip()

    return DEFAULT_CHAT_MODELS[_config_default_provider()]


def _split_provider_model(model_name: str, fallback_provider: str) -> Tuple[str, str]:
    model = model_name.strip()
    lower = model.lower()

    if ":" in model:
        provider, actual = model.split(":", 1)
        provider = provider.strip().lower()
        if provider in {"gemini", "openai"}:
            return provider, actual.strip()

    if "/" in model:
        provider, actual = model.split("/", 1)
        provider = provider.strip().lower()
        if provider in {"gemini", "openai"}:
            return provider, actual.strip()

    if lower.startswith("gemini") or lower.startswith("models/"):
        return "gemini", model
    if lower.startswith("gpt-") or lower.startswith("o1") or lower.startswith("o3") or lower.startswith("o4"):
        return "openai", model

    return fallback_provider, model


def _missing_key_message(provider: str) -> str:
    if provider == "gemini":
        return (
            "Gemini API key is required for this request. "
            "Set GEMINI_API_KEY in your environment (for example in .env) and retry."
        )
    return (
        "OpenAI API key is required for this request. "
        "Set OPENAI_API_KEY in your environment (for example in .env) and retry."
    )


def create_chat_model(
    tool_name: str,
    *,
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
    model_override: Optional[str] = None,
):
    """Create a chat model for a given tool key using configured provider defaults."""
    provider_default = _config_default_provider()
    configured_model = _resolve_model_name(tool_name, model_override=model_override)
    provider, model_name = _split_provider_model(configured_model, provider_default)

    if provider == "gemini":
        if ChatGoogleGenerativeAI is None:
            raise MissingModelDependencyError(
                "Gemini provider selected but langchain-google-genai is not installed. "
                "Install backend/requirements.txt dependencies and retry."
            )
        if not settings.gemini_api_key:
            raise MissingProviderKeyError(_missing_key_message("gemini"))

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
            "google_api_key": settings.gemini_api_key,
        }
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    if provider == "openai":
        if not settings.openai_api_key:
            raise MissingProviderKeyError(_missing_key_message("openai"))

        kwargs = {
            "model": model_name,
            "temperature": temperature,
            "openai_api_key": settings.openai_api_key,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported provider: {provider}")


def create_embeddings_model():
    """Create embedding model from `llm_config.embeddings` defaults."""
    embeddings_cfg = llm_config.get("embeddings", {}) if isinstance(llm_config, dict) else {}
    provider = str(embeddings_cfg.get("provider", _config_default_provider())).strip().lower()
    model_name = str(
        embeddings_cfg.get("model") or DEFAULT_EMBEDDING_MODELS.get(provider, DEFAULT_EMBEDDING_MODELS["gemini"])
    ).strip()

    provider, model_name = _split_provider_model(model_name, provider)

    if provider == "gemini":
        if GoogleGenerativeAIEmbeddings is None:
            raise MissingModelDependencyError(
                "Gemini embeddings selected but langchain-google-genai is not installed. "
                "Install backend/requirements.txt dependencies and retry."
            )
        if not settings.gemini_api_key:
            raise MissingProviderKeyError(_missing_key_message("gemini"))
        return GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=settings.gemini_api_key)

    if provider == "openai":
        if not settings.openai_api_key:
            raise MissingProviderKeyError(_missing_key_message("openai"))
        return OpenAIEmbeddings(model=model_name, openai_api_key=settings.openai_api_key)

    raise ValueError(f"Unsupported embeddings provider: {provider}")


def extract_text(response: Any) -> str:
    """Extract plain text content from a LangChain response object."""
    if hasattr(response, "content"):
        return str(response.content)
    return str(response)


async def predict_text(model: Any, prompt: str) -> str:
    """Provider-agnostic async text generation helper."""
    response = await model.ainvoke(prompt)
    return extract_text(response)
