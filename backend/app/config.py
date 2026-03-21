import os
from pathlib import Path
from typing import ClassVar

from dotenv import dotenv_values
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Ensure local `.env` wins over any preset DATABASE_URL from higher-up environments.
# This prevents the app from accidentally connecting to another project's DB (e.g., ids_db).
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    env_vals = dotenv_values(env_path)
    env_db = env_vals.get("DATABASE_URL")
    if env_db and os.getenv("DATABASE_URL", "") != env_db:
        os.environ["DATABASE_URL"] = env_db


class Settings(BaseSettings):
    # Load the .env file located at the project root (backend/.env) regardless of current CWD.
    project_root: ClassVar[Path] = Path(__file__).resolve().parents[1]
    model_config = SettingsConfigDict(
        env_file=str(project_root / ".env"),
        env_file_encoding="utf-8",
    )

    # Database
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    def normalize_database_url(cls, v: str) -> str:
        # Prefer psycopg2 for local/dev environments; avoid asyncpg dependency.
        if isinstance(v, str) and v.startswith("postgresql+asyncpg"):
            return v.replace("postgresql+asyncpg", "postgresql")
        return v

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    BCRYPT_ROUNDS: int = 12

    # Third-party integrations (optional)
    OPENAI_API_KEY: str | None = None
    GROQ_API_KEY: str = ""

    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Supabase Storage (optional)
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_BUCKET: str = "resumes"

    # Dev toggles
    RATE_LIMIT_ENABLED: bool = False
    LOG_LEVEL: str = "DEBUG"


settings = Settings()
