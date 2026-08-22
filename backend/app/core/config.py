"""
Central configuration. Every secret and environment-specific value comes from
the environment — nothing is hard-coded. See .env.example for the full list.

The `_validate_production` check below is deliberate: a development default
that silently survives into production is how JWT secrets end up on GitHub.
"""
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "insecure-development-secret-do-not-use-in-production-0000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "SpendShield AI"
    ENV: str = "development"

    DATABASE_URL: str = "postgresql+psycopg://spendshield:spendshield@localhost:5432/spendshield"

    JWT_SECRET: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Provider-agnostic LLM config — never hard-code a vendor in application code.
    LLM_PROVIDER: str = "anthropic"           # anthropic | openai | groq
    LLM_MODEL_NAME: str = "claude-opus-5"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 4096

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Auth brute-force protection: attempts allowed per client IP per window.
    AUTH_RATE_LIMIT_ATTEMPTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Lets anyone spin up a populated demo account. Turn off for a real deployment.
    DEMO_MODE_ENABLED: bool = True

    MAX_TRANSACTION_PAGE_SIZE: int = Field(default=200, gt=0)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """Accept both `["a","b"]` (JSON) and `a,b` (plain comma list) from the env."""
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.is_production:
            if self.JWT_SECRET == DEV_JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    "JWT_SECRET must be set to a random string of at least 32 characters "
                    "when ENV=production. Generate one with: openssl rand -hex 32"
                )
            if any("localhost" in o for o in self.CORS_ORIGINS):
                raise ValueError(
                    "CORS_ORIGINS still contains localhost while ENV=production. "
                    "Set it to your real frontend origin(s)."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
