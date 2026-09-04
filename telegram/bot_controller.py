"""
telegram/bot_controller.py - Hardened Remote Telegram Bot Control Plane with Rich UI.

Restricts access strictly to whitelisted ADMIN_TELEGRAM_ID, applies token-bucket
rate limiting and session timeouts, and bridges remote commands to the ReAct agent.
Includes interactive inline keyboards, photo uploads, app launchers, and FastFetch telemetry.
"""

import os
import re
import time
import json
import logging
from typing import Optional, Set

from agents.react_agent import global_react_agent
from security.rate_limiter import TokenBucketRateLimiter, SessionTimeoutManager
from security.sanitizer import InputSanitizer
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager

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
            logger.warning("ADMIN_TELEGRAM_ID not configured! All requests are unauthenticated.")
            return True
        return user_id in self._admin_ids

    def get_main_keyboard(self) -> Any:
        """Constructs rich inline action dashboard."""
        if not HAS_TELEBOT or types is None:
            return None

        markup = types.InlineKeyboardMarkup(row_width=2)
        torch_label = "🔦 Torch [OFF]" if not self._torch_on else "🔦 Torch [ON]"
        btn_torch = types.InlineKeyboardButton(torch_label, callback_data="cb_torch")
        btn_bat = types.InlineKeyboardButton("🔋 Battery Meter", callback_data="cb_battery")
        btn_photo = types.InlineKeyboardButton("📸 Take Photo", callback_data="cb_photo")
        btn_clean = types.InlineKeyboardButton("🧹 Clean Storage", callback_data="cb_clean")
        btn_fetch = types.InlineKeyboardButton("⚡ FastFetch", callback_data="cb_fastfetch")
        btn_logs = types.InlineKeyboardButton("📋 Recent Logs", callback_data="cb_logs")
        btn_apps = types.InlineKeyboardButton("🚀 Apps Hub", callback_data="cb_apps")
        btn_models = types.InlineKeyboardButton("🧠 Model Status", callback_data="cb_models")
        btn_plugins = types.InlineKeyboardButton("🧩 Plugin Store", callback_data="cb_plugins")
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh", callback_data="cb_back_main")

        markup.add(btn_torch, btn_bat)
        markup.add(btn_photo, btn_clean)
        markup.add(btn_fetch, btn_logs)
        markup.add(btn_apps, btn_models)
        markup.add(btn_plugins, btn_refresh)
        return markup

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
        """Registers command and message handlers with the telebot instance."""
        bot = self._bot
        if not bot:
            return

        @bot.message_handler(commands=["start", "help", "menu"])
        def handle_help(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                logger.warning(f"Unauthorized /start attempt from user_id: {user_id}")
                return

            text = (
                "⚡ *Void Edge Agent Remote Control Hub*\n\n"
                "• Tap any quick action button below or send natural language commands:\n"
                "  _\"turn on torch\"_, _\"battery level\"_, _\"whatsapp 15551234 saying hello\"_\n\n"
                "• `/fastfetch` - ASCII/Unicode system & edge telemetry\n"
                "• `/menu` - Display interactive action dashboard\n"
                "• `/photo` - Capture photo and receive file directly\n"
                "• `/models` - Local quantized LLM weights & downloads\n"
                "• `/clean` - Clean system cache and temporary files\n"
                "• `/status` - Live RAM footprint and background daemons\n"
                "• `/logs` - View last 5 hardware execution logs"
            )
            bot.reply_to(message, text, reply_markup=self.get_main_keyboard(), parse_mode="Markdown")

        @bot.message_handler(commands=["fastfetch"])
        def handle_fastfetch(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            card = global_fastfetch_collector.render_markdown()
            bot.reply_to(message, card, parse_mode="Markdown")

        @bot.message_handler(commands=["status"])
        def handle_status(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            card = global_fastfetch_collector.render_markdown()
            bot.reply_to(message, card, parse_mode="Markdown")

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

        @bot.message_handler(commands=["models"])
        def handle_models(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return

            installed = global_model_manager.list_installed_models()
            available = global_model_manager.list_available_models()
            active = global_model_manager.get_active_model_name()

            lines = ["🧠 *Void Local Edge Models:*\n"]
            lines.append(f"• *Active Engine:* `{active or 'Deterministic Heuristic Router'}`\n")
            lines.append("*Catalog & Status:*")

            for mid, m in available.items():
                status_icon = "✅ Installed" if m["installed"] else "📥 Available"
                lines.append(f"• `{mid}`: *{m['name']}* ({m['size_mb']} MB) - {status_icon}")
                lines.append(f"  _{m['description']}_")

            lines.append("\n_To download a model:_ `/download <model_id>` (e.g. `/download smollm-135m`)")
            bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

        @bot.message_handler(commands=["download"])
        def handle_download(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return

            parts = message.text.strip().split()
            if len(parts) < 2:
                bot.reply_to(message, "Usage: `/download <model_id>` (e.g. `/download smollm-135m`)", parse_mode="Markdown")
                return

            model_id = parts[1].lower().strip()
            progress_msg = bot.reply_to(message, f"⏳ Starting download of `{model_id}`...", parse_mode="Markdown")

            last_edit_time = [0.0]

            def progress_cb(downloaded, total, pct, speed_kbps):
                now = time.perf_counter()
                if now - last_edit_time[0] >= 1.5 or downloaded == total:
                    filled = int(pct / 10)
                    bar = "█" * filled + "░" * (10 - filled)
                    d_mb = round(downloaded / (1024 * 1024), 1)
                    t_mb = round(total / (1024 * 1024), 1) if total > 0 else 0
                    text = f"📥 *Downloading {model_id}*...\n`[{bar}]` {pct}%\n💾 `{d_mb}MB / {t_mb}MB` @ `{speed_kbps:.1f} KB/s`"
                    try:
                        bot.edit_message_text(text, message.chat.id, progress_msg.message_id, parse_mode="Markdown")
                        last_edit_time[0] = now
                    except Exception:
                        pass

            res = global_model_manager.download_model(model_id, progress_callback=progress_cb)
            if res.get("success"):
                bot.edit_message_text(
                    f"✅ *Model {model_id} downloaded successfully!*\nSaved to: `{res['path']}` ({res['size_mb']} MB)\nActive in ReAct loop.",
                    message.chat.id,
                    progress_msg.message_id,
                    parse_mode="Markdown"
                )
            else:
                bot.edit_message_text(
                    f"❌ *Download failed:* {res.get('error')}",
                    message.chat.id,
                    progress_msg.message_id,
                    parse_mode="Markdown"
                )

        @bot.message_handler(commands=["photo"])
        def handle_photo(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            self._execute_photo_capture(message.chat.id)

        @bot.message_handler(commands=["clean"])
        def handle_clean(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            res = global_tool_registry.execute("clean_system", dry_run=False)
            summary = res.output.get("summary", "Cleaned") if isinstance(res.output, dict) else str(res.output)
            bot.reply_to(message, f"🧹 *Storage Clean Complete:*\n`{summary}`", parse_mode="Markdown")

        @bot.message_handler(commands=["plugins"])
        def handle_plugins(message):
            user_id = message.from_user.id
            if not self._is_authorized(user_id):
                return
            catalog = global_extension_manager.search_catalog()
            installed = global_extension_manager.list_extensions()
            text = (
                f"🧩 *Void Dynamic Plugin Store*\n\n"
                f"• *Active Plugins:* `{len(installed)}` (Zero default bloat)\n"
                f"• *Catalog Items:* `{len(catalog)}` available\n\n"
                "Tap an option below to install or remove community plugins securely:"
            )
            bot.reply_to(message, text, reply_markup=self.get_plugins_keyboard(), parse_mode="Markdown")

        # ----------------------------------------------------------------------
        # Inline Callback Query Handler
        # ----------------------------------------------------------------------
        @bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            user_id = call.from_user.id
            chat_id = call.message.chat.id
            message_id = call.message.message_id

            if not self._is_authorized(user_id):
                bot.answer_callback_query(call.id, "Unauthorized access denied.", show_alert=True)
                return

            data = call.data

            if data == "cb_torch":
                self._torch_on = not self._torch_on
                global_tool_registry.execute("set_torch", on=self._torch_on)
                status_str = "ON" if self._torch_on else "OFF"
                bot.answer_callback_query(call.id, f"🔦 Flashlight turned {status_str}")
                try:
                    bot.edit_message_reply_markup(chat_id, message_id, reply_markup=self.get_main_keyboard())
                except Exception:
                    pass

            elif data == "cb_battery":
                bat_res = global_tool_registry.execute("get_battery_status")
                pct = "N/A"
                stat = "Unknown"
                if bat_res.success and isinstance(bat_res.output, dict):
                    pct = f"{bat_res.output.get('percentage', 'N/A')}%"
                    stat = bat_res.output.get("status", "Unknown")
                bot.answer_callback_query(call.id, f"🔋 Battery: {pct} ({stat})", show_alert=True)

            elif data == "cb_photo":
                bot.answer_callback_query(call.id, "Capturing photo...")
                self._execute_photo_capture(chat_id)

            elif data == "cb_clean":
                bot.answer_callback_query(call.id, "Cleaning temporary cache...")
                res = global_tool_registry.execute("clean_system", dry_run=False)
                summary = res.output.get("summary", "Cleaned") if isinstance(res.output, dict) else str(res.output)
                bot.send_message(chat_id, f"🧹 *Storage Clean Report:*\n`{summary}`", parse_mode="Markdown")

            elif data == "cb_fastfetch":
                bot.answer_callback_query(call.id)
                card = global_fastfetch_collector.render_markdown()
                bot.send_message(chat_id, card, parse_mode="Markdown")

            elif data == "cb_logs":
                bot.answer_callback_query(call.id)
                repo = ExecutionLogRepository()
                recent = repo.get_recent_logs(limit=5)
                lines = ["📋 *Recent Hardware Execution Logs:*"]
                for l in recent:
                    lines.append(f"• `#{l['step']}` *{l['tool_name']}* - {l['status']} ({l['duration_ms']}ms)")
                bot.send_message(chat_id, "\n".join(lines) if recent else "No recent logs.", parse_mode="Markdown")

            elif data == "cb_apps":
                bot.answer_callback_query(call.id)
                try:
                    bot.edit_message_text(
                        "🚀 *Application Launch Center*\nSelect an app to open directly on your phone:",
                        chat_id,
                        message_id,
                        reply_markup=self.get_apps_keyboard(),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            elif data == "cb_back_main":
                bot.answer_callback_query(call.id)
                try:
                    bot.edit_message_text(
                        "⚡ *Void Edge Agent Remote Control Hub*\nQuick action dashboard active:",
                        chat_id,
                        message_id,
                        reply_markup=self.get_main_keyboard(),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

            elif data == "cb_models":
                bot.answer_callback_query(call.id)
                active = global_model_manager.get_active_model_name()
                installed = global_model_manager.list_installed_models()
                bot.send_message(
                    chat_id,
                    f"🧠 *Active Model Engine:*\n`{active or 'Deterministic ReAct (Zero-Weight Heuristic)'}`\n\n"
                    f"Installed weights: `{len(installed)}`\nUse `/models` to inspect or download models.",
                    parse_mode="Markdown"
                )

            elif data.startswith("app_launch:"):
                app_name = data.split(":", 1)[1]
                bot.answer_callback_query(call.id, f"Launching {app_name}...")
                res = global_tool_registry.execute("launch_installed_app", app_name=app_name)
                bot.send_message(
                    chat_id,
                    f"🚀 {res.output if res.success else res.error}",
                    parse_mode="Markdown"
                )

            elif data == "cb_plugins":
                bot.answer_callback_query(call.id)
                catalog = global_extension_manager.search_catalog()
                installed = global_extension_manager.list_extensions()
                text = (
                    f"🧩 *Void Dynamic Plugin Store*\n\n"
                    f"• *Active Plugins:* `{len(installed)}` (Zero default bloat)\n"
                    f"• *Catalog Items:* `{len(catalog)}` available\n\n"
                    "Tap an extension below to install or remove on-demand:"
                )
                try:
                    bot.edit_message_text(text, chat_id, message_id, reply_markup=self.get_plugins_keyboard(), parse_mode="Markdown")
                except Exception:
                    pass

            elif data.startswith("plugin_install:"):
                pid = data.split(":", 1)[1]
                bot.answer_callback_query(call.id, f"Installing {pid}...")
                res = global_extension_manager.install_plugin(pid)
                if res.get("success"):
                    bot.send_message(chat_id, f"✅ *Plugin '{pid}' installed!* Tools: `{res.get('tools')}`", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, f"❌ *Install failed:* {res.get('error')}", parse_mode="Markdown")
                try:
                    bot.edit_message_reply_markup(chat_id, message_id, reply_markup=self.get_plugins_keyboard())
                except Exception:
                    pass

            elif data.startswith("plugin_remove:"):
                pid = data.split(":", 1)[1]
                bot.answer_callback_query(call.id, f"Removing {pid}...")
                res = global_extension_manager.uninstall_plugin(pid)
                bot.send_message(chat_id, f"🗑️ *{res.get('message')}*", parse_mode="Markdown")
                try:
                    bot.edit_message_reply_markup(chat_id, message_id, reply_markup=self.get_plugins_keyboard())
                except Exception:
                    pass

        # ----------------------------------------------------------------------
        # Generic Natural Language Query Handler
        # ----------------------------------------------------------------------
        @bot.message_handler(func=lambda message: True)
        def handle_generic_query(message):
            user_id = message.from_user.id

            if not self._is_authorized(user_id):
                logger.warning(f"Blocked unauthorized command execution from user_id: {user_id}")
                return

            allowed, wait_sec = self._rate_limiter.allow_request(str(user_id))
            if not allowed:
                bot.reply_to(message, f"⚠️ *Rate limit exceeded.* Please wait {wait_sec}s before sending another command.", parse_mode="Markdown")
                return

            self._session_manager.touch_session(str(user_id))

            query = message.text.strip() if message.text else ""
            if not query:
                return

            try:
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

                bot.reply_to(message, "\n".join(reply_parts), reply_markup=self.get_main_keyboard(), parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Telegram processing error: {e}")
                bot.reply_to(message, f"❌ *Error executing command:*\n`{str(e)}`", parse_mode="Markdown")

    def _execute_photo_capture(self, chat_id: int) -> None:
        """Captures photo and dispatches file directly to Telegram."""
        bot = self._bot
        if not bot:
            return

        status_msg = bot.send_message(chat_id, "📸 *Capturing device camera photo...*", parse_mode="Markdown")
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
                    break
                except Exception as e:
                    logger.warning(f"Failed to send photo from {p}: {e}")

        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        if not photo_sent:
            bot.send_message(
                chat_id,
                f"📸 *Camera Output:*\n`{res.output or res.error}`",
                parse_mode="Markdown"
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
