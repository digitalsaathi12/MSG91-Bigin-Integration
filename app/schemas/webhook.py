from typing import Optional
from pydantic import BaseModel, model_validator

class MSG91WebhookPayload(BaseModel):
    customer_name: Optional[str] = None
    name: Optional[str] = None
    sender_name: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    mobile: Optional[str] = None
    wa_number: Optional[str] = None
    message: Optional[str] = None
    text: Optional[str] = None
    content: Optional[str] = None
    event_type: Optional[str] = "MESSAGE_RECEIVED"
    event: Optional[str] = None
    msg91_contact_id: Optional[str] = None
    contact_id: Optional[str] = None
    source: Optional[str] = "WhatsApp"
    timestamp: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values

        # Normalize phone
        resolved_phone = (
            values.get("phone")
            or values.get("whatsapp_number")
            or values.get("mobile")
            or values.get("wa_number")
        )
        if not resolved_phone and isinstance(values.get("data"), dict):
            inner = values["data"]
            resolved_phone = inner.get("phone") or inner.get("whatsapp_number") or inner.get("mobile")

        if not resolved_phone:
            raise ValueError("WhatsApp number or phone is required.")
        values["phone"] = str(resolved_phone).strip()

        # Normalize customer name
        resolved_name = (
            values.get("customer_name")
            or values.get("name")
            or values.get("sender_name")
        )
        values["customer_name"] = str(resolved_name).strip() if resolved_name else None

        # Normalize message
        resolved_message = values.get("message") or values.get("text") or values.get("content")
        values["message"] = str(resolved_message).strip() if resolved_message else None

        # Normalize event type
        resolved_event = values.get("event_type") or values.get("event") or "MESSAGE_RECEIVED"
        event_str = str(resolved_event).upper().strip()
        if event_str not in ("CONTACT_ADDED", "MESSAGE_SENT", "MESSAGE_RECEIVED"):
            event_str = "MESSAGE_RECEIVED"
        values["event_type"] = event_str

        # Normalize msg91_contact_id
        resolved_contact_id = values.get("msg91_contact_id") or values.get("contact_id")
        values["msg91_contact_id"] = str(resolved_contact_id).strip() if resolved_contact_id else None

        # Normalize source
        values["source"] = str(values.get("source") or "WhatsApp").strip()

        return values

class WebhookResponse(BaseModel):
    status: str
    message: str
    lead_id: Optional[int] = None
    phone: str
    action: str  # 'created' or 'updated'
