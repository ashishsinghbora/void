"""
telegram/handlers/callback_handlers.py - Interactive Inline Keyboard Callback Query Router.

Dispatches callbacks for hardware toggles, application launchers, plugin managers,
settings updates, and invoice generation.
"""

import json
import logging
from typing import Any

from tools.registry import global_tool_registry
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager
from storage.repository import ExecutionLogRepository

from telegram.database.db_manager import global_bot_db
from telegram.database.models import UserTier
from telegram.services.device_service import global_device_service
from telegram.services.payment_service import global_payment_service
from telegram.services.cloud_vault import global_cloud_vault
from telegram.handlers.settings_handlers import render_settings_card, get_settings_keyboard
from telegram.handlers.billing_handlers import render_billing_card, get_billing_keyboard, dispatch_invoice
from telegram.handlers.vault_handlers import render_vault_status_card, get_vault_keyboard
from telegram.handlers.model_handlers import render_model_setup_card, get_model_setup_keyboard

logger = logging.getLogger("VoidTelegram.CallbackHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def register_callback_handlers(bot: Any, controller: Any) -> None:
    """Registers unified callback query handler."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback_query(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized access denied.", show_alert=True)
            return

        data = call.data

        # ----------------------------------------------------------------------
        # Quick Hardware Actions
        # ----------------------------------------------------------------------
        if data == "cb_torch":
            controller._torch_on = not controller._torch_on
            global_tool_registry.execute("set_torch", on=controller._torch_on)
            status_str = "ON" if controller._torch_on else "OFF"
            bot.answer_callback_query(call.id, f"🔦 Flashlight turned {status_str}")
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=controller.get_main_keyboard())
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
            controller._execute_photo_capture(chat_id)

        elif data == "cb_screenshot":
            bot.answer_callback_query(call.id, "Capturing screenshot...")
            if hasattr(controller, "_execute_screenshot_capture"):
                controller._execute_screenshot_capture(chat_id)
            else:
                global_tool_registry.execute("capture_screen")
                bot.send_message(chat_id, "📸 Screenshot captured!", parse_mode="Markdown")

        elif data in ("cb_vault", "cb_vault_status"):
            bot.answer_callback_query(call.id)
            card = render_vault_status_card()
            is_conf = global_cloud_vault.is_configured()
            try:
                bot.edit_message_text(
                    card,
                    chat_id,
                    message_id,
                    reply_markup=get_vault_keyboard(is_conf),
                    parse_mode="Markdown",
                )
            except Exception:
                bot.send_message(chat_id, card, reply_markup=get_vault_keyboard(is_conf), parse_mode="Markdown")

        elif data == "cb_vault_backup":
            bot.answer_callback_query(call.id, "Initiating memory backup to vault...")
            if not global_cloud_vault.is_configured():
                bot.send_message(chat_id, "⚠️ Vault not configured. Add bot to a group as Admin or run `/set_vault <id>`.", parse_mode="Markdown")
            else:
                res = global_cloud_vault.upload_memory_snapshot()
                if res.get("success"):
                    bot.send_message(chat_id, f"✅ *Memory snapshot backed up to Cloud Vault!* (Msg #{res.get('telegram_message_id')})", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, f"❌ Backup failed: {res.get('error')}", parse_mode="Markdown")

        elif data == "cb_vault_files":
            bot.answer_callback_query(call.id)
            records = global_cloud_vault.query_vault(limit=8)
            if not records:
                bot.send_message(chat_id, "📁 *No vault files recorded yet.*", parse_mode="Markdown")
            else:
                lines = ["📁 *Recent Cloud Vault Files:*\n"]
                for r in records:
                    ts = r.created_at[:16].replace("T", " ")
                    mb = round(r.file_size / (1024 * 1024), 2)
                    lines.append(f"• `#{r.id}` *{r.file_name}* ({mb} MB) | `{r.category}` | Msg `#{r.telegram_message_id}`")
                bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "cb_model_wizard":
            bot.answer_callback_query(call.id)
            card = render_model_setup_card()
            try:
                bot.edit_message_text(
                    card,
                    chat_id,
                    message_id,
                    reply_markup=get_model_setup_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                bot.send_message(chat_id, card, reply_markup=get_model_setup_keyboard(), parse_mode="Markdown")

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

        elif data == "cb_security":
            bot.answer_callback_query(call.id)
            card = controller._render_security_card(user_id)
            try:
                bot.edit_message_text(
                    card,
                    chat_id,
                    message_id,
                    reply_markup=controller.get_security_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                bot.send_message(chat_id, card, reply_markup=controller.get_security_keyboard(), parse_mode="Markdown")

        elif data == "cb_apps":
            bot.answer_callback_query(call.id)
            try:
                bot.edit_message_text(
                    "🚀 *Application Launch Center*\nSelect an app to open directly on your phone:",
                    chat_id,
                    message_id,
                    reply_markup=controller.get_apps_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        elif data == "cb_devices":
            bot.answer_callback_query(call.id)
            devices = global_device_service.list_user_devices(user_id)
            lines = ["📱 *Connected Android Edge Nodes:*\n"]
            for d in devices:
                stat_icon = "🟢 Online" if d.is_online else "🔴 Offline"
                lines.append(f"• *{d.name}* (`{d.device_id}`)")
                lines.append(f"  Status: {stat_icon} | 🔋 Battery: `{d.battery_level}%` | Model: `{d.model}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "cb_billing":
            bot.answer_callback_query(call.id)
            card = render_billing_card(user_id)
            try:
                bot.edit_message_text(card, chat_id, message_id, reply_markup=get_billing_keyboard(user_id), parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, card, reply_markup=get_billing_keyboard(user_id), parse_mode="Markdown")

        elif data == "cb_billing_history":
            bot.answer_callback_query(call.id)
            txs = global_bot_db.get_user_transactions(user_id, limit=5)
            if not txs:
                bot.send_message(chat_id, "📜 *No past payment receipts found.*", parse_mode="Markdown")
                return
            lines = ["📜 *Recent Payment Receipts:*\n"]
            for t in txs:
                lines.append(f"• *{t.tier_purchased}* — `{t.total_amount} {t.currency}` ({t.status})")
                lines.append(f"  Charge ID: `{t.telegram_payment_charge_id}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "cb_settings":
            bot.answer_callback_query(call.id)
            settings = global_bot_db.get_user_settings(user_id)
            card = render_settings_card(user_id, settings)
            try:
                bot.edit_message_text(card, chat_id, message_id, reply_markup=get_settings_keyboard(settings), parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, card, reply_markup=get_settings_keyboard(settings), parse_mode="Markdown")

        elif data == "cb_back_main":
            bot.answer_callback_query(call.id)
            try:
                bot.edit_message_text(
                    "⚡ *Void Edge Agent Remote Control Hub*\nQuick action dashboard active:",
                    chat_id,
                    message_id,
                    reply_markup=controller.get_main_keyboard(),
                    parse_mode="Markdown",
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
                parse_mode="Markdown",
            )

        # ----------------------------------------------------------------------
        # Subscription Purchases
        # ----------------------------------------------------------------------
        elif data.startswith("buy_tier:"):
            tier_name = data.split(":", 1)[1]
            try:
                tier = UserTier(tier_name)
                bot.answer_callback_query(call.id, f"Generating invoice for {tier.value}...")
                dispatch_invoice(bot, chat_id, user_id, tier)
            except Exception as e:
                logger.error(f"Error handling buy_tier: {e}")
                bot.answer_callback_query(call.id, f"Error: {e}", show_alert=True)

        # ----------------------------------------------------------------------
        # Dynamic Settings Toggles
        # ----------------------------------------------------------------------
        elif data.startswith("setting_toggle:"):
            toggle_key = data.split(":", 1)[1]
            settings = global_bot_db.get_user_settings(user_id)

            if toggle_key == "notif":
                settings.notifications_enabled = not settings.notifications_enabled
                bot.answer_callback_query(call.id, f"Notifications: {'ON' if settings.notifications_enabled else 'OFF'}")
            elif toggle_key == "otp":
                settings.otp_interception_enabled = not settings.otp_interception_enabled
                bot.answer_callback_query(call.id, f"OTP Interceptor: {'ACTIVE' if settings.otp_interception_enabled else 'DISABLED'}")
            elif toggle_key == "quiet":
                settings.quiet_hours_enabled = not settings.quiet_hours_enabled
                bot.answer_callback_query(call.id, f"Quiet Hours: {'ON' if settings.quiet_hours_enabled else 'OFF'}")
            elif toggle_key == "sec":
                levels = ["STANDARD", "HIGH", "STRICT"]
                cur_idx = levels.index(settings.security_level) if settings.security_level in levels else 1
                settings.security_level = levels[(cur_idx + 1) % len(levels)]
                bot.answer_callback_query(call.id, f"Security Level: {settings.security_level}")

            global_bot_db.update_user_settings(settings)
            card = render_settings_card(user_id, settings)
            try:
                bot.edit_message_text(card, chat_id, message_id, reply_markup=get_settings_keyboard(settings), parse_mode="Markdown")
            except Exception:
                pass

        # ----------------------------------------------------------------------
        # App Launchers
        # ----------------------------------------------------------------------
        elif data.startswith("app_launch:"):
            app_name = data.split(":", 1)[1]
            bot.answer_callback_query(call.id, f"Launching {app_name}...")
            res = global_tool_registry.execute("launch_installed_app", app_name=app_name)
            bot.send_message(
                chat_id,
                f"🚀 {res.output if res.success else res.error}",
                parse_mode="Markdown",
            )

        # ----------------------------------------------------------------------
        # Plugin Store Actions
        # ----------------------------------------------------------------------
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
                bot.edit_message_text(text, chat_id, message_id, reply_markup=controller.get_plugins_keyboard(), parse_mode="Markdown")
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
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=controller.get_plugins_keyboard())
            except Exception:
                pass

        elif data.startswith("plugin_remove:"):
            pid = data.split(":", 1)[1]
            bot.answer_callback_query(call.id, f"Removing {pid}...")
            res = global_extension_manager.uninstall_plugin(pid)
            bot.send_message(chat_id, f"🗑️ *{res.get('message')}*", parse_mode="Markdown")
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=controller.get_plugins_keyboard())
            except Exception:
                pass
