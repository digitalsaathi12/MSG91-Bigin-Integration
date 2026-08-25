from unittest.mock import patch, MagicMock
from app.services.bigin_client import (
    BiginClient,
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
)

class TestBiginClient:

    def setup_method(self):
        self.mock_oauth = MagicMock()
        self.mock_oauth.get_access_token.return_value = "mock_valid_token"
        self.client = BiginClient(
            oauth_manager=self.mock_oauth,
            api_domain="https://www.zohoapis.com",
            module_name="Leads",
            pipeline_stage="Leads",
        )
        self.sample_data = {
            "customer_name": "Suresh Raina",
            "phone": "+919876543210",
            "message": "Need home loan",
            "source": "WhatsApp",
        }

    @patch("requests.post")
    def test_create_lead_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [
                {
                    "code": "SUCCESS",
                    "details": {"id": "998877665544"},
                    "message": "record added",
                    "status": "SUCCESS",
                }
            ]
        }
        mock_post.return_value = mock_resp

        lead_id = self.client.create_lead(self.sample_data)

        assert lead_id == "998877665544"
        mock_post.assert_called_once()
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Zoho-oauthtoken mock_valid_token"

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Pipeline_Stage"] == "Leads"
        assert payload["Phone"] == "+919876543210"
        assert payload["Last_Name"] == "Suresh Raina"

    @patch("requests.post")
    def test_create_lead_raises_rate_limit_on_429(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        try:
            self.client.create_lead(self.sample_data)
            assert False, "Expected BiginRateLimitException"
        except BiginRateLimitException:
            pass

    @patch("requests.post")
    def test_create_lead_raises_quota_exhausted(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "LIMIT_EXCEEDED"
        mock_post.return_value = mock_resp

        try:
            self.client.create_lead(self.sample_data)
            assert False, "Expected BiginQuotaExhaustedException"
        except BiginQuotaExhaustedException:
            pass
