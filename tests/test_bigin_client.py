from unittest.mock import patch, MagicMock
from app.services.bigin_client import (
    BiginClient,
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
    normalize_phone_for_bigin,
)

LAYOUT_ID = "860541000000000173"
ENTRY_STAGE = "Customer Onboarding Standard"
PIPELINE_NAME = "All Leads - We Do Finsev"


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
            api_domain="https://www.zohoapis.in",
            module_name="Pipelines",
            pipeline_entry_stage=ENTRY_STAGE,
            pipeline_name=PIPELINE_NAME,
            layout_id=LAYOUT_ID,
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

        # Deal_Name present, Last_Name absent
        assert "Deal_Name" in payload
        assert "Last_Name" not in payload
        assert payload["Deal_Name"] == "Suresh Raina"

        # Layout must be sent as object with ID (not string)
        assert payload["Layout"] == {"id": LAYOUT_ID}

        # Sub_Pipeline = actual_value (not display_value)
        assert payload["Sub_Pipeline"] == ENTRY_STAGE

        # Pipeline_Stage is NOT a real field and must be absent
        assert "Pipeline_Stage" not in payload

        # "Pipeline" as a plain string field is NOT sent (it refers to Layout in v2)
        assert "Pipeline" not in payload

        # Phone normalized: +919876543210 → 9876543210
        assert payload["Phone"] == "9876543210"
        assert payload["Mobile"] == "9876543210"

    @patch("requests.post")
    def test_layout_id_sent_as_object(self, mock_post):
        """Layout must be sent as {'id': '860541000000000173'}, not as a plain string."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "777888999"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        self.client.create_lead(self.sample_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Layout"] == {"id": LAYOUT_ID}
        assert isinstance(payload["Layout"], dict)

    @patch("requests.post")
    def test_sub_pipeline_uses_actual_value_not_display_value(self, mock_post):
        """Sub_Pipeline must use actual_value 'Customer Onboarding Standard', not display_value."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "123"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        self.client.create_lead(self.sample_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Sub_Pipeline"] == "Customer Onboarding Standard"
        # Must NOT be the display_value
        assert payload["Sub_Pipeline"] != "All Leads - We Do Finsev"

    @patch("requests.post")
    def test_pipeline_stage_field_absent_from_payload(self, mock_post):
        """Pipeline_Stage is not a real Bigin field and must be absent from payload."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "456"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        self.client.create_lead(self.sample_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert "Pipeline_Stage" not in payload

    @patch("requests.post")
    def test_deal_name_falls_back_to_phone_when_customer_name_empty(self, mock_post):
        """When customer_name is empty, Deal_Name must fall back to 'WhatsApp Lead - {phone}'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "555666777888"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        lead_data = {
            "customer_name": "",
            "phone": "+919876543210",
            "message": "Test fallback",
            "source": "WhatsApp",
        }

        self.client.create_lead(lead_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Deal_Name"] == "WhatsApp Lead - 9876543210"
        assert "Last_Name" not in payload

    @patch("requests.post")
    def test_deal_name_present_when_customer_name_none(self, mock_post):
        """Deal_Name must use fallback when customer_name is absent."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "111222333"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        lead_data = {
            "phone": "9876543210",
            "message": "",
            "source": "WhatsApp",
        }

        self.client.create_lead(lead_data)

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Deal_Name"] == "WhatsApp Lead - 9876543210"
        assert "Last_Name" not in payload

    @patch("requests.post")
    def test_phone_country_code_stripped_in_bigin_payload(self, mock_post):
        """12-digit number with 91 prefix must be trimmed to 10 digits in the outgoing payload."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "data": [{"code": "SUCCESS", "details": {"id": "111222333444"}, "status": "SUCCESS"}]
        }
        mock_post.return_value = mock_resp

        self.client.create_lead({
            "customer_name": "Test Lead",
            "phone": "919876543210",
            "message": "Test",
            "source": "WhatsApp",
        })

        payload = mock_post.call_args[1]["json"]["data"][0]
        assert payload["Phone"] == "9876543210"
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
