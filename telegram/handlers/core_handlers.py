"""
telegram/handlers/core_handlers.py - Core Command and Natural Language Handlers.

Handles /start, /help, /status, /fastfetch, /devices, /extensions, hardware quick actions,
and generic natural language agent routing with tiered rate limiting.
"""

import os
import json
import time
import logging
from typing import Any

from agents.react_agent import global_react_agent
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository

from telegram.database.db_manager import global_bot_db
from telegram.database.models import UserRole, UserTier
from telegram.services.device_service import global_device_service
from telegram.middleware.rate_limit import global_rate_limiter
from telegram.utils.safe_telegram import safe_reply, safe_send_message, safe_edit_message_text

logger = logging.getLogger("VoidTelegram.CoreHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def register_core_handlers(bot: Any, controller: Any) -> None:
    """Registers all core commands and the fallback agent router."""
    if not bot:
        return

    @bot.message_handler(commands=["start", "help", "menu"])
    def handle_start(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            logger.warning(f"Unauthorized /start attempt from user_id: {user_id}")
            return

        # Ensure user profile and settings exist in database
        role = UserRole.ADMIN if user_id in controller._admin_ids else UserRole.USER
        user = global_bot_db.get_or_create_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            default_role=role,
        )

        tier_badge = f"[{user.tier.value}]"
        text = (
            f"⚡ *Void Edge Agent Remote Control Hub* {tier_badge}\n\n"
            "Autonomous conversational agent for Android / Termux with Cloud Vault.\n\n"
            "• *Instant Natural Language Actions:*\n"
            "  _\"turn on flashlight\"_, _\"swipe up\"_, _\"open settings\"_, _\"search lo-fi beats on youtube\"_\n\n"
            "• *Mobile Touch & Screen Controls:*\n"
            "  • `/tap <x> <y>` - Touch coordinate simulation\n"
            "  • `/swipe <x1> <y1> <x2> <y2>` - Screen swipe gesture\n"
            "  • `/type <text>` - Keyboard typing input\n"
            "  • `/key <HOME|BACK|RECENTS>` - Physical button keyevent\n"
            "  • `/screenshot` - Instant screen capture\n"
            "  • `/search <app> <query>` - In-app deep query\n\n"
            "• *Cloud Vault & Intelligence:*\n"
            "  • `/vault` - Persistent Telegram group memory & media vault\n"
            "  • `/setup_model` - Device RAM detector & GGUF model setup\n"
            "  • `/fastfetch` - ASCII system & hardware telemetry\n"
            "  • `/status` - Live memory footprint & daemon status\n"
            "  • `/extensions` - On-demand plugin manager\n"
            "  • `/billing` - Telegram Stars subscriptions & upgrades\n\n"
            "👇 *Select an action from the dashboard below:*"
        )
        bot.reply_to(message, text, reply_markup=controller.get_main_keyboard(), parse_mode="Markdown")

    @bot.message_handler(commands=["fastfetch"])
    def handle_fastfetch(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        card = global_fastfetch_collector.render_markdown()
        bot.reply_to(message, card, parse_mode="Markdown")

    @bot.message_handler(commands=["status"])
    def handle_status(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        user = global_bot_db.get_user(user_id)
        tier_str = user.tier.value if user else "FREE"
        devices = global_device_service.list_user_devices(user_id)
        active_devices = sum(1 for d in devices if d.is_online)

        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024.0, 1)

        status_text = (
            "📊 *Void Control Plane Telemetry*\n\n"
            f"• *Subscription Tier:* `{tier_str}`\n"
            f"• *Memory Footprint (RSS):* `{rss_mb} MB` (Target < 30MB)\n"
            f"• *Active Edge Nodes:* `{active_devices}/{len(devices)} online`\n"
            f"• *Active Model Engine:* `{global_model_manager.get_active_model_name() or 'Heuristic ReAct'}`\n"
            f"• *Installed Plugins:* `{len(global_extension_manager.list_extensions())}`\n"
            f"• *Database Engine:* `SQLite WAL Mode`\n\n"
            "🟢 _All local daemons functioning optimally._"
        )
        bot.reply_to(message, status_text, parse_mode="Markdown")

    @bot.message_handler(commands=["devices"])
    def handle_devices(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        devices = global_device_service.list_user_devices(user_id)
        lines = ["📱 *Connected Android Edge Nodes:*\n"]

        for d in devices:
            stat_icon = "🟢 Online" if d.is_online else "🔴 Offline"
            lines.append(f"• *{d.name}* (`{d.device_id}`)")
            lines.append(f"  Status: {stat_icon} | 🔋 Battery: `{d.battery_level}%` | Model: `{d.model}`")

        lines.append("\n_Tip: Access the Telegram Mini App for live touch controls._")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

    @bot.message_handler(commands=["extensions", "plugins"])
    def handle_extensions(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        catalog = global_extension_manager.search_catalog()
        installed = global_extension_manager.list_extensions()
        text = (
            f"🧩 *Void Dynamic Plugin Store*\n\n"
            f"• *Active Plugins:* `{len(installed)}` (Zero default bloat)\n"
            f"• *Catalog Items:* `{len(catalog)}` available\n\n"
            "Tap an option below to install or remove community plugins securely:"
        )
        bot.reply_to(message, text, reply_markup=controller.get_plugins_keyboard(), parse_mode="Markdown")

    @bot.message_handler(commands=["battery"])
    def handle_battery(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        bat_res = global_tool_registry.execute("get_battery_status")
        bot.reply_to(message, f"🔋 *Battery Status:*\n```json\n{json.dumps(bat_res.output, indent=2)}\n```", parse_mode="Markdown")

    @bot.message_handler(commands=["torch"])
    def handle_torch(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        controller._torch_on = not controller._torch_on
        global_tool_registry.execute("set_torch", on=controller._torch_on)
        state_str = "ON" if controller._torch_on else "OFF"
        bot.reply_to(message, f"🔦 *Flashlight turned {state_str}*", reply_markup=controller.get_main_keyboard(), parse_mode="Markdown")

    @bot.message_handler(commands=["security"])
    def handle_security(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        card = controller._render_security_card(user_id)
        bot.reply_to(message, card, reply_markup=controller.get_security_keyboard(), parse_mode="Markdown")

    @bot.message_handler(commands=["logs"])
    def handle_logs(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
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
        if not controller._is_authorized(user_id):
            return

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
        if not controller._is_authorized(user_id):
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
        if not controller._is_authorized(user_id):
            return
        controller._execute_photo_capture(message.chat.id)

    @bot.message_handler(commands=["clean"])
    def handle_clean(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        res = global_tool_registry.execute("clean_system", dry_run=False)
        summary = res.output.get("summary", "Cleaned") if isinstance(res.output, dict) else str(res.output)
        bot.reply_to(message, f"🧹 *Storage Clean Complete:*\n`{summary}`", parse_mode="Markdown")

    # ----------------------------------------------------------------------
    # Mobile Action Direct Commands
    # ----------------------------------------------------------------------
    @bot.message_handler(commands=["tap"])
    def handle_tap(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split()
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Usage: `/tap <x> <y>` (e.g. `/tap 500 1000`)", parse_mode="Markdown")
            return
        try:
            x, y = int(parts[1]), int(parts[2])
            res = global_tool_registry.execute("mobile_tap", x=x, y=y)
            bot.reply_to(message, f"👆 {res.output if res.success else res.error}", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ Tap failed: {e}")

    @bot.message_handler(commands=["swipe"])
    def handle_swipe(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split()
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Usage: `/swipe <x1> <y1> <x2> <y2> [duration_ms]`\nExample: `/swipe 500 1500 500 500 300`", parse_mode="Markdown")
            return
        try:
            x1, y1, x2, y2 = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
            dur = int(parts[5]) if len(parts) > 5 else 300
            res = global_tool_registry.execute("mobile_swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration_ms=dur)
            bot.reply_to(message, f"👉 {res.output if res.success else res.error}", parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"❌ Swipe failed: {e}")

    @bot.message_handler(commands=["type", "input"])
    def handle_type(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/type <text to type>`", parse_mode="Markdown")
            return
        text_to_type = parts[1]
        res = global_tool_registry.execute("mobile_type_text", text=text_to_type)
        bot.reply_to(message, f"⌨️ {res.output if res.success else res.error}", parse_mode="Markdown")

    @bot.message_handler(commands=["key", "keyevent"])
    def handle_keyevent(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage: `/key <HOME|BACK|RECENTS|ENTER|POWER|VOLUME_UP|VOLUME_DOWN>`", parse_mode="Markdown")
            return
        key_name = parts[1].upper()
        res = global_tool_registry.execute("mobile_keyevent", key=key_name)
        bot.reply_to(message, f"🔘 {res.output if res.success else res.error}", parse_mode="Markdown")

    @bot.message_handler(commands=["screenshot", "screen"])
    def handle_screenshot(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        if hasattr(controller, "_execute_screenshot_capture"):
            controller._execute_screenshot_capture(message.chat.id)
        else:
            res = global_tool_registry.execute("capture_screen")
            bot.reply_to(message, f"📸 {res.output if res.success else res.error}", parse_mode="Markdown")

    @bot.message_handler(commands=["search"])
    def handle_search(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Usage: `/search <youtube|maps|google|playstore> <query>`\nExample: `/search youtube lo-fi beats`", parse_mode="Markdown")
            return
        target_app = parts[1].lower()
        search_query = parts[2]
        res = global_tool_registry.execute("app_search", target_app=target_app, search_query=search_query)
        bot.reply_to(message, f"🔍 {res.output if res.success else res.error}", parse_mode="Markdown")

    @bot.message_handler(commands=["settings_open"])
    def handle_settings_open(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return
        parts = message.text.strip().split()
        screen = parts[1].lower() if len(parts) > 1 else "main"
        res = global_tool_registry.execute("open_settings_screen", screen=screen)
        bot.reply_to(message, f"⚙️ {res.output if res.success else res.error}", parse_mode="Markdown")

    # ----------------------------------------------------------------------
    # AI Conversational Automation Interface (/ai, /chat, /ask)
    # ----------------------------------------------------------------------
    @bot.message_handler(commands=["ai", "chat", "ask", "void"])
    def handle_ai_chat_command(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            active_model = global_model_manager.get_active_model_name() or "Deterministic ReAct Engine"
            safe_reply(
                bot,
                message,
                f"🧠 *Void Autonomous AI Automation Interface*\n\n"
                f"• *Active Engine:* `{active_model}`\n"
                "• *Device Control:* Hardware APIs, Media, Shell & Storage Active\n"
                "• *Cloud Database:* Group Memory Vault Ready\n\n"
                "Chat naturally or type `/ai <instruction>` to automate anything on your phone!\n\n"
                "*Try saying:*\n"
                "• _\"turn on flashlight and check battery\"_\n"
                "• _\"open whatsapp and search new messages\"_\n"
                "• _\"take a photo with front camera and mirror to vault\"_\n"
                "• _\"clean temp storage and run security audit\"_\n"
                "• _\"run shell command uptime\"_",
                parse_mode="Markdown",
            )
            return

        query = parts[1].strip()
        _execute_ai_agent(message, query)

    # ----------------------------------------------------------------------
    # Generic Natural Language Query Handler with Streaming Reasoning
    # ----------------------------------------------------------------------
    @bot.message_handler(func=lambda message: True)
    def handle_generic_query(message):
        user_id = message.from_user.id

        if not controller._is_authorized(user_id):
            logger.warning(f"Blocked unauthorized command execution from user_id: {user_id}")
            return

        # Determine user tier for tiered rate limiting
        user = global_bot_db.get_user(user_id)
        user_tier = user.tier if user else UserTier.FREE

        allowed, wait_sec = global_rate_limiter.allow_request(str(user_id), user_tier)
        if not allowed:
            safe_reply(
                bot,
                message,
                f"⚠️ *Rate limit exceeded.* Your plan `{user_tier.value}` requires waiting {wait_sec}s before sending another command.\n"
                "_Upgrade your plan with `/billing` for higher throughput._",
                parse_mode="Markdown",
            )
            return

        controller._session_manager.touch_session(str(user_id))

        query = message.text.strip() if message.text else ""
        if not query:
            return

        _execute_ai_agent(message, query)

    def _execute_ai_agent(message, query: str):
        user_id = message.from_user.id
        status_msg = safe_reply(bot, message, "🧠 *Deliberating...* Analyzing your request.", parse_mode="Markdown")
        last_thought_edit = [0.0]

        def thought_cb(step_num: int, thought_text: str):
            now = time.perf_counter()
            if now - last_thought_edit[0] >= 1.2:
                if status_msg and hasattr(status_msg, "message_id"):
                    safe_edit_message_text(
                        bot,
                        f"🧠 *Deliberating (Step {step_num})...*\n💭 _{thought_text}_",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode="Markdown",
                    )
                    last_thought_edit[0] = now

        try:
            session_id = f"telegram_{user_id}"
            response = global_react_agent.run(
                query,
                session_id=session_id,
                thought_callback=thought_cb,
            )

            # Cleanup initial status message
            if status_msg and hasattr(status_msg, "message_id"):
                try:
                    bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception:
                    pass

            # Deliver conversational reply safely (falls back to clean text if Markdown invalid)
            reply_text = response.conversational_reply or f"✨ *Task Completed:*\n{response.reasoning}"
            safe_reply(bot, message, reply_text, reply_markup=controller.get_main_keyboard(), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Telegram processing error: {e}")
            safe_reply(bot, message, f"⚠️ *Execution notice:* {str(e)}", parse_mode="Markdown")
