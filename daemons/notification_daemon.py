"""
daemons/notification_daemon.py - Smart Notification Interceptor & Auto-Summarizer.

Monitors incoming Android notifications via termux-notification-list, performs
local regex keyword classification, extracts OTP verification codes, and silences spam.
"""

import re
import time
import json
import logging
import threading
from typing import Set, Optional, Dict, Any

from core.types import NotificationRecord, NotificationCategory
from core.command_executor import SecureCommandExecutor
from core.event_bus import global_event_bus
from storage.repository import NotificationRepository, ClipboardRepository
from tools.registry import global_tool_registry

logger = logging.getLogger("VoidAdvancedCore.NotifDaemon")

# Regex for OTP code extraction (4-8 digits accompanied by auth keywords)
OTP_REGEX = re.compile(r"\b(\d{4,8})\b")
OTP_KEYWORDS = {"otp", "code", "verification", "passcode", "secret", "pin", "auth"}
SPAM_KEYWORDS = {"winner", "lottery", "prize", "discount", "promo", "loan", "free cash", "click here", "deal"}
URGENT_KEYWORDS = {"alert", "security", "warning", "bank", "fraud", "unauthorized", "urgent", "failed"}


class NotificationInterceptorDaemon:
    """Background worker continuously inspecting Android push notifications."""
    __slots__ = (
        "_interval",
        "_running",
        "_thread",
        "_seen_ids",
        "_repo",
        "_clipboard_repo",
        "_event_bus",
        "_lock",
    )

    def __init__(self, interval_seconds: float = 12.0):
        self._interval = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._seen_ids: Set[str] = set()
        self._repo = NotificationRepository()
        self._clipboard_repo = ClipboardRepository()
        self._event_bus = global_event_bus
        self._lock = threading.Lock()

    def start(self) -> None:
        """Launches the background daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="NotificationDaemon", daemon=True)
            self._thread.start()
            logger.info("NotificationInterceptorDaemon started.")

    def stop(self) -> None:
        """Gracefully signals the worker loop to terminate."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("NotificationInterceptorDaemon stopped.")

    def _run_loop(self) -> None:
        """Main periodic polling cycle."""
        while self._running:
            try:
                self.process_notifications()
            except Exception as e:
                logger.error(f"Error during notification inspection: {e}")
            time.sleep(self._interval)

    def process_notifications(self) -> None:
        """Pulls notification list and executes zero-copy streaming analysis."""
        res = SecureCommandExecutor.run(["termux-notification-list"], timeout=4)
        if not res or res.startswith("Error"):
            return

        for item in SecureCommandExecutor.stream_parse_json(res):
            notif_id = str(item.get("id") or item.get("key") or "")
            if not notif_id or notif_id in self._seen_ids:
                continue

            # Record seen ID (bounded window)
            self._seen_ids.add(notif_id)
            if len(self._seen_ids) > 200:
                self._seen_ids = set(list(self._seen_ids)[-100:])

            pkg = str(item.get("packageName", "unknown"))
            title = str(item.get("title", ""))
            content = str(item.get("content", ""))

            self._evaluate_single_notification(notif_id, pkg, title, content)

    def _evaluate_single_notification(self, notif_id: str, pkg: str, title: str, content: str) -> None:
        """Classifies notification, detects OTPs, and handles spam suppression."""
        combined_text = f"{title} {content}".lower()

        # 1. OTP Extraction
        is_otp = False
        extracted_otp: Optional[str] = None
        has_otp_keyword = any(k in combined_text for k in OTP_KEYWORDS)

        if has_otp_keyword:
            matches = OTP_REGEX.findall(combined_text)
            if matches:
                # Select the match that is 4-8 digits
                extracted_otp = matches[0]
                is_otp = True

        # 2. Category Classification
        if is_otp:
            category = NotificationCategory.OTP
        elif any(k in combined_text for k in SPAM_KEYWORDS):
            category = NotificationCategory.SPAM
        elif any(k in combined_text for k in URGENT_KEYWORDS):
            category = NotificationCategory.URGENT
        elif any(app in pkg.lower() for app in ("messaging", "whatsapp", "telegram", "sms")):
            category = NotificationCategory.MESSAGE
        else:
            category = NotificationCategory.GENERAL

        record = NotificationRecord(
            id=notif_id,
            package_name=pkg,
            title=title,
            content=content,
            timestamp=time.time(),
            category=category,
            is_otp=is_otp,
            otp_code=extracted_otp,
        )

        # Persist to database
        self._repo.upsert(record)
        self._event_bus.publish("notification_intercepted", record.to_dict())

        # 3. Proactive Automated Responses
        if is_otp and extracted_otp:
            logger.info(f"Proactive Action: Extracted OTP '{extracted_otp}'. Copying to clipboard.")
            self._clipboard_repo.record_clipboard(extracted_otp)
            global_tool_registry.execute("set_clipboard", text=extracted_otp)
            global_tool_registry.execute(
                "show_toast",
                message=f"OTP {extracted_otp} copied to clipboard.",
            )

        elif category == NotificationCategory.SPAM:
            logger.info(f"Proactive Action: Suppressing spam notification ID: {notif_id}")
            SecureCommandExecutor.run(["termux-notification-remove", notif_id])
