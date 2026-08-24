import logging
from datetime import datetime, timezone
from celery import shared_task
from app.db.session import SessionLocal
from app.models.lead import Lead, LeadStatus, LeadEventType
from app.services.msg91_client import MSG91Client, MSG91APIException
from app.services.bigin_client import (
    BiginClient,
    BiginAPIException,
    BiginRateLimitException,
    BiginQuotaExhaustedException,
)
from app.services.oauth_manager import InvalidRefreshTokenException

logger = logging.getLogger("app.tasks")

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 30

@shared_task(
    bind=True,
    rate_limit="60/m",
    max_retries=MAX_RETRIES,
    name="app.tasks.lead_tasks.create_or_update_bigin_lead_task"
)
def create_or_update_bigin_lead_task(self, lead_id: int):
    """
    Asynchronous task to sync a Lead to Zoho Bigin.
    Calls BiginClient.create_lead if lead has no bigin_lead_id, or BiginClient.update_lead if bigin_lead_id exists.
    """
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            logger.error(f"Lead ID {lead_id} not found in database.")
            return

        lead.status = LeadStatus.PROCESSING.value
        db.commit()

        lead_data = {
            "customer_name": lead.customer_name,
            "phone": lead.phone,
            "message": lead.message,
            "msg91_contact_id": lead.msg91_contact_id,
            "source": lead.source,
        }

        client = BiginClient()

        try:
            if not lead.bigin_lead_id:
                # Create Lead in Bigin
                bigin_id = client.create_lead(lead_data)
                lead.bigin_lead_id = bigin_id
                logger.info(f"Successfully created Bigin Lead ID '{bigin_id}' for Lead {lead.id} ({lead.phone}).")
            else:
                # Update existing Lead in Bigin
                bigin_id = client.update_lead(lead.bigin_lead_id, lead_data)
                logger.info(f"Successfully updated Bigin Lead ID '{bigin_id}' for Lead {lead.id} ({lead.phone}).")

            lead.status = LeadStatus.CREATED.value
            lead.error_message = None
            db.commit()

        except BiginRateLimitException as rate_err:
            lead.retry_count = self.request.retries + 1
            lead.status = LeadStatus.THROTTLED.value
            lead.error_message = str(rate_err)
            db.commit()

            backoff = BASE_BACKOFF_SECONDS * (2 ** self.request.retries)
            logger.warning(f"Rate limited by Bigin API. Retrying Lead {lead.id} in {backoff}s.")
            raise self.retry(exc=rate_err, countdown=backoff, max_retries=MAX_RETRIES)

        except BiginQuotaExhaustedException as quota_err:
            lead.status = LeadStatus.THROTTLED.value
            lead.error_message = "Daily Bigin API quota exhausted. Pausing task retry."
            db.commit()
            logger.error(f"Daily quota limit hit for Lead {lead.id}. Pausing processing.")
            raise self.retry(exc=quota_err, countdown=3600, max_retries=MAX_RETRIES)

        except InvalidRefreshTokenException as oauth_err:
            lead.status = LeadStatus.FAILED.value
            lead.error_message = "OAuth refresh token invalid or revoked. Requires re-authorization."
            db.commit()
            logger.critical(f"Operational Alert: Bigin OAuth token revoked for Lead {lead.id}. Stopping job.")

        except BiginAPIException as api_err:
            if self.request.retries < MAX_RETRIES:
                lead.retry_count = self.request.retries + 1
                lead.status = LeadStatus.RETRYING.value
                lead.error_message = str(api_err)
                db.commit()

                backoff = BASE_BACKOFF_SECONDS * (2 ** self.request.retries)
                logger.warning(f"Bigin API error on Lead {lead.id}: {api_err}. Retrying in {backoff}s.")
                raise self.retry(exc=api_err, countdown=backoff, max_retries=MAX_RETRIES)
            else:
                lead.status = LeadStatus.FAILED.value
                lead.error_message = f"Max retries reached. Last error: {api_err}"
                db.commit()
                logger.error(f"Lead {lead.id} failed permanently after {MAX_RETRIES} retries: {api_err}")

        except Exception as unhandled_err:
            lead.status = LeadStatus.FAILED.value
            lead.error_message = f"Unhandled error: {str(unhandled_err)}"
            db.commit()
            logger.error(f"Unexpected error processing Lead {lead.id}: {unhandled_err}")

    finally:
        db.close()


@shared_task(
    bind=True,
    name="app.tasks.lead_tasks.run_full_reconciliation_task"
)
def run_full_reconciliation_task(self):
    """
    Scheduled Celery Beat task that fetches the full contact list from MSG91 API,
    reconciles missing local Lead records, and retries any unpushed / failed Bigin Leads.
    This task is idempotent and safe to run repeatedly.
    """
    logger.info("Starting scheduled full reconciliation sync with MSG91 API...")
    msg91_client = MSG91Client()

    try:
        contacts = msg91_client.fetch_all_contacts()
    except MSG91APIException as exc:
        logger.error(f"Reconciliation failed during MSG91 contact fetching: {exc}")
        return {"status": "failed", "error": str(exc)}

    db = SessionLocal()
    created_count = 0
    enqueued_count = 0
    now = datetime.now(timezone.utc)

    try:
        for contact in contacts:
            phone = contact.get("phone")
            if not phone:
                continue

            existing_lead = db.query(Lead).filter(Lead.phone == phone).first()

            if not existing_lead:
                # Missing lead -> Create local record
                new_lead = Lead(
                    customer_name=contact.get("customer_name"),
                    phone=phone,
                    msg91_contact_id=contact.get("msg91_contact_id"),
                    last_event_type=LeadEventType.CONTACT_ADDED.value,
                    source="WhatsApp",
                    status=LeadStatus.RECEIVED.value,
                    last_event_at=now,
                )
                db.add(new_lead)
                db.commit()
                db.refresh(new_lead)
                created_count += 1

                # Enqueue Bigin creation
                create_or_update_bigin_lead_task.delay(new_lead.id)
                enqueued_count += 1
            else:
                # Existing lead -> check if retry needed (bigin_lead_id is null or status is FAILED)
                if not existing_lead.bigin_lead_id or existing_lead.status == LeadStatus.FAILED.value:
                    logger.info(f"Reconciliation re-triggering Bigin sync for Lead {existing_lead.id} ({phone}).")
                    create_or_update_bigin_lead_task.delay(existing_lead.id)
                    enqueued_count += 1

        logger.info(f"Reconciliation sync completed. Contacts processed: {len(contacts)}, New leads created: {created_count}, Jobs enqueued: {enqueued_count}.")
        return {
            "status": "success",
            "total_contacts": len(contacts),
            "new_leads_created": created_count,
            "jobs_enqueued": enqueued_count,
        }
    finally:
        db.close()
