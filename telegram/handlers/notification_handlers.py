"""
telegram/handlers/notification_handlers.py - Notifications & Clipboard Sub-Menu (5 buttons).

Pulls active system notifications, inspects and clears clipboard buffer,
and broadcasts high-priority alerts to the Android device.
"""

import json
import logging
from typing import Any, Tuple

from tools.registry import global_tool_registry
from core.command_executor import SecureCommandExecutor, IS_TERMUX

logger = logging.getLogger("VoidTelegram.NotificationHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_notification_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Notifications & Clipboard (5 buttons)."""
    clip_preview = "Empty"
    try:
        res = global_tool_registry.execute("get_clipboard")
        if res.success and res.output:
            txt = str(res.output).strip()
            clip_preview = (txt[:24] + "...") if len(txt) > 24 else txt
    except Exception:
        pass

    card = (
        "🔔 *Notifications & Clipboard Hub*\n\n"
        f"• *Clipboard Peek:* `{clip_preview}`\n"
        "• *Notification Listener:* Active (OTP & Alert Filters)\n"
        "• *Broadcast Engine:* Direct Android HUD Alerting\n\n"
        "Select an operation below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔔 Pull Notifications", callback_data="notif_pull"),
        types.InlineKeyboardButton("📋 View Clipboard", callback_data="notif_clip_view"),
    )
    markup.add(
        types.InlineKeyboardButton("🗑️ Clear Clipboard", callback_data="notif_clip_clear"),
        types.InlineKeyboardButton("✉️ Broadcast Alert", callback_data="notif_broadcast"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_notification_handlers(bot: Any, controller: Any) -> None:
    """Registers notif_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("notif_"))
    def handle_notification_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "notif_pull":
            if IS_TERMUX:
                res = SecureCommandExecutor.run(["termux-notification-list"])
                try:
                    notifs = json.loads(res)
                    if not notifs:
                        bot.send_message(chat_id, "🔔 *No unread notifications in drawer.*", parse_mode="Markdown")
                        return

                    lines = ["🔔 *Active Android Notifications:*\n"]
                    for n in notifs[:6]:
                        app = n.get("packageName", "App").split(".")[-1]
                        title = n.get("title", "Notice")
                        content = n.get("content", "")
                        lines.append(f"• *{app}* — {title}\n  _{content[:100]}_")
                    bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
                except Exception:
                    bot.send_message(chat_id, f"🔔 *Notifications:* {res[:1000]}", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "🔔 *Notifications (Simulator):*\n• Telegram: 2 new messages\n• System: Battery fully charged", parse_mode="Markdown")

        elif data == "notif_clip_view":
            res = global_tool_registry.execute("get_clipboard")
            content = res.output if res.success and res.output else "(Clipboard is empty)"
            bot.send_message(
                chat_id,
                f"📋 *Current Clipboard Content:*\n```text\n{str(content)[:2000]}\n```",
                parse_mode="Markdown",
            )

        elif data == "notif_clip_clear":
            res = global_tool_registry.execute("set_clipboard", text="")
            bot.send_message(chat_id, "🗑️ *Clipboard purged successfully.*", parse_mode="Markdown")

        elif data == "notif_broadcast":
            res = global_tool_registry.execute(
                "show_notification",
                title="Void Edge Alert",
                content="Urgent dispatch from Telegram Control Center",
            )
            bot.send_message(chat_id, "✉️ *Broadcast alert dispatched to device notification tray.*", parse_mode="Markdown")
