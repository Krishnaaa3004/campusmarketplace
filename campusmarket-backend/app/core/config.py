from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CampusMarket API"
    ENVIRONMENT: str = "development"

    # Full Postgres connection string from Supabase (see .env.example for where to get it)
    DATABASE_URL: str

    # Comma-separated list of frontend origins allowed to call this API
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
