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
    ollama_api_key: str = Field(default="")

    # Multi-tenancy
    default_tenant_id: str = Field(default="00000000-0000-0000-0000-000000000001")

    # Pipeline thresholds
    confidence_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    # Demo defaults (3-7s). Production: DEBOUNCE_MIN_SECONDS=30, DEBOUNCE_MAX_SECONDS=90
    debounce_min_seconds: int = Field(default=3, ge=0)
    debounce_max_seconds: int = Field(default=7, ge=0)

    # LLM routing
    preferred_llm_provider: str = Field(default="openrouter")

    # n8n (local por default; sobreescribe con N8N_BASE_URL en .env para self-hosted)
    n8n_base_url: str = Field(default="http://localhost:5678")
    n8n_api_key: str = Field(default="")

    # App
    env: Literal["dev", "test", "prod"] = Field(default="dev")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
