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
            "msg91_contact_id": "MSG_CNT_001",
            "source": "WhatsApp",
        }

    @patch("requests.post")
    def test_create_lead_includes_leads_pipeline_stage(self, mock_post):
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
        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Pipeline_Stage"] == "Leads"
        assert payload["Phone"] == "+919876543210"
        assert payload["External_Contact_ID"] == "MSG_CNT_001"

    @patch("requests.put")
    def test_update_lead_success(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "code": "SUCCESS",
                    "details": {"id": "998877665544"},
                    "status": "SUCCESS",
                }
            ]
        }
        mock_put.return_value = mock_resp

        lead_id = self.client.update_lead("998877665544", self.sample_data)

        assert lead_id == "998877665544"
        mock_put.assert_called_once()
        url = mock_put.call_args[0][0]
        assert "998877665544" in url
