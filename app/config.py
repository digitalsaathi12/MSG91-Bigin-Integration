from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "MSG91-Bigin Pass-Through Webhook"
    DEBUG: bool = True

    # Shared secret URL path parameter: /webhook/msg91/{MSG91_SHARED_SECRET}
    MSG91_SHARED_SECRET: str = "my_custom_secret_key_12345"

    # Zoho Bigin OAuth 2.0 Credentials
    BIGIN_CLIENT_ID: str = ""
    BIGIN_CLIENT_SECRET: str = ""
    BIGIN_REFRESH_TOKEN: str = ""
    BIGIN_ACCOUNTS_URL: str = "https://accounts.zoho.com"
    BIGIN_API_DOMAIN: str = "https://www.zohoapis.com"
    BIGIN_MODULE_NAME: str = "Pipelines"
    BIGIN_PIPELINE_STAGE: str = "Leads"
    # Sub_Pipeline = team pipeline/board name (Bigin API v2 rename from v1 "Pipeline")
    BIGIN_PIPELINE_NAME: str = "All Leads - We Do Finserv"

    model_config = ConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
