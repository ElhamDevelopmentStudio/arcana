from functools import lru_cache
import json
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://postgres@localhost:5432/nipe_poc",
        alias="DATABASE_URL",
    )
    llm_provider_priority_order: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["openrouter", "siliconflow", "groq"],
        alias="LLM_PROVIDER_PRIORITY_ORDER",
    )
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_api_keys: Annotated[list[str] | None, NoDecode] = Field(
        default=None,
        alias="OPENROUTER_API_KEYS",
    )
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    siliconflow_api_key: str | None = Field(default=None, alias="SILICONFLOW_API_KEY")
    siliconflow_api_keys: Annotated[list[str] | None, NoDecode] = Field(
        default=None,
        alias="SILICONFLOW_API_KEYS",
    )
    siliconflow_model: str = Field(default="deepseek-ai/DeepSeek-V3", alias="SILICONFLOW_MODEL")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1", alias="SILICONFLOW_BASE_URL")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_api_keys: Annotated[list[str] | None, NoDecode] = Field(
        default=None,
        alias="GROQ_API_KEYS",
    )
    data_encryption_key: str | None = Field(default=None, alias="DATA_ENCRYPTION_KEY")
    saas_mode: bool = Field(default=False, alias="SAAS_MODE")

    @field_validator(
        "openrouter_api_keys",
        "siliconflow_api_keys",
        "groq_api_keys",
        mode="before",
    )
    @classmethod
    def _coerce_api_key_list(cls, value: Any) -> Any:
        if value is None or value == "":
            return None

        if isinstance(value, list):
            keys = [str(item).strip() for item in value]
            return [key for key in keys if key]

        if isinstance(value, tuple):
            keys = [str(item).strip() for item in value]
            return [key for key in keys if key]

        text = str(value).strip()
        if not text:
            return None

        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                keys = [str(item).strip() for item in parsed]
                return [key for key in keys if key]

        keys = [entry.strip() for entry in text.split(",")]
        return [entry for entry in keys if entry]

    @field_validator("llm_provider_priority_order", mode="before")
    @classmethod
    def _coerce_provider_priority_order(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["openrouter", "siliconflow", "groq"]

        if isinstance(value, (list, tuple)):
            parsed = [str(item).strip().lower() for item in value if str(item).strip()]
            return parsed or ["openrouter", "siliconflow", "groq"]

        text = str(value).strip()
        if not text:
            return ["openrouter", "siliconflow", "groq"]

        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                normalized = [str(item).strip().lower() for item in parsed if str(item).strip()]
                return normalized or ["openrouter", "siliconflow", "groq"]
            return ["openrouter", "siliconflow", "groq"]

        normalized = [item.strip().lower() for item in text.split(",") if item.strip()]
        return normalized or ["openrouter", "siliconflow", "groq"]
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    enable_epub_ingestion: bool = Field(default=False, alias="ENABLE_EPUB_INGESTION")
    normalize_quote_style: Literal["straight", "curly"] = Field(default="straight", alias="NORMALIZE_QUOTE_STYLE")
    contradiction_review_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        alias="CONTRADICTION_REVIEW_THRESHOLD",
    )
    copy_artifact_patterns: str = Field(
        default=r"^\s*Page\s+\d+\s*$||^\s*<<<[^>]+>>>\s*$||^\s*\[?Advertisement\]?\s*$",
        alias="COPY_ARTIFACT_PATTERNS",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
