from unittest.mock import patch, MagicMock
from app.services.msg91_client import MSG91Client, MSG91APIException

class TestMSG91Client:

    def setup_method(self):
        self.client = MSG91Client(auth_key="test_key", contacts_api_url="https://api.msg91.com/api/v5/contacts")

    @patch("requests.get")
    def test_fetch_all_contacts_pagination(self, mock_get):
        resp_page1 = MagicMock()
        resp_page1.status_code = 200
        resp_page1.json.return_value = {
            "total_pages": 2,
            "data": [
                {"mobiles": "+919876543210", "name": "User One", "id": "CNT_001"},
            ]
        }

        resp_page2 = MagicMock()
        resp_page2.status_code = 200
        resp_page2.json.return_value = {
            "total_pages": 2,
            "data": [
                {"mobiles": "+919876543211", "name": "User Two", "id": "CNT_002"},
            ]
        }

        mock_get.side_effect = [resp_page1, resp_page2]

        contacts = self.client.fetch_all_contacts()

        assert len(contacts) == 2
        assert contacts[0]["phone"] == "+919876543210"
        assert contacts[0]["customer_name"] == "User One"
        assert contacts[1]["phone"] == "+919876543211"

    def test_parse_webhook_event(self):
        payload = {
            "whatsapp_number": "+919988776655",
            "name": "Anil Verma",
            "text": "Hello, need finserv quote",
            "event_type": "MESSAGE_RECEIVED",
            "contact_id": "MSG91_CNT_99",
        }

        parsed = MSG91Client.parse_webhook_event(payload)

        assert parsed["phone"] == "+919988776655"
        assert parsed["customer_name"] == "Anil Verma"
        assert parsed["message"] == "Hello, need finserv quote"
        assert parsed["event_type"] == "MESSAGE_RECEIVED"
        assert parsed["msg91_contact_id"] == "MSG91_CNT_99"
