"""Application configuration management.

Handles environment-specific configuration loading and parsing.
Supports a DEMO_MODE flag to restrict expensive operations on the hosted demo.
"""

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def get_environment() -> Environment:
    """Get the current environment from APP_ENV."""
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


def load_env_file():
    """Load environment-specific .env file."""
    env = get_environment()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    env_files = [
        os.path.join(base_dir, f".env.{env.value}.local"),
        os.path.join(base_dir, f".env.{env.value}"),
        os.path.join(base_dir, ".env.local"),
        os.path.join(base_dir, ".env"),
    ]

    for env_file in env_files:
        if os.path.isfile(env_file):
            load_dotenv(dotenv_path=env_file)
            return env_file

    return None


ENV_FILE = load_env_file()


def parse_list_from_env(env_key, default=None):
    """Parse a comma-separated list from an environment variable."""
    value = os.getenv(env_key)
    if not value:
        return default or []

    value = value.strip("\"'")
    if "," not in value:
        return [value]
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        """Initialize settings from environment variables with sensible defaults."""
        self.ENVIRONMENT = get_environment()

        # Application
        self.PROJECT_NAME = os.getenv("PROJECT_NAME", "Repository Intelligence Platform")
        self.VERSION = os.getenv("VERSION", "1.0.0")
        self.DESCRIPTION = os.getenv(
            "DESCRIPTION", "AI-powered repository analysis with semantic search, PR review, and documentation"
        )
        self.API_V1_STR = os.getenv("API_V1_STR", "/api/v1")
        self.DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t", "yes")

        # CORS
        self.ALLOWED_ORIGINS = parse_list_from_env("ALLOWED_ORIGINS", ["*"])

        # Langfuse (optional observability)
        self.LANGFUSE_TRACING_ENABLED = os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() in (
            "true",
            "1",
        )
        self.LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        # LLM — Groq is the primary (and only) provider
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
        self.GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile")
        self.DEFAULT_LLM_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))
        self.MAX_LLM_CALL_RETRIES = int(os.getenv("MAX_LLM_CALL_RETRIES", "3"))
        self.LLM_TOTAL_TIMEOUT = int(os.getenv("LLM_TOTAL_TIMEOUT", "60"))
        self.SESSION_NAMING_ENABLED = os.getenv("SESSION_NAMING_ENABLED", "true").lower() == "true"

        # Embeddings
        self.HF_TOKEN = os.getenv("HF_TOKEN", "")
        self.LONG_TERM_MEMORY_EMBEDDER_MODEL = os.getenv("LONG_TERM_MEMORY_EMBEDDER_MODEL", "BAAI/bge-small-en-v1.5")

        # Logging
        self.LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "json")

        # Profiling (DEBUG only)
        self.PROFILING_DIR = Path(os.getenv("PROFILING_DIR", "/tmp/fastapi_profiles"))
        self.PROFILING_THRESHOLD_SECONDS = float(os.getenv("PROFILING_THRESHOLD_SECONDS", "2.0"))

        # PostgreSQL — parse DATABASE_URL first if provided (Render / Heroku style)
        _db_url = os.getenv("DATABASE_URL", "")
        if _db_url:
            # Normalize postgres:// -> postgresql://
            if _db_url.startswith("postgres://"):
                _db_url = _db_url.replace("postgres://", "postgresql://", 1)
            from urllib.parse import urlparse
            _parsed = urlparse(_db_url)
            self.POSTGRES_HOST = _parsed.hostname or "localhost"
            self.POSTGRES_PORT = _parsed.port or 5432
            self.POSTGRES_DB = (_parsed.path or "/repo_intel_db").lstrip("/")
            self.POSTGRES_USER = _parsed.username or "postgres"
            self.POSTGRES_PASSWORD = _parsed.password or "postgres"
            self.DATABASE_URL = _db_url
        else:
            self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
            self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
            self.POSTGRES_DB = os.getenv("POSTGRES_DB", "repo_intel_db")
            self.POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
            self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        self.POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "5"))
        self.POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "2"))
        self.CHECKPOINT_TABLES = ["checkpoint_blobs", "checkpoint_writes", "checkpoints"]

        # GitHub MCP
        self.GITHUB_PERSONAL_ACCESS_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")

        self.apply_environment_settings()

    def apply_environment_settings(self):
        """Apply environment-specific overrides when not explicitly set."""
        env_settings = {
            Environment.DEVELOPMENT: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
            },
            Environment.STAGING: {
                "DEBUG": False,
                "LOG_LEVEL": "INFO",
            },
            Environment.PRODUCTION: {
                "DEBUG": False,
                "LOG_LEVEL": "WARNING",
            },
            Environment.TEST: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
            },
        }

        current_env_settings = env_settings.get(self.ENVIRONMENT, {})
        for key, value in current_env_settings.items():
            if key.upper() not in os.environ:
                setattr(self, key, value)


settings = Settings()
