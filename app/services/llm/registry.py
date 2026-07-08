"""LLM model registry — all models use Groq as the provider."""

from typing import (
    Any,
    Dict,
    List,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings
from app.core.logging import logger

_TOKEN_LIMIT: Dict[str, Any] = {"max_completion_tokens": settings.MAX_TOKENS}
_GROQ_KEY = SecretStr(settings.GROQ_API_KEY or "dummy_key")


class LLMRegistry:
    """Registry of available Groq LLM models with pre-initialized instances.

    All models use the Groq API via the OpenAI-compatible endpoint.
    The circular fallback in LLMService iterates through these in order.
    """

    LLMS: List[Dict[str, Any]] = [
        {
            "name": "llama-3.3-70b-versatile",
            "llm": ChatOpenAI(
                model="llama-3.3-70b-versatile",
                api_key=_GROQ_KEY,
                base_url=settings.GROQ_BASE_URL,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "llama-3.1-8b-instant",
            "llm": ChatOpenAI(
                model="llama-3.1-8b-instant",
                api_key=_GROQ_KEY,
                base_url=settings.GROQ_BASE_URL,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
        {
            "name": "mixtral-8x7b-32768",
            "llm": ChatOpenAI(
                model="mixtral-8x7b-32768",
                api_key=_GROQ_KEY,
                base_url=settings.GROQ_BASE_URL,
                model_kwargs=_TOKEN_LIMIT,
            ),
        },
    ]

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        Args:
            model_name: Name of the model to retrieve.
            **kwargs: Optional overrides for a fresh instance.

        Returns:
            BaseChatModel instance.

        Raises:
            ValueError: If model_name is not found in LLMS.
        """
        model_entry = next((e for e in cls.LLMS if e["name"] == model_name), None)

        if not model_entry:
            available = ", ".join(e["name"] for e in cls.LLMS)
            raise ValueError(f"model '{model_name}' not found in registry. available models: {available}")

        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return ChatOpenAI(model=model_name, api_key=_GROQ_KEY, base_url=settings.GROQ_BASE_URL, **kwargs)

        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Return all registered model names in order."""
        return [e["name"] for e in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Return the model entry at a specific index, wrapping if out of range."""
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]
