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
    source: Optional[str] = "WhatsApp"

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
        values["customer_name"] = str(resolved_name).strip() if resolved_name else "WhatsApp Lead"

        # Normalize message
        resolved_message = values.get("message") or values.get("text") or values.get("content")
        values["message"] = str(resolved_message).strip() if resolved_message else ""

        # Normalize source
        values["source"] = str(values.get("source") or "WhatsApp").strip()

        return values

class WebhookResponse(BaseModel):
    status: str
    message: str
    bigin_lead_id: Optional[str] = None
    phone: str
