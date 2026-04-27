from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if getattr(sys, "frozen", False):
    _BACKEND_DIR = Path(sys.executable).parent
    _BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(_BACKEND_DIR)))
    if str(_BUNDLE_DIR) not in sys.path:
        sys.path.insert(0, str(_BUNDLE_DIR))
else:
    _BACKEND_DIR = Path(__file__).resolve().parents[1]
    _BUNDLE_DIR = _BACKEND_DIR

_REPO_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ZT-ATE Interview Agent"
    app_env: str = "dev"
    api_prefix: str = "/api"
    # Explicit origin whitelist — never use ["*"] in production.
    # Set via CORS_ORIGINS env var as a comma-separated list.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "tauri://localhost",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "http://localhost:3000",
        ]
    )

    # JWT signing secret (HS256). Min 32 bytes of entropy.
    # For Option B migration: replace with jwks_uri pointing to your IdP.
    jwt_secret_key: str = Field(
        default="CHANGE_ME_GENERATE_WITH_openssl_rand_hex_32",
        alias="JWT_SECRET_KEY",
    )
    # Operator master secret — required to mint operator-tier tokens.
    operator_master_secret: str = Field(
        default="CHANGE_ME_OPERATOR_SECRET",
        alias="OPERATOR_MASTER_SECRET",
    )

    data_dir: Path = _BACKEND_DIR / "data"
    sqlite_path: Path = _BACKEND_DIR / "data" / "interview_agent.db"
    frontend_dir: Path = _REPO_DIR / "frontend"
    enforce_secret_scan: bool = True

    adk_router_url: str | None = None
    adk_api_key: str | None = None
    adk_timeout_seconds: float = 8.0

    # Gemini API key — required for live model calls.
    # Set via GEMINI_API_KEY env var or backend/.env
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    # Model identifiers — override per environment via .env.
    # Defaults reflect current Gemini stable series.
    flash_model: str = "gemini-2.5-flash-lite"
    live_model: str = "gemini-2.5-flash"
    pro_model: str = "gemini-2.5-pro"

    # Live interface sliding window — max chars kept in conversation context.
    # ~80k chars ≈ 20k tokens, well within Gemini's 1M token context window.
    live_context_max_chars: int = 80_000

    trace_history_limit: int = 400
    l0_silence_cutoff_ms: int = 10_000


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
