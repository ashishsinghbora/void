"""
telegram/handlers/settings_handlers.py - In-Chat User Preferences & Security Settings.

Provides interactive settings cards with inline toggles for notification policies,
OTP interception, quiet hours, and security levels stored in SQLite WAL database.
"""

import logging
from typing import Any

from telegram.database.db_manager import global_bot_db
from telegram.database.models import UserSettings

logger = logging.getLogger("VoidTelegram.Settings")

try:
    from telebot import types
except ImportError:
    types = None


def get_settings_keyboard(settings: UserSettings) -> Any:
    """Constructs inline keyboard reflecting current settings state."""
    if not types:
        return None

    markup = types.InlineKeyboardMarkup(row_width=1)

    notif_icon = "🔔 Enabled" if settings.notifications_enabled else "🔕 Disabled"
    btn_notif = types.InlineKeyboardButton(f"Notifications: {notif_icon}", callback_data="setting_toggle:notif")

    otp_icon = "🔐 Active" if settings.otp_interception_enabled else "🚫 Disabled"
    btn_otp = types.InlineKeyboardButton(f"OTP Interceptor: {otp_icon}", callback_data="setting_toggle:otp")

    quiet_icon = "🌙 Active (Quiet)" if settings.quiet_hours_enabled else "☀️ Inactive"
    btn_quiet = types.InlineKeyboardButton(f"Quiet Hours: {quiet_icon}", callback_data="setting_toggle:quiet")

    sec_icon = f"🛡️ Level: {settings.security_level}"
    btn_sec = types.InlineKeyboardButton(sec_icon, callback_data="setting_toggle:sec")

    btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main")

    markup.add(btn_notif)
    markup.add(btn_otp)
    markup.add(btn_quiet)
    markup.add(btn_sec)
    markup.add(btn_back)
    return markup


def render_settings_card(user_id: int, settings: UserSettings) -> str:
    """Formats Markdown card for user settings dashboard."""
    return (
        "⚙️ *Void Orchestrator Settings Panel*\n\n"
        f"• *Telegram User ID:* `{user_id}`\n"
        f"• *Push Notifications:* {'`Enabled ✅`' if settings.notifications_enabled else '`Disabled ❌`'}\n"
        f"• *OTP Interception:* {'`Active 🛡️`' if settings.otp_interception_enabled else '`Disabled ⚠️`'}\n"
        f"• *Quiet Hours (No-Disturb):* {'`Active 🌙`' if settings.quiet_hours_enabled else '`Disabled ☀️`'}\n"
        f"• *Security Hardening:* `{settings.security_level}` (Rate Limiter + AES Vault)\n"
        f"• *UI Theme:* `{settings.theme}`\n\n"
        "Tap any button below to toggle preferences instantly:"
    )


def register_settings_handlers(bot: Any, controller: Any) -> None:
    """Registers settings command handler."""
    if not bot:
        return

    @bot.message_handler(commands=["settings"])
    def handle_settings(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        settings = global_bot_db.get_user_settings(user_id)
        card = render_settings_card(user_id, settings)
        bot.reply_to(message, card, reply_markup=get_settings_keyboard(settings), parse_mode="Markdown")
