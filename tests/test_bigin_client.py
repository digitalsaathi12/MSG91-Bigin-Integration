from unittest.mock import patch, MagicMock
from app.services.bigin_client import (
    BiginClient,
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
    normalize_phone_for_bigin,
)


class TestNormalizePhoneForBigin:
    """Unit tests for the standalone normalize_phone_for_bigin helper."""

    def test_strips_91_country_code_from_12_digit_number(self):
        assert normalize_phone_for_bigin("919876543210") == "9876543210"

    def test_strips_plus91_prefix_from_13_char_string(self):
        assert normalize_phone_for_bigin("+919876543210") == "9876543210"

    def test_plain_10_digit_number_unchanged(self):
        assert normalize_phone_for_bigin("9876543210") == "9876543210"

    def test_strips_spaces_and_dashes(self):
        assert normalize_phone_for_bigin("+91 98765-43210") == "9876543210"

    def test_does_not_strip_91_prefix_when_already_10_digits(self):
        # A 10-digit number that happens to start with 91 should NOT be stripped
        assert normalize_phone_for_bigin("9198765432") == "9198765432"

    def test_non_10_digit_result_still_returns_digits(self):
        # 8-digit number — should return as-is with a warning (not crash)
        result = normalize_phone_for_bigin("12345678")
        assert result == "12345678"


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
        # +919876543210 → stripped to 9876543210
        assert payload["Phone"] == "9876543210"
        assert payload["Mobile"] == "9876543210"
        assert payload["Last_Name"] == "Suresh Raina"

    @patch("requests.post")
    def test_phone_country_code_stripped_in_bigin_payload(self, mock_post):
        """12-digit number with 91 prefix must be trimmed to 10 digits in the outgoing payload."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "111222333444"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        lead_data = {
            "customer_name": "Test Lead",
            "phone": "919876543210",  # raw 12-digit with 91 prefix, no +
            "message": "Test",
            "source": "WhatsApp",
        }

        self.client.create_lead(lead_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Phone"] == "9876543210", (
            f"Expected '9876543210' but got '{payload['Phone']}'"
        )
        assert payload["Mobile"] == "9876543210"

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
