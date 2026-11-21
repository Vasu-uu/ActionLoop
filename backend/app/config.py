"""Settings, loaded from environment variables (and an optional .env file)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(ROOT / ".env"), ".env"), extra="ignore")

    # LLM
    llm_provider: str = ""  # anthropic | openai | ollama | demo ("" = auto)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    llm_timeout: float = 120.0

    # Whisper
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    # Server
    database_url: str = f"sqlite:///{ROOT / 'data' / 'actionloop.db'}"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    max_upload_mb: int = 100
    max_transcript_chars: int = 400_000
    frontend_dist: str = str(ROOT / "frontend" / "dist")
    samples_dir: str = str(ROOT / "samples")
    default_timezone: str = "UTC"
    chunk_token_threshold: int = Field(6000, description="Chunk transcripts longer than this many tokens")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_provider(self) -> str:
        p = self.llm_provider.strip().lower()
        if p in {"anthropic", "openai", "ollama", "demo"}:
            return p
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
