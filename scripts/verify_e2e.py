"""
End-to-End Test & Verification Script for MSG91 -> Bigin Lead Automation
Run this script to simulate a webhook lead event and verify local DB & Bigin sync status.
"""

import os
import sys
import time
import requests

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.db.session import SessionLocal
from app.models.lead import Lead

BASE_URL = "http://127.0.0.1:8000"

def test_webhook_flow():
    print("=" * 60)
    print(" 1. Testing Webhook Endpoint (POST /api/msg91/webhook/)")
    print("=" * 60)

    test_phone = f"+9199999{int(time.time()) % 1000000:06d}"
    test_payload = {
        "customer_name": "Test Automation Lead",
        "phone": test_phone,
        "message": "Hi, I am testing the MSG91 -> Bigin sync pipeline.",
        "event_type": "MESSAGE_RECEIVED",
        "msg91_contact_id": "TEST_CNT_123",
        "source": "WhatsApp"
    }

    headers = {}
    if settings.MSG91_SHARED_SECRET:
        headers["X-MSG91-Secret"] = settings.MSG91_SHARED_SECRET

    print(f"Sending test payload for phone: {test_phone}...")
    try:
        resp = requests.post(f"{BASE_URL}/api/msg91/webhook/", json=test_payload, headers=headers, timeout=5)
        print(f"HTTP Status: {resp.status_code}")
        print(f"Response Body: {resp.json()}")
    except requests.RequestException as err:
        print(f"❌ Failed to reach FastAPI server at {BASE_URL}: {err}")
        print("Please ensure Uvicorn server is running: uvicorn app.main:app --reload")
        return

    print("\n" + "=" * 60)
    print(" 2. Checking Local Database (leads table)")
    print("=" * 60)
    
    time.sleep(1)
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.phone == test_phone).first()
        if lead:
            print(f"✅ Lead record found in DB:")
            print(f"   - ID: {lead.id}")
            print(f"   - Phone: {lead.phone}")
            print(f"   - Status: {lead.status}")
            print(f"   - Bigin Lead ID: {lead.bigin_lead_id}")
            print(f"   - Error Message: {lead.error_message}")
        else:
            print("❌ Lead record not found in database.")
    finally:
        db.close()

def test_reconciliation_trigger():
    print("\n" + "=" * 60)
    print(" 3. Testing Full Reconciliation Sync Task")
    print("=" * 60)
    
    from app.tasks.lead_tasks import run_full_reconciliation_task
    print("Executing run_full_reconciliation_task()...")
    try:
        res = run_full_reconciliation_task()
        print(f"Result: {res}")
    except Exception as err:
        print(f"Reconciliation error (check MSG91_AUTH_KEY in .env): {err}")

if __name__ == "__main__":
    test_webhook_flow()
    if "--reconcile" in sys.argv:
        test_reconciliation_trigger()
