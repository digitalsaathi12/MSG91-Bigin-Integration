from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.lead import Lead, LeadStatus, LeadEventType

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

class TestMSG91WebhookAPI:

    @patch("app.api.webhook.create_or_update_bigin_lead_task.delay")
    def test_new_contact_webhook_creates_lead(self, mock_task_delay):
        payload = {
            "customer_name": "Rohan Das",
            "phone": "+919876543210",
            "message": "Interested in finserv product",
            "event_type": "CONTACT_ADDED",
            "source": "WhatsApp",
        }
        headers = {"X-MSG91-Secret": "test_msg91_secret"}

        response = client.post("/api/msg91/webhook/", json=payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["action"] == "created"
        assert data["phone"] == "+919876543210"

        db = TestingSessionLocal()
        lead = db.query(Lead).filter(Lead.phone == "+919876543210").first()
        assert lead is not None
        assert lead.customer_name == "Rohan Das"
        assert lead.status == LeadStatus.RECEIVED.value
        assert lead.last_event_type == "CONTACT_ADDED"
        db.close()

        mock_task_delay.assert_called_once_with(lead.id)

    @patch("app.api.webhook.create_or_update_bigin_lead_task.delay")
    def test_existing_contact_webhook_updates_lead(self, mock_task_delay):
        db = TestingSessionLocal()
        existing = Lead(
            customer_name="Rohan Das",
            phone="+919876543210",
            message="Old message",
            last_event_type="CONTACT_ADDED",
            bigin_lead_id="BIGIN_100",
            status=LeadStatus.CREATED.value,
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id
        db.close()

        payload = {
            "customer_name": "Rohan Das Updated",
            "phone": "+919876543210",
            "message": "New reply message",
            "event_type": "MESSAGE_RECEIVED",
        }
        headers = {"X-MSG91-Secret": "test_msg91_secret"}

        response = client.post("/api/msg91/webhook/", json=payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["action"] == "updated"
        assert data["lead_id"] == existing_id

        db = TestingSessionLocal()
        updated_lead = db.query(Lead).filter(Lead.id == existing_id).first()
        assert updated_lead.customer_name == "Rohan Das Updated"
        assert updated_lead.message == "New reply message"
        assert updated_lead.last_event_type == "MESSAGE_RECEIVED"
        db.close()

        mock_task_delay.assert_called_once_with(existing_id)

    def test_unauthorized_webhook_rejected(self):
        payload = {
            "phone": "+919876543210",
        }
        headers = {"X-MSG91-Secret": "wrong_secret"}

        response = client.post("/api/msg91/webhook/", json=payload, headers=headers)
        assert response.status_code == 403
