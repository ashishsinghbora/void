"""
telegram/handlers/model_handlers.py - Interactive Edge LLM Model Selection & Download Wizard.

Provides Telegram UI for device RAM auto-detection, curated 1B-3B model recommendations,
and live streaming download progress bars.
"""

import time
import logging
from typing import Any

from core.model_manager import global_model_manager, MODEL_CATALOG

logger = logging.getLogger("VoidTelegram.ModelHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_model_setup_keyboard() -> Any:
    """Constructs inline keyboard for model catalog selection."""
    if types is None:
        return None

    markup = types.InlineKeyboardMarkup(row_width=1)
    installed = set(global_model_manager.list_installed_models().keys())
    active = global_model_manager.get_active_model_name()
    recommended = global_model_manager.recommend_model_for_device()

    for mid, info in MODEL_CATALOG.items():
        name = info["name"]
        size_mb = info["size_mb"]

        if mid == active:
            label = f"🟢 ACTIVE: {name} ({size_mb}MB)"
        elif mid in installed:
            label = f"✅ Switch to: {name} ({size_mb}MB)"
        elif mid == recommended:
            label = f"⭐ [Recommended] {name} ({size_mb}MB)"
        else:
            label = f"📥 Download: {name} ({size_mb}MB)"

        markup.add(types.InlineKeyboardButton(label, callback_data=f"model_action:{mid}"))

    markup.add(types.InlineKeyboardButton("🔄 Refresh List", callback_data="cb_model_wizard"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return markup


def render_model_setup_card() -> str:
    """Generates formatted Markdown device specs and model recommendation card."""
    ram_mb = global_model_manager.detect_system_ram_mb()
    active = global_model_manager.get_active_model_name() or "Zero-Weight Heuristic Router"
    recommended = global_model_manager.recommend_model_for_device()
    rec_info = MODEL_CATALOG.get(recommended, {})

    ram_str = f"{ram_mb} MB ({round(ram_mb / 1024.0, 1)} GB)" if ram_mb else "Unknown"

    lines = [
        "🧙 *Void Edge Model Setup Wizard*\n",
        f"• *Detected Device RAM:* `{ram_str}`",
        f"• *Active Engine:* `{active}`",
        f"• *Recommended Model:* *{rec_info.get('name', recommended)}* (`{recommended}`)",
        f"  _{rec_info.get('description', '')}_\n",
        "Select a model below to download with SHA-256 verification and activate directly in your ReAct loop:",
    ]
    return "\n".join(lines)


def register_model_handlers(bot: Any, controller: Any) -> None:
    """Registers /setup_model and model action callback handlers."""
    if not bot:
        return

    @bot.message_handler(commands=["setup_model", "model_wizard", "llm"])
    def handle_setup_model(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        card = render_model_setup_card()
        bot.reply_to(message, card, reply_markup=get_model_setup_keyboard(), parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("model_action:"))
    def handle_model_action(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        model_id = call.data.split(":", 1)[1]
        if model_id not in MODEL_CATALOG:
            bot.answer_callback_query(call.id, f"Unknown model {model_id}", show_alert=True)
            return

        installed = global_model_manager.list_installed_models()

        # If already installed, switch active model
        if model_id in installed:
            global_model_manager.set_active_model(model_id)
            bot.answer_callback_query(call.id, f"Activated {model_id}!")
            try:
                bot.edit_message_text(
                    render_model_setup_card(),
                    chat_id,
                    message_id,
                    reply_markup=get_model_setup_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            return

        # Not installed: start streaming download
        bot.answer_callback_query(call.id, f"Starting download of {model_id}...")
        status_msg = bot.send_message(chat_id, f"⏳ *Preparing download for `{model_id}`...*", parse_mode="Markdown")

        last_edit_time = [0.0]

        def progress_cb(downloaded, total, pct, speed_kbps):
            now = time.perf_counter()
            if now - last_edit_time[0] >= 1.5 or downloaded == total:
                filled = int(pct / 10)
                bar = "█" * filled + "░" * (10 - filled)
                d_mb = round(downloaded / (1024 * 1024), 1)
                t_mb = round(total / (1024 * 1024), 1) if total > 0 else 0
                text = (
                    f"📥 *Downloading {model_id}*...\n"
                    f"`[{bar}]` {pct}%\n"
                    f"💾 `{d_mb}MB / {t_mb}MB` @ `{speed_kbps:.1f} KB/s`"
                )
                try:
                    bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode="Markdown")
                    last_edit_time[0] = now
                except Exception:
                    pass

        res = global_model_manager.download_model(model_id, progress_callback=progress_cb)
        if res.get("success"):
            global_model_manager.set_active_model(model_id)
            try:
                bot.edit_message_text(
                    f"✅ *Model `{model_id}` verified & activated!*\n"
                    f"• Size: `{res['size_mb']} MB`\n"
                    f"• SHA-256 Integrity: Verified ✅\n"
                    f"• Active in ReAct loop.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        else:
            try:
                bot.edit_message_text(
                    f"❌ *Download of `{model_id}` failed:*\n`{res.get('error')}`",
                    chat_id,
                    status_msg.message_id,
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        # Update main wizard card
        try:
            bot.edit_message_text(
                render_model_setup_card(),
                chat_id,
                message_id,
                reply_markup=get_model_setup_keyboard(),
                parse_mode="Markdown",
            )
        except Exception:
            pass
