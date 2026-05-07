import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "atalaia")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/atalaia",
        )
        self.bootstrap_admin_token = os.getenv("ATALAIA_BOOTSTRAP_TOKEN", "dev-bootstrap")


@lru_cache
def get_settings() -> Settings:
    return Settings()
