import time
import logging
import requests
from app.config import settings

logger = logging.getLogger("app.oauth")

EXPIRY_BUFFER_SECONDS = 120  # 2 minute buffer before actual expiry

class InvalidRefreshTokenException(Exception):
    """Raised when the Zoho Bigin refresh token is invalid or revoked."""
    pass

class ZohoOAuthManager:
    """
    Manages OAuth 2.0 Access Token generation and in-memory caching for Zoho Bigin.
    Tokens are stored in memory with automatic expiration handling.
    """

    _cached_token: str = None
    _expiry_timestamp: float = 0.0

    def __init__(self, client_id: str = None, client_secret: str = None, refresh_token: str = None, accounts_url: str = None):
        self.client_id = client_id or settings.BIGIN_CLIENT_ID
        self.client_secret = client_secret or settings.BIGIN_CLIENT_SECRET
        self.refresh_token = refresh_token or settings.BIGIN_REFRESH_TOKEN
        self.accounts_url = (accounts_url or settings.BIGIN_ACCOUNTS_URL).rstrip("/")

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Returns a valid Bigin access token.
        If missing, expired, or within 2-min buffer zone, fetches a new token.
        """
        if not force_refresh and ZohoOAuthManager._cached_token and ZohoOAuthManager._expiry_timestamp:
            current_time = time.time()
            if current_time + EXPIRY_BUFFER_SECONDS < ZohoOAuthManager._expiry_timestamp:
                logger.debug("Using cached valid Bigin access token.")
                return ZohoOAuthManager._cached_token
            else:
                logger.info("Cached Bigin token within 2-min buffer of expiry. Refreshing...")

        return self.refresh_access_token()

    def refresh_access_token(self) -> str:
        """
        Requests a new access token from Zoho OAuth endpoint.
        """
        if not self.client_id or not self.client_secret or not self.refresh_token:
            logger.error("Zoho OAuth credentials incomplete in environment.")
            raise InvalidRefreshTokenException("OAuth credentials missing in server configuration.")

        token_url = f"{self.accounts_url}/oauth/v2/token"
        params = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }

        logger.info("Requesting new access token from Zoho OAuth endpoint.")

        try:
            response = requests.post(token_url, params=params, timeout=10)
        except requests.RequestException as exc:
            logger.error(f"Network error contacting Zoho OAuth endpoint: {exc}")
            raise Exception(f"OAuth network error: {exc}") from exc

        if response.status_code != 200:
            logger.error(f"OAuth token refresh failed with status {response.status_code}: {response.text}")
            if response.status_code in (400, 401) or "invalid_code" in response.text or "invalid_token" in response.text:
                raise InvalidRefreshTokenException("Zoho Bigin refresh token is invalid or revoked. Operational alert triggered.")
            raise Exception(f"Zoho OAuth token request failed with status {response.status_code}")

        data = response.json()
        if "error" in data:
            error_msg = data.get("error")
            logger.error(f"Zoho OAuth response error: {error_msg}")
            if error_msg in ("invalid_code", "invalid_token", "invalid_client", "invalid_grant"):
                raise InvalidRefreshTokenException(f"Revoked/Invalid refresh token: {error_msg}")
            raise Exception(f"Zoho OAuth error: {error_msg}")

        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        if not access_token:
            logger.error("No access_token found in Zoho OAuth response.")
            raise Exception("Access token missing in OAuth response.")

        current_time = time.time()
        ZohoOAuthManager._cached_token = access_token
        ZohoOAuthManager._expiry_timestamp = current_time + expires_in

        logger.info("Successfully refreshed and cached new Bigin access token.")
        return access_token
