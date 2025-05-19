from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path

# Obtener la ruta al directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    PROJECT_NAME: str = "WebNovel Manager API"
    API_V1_STR: str = "/api/v1"

    # MongoDB settings
    MONGODB_URL: str
    MONGODB_DB_NAME: str

    # Flags
    IS_DEBUG: bool = False

    # Translation settings
    DEEPL_API_KEY: str | None = None
    GOOGLE_TRANSLATE_API_KEY: str | None = None
    TARGET_LANGUAGE: str = "ES"

    # JWT settings
    SECRET_KEY: str = "dev-secret-key-change-in-production"  # Default value for development
    REFRESH_SECRET_KEY: str = "dev-refresh-secret-key-change-in-production"  # Default value for development
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 3600
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ScraperAPI settings
    SCRAPERAPI_KEY: str | None = None

    # Proxy settings
    PROXY_URL: str | None = None
    PROXY_USERNAME: str | None = None
    PROXY_PASSWORD: str | None = None

    class Config:
        case_sensitive = True
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"


settings = Settings()
