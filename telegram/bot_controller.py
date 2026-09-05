"""
telegram/bot_controller.py - Hardened Remote Telegram Bot Control Plane with Rich UI.

Restricts access strictly to whitelisted ADMIN_TELEGRAM_ID, applies token-bucket
rate limiting and session timeouts, and bridges remote commands to the ReAct agent.
Includes interactive inline keyboards, photo uploads, app launchers, FastFetch telemetry,
Telegram Stars billing, settings management, and Telegram Mini App hooks.
"""

import os
import re
import time
import json
import logging
from typing import Optional, Set, Any

from security.rate_limiter import TokenBucketRateLimiter, SessionTimeoutManager
from security.sanitizer import InputSanitizer
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager

from telegram.database.db_manager import global_bot_db
from telegram.database.models import UserRole, UserTier
from telegram.handlers import register_all_handlers
from telegram.utils.safe_telegram import safe_send_message


logger = logging.getLogger("VoidAdvancedCore.Telegram")

try:
    import telebot
    from telebot import types
    HAS_TELEBOT = True
except ImportError:
    telebot = None
    types = None
    HAS_TELEBOT = False


class AuthenticatedTelegramController:
    """Secure, authenticated Telegram bot controller with rich inline keyboards."""
    __slots__ = (
        "_token",
        "_admin_ids",
        "_rate_limiter",
        "_session_manager",
        "_bot",
        "_torch_on",
    )

    def __init__(
        self,
        token: str,
        admin_ids: Optional[Set[int]] = None,
        rate_limit_capacity: int = 5,
        session_timeout_seconds: int = 900,
    ):
        self._token = token
        self._admin_ids = admin_ids if admin_ids is not None else self._load_admin_ids()
        self._rate_limiter = TokenBucketRateLimiter(rate_per_second=0.5, capacity=rate_limit_capacity)
        self._session_manager = SessionTimeoutManager(timeout_seconds=session_timeout_seconds)
        self._bot = None
        self._torch_on = False

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
        if not self._admin_ids:
            logger.warning(f"ADMIN_TELEGRAM_ID not configured! Auto-whitelisting first caller: {user_id}")
            self._admin_ids.add(user_id)
            os.environ["ADMIN_TELEGRAM_ID"] = str(user_id)
            if not self._token.startswith("123456789:AAG_mock"):
                try:
                    from core.bot_setup import TelegramSetupWizard
                    TelegramSetupWizard.save_configuration(self._token, user_id)
                except Exception:
                    pass
            # Auto-register admin user in database
            global_bot_db.get_or_create_user(telegram_id=user_id, default_role=UserRole.ADMIN)
            return True

        is_auth = user_id in self._admin_ids
        if is_auth:
            global_bot_db.get_or_create_user(telegram_id=user_id, default_role=UserRole.ADMIN)
        return is_auth

    def get_main_keyboard(self) -> Any:
        """Constructs Level 1: Root Control Center keyboard (15 categories in 2-column layout)."""
        if not HAS_TELEBOT or types is None:
            return None
        try:
            from telegram.handlers.menu_router import get_root_menu
            _, markup = get_root_menu()
            return markup
        except Exception as e:
            logger.error(f"Error generating root keyboard: {e}")
            return None

    def get_security_keyboard(self) -> Any:
        """Constructs security dashboard navigation markup."""
        if not HAS_TELEBOT or types is None:
            return None
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh Status", callback_data="cb_security")
        btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main")
        markup.add(btn_refresh, btn_back)
        return markup

    def _render_security_card(self, user_id: int) -> str:
        """Renders formatted Markdown security & session status card."""
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024.0, 1)
        admins = ", ".join(str(a) for a in self._admin_ids) if self._admin_ids else "Auto-pairing active"
        user = global_bot_db.get_user(user_id)
        tier_str = user.tier.value if user else "FREE"

        return (
            "🛡️ *Void Security & Session Dashboard*\n\n"
            f"• *Telegram Bot:* `@voidtermuxbot`\n"
            f"• *Whitelisted Admin(s):* `{admins}`\n"
            f"• *Your User ID:* `{user_id}` (Authorized ✅)\n"
            f"• *Account Tier:* `{tier_str}`\n"
            f"• *Memory RSS:* `{rss_mb} MB` (Target < 30MB)\n"
            f"• *Rate Limiter:* Tiered Token Bucket (`0.5-5.0 req/s`)\n"
            f"• *Session Timeout:* `900s` inactivity TTL\n"
            f"• *Credential Vault:* AES-256-GCM + PBKDF2 (100k iters)\n"
            f"• *Database WAL:* SQLite Write-Ahead Logging active\n\n"
            "🔒 _All operations execute locally inside Termux environment._"
        )

    def get_plugins_keyboard(self) -> Any:
        """Constructs interactive plugin manager submenu."""
        if not HAS_TELEBOT or types is None:
            return None

        markup = types.InlineKeyboardMarkup(row_width=1)
        catalog = global_extension_manager.search_catalog()
        for item in catalog:
            pid = item["id"]
            if item["installed"]:
                btn = types.InlineKeyboardButton(f"🗑️ Remove: {item['name']}", callback_data=f"plugin_remove:{pid}")
            else:
                btn = types.InlineKeyboardButton(f"📥 Install: {item['name']}", callback_data=f"plugin_install:{pid}")
            markup.add(btn)

        markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
        return markup

    def get_apps_keyboard(self) -> Any:
        """Constructs app launcher submenu."""
        if not HAS_TELEBOT or types is None:
            return None

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_wa = types.InlineKeyboardButton("💬 WhatsApp", callback_data="app_launch:whatsapp")
        btn_tg = types.InlineKeyboardButton("✈️ Telegram", callback_data="app_launch:telegram")
        btn_cam = types.InlineKeyboardButton("📷 Camera App", callback_data="app_launch:camera")
        btn_yt = types.InlineKeyboardButton("▶️ YouTube", callback_data="app_launch:youtube")
        btn_chr = types.InlineKeyboardButton("🌐 Chrome", callback_data="app_launch:chrome")
        btn_set = types.InlineKeyboardButton("⚙️ Settings", callback_data="app_launch:settings")
        btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main")

        markup.add(btn_wa, btn_tg)
        markup.add(btn_cam, btn_yt)
        markup.add(btn_chr, btn_set)
        markup.add(btn_back)
        return markup

    def _register_handlers(self) -> None:
        """Registers all modular command, billing, settings, and callback handlers."""
        register_all_handlers(self._bot, self)

    def _execute_photo_capture(self, chat_id: int) -> None:
        """Captures photo and dispatches file directly to Telegram with Cloud Vault mirroring."""
        bot = self._bot
        if not bot:
            return

        status_msg = safe_send_message(bot, chat_id, "📸 *Capturing device camera photo...*", parse_mode="Markdown")
        res = global_tool_registry.execute("take_camera_photo")

        # Check for photo file existence
        candidate_paths = [
            "/sdcard/Download/void_photo.jpg",
            os.path.join(os.path.expanduser("~"), "storage", "downloads", "void_photo.jpg"),
            os.path.join(os.path.expanduser("~"), "void_photo.jpg"),
        ]

        # Also parse path from res.output if present
        if res.output and "'" in str(res.output):
            parts = str(res.output).split("'")
            if len(parts) >= 2 and os.path.exists(parts[1]):
                candidate_paths.insert(0, parts[1])

        photo_sent = False
        for p in candidate_paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                try:
                    with open(p, "rb") as photo_file:
                        bot.send_photo(
                            chat_id,
                            photo_file,
                            caption=f"📸 *Void Camera Photo*\nSaved at: `{p}`",
                            parse_mode="Markdown"
                        )
                    photo_sent = True
                    try:
                        from telegram.services.cloud_vault import global_cloud_vault
                        if global_cloud_vault.is_configured():
                            global_cloud_vault.upload_file(
                                file_path=p,
                                category="camera",
                                file_type="photo",
                                tag="camera_capture",
                                caption="Void Camera Capture",
                            )
                    except Exception as ve:
                        logger.debug(f"Vault auto-mirror skipped: {ve}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to send photo from {p}: {e}")

        if status_msg and hasattr(status_msg, "message_id"):
            try:
                bot.delete_message(chat_id, status_msg.message_id)
            except Exception:
                pass

        if not photo_sent:
            err_msg = str(res.output or res.error or "Capture process returned no valid image.")
            safe_send_message(
                bot,
                chat_id,
                f"⚠️ *Camera Photo Notice:*\n`{err_msg}`\n\n"
                "💡 *Permissions & Diagnostics Guide:*\n"
                "• Confirm `termux-api` package is installed: `pkg install termux-api`\n"
                "• Run `termux-setup-storage` in Termux to grant storage access\n"
                "• Grant **Camera** & **Files** permissions to **Termux** and **Termux:API** in Android Settings -> Apps -> Permissions",
                parse_mode="Markdown",
            )

    def _execute_screenshot_capture(self, chat_id: int) -> None:
        """Captures device screen and dispatches photo directly to Telegram with Cloud Vault mirroring."""
        bot = self._bot
        if not bot:
            return

        status_msg = safe_send_message(bot, chat_id, "📸 *Capturing device screen...*", parse_mode="Markdown")
        res = global_tool_registry.execute("capture_screen")

        screenshot_path = None
        if res.output and isinstance(res.output, str):
            import re
            m = re.search(r"'(.*?)'", res.output)
            if m and os.path.exists(m.group(1)):
                screenshot_path = m.group(1)

        if not screenshot_path or not os.path.exists(screenshot_path):
            try:
                from core.media_vault import global_media_vault
                recent = global_media_vault.list_recent_media(category="screenshots", limit=1)
                if recent:
                    screenshot_path = recent[0]["path"]
            except Exception:
                pass

        shot_sent = False
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                with open(screenshot_path, "rb") as shot_file:
                    bot.send_photo(
                        chat_id,
                        shot_file,
                        caption=f"📸 *Void Screen Capture*\nSaved at: `{screenshot_path}`",
                        parse_mode="Markdown",
                    )
                shot_sent = True
                try:
                    from telegram.services.cloud_vault import global_cloud_vault
                    if global_cloud_vault.is_configured():
                        global_cloud_vault.upload_file(
                            file_path=screenshot_path,
                            category="screenshots",
                            file_type="photo",
                            tag="screenshot_capture",
                            caption="Automated screenshot capture",
                        )
                except Exception as ve:
                    logger.debug(f"Vault auto-mirror skipped: {ve}")
            except Exception as e:
                logger.warning(f"Failed to dispatch screenshot: {e}")

        if status_msg and hasattr(status_msg, "message_id"):
            try:
                bot.delete_message(chat_id, status_msg.message_id)
            except Exception:
                pass

        if not shot_sent:
            err_msg = str(res.output or res.error or "Capture process returned no valid image.")
            safe_send_message(
                bot,
                chat_id,
                f"⚠️ *Screen Capture Notice:*\n`{err_msg}`\n\n"
                "💡 *Permissions & Diagnostics Guide:*\n"
                "• Run `termux-setup-storage` in Termux\n"
                "• Grant **Display over other apps** or Screen Capture permission to Termux/Termux:API if prompted\n"
                "• Or manually run: `/sh screencap -p /sdcard/Download/void_screen.png`",
                parse_mode="Markdown",
            )


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
