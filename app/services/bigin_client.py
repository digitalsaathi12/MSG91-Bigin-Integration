import json
import logging
import requests
from typing import Dict, Any
from app.config import settings
from .oauth_manager import ZohoOAuthManager, InvalidRefreshTokenException

logger = logging.getLogger("app.bigin")


def normalize_phone_for_bigin(phone: str) -> str:
    """
    Normalizes an Indian WhatsApp phone number to 10 digits for the Bigin Phone field
    (which has a maximum_length of 10).

    Steps:
    1. Strip leading '+' and any spaces or dashes.
    2. If the number starts with '91' and is longer than 10 digits, strip the leading '91'.
    3. Log a warning if the result is not exactly 10 digits, but still return it.
    """
    # Remove +, spaces, dashes
    digits = phone.strip().lstrip("+").replace(" ", "").replace("-", "")

    # Strip '91' country code when number is longer than 10 digits
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[2:]

    if len(digits) != 10:
        logger.warning(
            f"Phone number '{phone}' normalized to '{digits}' which is not 10 digits "
            f"(got {len(digits)}). Sending as-is."
        )

    return digits

class BiginAPIException(Exception):
    """General Bigin API error exception."""
    pass

class BiginRateLimitException(Exception):
    """HTTP 429 Rate limit exceeded."""
    pass

class BiginQuotaExhaustedException(Exception):
    """Daily API quota exhausted."""
    pass

