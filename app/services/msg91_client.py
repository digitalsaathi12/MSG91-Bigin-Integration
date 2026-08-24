import logging
import requests
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger("app.msg91")

class MSG91APIException(Exception):
    """General MSG91 API Exception."""
    pass

class MSG91Client:
    """
    Client wrapper for MSG91 REST API.
    Handles fetching full contact list for periodic reconciliation and parsing webhook events.
    """

    def __init__(self, auth_key: str = None, contacts_api_url: str = None):
        self.auth_key = auth_key or settings.MSG91_AUTH_KEY
        self.contacts_api_url = (contacts_api_url or settings.MSG91_CONTACTS_API_URL).rstrip("/")

    def fetch_all_contacts(self) -> List[Dict[str, Any]]:
        """
        Fetches all contacts from MSG91 API handling pagination.
        :return: List of standardized contact dicts [{'phone', 'customer_name', 'msg91_contact_id'}]
        """
        all_contacts = []
        page = 1
        limit = 100
        has_more = True

        headers = {
            "authkey": self.auth_key,
            "Content-Type": "application/json",
        }

        while has_more:
            try:
                response = requests.get(
                    self.contacts_api_url,
                    headers=headers,
                    params={"page": page, "limit": limit},
                    timeout=15,
                )
            except requests.RequestException as exc:
                logger.error(f"Network failure fetching MSG91 contacts (page {page}): {exc}")
                raise MSG91APIException(f"Network error fetching MSG91 contacts: {exc}") from exc

            if response.status_code != 200:
                logger.error(f"MSG91 contacts API returned HTTP {response.status_code}: {response.text}")
                raise MSG91APIException(f"MSG91 API error status code {response.status_code}")

            data = response.json()
            contacts_page = data.get("data") or data.get("contacts") or []

            if not isinstance(contacts_page, list) or len(contacts_page) == 0:
                has_more = False
                break

            for item in contacts_page:
                phone = str(item.get("mobiles") or item.get("phone") or item.get("mobile") or "").strip()
                if not phone:
                    continue

                contact_name = str(item.get("name") or item.get("customer_name") or "").strip() or None
                contact_id = str(item.get("id") or item.get("contact_id") or "").strip() or None

                all_contacts.append({
                    "phone": phone,
                    "customer_name": contact_name,
                    "msg91_contact_id": contact_id,
                })

            # Check pagination end condition
            total_pages = data.get("total_pages") or data.get("last_page")
            if total_pages is not None:
                if page >= int(total_pages):
                    has_more = False
                else:
                    page += 1
            elif len(contacts_page) < limit:
                has_more = False
            else:
                page += 1

        logger.info(f"Successfully fetched {len(all_contacts)} contacts from MSG91 API.")
        return all_contacts

    @staticmethod
    def parse_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses incoming webhook payload into a standardized dictionary.
        """
        phone = (
            payload.get("phone")
            or payload.get("whatsapp_number")
            or payload.get("mobile")
            or payload.get("wa_number")
            or ""
        )
        if not phone and isinstance(payload.get("data"), dict):
            inner = payload["data"]
            phone = inner.get("phone") or inner.get("whatsapp_number") or inner.get("mobile") or ""

        phone = str(phone).strip()
        if not phone:
            raise ValueError("Missing required phone number in webhook payload.")

        customer_name = (
            payload.get("customer_name")
            or payload.get("name")
            or payload.get("sender_name")
        )
        if customer_name:
            customer_name = str(customer_name).strip()

        message = payload.get("message") or payload.get("text") or payload.get("content")
        if message:
            message = str(message).strip()

        event_type = payload.get("event_type") or payload.get("event") or "MESSAGE_RECEIVED"
        event_type = str(event_type).upper().strip()
        if event_type not in ("CONTACT_ADDED", "MESSAGE_SENT", "MESSAGE_RECEIVED"):
            event_type = "MESSAGE_RECEIVED"

        contact_id = payload.get("msg91_contact_id") or payload.get("contact_id")
        if contact_id:
            contact_id = str(contact_id).strip()

        timestamp = payload.get("timestamp") or payload.get("event_time")

        return {
            "phone": phone,
            "customer_name": customer_name,
            "message": message,
            "event_type": event_type,
            "msg91_contact_id": contact_id,
            "timestamp": timestamp,
            "source": str(payload.get("source") or "WhatsApp").strip(),
        }
