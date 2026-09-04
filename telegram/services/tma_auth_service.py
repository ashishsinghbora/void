"""
telegram/services/tma_auth_service.py - Cryptographic HMAC-SHA256 TMA Authentication.

Implements Telegram's official specification for validating Telegram Mini App
initData signatures to authenticate users connecting from embedded Web Apps.
"""

import time
import json
import hmac
import hashlib
import urllib.parse
from typing import Tuple, Optional, Dict, Any


class TelegramMiniAppAuthService:
    """Validates Telegram WebApp initData string using HMAC-SHA256 signature checking."""

    @staticmethod
    def validate_init_data(
        init_data_raw: str,
        bot_token: str,
        max_age_seconds: int = 86400,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validates initData query string according to Telegram specification:
        1. Parse key-value pairs from initData string.
        2. Extract and strip 'hash'.
        3. Sort items alphabetically and format as 'key=value\n'.
        4. Derive secret key: HMAC-SHA256(b"WebAppData", bot_token).
        5. Verify HMAC-SHA256(secret_key, data_check_string) == received hash.
        6. Verify auth_date freshness within max_age_seconds.

        Returns (is_valid, user_data_dict, error_reason).
        """
        if not init_data_raw or not bot_token:
            return False, None, "Missing init_data or bot_token"

        try:
            parsed = urllib.parse.parse_qsl(init_data_raw, keep_blank_values=True)
            params = dict(parsed)
        except Exception as e:
            return False, None, f"Malformed query string: {e}"

        received_hash = params.pop("hash", None)
        if not received_hash:
            return False, None, "Missing 'hash' parameter in initData"

        # Check freshness
        auth_date_raw = params.get("auth_date")
        if not auth_date_raw or not auth_date_raw.isdigit():
            return False, None, "Invalid or missing 'auth_date'"

        auth_date = int(auth_date_raw)
        now = int(time.time())
        if now - auth_date > max_age_seconds:
            return False, None, f"initData expired (age: {now - auth_date}s, max: {max_age_seconds}s)"

        # Sort remaining keys alphabetically
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

        # Compute secret key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        # Compute expected hash = HMAC_SHA256(secret_key, data_check_string)
        expected_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            return False, None, "HMAC-SHA256 signature mismatch (tampered payload)"

        # Extract parsed user object if present
        user_data = None
        if "user" in params:
            try:
                user_data = json.loads(params["user"])
            except Exception:
                user_data = {"raw": params["user"]}

        return True, user_data, None


global_tma_auth_service = TelegramMiniAppAuthService()
