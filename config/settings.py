from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Reads every field from environment variables (case-insensitive).
    Falls back to the default value if the variable is not set.
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # load from .env in project root
        env_file_encoding="utf-8",
        case_sensitive=False,      # GROQ_API_KEY == groq_api_key
        extra="ignore",            # ignore unknown env vars silently
    )

    # ── Groq LLM ──────────────────────────────────────────────────────────────
    groq_api_key: str = Field(..., description="Groq API key (required)")
    groq_model: str = Field(
        default="llama-3.1-8b-instant",
        description="Groq model identifier",
    )

    # ── Tavily Search ─────────────────────────────────────────────────────────
    tavily_api_key: str = Field(..., description="Tavily API key (required)")
    tavily_max_results: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max search results per sub-question",
    )

    # ── LangSmith Observability ───────────────────────────────────────────────
    langchain_tracing_v2: bool = Field(
        default=True,
        description="Enable LangSmith tracing",
    )
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com",
    )
    langchain_api_key: str = Field(
        default="",
        description="LangSmith API key (optional — tracing disabled if empty)",
    )
    langchain_project: str = Field(
        default="research-agent",
        description="LangSmith project name",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_cache_ttl: int = Field(
        default=3600,
        ge=60,
        description="Cache TTL in seconds (minimum 60)",
    )

    # ── Agent Behaviour ───────────────────────────────────────────────────────
    max_critic_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Max Critic → Researcher feedback loops",
    )

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_reload: bool = Field(
        default=False,
        description="Uvicorn auto-reload (dev only)",
    )

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("groq_api_key")
    @classmethod
    def groq_key_must_not_be_placeholder(cls, v: str) -> str:
        if v.startswith("gsk_your"):
            raise ValueError(
                "GROQ_API_KEY is still set to the placeholder value. "
                "Get a real key at https://console.groq.com/keys"
            )
        return v

    @field_validator("tavily_api_key")
    @classmethod
    def tavily_key_must_not_be_placeholder(cls, v: str) -> str:
        if v.startswith("tvly-your"):
            raise ValueError(
                "TAVILY_API_KEY is still set to the placeholder value. "
                "Get a real key at https://app.tavily.com/home"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached singleton Settings instance.

    Using @lru_cache means the .env file is read exactly once per process,
    even if get_settings() is called from many modules.
    """
    return Settings()


# ── Convenience singleton ─────────────────────────────────────────────────────
# Most modules can simply do:  from config.settings import settings
settings: Settings = get_settings()
