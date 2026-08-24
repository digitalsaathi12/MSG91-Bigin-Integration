import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "MSG91-Bigin Integration"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./digsaathi.db"

    # Redis & Celery
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/0"
    REDIS_CACHE_URL: str = "redis://127.0.0.1:6379/1"

    # MSG91 Webhook Security & API Configuration
    MSG91_SHARED_SECRET: str = ""
    MSG91_AUTH_KEY: str = ""
    MSG91_CONTACTS_API_URL: str = "https://api.msg91.com/api/v5/contacts"
    RECONCILIATION_INTERVAL_HOURS: int = 4

    # Zoho Bigin OAuth 2.0 Credentials & Layout Configuration
    BIGIN_CLIENT_ID: str = ""
    BIGIN_CLIENT_SECRET: str = ""
    BIGIN_REFRESH_TOKEN: str = ""
    BIGIN_ACCOUNTS_URL: str = "https://accounts.zoho.com"
    BIGIN_API_DOMAIN: str = "https://www.zohoapis.com"
    BIGIN_MODULE_NAME: str = "Leads"
    BIGIN_PIPELINE_STAGE: str = "Leads"


    model_config = ConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
