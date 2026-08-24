import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.lead import Lead, LeadStatus, LeadEventType
from app.schemas.webhook import MSG91WebhookPayload, WebhookResponse
from app.tasks.lead_tasks import create_or_update_bigin_lead_task

logger = logging.getLogger("app.api.webhook")

router = APIRouter(prefix="/api/msg91", tags=["MSG91 Webhook"])

def verify_webhook_security(
    request: Request,
    x_msg91_secret: Optional[str] = Header(None, alias="X-MSG91-Secret"),
    x_secret_key: Optional[str] = Header(None, alias="X-Secret-Key"),
    x_msg91_signature: Optional[str] = Header(None, alias="X-MSG91-Signature"),
    secret: Optional[str] = None,
):
    expected_secret = settings.MSG91_SHARED_SECRET
    if not expected_secret:
        return True

    # 1. Direct header match
    provided_secret = x_msg91_secret or x_secret_key or secret
    if provided_secret and hmac.compare_digest(provided_secret.strip(), expected_secret.strip()):
        return True

    # 2. HMAC SHA-256 signature match
    if x_msg91_signature:
        try:
            import asyncio
            body = asyncio.run(request.body()) if asyncio.iscoroutinefunction(request.body) else b""
        except Exception:
            body = b""
        computed = hmac.new(expected_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(x_msg91_signature.strip(), computed):
            return True

    logger.warning("Rejected MSG91 webhook request due to invalid secret/signature.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unauthorized: Invalid webhook secret or signature."
    )

@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_webhook_security)],
    summary="Process MSG91 WhatsApp Event (Real-Time Upsert)",
    description="Receives all MSG91 WhatsApp events (contact added, outbound sent, inbound received), upserts Lead keyed on phone number, and enqueues Bigin API sync."
)
def handle_msg91_webhook(
    payload: MSG91WebhookPayload,
    db: Session = Depends(get_db)
):
    phone = payload.phone
    now = datetime.now(timezone.utc)

    # Phone-based lookup
    existing_lead = db.query(Lead).filter(Lead.phone == phone).first()

    if existing_lead:
        # Upsert: Update existing lead's fields
        if payload.customer_name:
            existing_lead.customer_name = payload.customer_name
        if payload.message:
            existing_lead.message = payload.message
        if payload.event_type:
            existing_lead.last_event_type = payload.event_type
        if payload.msg91_contact_id:
            existing_lead.msg91_contact_id = payload.msg91_contact_id
        
        existing_lead.last_event_at = now
        existing_lead.updated_at = now
        db.commit()
        db.refresh(existing_lead)

        # Enqueue Bigin creation/update task
        try:
            create_or_update_bigin_lead_task.delay(existing_lead.id)
            logger.info(f"Enqueued sync task for existing Lead ID {existing_lead.id} (phone: '{phone}').")
        except Exception as queue_err:
            logger.error(f"Failed to enqueue Celery task for Lead {existing_lead.id}: {queue_err}")

        return WebhookResponse(
            status="queued",
            message="Existing lead updated and queued for Bigin sync.",
            lead_id=existing_lead.id,
            phone=phone,
            action="updated",
        )
    else:
        # Create new lead
        try:
            new_lead = Lead(
                customer_name=payload.customer_name,
                phone=phone,
                message=payload.message,
                last_event_type=payload.event_type or LeadEventType.MESSAGE_RECEIVED.value,
                msg91_contact_id=payload.msg91_contact_id,
                source=payload.source,
                status=LeadStatus.RECEIVED.value,
                last_event_at=now,
            )
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to persist new Lead record: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error persisting lead."
            )

        # Enqueue Bigin task
        try:
            create_or_update_bigin_lead_task.delay(new_lead.id)
            logger.info(f"Enqueued create task for new Lead ID {new_lead.id} (phone: '{phone}').")
        except Exception as queue_err:
            logger.error(f"Failed to enqueue Celery task for new Lead {new_lead.id}: {queue_err}")

        return WebhookResponse(
            status="queued",
            message="New lead created and queued for Bigin sync.",
            lead_id=new_lead.id,
            phone=phone,
            action="created",
        )
