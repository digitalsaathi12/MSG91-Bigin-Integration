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
    # Sub_Pipeline actual_value for selecting the pipeline board ("All Leads - We Do Finsev")
    BIGIN_SUB_PIPELINE: str = "Customer Onboarding Standard"
    # Stage actual_value for selecting starting stage within the board (display label "Leads")
    BIGIN_PIPELINE_ENTRY_STAGE: str = "Documentation"
    BIGIN_PIPELINE_STAGE: str = "Documentation"
    # Sub_Pipeline display_value (cosmetic reference only — Layout ID drives the API call)
    BIGIN_PIPELINE_NAME: str = "All Leads - We Do Finsev"
    # Layout ID for "All Leads - We Do Finsev" pipeline (from GET /bigin/v2/settings/layouts)
    BIGIN_LAYOUT_ID: str = "860541000000000173"

    model_config = ConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
