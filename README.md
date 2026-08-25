# MSG91 WhatsApp → Zoho Bigin Pure Pass-Through Webhook

Stateless, ultra-lightweight **FastAPI pass-through webhook** designed to receive MSG91 WhatsApp leads and instantly create them as Lead records in Zoho Bigin under **All Leads – We Do Finserv** (in the **"Leads" stage**), using Zoho's REST API v2 with OAuth 2.0.

---

## ⚡ Pure Pass-Through Architecture

- **Zero Database / Queue Required**: No SQL database, no Redis, and no Celery worker.
- **Single Service Render Deployment**: Deploys as a single Web Service on Render.
- **URL Path Secret Security**: URL path parameter authentication (`POST /webhook/msg91/{secret}`). Returns `404 Not Found` if secret does not match.
- **In-Memory OAuth Manager**: Access tokens are cached in memory and auto-refreshed when near expiry.

---

## 🛠️ Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Validation**: Pydantic v2 & `pydantic-settings`
- **HTTP Client**: `requests` / `httpx`
- **Testing**: `pytest`

---

## 🚀 Deployment Instructions (Render.com)

### Render Settings

| Setting Field | Value |
|---|---|
| **Root Directory** | *(Leave blank)* |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

---

## 🔐 Environment Variables Configuration

Set these variables in your deployment environment (e.g. Render Environment Variables tab):

```env
PROJECT_NAME=MSG91-Bigin Pass-Through Webhook
DEBUG=False

# URL Path Secret: /webhook/msg91/{MSG91_SHARED_SECRET}
MSG91_SHARED_SECRET=your_custom_secret_key_12345

# Zoho Bigin OAuth Credentials
BIGIN_CLIENT_ID=1000.XXXXXXXXXXXXXXXXXXXXXXXX
BIGIN_CLIENT_SECRET=your_zoho_client_secret
BIGIN_REFRESH_TOKEN=1000.YYYYYYYYYYYYYYYYYYYYYYYY
BIGIN_ACCOUNTS_URL=https://accounts.zoho.com
BIGIN_API_DOMAIN=https://www.zohoapis.com
BIGIN_MODULE_NAME=Leads
BIGIN_PIPELINE_STAGE=Leads
```

---

## 📡 Webhook URL Configuration in MSG91

Set your MSG91 Webhook destination URL to:

```text
https://<your-render-app-name>.onrender.com/webhook/msg91/<MSG91_SHARED_SECRET>
```

#### Request Payload Example
```json
{
  "customer_name": "Rahul Sharma",
  "phone": "+919876543210",
  "message": "I am interested in loan services.",
  "source": "WhatsApp"
}
```

#### Success Response (`200 OK`)
```json
{
  "status": "success",
  "message": "Lead synced to Bigin successfully.",
  "bigin_lead_id": "110022334455",
  "phone": "+919876543210"
}
```

---

## 🧪 Running Unit Tests

Run pytest to execute the unit test suite:
```bash
python -m pytest
```
