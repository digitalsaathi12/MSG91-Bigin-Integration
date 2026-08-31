# PROJECT STATUS & ARCHITECTURE SUMMARY

This document provides a complete technical summary of the **MSG91 WhatsApp → Zoho Bigin Lead Automation** backend repository to share with any deployment assistant or developer.

---

## 1. PROJECT STRUCTURE

```text
digsaathi/
├── app/
│   ├── api/
│   │   ├── __init__.py           # Package marker for API routers
│   │   └── webhook.py            # POST /webhook/msg91/{secret} pass-through endpoint
│   ├── schemas/
│   │   ├── __init__.py           # Package marker for Pydantic schemas
│   │   └── webhook.py            # Pydantic v2 payload models and field normalization
│   ├── services/
│   │   ├── __init__.py           # Package marker for service wrappers
│   │   ├── bigin_client.py       # REST API client for Zoho Bigin lead creation
│   │   └── oauth_manager.py      # In-memory OAuth 2.0 token manager with auto-refresh
│   ├── __init__.py               # Package marker for app module
│   ├── config.py                 # Pydantic BaseSettings class loading .env variables
│   └── main.py                   # FastAPI app entrypoint with CORS, logging, and health check
├── tests/
│   ├── __init__.py               # Package marker for test suite
│   ├── test_bigin_client.py      # Pytest unit tests for Bigin API client mapping & error handling
│   ├── test_oauth_manager.py     # Pytest unit tests for in-memory OAuth token refresh & buffer logic
│   └── test_webhook.py           # Pytest unit tests for webhook URL secret check & end-to-end routing
├── .env                          # Local environment variables file storing credentials (git-ignored)
├── .env.example                  # Environment template file for production/deployment reference
├── .gitignore                    # Specifies untracked files excluded from Git (e.g. .env, cache, logs)
├── README.md                     # Project documentation with setup, Render commands, and endpoint specs
├── requirements.txt              # Full Python package dependencies for pip install
└── PROJECT_STATUS.md             # This comprehensive summary document
```

---

## 2. WEBHOOK ENDPOINT DETAILS

- **Route Path**: `/webhook/msg91/{secret}`
- **HTTP Method**: `POST`
- **Path Secret Validation Implementation**:
  Secret validation is baked directly into the URL path parameter. If `{secret}` in the request path does not match `settings.MSG91_SHARED_SECRET`, FastAPI raises an HTTP `404 Not Found` response.

  *Exact code snippet from `app/api/webhook.py`*:
  ```python
  @router.post(
      "/webhook/msg91/{secret}",
      response_model=WebhookResponse,
      status_code=status.HTTP_200_OK,
      summary="MSG91 WhatsApp Pass-Through Webhook Endpoint",
  )
  def msg91_webhook_pass_through(
      secret: str,
      payload: MSG91WebhookPayload
  ):
      # Secret baked directly into URL path
      if secret != settings.MSG91_SHARED_SECRET:
          logger.warning(f"Rejected webhook request with invalid secret path: '{secret}'.")
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail="Not Found"
          )

      lead_data = {
          "customer_name": payload.customer_name,
          "phone": payload.phone,
          "message": payload.message,
          "source": payload.source,
      }

      client = BiginClient()
      bigin_lead_id = client.create_lead(lead_data)
      return WebhookResponse(
          status="success",
          message="Lead synced to Bigin successfully.",
          bigin_lead_id=bigin_lead_id,
          phone=payload.phone,
      )
  ```

