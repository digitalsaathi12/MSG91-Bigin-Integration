import time
from unittest.mock import patch, MagicMock
from app.services.oauth_manager import (
    ZohoOAuthManager,
    InvalidRefreshTokenException,
    _memory_cache,
    CACHE_KEY_ACCESS_TOKEN,
    CACHE_KEY_EXPIRY,
)

class TestZohoOAuthManager:

    def setup_method(self):
        _memory_cache.clear()
        self.oauth_manager = ZohoOAuthManager(
            client_id="test_client",
            client_secret="test_secret",
            refresh_token="test_refresh",
            accounts_url="https://accounts.zoho.com",
        )

    def test_get_access_token_uses_valid_cached_token(self):
        future_expiry = time.time() + 3600
        _memory_cache[CACHE_KEY_ACCESS_TOKEN] = "cached_valid_token_123"
        _memory_cache[CACHE_KEY_EXPIRY] = future_expiry

        token = self.oauth_manager.get_access_token()
        assert token == "cached_valid_token_123"

    @patch("requests.post")
    def test_get_access_token_refreshes_when_near_expiry(self, mock_post):
        near_expiry = time.time() + 60
        _memory_cache[CACHE_KEY_ACCESS_TOKEN] = "expiring_token"
        _memory_cache[CACHE_KEY_EXPIRY] = near_expiry

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "fresh_new_token_456",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        token = self.oauth_manager.get_access_token()

        assert token == "fresh_new_token_456"
        mock_post.assert_called_once()
        assert _memory_cache[CACHE_KEY_ACCESS_TOKEN] == "fresh_new_token_456"

    @patch("requests.post")
    def test_refresh_token_revoked_raises_exception(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "invalid_code"}'
        mock_resp.json.return_value = {"error": "invalid_code"}
        mock_post.return_value = mock_resp

        try:
            self.oauth_manager.refresh_access_token()
            assert False, "Expected InvalidRefreshTokenException"
        except InvalidRefreshTokenException:
            pass
