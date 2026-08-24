import time
import logging
import requests
import redis
from app.config import settings

logger = logging.getLogger("app.oauth")

CACHE_KEY_ACCESS_TOKEN = "bigin_oauth_access_token"
CACHE_KEY_EXPIRY = "bigin_oauth_token_expiry"
EXPIRY_BUFFER_SECONDS = 120  # 2 minute buffer before expiry

# In-memory token cache fallback if Redis is unavailable
_memory_cache = {}

class InvalidRefreshTokenException(Exception):
    """Raised when the Zoho Bigin refresh token is invalid or revoked."""
    pass

class ZohoOAuthManager:
    """
    Manages OAuth 2.0 Access Token generation and caching for Zoho Bigin.
    Uses Redis cache with in-memory fallback.
    """

    def __init__(self, client_id: str = None, client_secret: str = None, refresh_token: str = None, accounts_url: str = None):
        self.client_id = client_id or settings.BIGIN_CLIENT_ID
        self.client_secret = client_secret or settings.BIGIN_CLIENT_SECRET
        self.refresh_token = refresh_token or settings.BIGIN_REFRESH_TOKEN
        self.accounts_url = (accounts_url or settings.BIGIN_ACCOUNTS_URL).rstrip("/")
        self._redis_client = None

    def _get_redis(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis.from_url(settings.REDIS_CACHE_URL, decode_responses=True, socket_timeout=2)
                self._redis_client.ping()
            except Exception:
                self._redis_client = False
        return self._redis_client if self._redis_client is not False else None

    def _cache_get(self, key: str):
        r = self._get_redis()
        if r:
            try:
                val = r.get(key)
                if val:
                    return float(val) if key == CACHE_KEY_EXPIRY else str(val)
            except Exception:
                pass
        return _memory_cache.get(key)

    def _cache_set(self, key: str, value, ttl: int):
        r = self._get_redis()
        if r:
            try:
                r.set(key, str(value), ex=ttl)
            except Exception:
                pass
        _memory_cache[key] = value

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Returns a valid Bigin access token.
        If missing, expired, or within 2-min buffer zone, fetches a new token.
        """
        if not force_refresh:
            cached_token = self._cache_get(CACHE_KEY_ACCESS_TOKEN)
            expiry_time = self._cache_get(CACHE_KEY_EXPIRY)

            if cached_token and expiry_time:
                try:
                    expiry_float = float(expiry_time)
                    current_time = time.time()
                    if current_time + EXPIRY_BUFFER_SECONDS < expiry_float:
                        logger.debug("Using cached valid Bigin access token.")
                        return str(cached_token)
                    else:
                        logger.info("Cached Bigin token within 2-min buffer of expiry. Refreshing...")
                except (ValueError, TypeError):
                    pass

        return self.refresh_access_token()

    def refresh_access_token(self) -> str:
        """
        Requests a new access token from Zoho OAuth endpoint.
        """
        if not self.client_id or not self.client_secret or not self.refresh_token:
            logger.error("Zoho OAuth credentials incomplete.")
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
        expiry_timestamp = current_time + expires_in
        cache_ttl = max(1, expires_in - EXPIRY_BUFFER_SECONDS)

        self._cache_set(CACHE_KEY_ACCESS_TOKEN, access_token, cache_ttl)
        self._cache_set(CACHE_KEY_EXPIRY, expiry_timestamp, cache_ttl)

        logger.info("Successfully refreshed and cached new Bigin access token.")
        return access_token
