# MSG91 WhatsApp → Zoho Bigin Lead Automation (Full Sync & Reconciliation)

Production-ready **FastAPI** backend designed to sync **every lead/contact from MSG91 WhatsApp** into Zoho Bigin landing in the **"Leads" stage** of **"All Leads – We Do Finserv"**, using Zoho's REST API v2 with OAuth 2.0.

---

## 🏗️ Sync Architecture & Complementary Mechanisms

To guarantee **100% complete sync** without missing contacts, the system uses two complementary mechanisms keyed on **WhatsApp Phone Number (`phone`)**:

1. **Real-time Webhook Capture**: Webhook endpoint `POST /api/msg91/webhook/` receives all MSG91 events (`CONTACT_ADDED`, `MESSAGE_SENT`, `MESSAGE_RECEIVED`), upserts local `Lead` records by `phone`, and enqueues immediate Bigin creation/update.
2. **Scheduled Reconciliation Sync**: Periodic **Celery Beat** job (configurable every 2–6 hours) fetches full contact lists from MSG91 API via `MSG91Client` and idempotently syncs any missing or unpushed leads into Bigin.

---

## 🛠️ Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Data Validation**: Pydantic v2 & `pydantic-settings`
- **Database / ORM**: SQLAlchemy 2.0 + PyMySQL / SQLite
- **Task Queue & Scheduler**: Celery + Celery Beat + Redis
- **HTTP Client**: `requests` / `httpx`
- **Testing**: `pytest` & `httpx`

---

## 🚀 Environment Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure parameters in `.env`:
```env
PROJECT_NAME=MSG91-Bigin Integration
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Database Configuration (SQLAlchemy)
DATABASE_URL=sqlite:///./digsaathi.db

# Redis & Celery Configuration
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
REDIS_CACHE_URL=redis://127.0.0.1:6379/1

# MSG91 Security & Reconciliation API Configuration
MSG91_SHARED_SECRET=your_msg91_webhook_shared_secret
MSG91_AUTH_KEY=your_msg91_api_auth_key
MSG91_CONTACTS_API_URL=https://api.msg91.com/api/v5/contacts
RECONCILIATION_INTERVAL_HOURS=4

# Zoho Bigin OAuth Credentials & Layout
BIGIN_CLIENT_ID=1000.XXXXXXXXXXXXXXXXXXXXXXXX
BIGIN_CLIENT_SECRET=your_zoho_client_secret
BIGIN_REFRESH_TOKEN=1000.YYYYYYYYYYYYYYYYYYYYYYYY
BIGIN_ACCOUNTS_URL=https://accounts.zoho.com
BIGIN_API_DOMAIN=https://www.zohoapis.com
BIGIN_MODULE_NAME=Leads
BIGIN_PIPELINE_STAGE=Leads
```

---

## ⚡ Running Services

### 1. Start Celery Worker
```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

### 2. Start Celery Beat Scheduler (Reconciliation Sync)
```bash
celery -A app.celery_app.celery_app beat --loglevel=info
```

### 3. Launch FastAPI Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive OpenAPI documentation will be accessible at `http://localhost:8000/docs`.

---

## 📡 Webhook Endpoint

### `POST /api/msg91/webhook/`

Receives real-time contact and message events from MSG91.

#### Request Payload
```json
{
  "customer_name": "Rahul Sharma",
  "phone": "+919876543210",
  "message": "I am interested in We Do Finserv loan services.",
  "event_type": "MESSAGE_RECEIVED",
  "msg91_contact_id": "CNT_98765",
  "source": "WhatsApp"
}
```

#### Success Response (`200 OK`)
```json
{
  "status": "queued",
  "message": "New lead created and queued for Bigin sync.",
  "lead_id": 1,
  "phone": "+919876543210",
  "action": "created"
}
```

---

## 🧪 Running Unit Tests

Run pytest to execute the full unit test suite:
```bash
pytest
```
