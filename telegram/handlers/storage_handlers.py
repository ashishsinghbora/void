"""
telegram/handlers/storage_handlers.py - Storage & Files Sub-Menu.

Inspects device storage pools (Internal, Downloads, Media Vault),
allocation breakdowns, and file operations.
"""

import os
import shutil
import logging
from typing import Any, Tuple

logger = logging.getLogger("VoidTelegram.StorageHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_storage_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Storage & Files."""
    try:
        total, used, free = shutil.disk_usage("/")
        free_gb = round(free / (1024**3), 1)
        used_gb = round(used / (1024**3), 1)
    except Exception:
        free_gb, used_gb = "N/A", "N/A"

    card = (
        "📁 *Storage & File Operations*\n\n"
        f"• *Internal Storage:* `{used_gb} GB used` / `{free_gb} GB free`\n"
        "• *Vault Cache:* `~/.void/media` (Indexed & Encrypted)\n"
        "• *Download Path:* `/sdcard/Download`\n\n"
        "Select a storage explorer action:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📁 Internal Storage", callback_data="stor_internal"),
        types.InlineKeyboardButton("💾 Download Directory", callback_data="stor_downloads"),
    )
    markup.add(
        types.InlineKeyboardButton("🔍 Recent Media Files", callback_data="stor_media"),
        types.InlineKeyboardButton("📊 Storage Allocation", callback_data="stor_alloc"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_storage_handlers(bot: Any, controller: Any) -> None:
    """Registers stor_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("stor_"))
    def handle_storage_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "stor_internal":
            home = os.path.expanduser("~")
            items = os.listdir(home)[:10]
            lines = ["📁 *Termux Internal Directory (`~`):*\n"]
            for item in items:
                lines.append(f"• `{item}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "stor_downloads":
            dl_path = os.path.join(os.path.expanduser("~"), "storage", "downloads")
            if not os.path.exists(dl_path):
                dl_path = "/sdcard/Download"
            lines = [f"💾 *Downloads Directory (`{dl_path}`):*\n"]
            try:
                if os.path.exists(dl_path):
                    files = os.listdir(dl_path)[:8]
                    for f in files:
                        lines.append(f"• `{f}`")
                else:
                    lines.append("Download directory not mounted in Termux.")
            except Exception as e:
                lines.append(f"Access error: {e}")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "stor_media":
            from core.media_vault import global_media_vault
            media_files = global_media_vault.list_recent_media(limit=6)
            if not media_files:
                bot.send_message(chat_id, "🔍 *No media files stored in local vault.*", parse_mode="Markdown")
            else:
                lines = ["🔍 *Recent Local Media Files:*\n"]
                for m in media_files:
                    lines.append(f"• *{m['filename']}* ({m['size_kb']} KB) [{m['category']}]")
                bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "stor_alloc":
            total, used, free = shutil.disk_usage("/")
            t_gb = round(total / (1024**3), 1)
            u_gb = round(used / (1024**3), 1)
            f_gb = round(free / (1024**3), 1)
            pct = int((used / total) * 100)
            bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))

            bot.send_message(
                chat_id,
                f"📊 *Storage Allocation Breakdown:*\n\n"
                f"`[{bar}]` {pct}%\n"
                f"• *Total Capacity:* `{t_gb} GB`\n"
                f"• *Used Space:* `{u_gb} GB`\n"
                f"• *Available Space:* `{f_gb} GB`",
                parse_mode="Markdown",
            )
