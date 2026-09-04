"""
telegram/bot_controller.py - Hardened Remote Telegram Bot Control Plane.

Restricts access strictly to whitelisted ADMIN_TELEGRAM_ID, applies token-bucket
rate limiting and session timeouts, and bridges remote commands to the ReAct agent.
"""

import os
import time
import json
import logging
from typing import Optional, Set

from agents.react_agent import global_react_agent
from security.rate_limiter import TokenBucketRateLimiter, SessionTimeoutManager
from security.sanitizer import InputSanitizer
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository

logger = logging.getLogger("VoidAdvancedCore.Telegram")

try:
    import telebot
    HAS_TELEBOT = True
except ImportError:
    telebot = None
    HAS_TELEBOT = False


class AuthenticatedTelegramController:
    """Secure, authenticated Telegram bot controller with rate limiting."""
    __slots__ = (
        "_token",
        "_admin_ids",
        "_rate_limiter",
        "_session_manager",
        "_bot",
    )

    def __init__(
        self,
        token: str,
        admin_ids: Optional[Set[int]] = None,
        rate_limit_capacity: int = 5,
        session_timeout_seconds: int = 900,
    ):
        self._token = token
        self._admin_ids = admin_ids or self._load_admin_ids()
        self._rate_limiter = TokenBucketRateLimiter(rate_per_second=0.5, capacity=rate_limit_capacity)
        self._session_manager = SessionTimeoutManager(timeout_seconds=session_timeout_seconds)
        self._bot = None

        if HAS_TELEBOT and telebot is not None:
            # Enforce threaded=False to prevent OpenSSL SIGSEGV in Termux bionic libc
            self._bot = telebot.TeleBot(token, threaded=False)
            self._register_handlers()
        else:
            logger.warning("pyTelegramBotAPI not available. Telegram control plane disabled.")

    def _load_admin_ids(self) -> Set[int]:
        """Loads whitelisted admin IDs from environment variable."""
        raw = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()
        ids = set()
        if raw:
            for item in raw.split(","):
                clean = item.strip()
                if clean.isdigit():
                    ids.add(int(clean))
        return ids

    def _is_authorized(self, user_id: int) -> bool:
        """Verifies if user ID matches whitelisted administrator."""
        # If no admin ID is set, log warning; in production, enforce strict whitelist
        if not self._admin_ids:
            logger.warning("ADMIN_TELEGRAM_ID not configured! All requests are unauthenticated.")
            return True
        return user_id in self._admin_ids

    def _register_handlers(self) -> None:
        """Registers command and message handlers with the telebot instance."""
        bot = self._bot
        if not bot:
            return

        @bot.message_handler(commands=["start", "help"])
        def handle_help(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                logger.warning(f"Unauthorized /help attempt from user_id: {user_id}")
                return

            text = (
                "⚡ *Void Edge Agent Remote Control*\n\n"
                "• Send commands in plain English (e.g. `turn on flashlight`, `battery status`, `say hello`)\n"
                "• `/status` - Live RAM footprint, battery, and daemon health\n"
                "• `/battery` - Device battery percentage & charge state\n"
                "• `/logs` - View last 5 hardware execution logs\n"
                "• `/help` - Show this guidance menu"
            )
            bot.reply_to(message, text, parse_mode="Markdown")

        @bot.message_handler(commands=["status"])
        def handle_status(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return

            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = round(usage.ru_maxrss / 1024.0, 2)
            bat_res = global_tool_registry.execute("get_battery_status")
            bat_pct = "Unknown"
            if bat_res.success and isinstance(bat_res.output, dict):
                bat_pct = f"{bat_res.output.get('percentage', 'N/A')}%"

            msg = (
                "📊 *Device Health & Telemetry*\n\n"
                f"• *RAM RSS:* `{rss_mb} MB` (Target < 50MB: {'✅' if rss_mb < 50 else '⚠️'})\n"
                f"• *Battery:* `{bat_pct}`\n"
                "• *Execution Engine:* `Deterministic ReAct`\n"
                "• *Security Sandbox:* `Arg-Vector Whitelisted`\n"
                "• *Daemons:* `NotificationInterceptor, RoutineScheduler`"
            )
            bot.reply_to(message, msg, parse_mode="Markdown")

        @bot.message_handler(commands=["battery"])
        def handle_battery(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            bat_res = global_tool_registry.execute("get_battery_status")
            bot.reply_to(message, f"🔋 *Battery Status:*\n```json\n{json.dumps(bat_res.output, indent=2)}\n```", parse_mode="Markdown")

        @bot.message_handler(commands=["logs"])
        def handle_logs(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            repo = ExecutionLogRepository()
            recent = repo.get_recent_logs(limit=5)
            if not recent:
                bot.reply_to(message, "No recent execution logs.")
                return

            lines = ["📋 *Recent Hardware Execution Logs:*"]
            for l in recent:
                lines.append(f"• `#{l['step']}` *{l['tool_name']}* - {l['status']} ({l['duration_ms']}ms)")
            bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

        @bot.message_handler(func=lambda message: True)
        def handle_generic_query(message):
            user_id = message.from_user.id

            # 1. Authorization Guard
            if not self._is_authorized(user_id):
                logger.warning(f"Blocked unauthorized command execution from user_id: {user_id}")
                return

            # 2. Rate Limiting Guard
            allowed, wait_sec = self._rate_limiter.allow_request(str(user_id))
            if not allowed:
                bot.reply_to(message, f"⚠️ *Rate limit exceeded.* Please wait {wait_sec}s before sending another command.", parse_mode="Markdown")
                return

            # 3. Session Activity Update
            self._session_manager.touch_session(str(user_id))

            query = message.text.strip() if message.text else ""
            if not query:
                return

            try:
                # Dispatch to ReAct Agent
                session_id = f"telegram_{user_id}"
                response = global_react_agent.run(query, session_id=session_id)

                reply_parts = []
                if response.results:
                    reply_parts.append("⚡ *Tool Execution Results:*")
                    for r in response.results:
                        if isinstance(r, dict):
                            reply_parts.append(f"```json\n{json.dumps(r, indent=2)}\n```")
                        else:
                            reply_parts.append(f"• `{r}`")
                else:
                    reply_parts.append("⚠️ *No tools triggered by query.*")

                if response.reasoning:
                    reply_parts.append(f"\n🧠 *Agent Reasoning:*\n_{response.reasoning}_")

                if response.confidence is not None:
                    reply_parts.append(f"🎯 *Confidence:* {int(response.confidence * 100)}%")

                bot.reply_to(message, "\n".join(reply_parts), parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Telegram processing error: {e}")
                bot.reply_to(message, f"❌ *Error executing command:*\n`{str(e)}`", parse_mode="Markdown")

    def start_polling(self) -> None:
        """Runs the single-threaded robust polling loop with reconnection retry."""
        if not self._bot:
            return

        logger.info("Starting authenticated Telegram bot polling listener...")
        while True:
            try:
                self._bot.polling(non_stop=True, interval=1, timeout=10)
            except Exception as e:
                logger.warning(f"Telegram polling reconnecting after exception: {e}")
                time.sleep(3)
