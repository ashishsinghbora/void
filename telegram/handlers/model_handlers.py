"""
telegram/handlers/model_handlers.py - Model Management Core Sub-Menu (7 buttons).

Interactive GGUF weight lifecycle manager with RAM detection, symmetrical add & remove,
context window tuning, and quantization profiles.
"""

import time
import logging
from typing import Any, Tuple, Optional

from core.model_manager import global_model_manager, MODEL_CATALOG

logger = logging.getLogger("VoidTelegram.ModelHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_model_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Model Management Core sub-menu (7 buttons)."""
    ram_mb = global_model_manager.detect_system_ram_mb()
    active = global_model_manager.get_active_model_name() or "Deterministic ReAct (Zero-Weight)"
    installed = global_model_manager.list_installed_models()

    ram_str = f"{ram_mb} MB" if isinstance(ram_mb, (int, float)) else "Unknown"

    card = (
        "🧠 *Model Management Core*\n\n"
        f"• *Active Engine:* `{active}`\n"
        f"• *Device Total RAM:* `{ram_str}`\n"
        f"• *Installed Weights:* `{len(installed)}` models on disk\n\n"
        "Symmetrical model lifecycle controls:\n"
        "Select an action below or run `/setup_model <id>` | `/remove_model <id>`:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 Setup New Model", callback_data="model_setup"),
        types.InlineKeyboardButton("🗑️ Remove Active Model", callback_data="model_remove"),
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Switch Active Model", callback_data="model_switch"),
        types.InlineKeyboardButton("🔍 List Cached Models", callback_data="model_list"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Context Window Stats", callback_data="model_context"),
        types.InlineKeyboardButton("⚙️ Adjust Quantization", callback_data="model_quant"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def get_model_setup_keyboard() -> Any:
    """Constructs inline keyboard for model catalog selection."""
    if types is None:
        return None

    markup = types.InlineKeyboardMarkup(row_width=1)
    installed_files = {m["filename"] for m in global_model_manager.list_installed_models()}
    active = global_model_manager.get_active_model_name()
    total_ram, _ = global_model_manager.detect_system_ram_mb()
    recommended = global_model_manager.recommend_model_for_device(total_ram)

    for mid, info in MODEL_CATALOG.items():
        name = info["name"]
        size_mb = info["size_mb"]
        is_inst = info["filename"] in installed_files

        if mid == active or info["name"] == active:
            label = f"🟢 ACTIVE: {name} ({size_mb}MB)"
        elif is_inst:
            label = f"✅ Switch to: {name} ({size_mb}MB)"
        elif mid == recommended:
            label = f"⭐ [Recommended] {name} ({size_mb}MB)"
        else:
            label = f"📥 Download: {name} ({size_mb}MB)"

        markup.add(types.InlineKeyboardButton(label, callback_data=f"model_action:{mid}"))

    markup.add(types.InlineKeyboardButton("🔄 Refresh List", callback_data="model_setup"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Models Menu", callback_data="menu_models"))
    return markup


def render_model_setup_card() -> str:
    """Generates formatted Markdown device specs and model recommendation card."""
    total_ram, avail_ram = global_model_manager.detect_system_ram_mb()
    active = global_model_manager.get_active_model_name() or "Zero-Weight Heuristic Router"
    recommended = global_model_manager.recommend_model_for_device(total_ram)
    rec_info = MODEL_CATALOG.get(recommended, {})

    ram_str = f"{total_ram} MB ({round(total_ram / 1024.0, 1)} GB)" if total_ram else "Unknown"
    avail_str = f"{avail_ram} MB free" if avail_ram else "RAM Headroom OK"

    lines = [
        "🧙 *Void Edge Model Setup Wizard*\n",
        f"• *Detected Device RAM:* `{ram_str}` ({avail_str})",
        f"• *Active Engine:* `{active}`",
        f"• *Recommended Model:* *{rec_info.get('name', recommended)}* (`{recommended}`)",
        f"  _{rec_info.get('description', '')}_\n",
        "Select a model below to download with SHA-256 verification and activate directly in your ReAct loop:",
    ]
    return "\n".join(lines)


def register_model_handlers(bot: Any, controller: Any) -> None:
    """Registers /setup_model, /remove_model, /models and callback handlers."""
    if not bot:
        return

    @bot.message_handler(commands=["setup_model", "model_wizard", "llm"])
    def handle_setup_model_cmd(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split()
        if len(parts) > 1:
            mid = parts[1].lower().strip()
            if mid in MODEL_CATALOG:
                # Direct setup requested
                _trigger_model_download(bot, message.chat.id, mid)
                return
            else:
                bot.reply_to(
                    message,
                    f"⚠️ Unknown model `{mid}`.\nAvailable: `{', '.join(MODEL_CATALOG.keys())}`",
                    parse_mode="Markdown",
                )
                return

        card = render_model_setup_card()
        bot.reply_to(message, card, reply_markup=get_model_setup_keyboard(), parse_mode="Markdown")

    @bot.message_handler(commands=["remove_model", "unload_model"])
    def handle_remove_model_cmd(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            # Show interactive removal keyboard
            installed = global_model_manager.list_installed_models()
            if not installed:
                bot.reply_to(message, "ℹ️ No model weights currently installed to remove.")
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for m in installed:
                fname = m["filename"]
                mid = fname.replace(".gguf", "").replace(".bin", "")
                for k, v in MODEL_CATALOG.items():
                    if v["filename"] == fname:
                        mid = k
                        break
                markup.add(types.InlineKeyboardButton(f"🗑️ Purge {mid} ({m['size_mb']} MB)", callback_data=f"model_purge:{mid}"))
            markup.add(types.InlineKeyboardButton("🔙 Models Menu", callback_data="menu_models"))
            bot.reply_to(message, "🗑️ *Select a model to purge from memory & disk:*", reply_markup=markup, parse_mode="Markdown")
            return

        target_mid = parts[1].lower().strip()
        res = global_model_manager.remove_model(target_mid)
        if res.get("success"):
            bot.reply_to(
                message,
                f"✅ *Model `{target_mid}` purged successfully!*\n"
                f"• Reclaimed Memory & Storage: `{res.get('freed_mb', 0)} MB`\n"
                f"• Engine: Reverted to Deterministic Zero-Weight ReAct (< 30MB RAM mode)",
                parse_mode="Markdown",
            )
        else:
            bot.reply_to(message, f"❌ Removal failed: {res.get('error')}")

    @bot.message_handler(commands=["models"])
    def handle_models_list_cmd(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        installed = global_model_manager.list_installed_models()
        active = global_model_manager.get_active_model_name()
        total_ram, avail_ram = global_model_manager.detect_system_ram_mb()

        lines = [
            "🧠 *Local Model Engine Status:*\n",
            f"• *Active Model:* `{active or 'Deterministic ReAct (Zero-Weight)'}`",
            f"• *RAM Total / Avail:* `{total_ram}MB` / `{avail_ram}MB`",
            f"• *Cached Weights on Disk:* `{len(installed)}`\n",
            "*Installed Models:*",
        ]

        if not installed:
            lines.append("  _None installed. Running lean zero-weight engine._")
        else:
            for m in installed:
                is_active = "🟢 [ACTIVE]" if (active and m["filename"] in active) else "⚪"
                lines.append(f"• {is_active} *{m['filename']}* ({m['size_mb']} MB)")

        lines.append("\n_Commands:_ `/setup_model <id>` | `/remove_model <id>`")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

    def _trigger_model_download(bot_inst, chat_id, model_id):
        installed_files = {m["filename"] for m in global_model_manager.list_installed_models()}
        cat_info = MODEL_CATALOG[model_id]

        if cat_info["filename"] in installed_files:
            global_model_manager.set_active_model(model_id)
            bot_inst.send_message(chat_id, f"✅ Activated `{model_id}` as current engine!", parse_mode="Markdown")
            return

        status_msg = bot_inst.send_message(chat_id, f"⏳ *Preparing download for `{model_id}`...*", parse_mode="Markdown")
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
                    bot_inst.edit_message_text(text, chat_id, status_msg.message_id, parse_mode="Markdown")
                    last_edit_time[0] = now
                except Exception:
                    pass

        res = global_model_manager.download_model(model_id, progress_callback=progress_cb)
        if res.get("success"):
            global_model_manager.set_active_model(model_id)
            try:
                bot_inst.edit_message_text(
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
                bot_inst.edit_message_text(
                    f"❌ *Download of `{model_id}` failed:*\n`{res.get('error')}`",
                    chat_id,
                    status_msg.message_id,
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data and (call.data.startswith("model_") or call.data == "cb_model_wizard"))
    def handle_model_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data in ("model_setup", "cb_model_wizard"):
            card = render_model_setup_card()
            try:
                bot.edit_message_text(card, chat_id, message_id, reply_markup=get_model_setup_keyboard(), parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, card, reply_markup=get_model_setup_keyboard(), parse_mode="Markdown")

        elif data == "model_remove":
            # Show list of removable models or remove active
            installed = global_model_manager.list_installed_models()
            if not installed:
                bot.send_message(chat_id, "ℹ️ No models currently installed on disk to remove.", parse_mode="Markdown")
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for m in installed:
                fname = m["filename"]
                mid = fname.replace(".gguf", "").replace(".bin", "")
                for k, v in MODEL_CATALOG.items():
                    if v["filename"] == fname:
                        mid = k
                        break
                markup.add(types.InlineKeyboardButton(f"🗑️ Purge {mid} ({m['size_mb']} MB)", callback_data=f"model_purge:{mid}"))
            markup.add(types.InlineKeyboardButton("🔙 Back to Models Menu", callback_data="menu_models"))

            bot.send_message(chat_id, "🗑️ *Select a model to purge immediately from memory & disk:*", reply_markup=markup, parse_mode="Markdown")

        elif data.startswith("model_purge:"):
            mid = data.split(":", 1)[1]
            res = global_model_manager.remove_model(mid)
            if res.get("success"):
                bot.send_message(
                    chat_id,
                    f"✅ *Model `{mid}` purged!*\n"
                    f"• Memory & Disk reclaimed: `{res.get('freed_mb', 0)} MB`\n"
                    f"• Active Engine: Reverted to Deterministic ReAct (< 30MB RAM)",
                    parse_mode="Markdown",
                )
            else:
                bot.send_message(chat_id, f"❌ Failed to remove `{mid}`: {res.get('error')}", parse_mode="Markdown")

        elif data == "model_switch":
            installed = global_model_manager.list_installed_models()
            if not installed:
                bot.send_message(chat_id, "ℹ️ No additional models installed. Download one via `/setup_model`.", parse_mode="Markdown")
                return

            markup = types.InlineKeyboardMarkup(row_width=1)
            for m in installed:
                fname = m["filename"]
                mid = fname.replace(".gguf", "").replace(".bin", "")
                for k, v in MODEL_CATALOG.items():
                    if v["filename"] == fname:
                        mid = k
                        break
                markup.add(types.InlineKeyboardButton(f"🟢 Switch to {mid}", callback_data=f"model_action:{mid}"))
            markup.add(types.InlineKeyboardButton("🔙 Models Menu", callback_data="menu_models"))
            bot.send_message(chat_id, "🔄 *Select active model engine:*", reply_markup=markup, parse_mode="Markdown")

        elif data == "model_list":
            installed = global_model_manager.list_installed_models()
            active = global_model_manager.get_active_model_name()
            lines = ["🔍 *Cached Local Model Weights:*\n"]
            if not installed:
                lines.append("No models cached on disk.")
            else:
                for m in installed:
                    stat = "🟢 ACTIVE" if (active and m["filename"] in active) else "⚪ INSTALLED"
                    lines.append(f"• *{m['filename']}* ({m['size_mb']} MB) - `{stat}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "model_context":
            stats = global_model_manager.get_context_window_stats()
            bot.send_message(
                chat_id,
                f"📊 *Context Window & Token Allocation:*\n\n"
                f"• *Engine:* `{stats['active_model']}`\n"
                f"• *Total Context Window:* `{stats['context_window_tokens']}` tokens\n"
                f"• *Max Completion Tokens:* `{stats['reserved_response_tokens']}` tokens\n"
                f"• *System Prompt Reserve:* `{stats['system_prompt_tokens']}` tokens\n"
                f"• *Usable Input Window:* `{stats['effective_user_tokens']}` tokens\n"
                f"• *RAM Headroom:* `{stats['ram_headroom_mb']} MB`",
                parse_mode="Markdown",
            )

        elif data == "model_quant":
            bot.send_message(
                chat_id,
                "⚙️ *Quantization Settings & Profiles:*\n\n"
                "• *Default Profile:* `Q4_K_M` (Optimal 4-bit balance for ARM Mali/Adreno)\n"
                "• *RAM Overhead:* ~0.65x parameter count in bytes\n"
                "• *Inference Backend:* `llama.cpp` mobile vector optimizations\n"
                "• *Zero-Weight Fallback:* Deterministic ReAct parser (< 30MB RSS)\n\n"
                "_All models in the Void catalog are pre-quantized for ARM64 Termux._",
                parse_mode="Markdown",
            )

        elif data.startswith("model_action:"):
            mid = data.split(":", 1)[1]
            _trigger_model_download(bot, chat_id, mid)
