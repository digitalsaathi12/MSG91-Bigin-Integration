from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

class TestMSG91PassThroughWebhook:

    @patch("app.api.webhook.BiginClient")
    def test_valid_secret_and_payload_syncs_to_bigin(self, mock_bigin_class):
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.return_value = "BIGIN_LEAD_PASSTHROUGH_101"

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {
            "customer_name": "Rohan Verma",
            "phone": "+919876543210",
            "message": "Interested in finserv product",
            "source": "WhatsApp",
        }

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["bigin_lead_id"] == "BIGIN_LEAD_PASSTHROUGH_101"
        assert data["phone"] == "+919876543210"

        mock_instance.create_lead.assert_called_once_with({
            "customer_name": "Rohan Verma",
            "phone": "+919876543210",
            "message": "Interested in finserv product",
            "source": "WhatsApp",
        })

    def test_invalid_url_secret_returns_404(self):
        payload = {
            "phone": "+919876543210",
            "customer_name": "Test User",
        }

        response = client.post("/webhook/msg91/wrong_invalid_secret_key", json=payload)

        assert response.status_code == 404

    def test_missing_phone_returns_422(self):
        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {
            "customer_name": "Test User",
            # missing phone
        }

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 422
