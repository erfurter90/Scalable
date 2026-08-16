"""Central application settings, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved absolute, not relative to the process's cwd — the app may be launched with a
# different working directory (e.g. from a repo-root task runner), and both the .env lookup
# and the default SQLite file path below need to still land inside backend/.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database — dialect-agnostic URL, SQLite for local dev, Postgres via docker-compose later.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'finanz_agent.db'}"

    # Signs session cookies. Must be overridden in production via env var.
    secret_key: str = "changeme-generate-a-random-64-char-hex-string"
    session_cookie_name: str = "finanz_agent_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 7  # 7 days

    # Optional: AI assistant degrades gracefully to "not configured" when unset.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    # "live" calls real external APIs, "mock" always uses deterministic fixtures.
    market_data_mode: str = "live"

    # Used only by the bootstrap CLI script to create the single app user.
    bootstrap_username: str = "admin"
    bootstrap_password: str = "changeme"

    cors_allow_origins: list[str] = ["http://localhost:3000"]

    # Optional: Bitvavo transaction sync degrades gracefully to "not configured" when unset.
    # Must be a read-only API key (no trading/withdraw permission) — see providers/bitvavo_provider.py.
    bitvavo_api_key: str | None = None
    bitvavo_api_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