- **Expected Payload Shape from MSG91**:
  Pydantic model `MSG91WebhookPayload` ([app/schemas/webhook.py](file:///c:/Users/Admin/Desktop/digsaathi/app/schemas/webhook.py)) accepts flexible key variations from MSG91 webhooks and normalizes them:
  - **Phone** (Required): extracted from `phone`, `whatsapp_number`, `mobile`, `wa_number`, or nested `data.phone`.
  - **Customer Name**: extracted from `customer_name`, `name`, `sender_name` (defaults to `"WhatsApp Lead"` if empty).
  - **Message**: extracted from `message`, `text`, `content` (defaults to `""`).
  - **Source**: extracted from `source` (defaults to `"WhatsApp"`).

---

## 3. DATABASE

- **Database Status**: **NO DATABASE IS USED**.
- **Architecture**: The project is a **pure stateless pass-through**. When MSG91 posts a lead event to `/webhook/msg91/{secret}`, FastAPI immediately validates the URL path secret, parses the payload, calls Zoho Bigin's REST API synchronously, and returns the response. No local storage, ORM, SQL database, or Celery task broker is required.

---

## 4. ENVIRONMENT VARIABLES

The app reads configuration using `pydantic-settings` in `app/config.py`.

| Variable Name | Description | Default Value |
|---|---|---|
| `PROJECT_NAME` | Title of the FastAPI application | `"MSG91-Bigin Pass-Through Webhook"` |
| `DEBUG` | Enables verbose debug logging when True | `True` |
| `MSG91_SHARED_SECRET` | Secret key embedded in URL path parameter (`/webhook/msg91/{MSG91_SHARED_SECRET}`) | `"my_custom_secret_key_12345"` |
| `BIGIN_CLIENT_ID` | Zoho OAuth 2.0 Client ID | `""` |
| `BIGIN_CLIENT_SECRET` | Zoho OAuth 2.0 Client Secret | `""` |
| `BIGIN_REFRESH_TOKEN` | Zoho OAuth 2.0 Refresh Token | `""` |
| `BIGIN_ACCOUNTS_URL` | Zoho OAuth domain endpoint | `"https://accounts.zoho.com"` |
| `BIGIN_API_DOMAIN` | Zoho Bigin REST API domain | `"https://www.zohoapis.com"` |
| `BIGIN_MODULE_NAME` | Zoho Bigin module name | `"Pipelines"` |
| `BIGIN_PIPELINE_ENTRY_STAGE` | Entry stage actual_value in Bigin pipeline | `"Customer Onboarding Standard"` |
| `BIGIN_PIPELINE_NAME` | Pipeline display name (for reference/logging) | `"All Leads - We Do Finsev"` |
| `BIGIN_LAYOUT_ID` | Layout ID for the target pipeline board | `"860541000000000173"` |

- **`.env.example` File Exists**: **YES** ([.env.example](file:///c:/Users/Admin/Desktop/digsaathi/.env.example)).

---

## 5. DEPENDENCIES

Full contents of `requirements.txt`:

```text
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=7.4.0
httpx>=0.26.0
```

---

## 6. HOW TO RUN IT LOCALLY

- **Command to Start Server Locally**:
  ```bash
  uvicorn app.main:app --reload
  ```
  *(Or `python -m uvicorn app.main:app --reload --port 8000`)*

- **Local Port**: Runs on **Port `8000`**.
- **Interactive Documentation**: Accessible at `http://127.0.0.1:8000/docs`.

---

## 7. DEPLOYMENT READINESS

- **`.gitignore` Status**: **YES**, `.gitignore` exists and explicitly excludes `.env` (`.env` is listed on line 5).
- **Git Repository**: **YES**, repository is initialized and connected to GitHub remote (`https://github.com/digitalsaathi12/MSG91-Bigin-Integration.git` on branch `main`).
- **Cloud/Render Port Compatibility**:
  - **No hardcoded ports**: Render automatically passes a `$PORT` environment variable.
  - **Start Command for Render**:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
    ```
  - **Build Command for Render**:
    ```bash
    pip install -r requirements.txt
    ```
  - **No hardcoded file paths**: All application paths are resolved dynamically using `Path(__file__).resolve()`.

---

## 8. ZOHO BIGIN INTEGRATION DETAILS

- **Bigin REST API Endpoint Called**: `POST {BIGIN_API_DOMAIN}/bigin/v2/{BIGIN_MODULE_NAME}` (e.g. `POST https://www.zohoapis.in/bigin/v2/Pipelines`).
- **Record Field Mapping (Bigin API v2 Pipelines)**:
  - `Deal_Name` $\leftarrow$ `customer_name` (defaults to `WhatsApp Lead - {phone}` if empty)
  - `Layout` $\leftarrow$ `{"id": "860541000000000173"}` (Layout object for `"All Leads - We Do Finsev"`)
  - `Sub_Pipeline` $\leftarrow$ `BIGIN_PIPELINE_ENTRY_STAGE` (`"Customer Onboarding Standard"`)
  - `Phone` $\leftarrow$ 10-digit normalized phone number (country code `91` stripped if 12 digits)
  - `Mobile` $\leftarrow$ 10-digit normalized phone number
  - `Description` $\leftarrow$ `message`
  - `Lead_Source` $\leftarrow$ `"WhatsApp"`

- **OAuth 2.0 Token Refresh Logic**:
  - Implemented in `ZohoOAuthManager` ([app/services/oauth_manager.py](file:///c:/Users/Admin/Desktop/digsaathi/app/services/oauth_manager.py)).
  - **In-Memory Caching**: Access tokens and expiration timestamps (`_expiry_timestamp`) are cached in memory.
  - **Expiry Buffer**: Before any API call, `get_access_token()` checks if the cached token is valid. If missing, expired, or within a 2-minute buffer (`120s`) of expiry, it sends a `POST` request to `{BIGIN_ACCOUNTS_URL}/oauth/v2/token` using `refresh_token`, `client_id`, and `client_secret` to obtain a new access token.
  - **401 Unauthorized Retry**: If Bigin returns an HTTP `401`, `BiginClient` automatically forces a token refresh (`force_refresh=True`) and retries the API call once before raising an error.
