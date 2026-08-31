from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.bigin_client import (
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
)

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

    @patch("app.api.webhook.BiginClient")
    def test_msg91_customer_number_payload_extraction(self, mock_bigin_class):
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.return_value = "BIGIN_LEAD_MSG91_102"

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {
            "customerNumber": "9181588XXXXX",
            "integratedNumber": "9190287XXXXX",
            "text": "Hello, interested in finserv",
            "name": "Test Customer",
        }

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["bigin_lead_id"] == "BIGIN_LEAD_MSG91_102"
        assert data["phone"] == "9181588XXXXX"

        mock_instance.create_lead.assert_called_once_with({
            "customer_name": "Test Customer",
            "phone": "9181588XXXXX",
            "message": "Hello, interested in finserv",
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

    @patch("app.api.webhook.BiginClient")
    def test_bigin_api_exception_returns_500_not_502(self, mock_bigin_class):
        """BiginAPIException must produce a clean 500 — not 502 or unhandled crash."""
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.side_effect = BiginAPIException(
            "Zoho-oauthtoken secret_token_do_not_leak INVALID_DATA"
        )

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {"phone": "+919876543210", "customer_name": "Error Test"}

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 500
        body = response.json()
        # Safe message — must NOT contain raw token or Bigin error internals
        assert "detail" in body
        assert "Zoho-oauthtoken" not in body["detail"]
        assert "secret_token_do_not_leak" not in body["detail"]

    @patch("app.api.webhook.BiginClient")
    def test_bigin_rate_limit_returns_500(self, mock_bigin_class):
        """BiginRateLimitException (HTTP 429) must also return clean 500 JSON."""
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.side_effect = BiginRateLimitException(
            "Bigin API rate limit hit (HTTP 429)."
        )

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {"phone": "+919876543210", "customer_name": "Rate Limit Test"}

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 500
        body = response.json()
        assert "rate limit" in body["detail"].lower()

    @patch("app.api.webhook.BiginClient")
    def test_bigin_quota_exhausted_returns_500(self, mock_bigin_class):
        """BiginQuotaExhaustedException must return clean 500 JSON."""
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.side_effect = BiginQuotaExhaustedException(
            "Bigin API daily limit exceeded."
        )

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {"phone": "+919876543210", "customer_name": "Quota Test"}

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 500
        body = response.json()
        assert "quota" in body["detail"].lower()

    @patch("app.api.webhook.BiginClient")
    def test_unexpected_exception_returns_500_safely(self, mock_bigin_class):
        """Any unexpected exception must be caught and return a clean 500."""
        mock_instance = mock_bigin_class.return_value
        mock_instance.create_lead.side_effect = RuntimeError("Something went very wrong")

        valid_secret = settings.MSG91_SHARED_SECRET
        payload = {"phone": "+919876543210", "customer_name": "Crash Test"}

        response = client.post(f"/webhook/msg91/{valid_secret}", json=payload)

        assert response.status_code == 500
        body = response.json()
        assert "detail" in body
        # Raw exception message must not leak through
        assert "Something went very wrong" not in body["detail"]
