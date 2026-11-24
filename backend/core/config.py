"""Application settings, loaded from environment variables / `.env`.

Settings are validated once at startup so a misconfigured deployment fails
fast with a clear message instead of erroring on the first user request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["groq", "azure", "openai"]
EmbeddingsProvider = Literal["none", "azure", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- LLM providers -------------------------------------------------------
    llm_provider: Provider = "groq"
    # Optional second provider used automatically if the primary one fails.
    llm_fallback_provider: Provider | None = None
    llm_temperature: float = 0.3
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_deployment_name: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None

    # --- Embeddings (only used for pages too large to send in full) ----------
    # "none" falls back to fast lexical (BM25) retrieval with no extra API calls.
    embeddings_provider: EmbeddingsProvider = "none"
    azure_embeddings_deployment: str | None = None
    openai_embeddings_model: str = "text-embedding-3-small"

    # --- Context strategy ----------------------------------------------------
    # Pages up to this many (estimated) tokens are sent to the model in full.
    # Raise this for providers with generous rate limits (e.g. Azure / paid Groq).
    max_context_tokens: int = Field(default=10_000, ge=1_000)
    chunk_size_chars: int = Field(default=1_500, ge=200)
    chunk_overlap_chars: int = Field(default=200, ge=0)
    max_map_concurrency: int = Field(default=4, ge=1)
    max_history_messages: int = Field(default=10, ge=0)

    # --- HTTP ------------------------------------------------------------------
    # Regex of allowed CORS origins. Default allows any Chrome extension; lock
    # this to your published extension ID in production.
    cors_allow_origin_regex: str = r"^chrome-extension://[a-z]{32}$|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    max_page_chars: int = Field(default=1_000_000, ge=1_000)

    # --- Generated files -------------------------------------------------------
    files_dir: str | None = None  # defaults to a temp directory
    file_ttl_seconds: int = Field(default=3_600, ge=60)

    @model_validator(mode="after")
    def _validate_provider_credentials(self) -> "Settings":
        for provider in filter(None, {self.llm_provider, self.llm_fallback_provider}):
            missing = self.missing_for(provider)
            if missing:
                raise ValueError(
                    f"LLM provider '{provider}' is selected but these settings are missing: "
                    + ", ".join(m.upper() for m in missing)
                )
        if self.llm_fallback_provider == self.llm_provider:
            raise ValueError("LLM_FALLBACK_PROVIDER must differ from LLM_PROVIDER")
        if self.embeddings_provider == "azure":
            missing = self.missing_for("azure", embeddings=True)
            if missing:
                raise ValueError("Azure embeddings need: " + ", ".join(m.upper() for m in missing))
        if self.embeddings_provider == "openai" and not self.openai_api_key:
            raise ValueError("OpenAI embeddings need: OPENAI_API_KEY")
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("CHUNK_OVERLAP_CHARS must be smaller than CHUNK_SIZE_CHARS")
        return self

    def missing_for(self, provider: str, embeddings: bool = False) -> list[str]:
        required = {
            "groq": ["groq_api_key"],
            "openai": ["openai_api_key"],
            "azure": ["azure_openai_api_key", "azure_openai_endpoint"]
            + (["azure_embeddings_deployment"] if embeddings else ["azure_deployment_name"]),
        }[provider]
        return [name for name in required if not getattr(self, name)]


@lru_cache
def get_settings() -> Settings:
    return Settings()
