import logging
import requests
from typing import Dict, Any
from app.config import settings
from .oauth_manager import ZohoOAuthManager, InvalidRefreshTokenException

logger = logging.getLogger("app.bigin")

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
    Handles lead creation and update under the "Leads" stage of "All Leads - We Do Finserv".
    """

    def __init__(self, oauth_manager: ZohoOAuthManager = None, api_domain: str = None, module_name: str = None, pipeline_stage: str = None):
        self.oauth_manager = oauth_manager or ZohoOAuthManager()
        self.api_domain = (api_domain or settings.BIGIN_API_DOMAIN).rstrip("/")
        self.module_name = module_name or settings.BIGIN_MODULE_NAME
        self.pipeline_stage = pipeline_stage or settings.BIGIN_PIPELINE_STAGE

    def create_lead(self, lead_data: Dict[str, Any]) -> str:
        """
        Creates a Lead record in Zoho Bigin in the 'Leads' pipeline stage.
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

    def update_lead(self, bigin_lead_id: str, lead_data: Dict[str, Any]) -> str:
        """
        Updates an existing Lead record in Zoho Bigin.
        """
        payload = self._build_lead_payload(lead_data)
        access_token = self.oauth_manager.get_access_token()

        try:
            return self._make_put_request_with_retry(bigin_lead_id, payload, access_token)
        except InvalidRefreshTokenException:
            raise
        except Exception as exc:
            logger.error(f"Error updating lead {bigin_lead_id} in Bigin: {exc}")
            raise

    def _build_lead_payload(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps MSG91 lead dictionary to Zoho Bigin field structure.
        """
        customer_name = str(lead_data.get("customer_name") or "WhatsApp Lead").strip() or "WhatsApp Lead"

        record = {
            "Last_Name": customer_name,
            "Phone": str(lead_data.get("phone", "")),
            "Mobile": str(lead_data.get("phone", "")),
            "Description": str(lead_data.get("message", "")),
            "Lead_Source": str(lead_data.get("source", "WhatsApp")),
            "External_Contact_ID": str(lead_data.get("msg91_contact_id", "")),
            "Pipeline_Stage": self.pipeline_stage,
        }

        return {"data": [record]}

    def _make_post_request_with_retry(self, payload: Dict[str, Any], access_token: str, is_retry: bool = False) -> str:
        url = f"{self.api_domain}/bigin/v2/{self.module_name}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }

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

        raise BiginAPIException(f"Bigin API call failed with status code {status_code}")

    def _make_put_request_with_retry(self, bigin_lead_id: str, payload: Dict[str, Any], access_token: str, is_retry: bool = False) -> str:
        url = f"{self.api_domain}/bigin/v2/{self.module_name}/{bigin_lead_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.put(url, json=payload, headers=headers, timeout=15)
        except requests.RequestException as req_err:
            raise BiginAPIException(f"Network error communicating with Bigin API: {req_err}") from req_err

        status_code = response.status_code

        if status_code == 401:
            if not is_retry:
                logger.warning(f"Bigin returned 401 on update {bigin_lead_id}. Retrying with forced token refresh...")
                new_token = self.oauth_manager.get_access_token(force_refresh=True)
                return self._make_put_request_with_retry(bigin_lead_id, payload, new_token, is_retry=True)
            else:
                raise BiginAPIException("Unauthorized: Access token rejected by Bigin API.")

        if status_code == 429:
            raise BiginRateLimitException("Bigin API rate limit hit (HTTP 429).")

        if status_code in (200, 201):
            return self._parse_success_response(response.json(), fallback_id=bigin_lead_id)

        body_text = response.text
        if "LIMIT_EXCEEDED" in body_text or "MAX_DAILY_CALLS_EXCEEDED" in body_text:
            raise BiginQuotaExhaustedException("Bigin API daily limit exceeded.")

        raise BiginAPIException(f"Bigin API update failed with status code {status_code}")

    def _parse_success_response(self, resp_json: Dict[str, Any], fallback_id: str = None) -> str:
        data_list = resp_json.get("data", [])
        if data_list and isinstance(data_list, list):
            result = data_list[0]
            status = result.get("status")
            if status == "SUCCESS":
                details = result.get("details", {})
                lead_id = details.get("id") or fallback_id
                if lead_id:
                    return str(lead_id)

            code = result.get("code")
            message = result.get("message", "Unknown error from Bigin")
            if code in ("INVALID_DATA", "MANDATORY_NOT_FOUND", "DUPLICATE_DATA"):
                raise BiginAPIException(f"Bigin API Validation Error [{code}]: {message}")

        if fallback_id:
            return str(fallback_id)

        raise BiginAPIException(f"Unexpected response format: {resp_json}")
