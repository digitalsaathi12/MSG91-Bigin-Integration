import logging
from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.schemas.webhook import MSG91WebhookPayload, WebhookResponse
from app.services.bigin_client import (
    BiginClient,
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
)

logger = logging.getLogger("app.api.webhook")

router = APIRouter(tags=["MSG91 Webhook Pass-Through"])

@router.post(
    "/webhook/msg91/{secret}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="MSG91 WhatsApp Pass-Through Webhook Endpoint",
    description=(
        "Receives MSG91 WhatsApp webhook payload, validates URL path secret, "
        "and immediately calls Bigin REST API to create the Lead."
    ),
)
def msg91_webhook_pass_through(
    secret: str,
    payload: MSG91WebhookPayload,
):
    # Secret baked directly into URL path
    if secret != settings.MSG91_SHARED_SECRET:
        logger.warning(f"Rejected webhook request with invalid secret path: '{secret}'.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    logger.info(f"Received webhook event for phone '{payload.phone}'. Calling Bigin API...")
    # [TEMP DEBUG] Log all parsed fields to identify button-click field name in MSG91 payload
    logger.warning(f"[RAW PAYLOAD] {payload.model_dump()}")



    # ── Interested-only filter ─────────────────────────────────────────────
    # Only forward to Bigin if the customer's message/button text matches
    # at least one configured keyword (case-insensitive substring match).
    message_text = (payload.message or "").strip().lower()
    keywords = [
        kw.strip().lower()
        for kw in settings.INTERESTED_KEYWORDS.split(",")
        if kw.strip()
    ]
    if not any(kw in message_text for kw in keywords):
        logger.info(
            f"Skipping non-interested lead for phone '{payload.phone}': "
            f"text={payload.message!r} did not match any keyword in {keywords}."
        )
        return WebhookResponse(
            status="skipped",
            message="Lead response did not match interest keywords. No Bigin record created.",
            phone=payload.phone,
        )
    # ── End filter ────────────────────────────────────────────────────────

    lead_data = {
        "customer_name": payload.customer_name,
        "phone": payload.phone,
        "message": payload.message,
        "source": payload.source,
    }

    try:
        client = BiginClient()
        bigin_lead_id = client.create_lead(lead_data)
        logger.info(
            f"Successfully created Bigin Lead ID '{bigin_lead_id}' for phone '{payload.phone}'."
        )
        return WebhookResponse(
            status="success",
            message="Lead synced to Bigin successfully.",
            bigin_lead_id=bigin_lead_id,
            phone=payload.phone,
        )

    except BiginRateLimitException:
        logger.warning(
            f"Bigin rate limit hit for phone '{payload.phone}'. Lead was NOT created."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bigin API rate limit reached. Please retry shortly.",
        )

    except BiginQuotaExhaustedException:
        logger.error(
            f"Bigin daily quota exhausted for phone '{payload.phone}'. Lead was NOT created."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bigin API daily quota exhausted. Lead was not created.",
        )

    except BiginAPIException as err:
        logger.error(f"Bigin API sync failed for phone '{payload.phone}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bigin API error: lead could not be synced.",
        )

    except Exception as err:
        logger.error(
            f"Unexpected error processing lead for phone '{payload.phone}': {err}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook.",
        )
