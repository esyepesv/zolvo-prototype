from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase / Postgres
    database_url: str = Field(default="sqlite+aiosqlite:///:memory:", description="Async DB URL")
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(default="")

    # LLM providers
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen3-coder")

    # Multi-tenancy
    default_tenant_id: str = Field(default="00000000-0000-0000-0000-000000000001")

    # Pipeline thresholds
    confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    debounce_min_seconds: int = Field(default=30, ge=0)
    debounce_max_seconds: int = Field(default=90, ge=0)

    # LLM routing
    preferred_llm_provider: str = Field(default="openrouter")

    # App
    env: Literal["dev", "test", "prod"] = Field(default="dev")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
