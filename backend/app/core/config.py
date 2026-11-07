from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./pricelurk.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_TIMEOUT: float = Field(default=5, ge=1, le=15)
    TELEGRAM_ATTEMPTS: int = Field(default=3, ge=1, le=3)
    WRITE_API_KEY: str = ""
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    CELERY_QUEUE: str = "main-queue"
    MONITOR_INTERVAL_SECONDS: int = Field(default=3600, ge=60)
    ENVIRONMENT: str = "development"
    DEMO_MODE: bool = False
    BROWSER_FALLBACK: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def database_driver(cls, value):
        # SQLAlchemy 2.1 changed PostgreSQL's default driver to psycopg3.
        # Keep existing generic URLs compatible with the pinned psycopg2 package.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg2://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg2://", 1)
        return value

    @model_validator(mode="after")
    def validate_demo(self):
        if self.DEMO_MODE and self.ENVIRONMENT == "production":
            raise ValueError("Demo data cannot be enabled in production")
        if self.DEMO_MODE and "demo" not in self.DATABASE_URL.lower():
            raise ValueError("Demo mode requires a separate database with 'demo' in its name")
        return self

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID) and not self.DEMO_MODE


settings = Settings()