class BiginClient:
    """
    REST API client for Zoho Bigin.
    Handles lead creation under the configured pipeline/layout using OAuth tokens.
    """

    def __init__(
        self,
        oauth_manager: ZohoOAuthManager = None,
        api_domain: str = None,
        module_name: str = None,
        sub_pipeline: str = None,
        pipeline_entry_stage: str = None,
        pipeline_name: str = None,
        layout_id: str = None,
    ):
        self.oauth_manager = oauth_manager or ZohoOAuthManager()
        self.api_domain = (api_domain or settings.BIGIN_API_DOMAIN).rstrip("/")
        self.module_name = module_name or settings.BIGIN_MODULE_NAME
        # Sub_Pipeline actual_value selecting the target pipeline board ("Customer Onboarding Standard")
        self.sub_pipeline = sub_pipeline or getattr(settings, "BIGIN_SUB_PIPELINE", "Customer Onboarding Standard")
        # Stage actual_value selecting the entry stage within that board ("Documentation")
        self.pipeline_entry_stage = pipeline_entry_stage or settings.BIGIN_PIPELINE_STAGE
        # Pipeline display name (cosmetic/logging reference)
        self.pipeline_name = pipeline_name or settings.BIGIN_PIPELINE_NAME
        # Layout ID from GET /bigin/v2/settings/layouts?module=Pipelines
        self.layout_id = layout_id or settings.BIGIN_LAYOUT_ID

        # ── DIAGNOSTIC: log resolved config values at startup ──────────────────
        logger.warning(
            "[DIAG] BiginClient config resolved — "
            "BIGIN_LAYOUT_ID=%r (type=%s) | "
            "BIGIN_SUB_PIPELINE=%r (type=%s) | "
            "BIGIN_PIPELINE_STAGE=%r (type=%s) | "
            "BIGIN_PIPELINE_NAME=%r",
            self.layout_id, type(self.layout_id).__name__,
            self.sub_pipeline, type(self.sub_pipeline).__name__,
            self.pipeline_entry_stage, type(self.pipeline_entry_stage).__name__,
            self.pipeline_name,
        )
        # ── END DIAGNOSTIC ─────────────────────────────────────────────────────

    def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """
        Creates a Lead record directly in Zoho Bigin.
        """
        payload = self._build_lead_payload(lead_data)
        access_token = self.oauth_manager.get_access_token()

        try:
            return self._make_post_request_with_retry(payload, access_token)
        except InvalidRefreshTokenException:
            raise
        except Exception as exc:
            logger.error(f"Error creating lead in Bigin: {exc}")
            raise

    def _build_lead_payload(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        raw_phone = str(lead_data.get("phone", ""))
        normalized_phone = normalize_phone_for_bigin(raw_phone) if raw_phone else ""

        # Deal_Name is the mandatory primary/name field for Bigin's Pipelines module.
        customer_name = (lead_data.get("customer_name") or "").strip()
        deal_name = customer_name if customer_name else f"WhatsApp Lead - {normalized_phone or raw_phone}"

        record = {
            # --- Required: primary name field ---
            "Deal_Name": deal_name,

            # --- Required: Pipeline (layout/board selector, bigint field, plain string value per API v2) ---
            "Pipeline": self.layout_id,

            # --- Required: Sub_Pipeline (pipeline board selector) ---
            # actual_value = "Customer Onboarding Standard"
            "Sub_Pipeline": self.sub_pipeline,

            # --- Required: Stage (entry stage selector within the board) ---
            # actual_value = "Documentation" (display_label = "Leads")
            "Stage": self.pipeline_entry_stage,

            # --- Contact / phone fields ---
            "Phone": normalized_phone,
            "Mobile": normalized_phone,

            # --- Additional context fields ---
            "Description": str(lead_data.get("message", "")),
            "Lead_Source": str(lead_data.get("source", "WhatsApp")),
        }

        return {"data": [record]}

    def _make_post_request_with_retry(self, payload: Dict[str, Any], access_token: str, is_retry: bool = False) -> str:
        url = f"{self.api_domain}/bigin/v2/{self.module_name}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }

        # ── DIAGNOSTIC: dump full outgoing payload before POST ─────────────────
        record = payload.get("data", [{}])[0]
        pipeline_val = record.get("Pipeline")
        sub_pipeline_val = record.get("Sub_Pipeline")
        logger.warning(
            "[DIAG] About to POST to %s\n"
            "Full payload:\n%s\n"
            "--- Pipeline value=%r  type=%s ---\n"
            "--- Sub_Pipeline value=%r  type=%s  repr=%s ---",
            url,
            json.dumps(payload, indent=2, default=str),
            pipeline_val, type(pipeline_val).__name__,
            sub_pipeline_val, type(sub_pipeline_val).__name__,
            repr(sub_pipeline_val),
        )
        # ── END DIAGNOSTIC ─────────────────────────────────────────────────────

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
        except requests.RequestException as req_err:
            raise BiginAPIException(f"Network error communicating with Bigin API: {req_err}") from req_err

        status_code = response.status_code

        if status_code == 401:
            if not is_retry:
                logger.warning("Bigin returned 401 Unauthorized. Retrying with forced token refresh...")
                new_token = self.oauth_manager.get_access_token(force_refresh=True)
                return self._make_post_request_with_retry(payload, new_token, is_retry=True)
            else:
                raise BiginAPIException("Unauthorized: Access token rejected by Bigin API.")

        if status_code == 429:
            raise BiginRateLimitException("Bigin API rate limit hit (HTTP 429).")

        if status_code in (200, 201):
            return self._parse_success_response(response.json())

        body_text = response.text
        if "LIMIT_EXCEEDED" in body_text or "MAX_DAILY_CALLS_EXCEEDED" in body_text:
            raise BiginQuotaExhaustedException("Bigin API daily limit exceeded.")

        raise BiginAPIException(f"Bigin API call failed with status code {status_code}: {body_text}")

    def _parse_success_response(self, resp_json: Dict[str, Any]) -> str:
        data_list = resp_json.get("data", [])
        if data_list and isinstance(data_list, list):
            result = data_list[0]
            status = result.get("status")
            if status == "SUCCESS":
                details = result.get("details", {})
                lead_id = details.get("id")
                if lead_id:
                    return str(lead_id)

            code = result.get("code")
            message = result.get("message", "Unknown error from Bigin")
            if code in ("INVALID_DATA", "MANDATORY_NOT_FOUND", "DUPLICATE_DATA"):
                raise BiginAPIException(f"Bigin API Validation Error [{code}]: {message}")

        raise BiginAPIException(f"Unexpected response format: {resp_json}")
