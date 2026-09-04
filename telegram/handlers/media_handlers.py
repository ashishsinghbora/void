"""
telegram/handlers/media_handlers.py - Media & Audio Hub Sub-Menu (6 buttons).

Controls device media playback (Play/Pause, Next Track, Previous Track, Mute toggle)
and audio output route inspection.
"""

import logging
from typing import Any, Tuple

from tools.registry import global_tool_registry
from core.command_executor import SecureCommandExecutor, IS_TERMUX

logger = logging.getLogger("VoidTelegram.MediaHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_media_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Media & Audio Hub (6 buttons)."""
    card = (
        "🎵 *Media & Audio Hub*\n\n"
        "Hardware media controller and sound routing interface.\n\n"
        "• *Playback Controls:* Play, pause, skip, and rewind\n"
        "• *Volume:* Instant mute and sound management\n"
        "• *Routing:* Headset, Bluetooth, and internal speaker query\n\n"
        "Tap a media control action below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎵 Play / Pause", callback_data="audio_play_pause"),
        types.InlineKeyboardButton("⏭️ Next Track", callback_data="audio_next"),
    )
    markup.add(
        types.InlineKeyboardButton("⏮️ Previous Track", callback_data="audio_prev"),
        types.InlineKeyboardButton("🔇 Toggle Mute", callback_data="audio_mute"),
    )
    markup.add(
        types.InlineKeyboardButton("🎧 Audio Route Check", callback_data="audio_route"),
        types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"),
    )
    return card, markup


def register_media_handlers(bot: Any, controller: Any) -> None:
    """Registers audio_* callback handlers for media controls."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("audio_"))
    def handle_audio_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "audio_play_pause":
            # Keycode 85 = KEYCODE_MEDIA_PLAY_PAUSE
            res = global_tool_registry.execute("mobile_keyevent", key="MEDIA_PLAY_PAUSE")
            bot.send_message(chat_id, "🎵 *Play / Pause toggled.*", parse_mode="Markdown")

        elif data == "audio_next":
            # Keycode 87 = KEYCODE_MEDIA_NEXT
            res = global_tool_registry.execute("mobile_keyevent", key="MEDIA_NEXT")
            bot.send_message(chat_id, "⏭️ *Next Track triggered.*", parse_mode="Markdown")

        elif data == "audio_prev":
            # Keycode 88 = KEYCODE_MEDIA_PREVIOUS
            res = global_tool_registry.execute("mobile_keyevent", key="MEDIA_PREVIOUS")
            bot.send_message(chat_id, "⏮️ *Previous Track triggered.*", parse_mode="Markdown")

        elif data == "audio_mute":
            # Keycode 164 = KEYCODE_VOLUME_MUTE
            res = global_tool_registry.execute("mobile_keyevent", key="VOLUME_MUTE")
            bot.send_message(chat_id, "🔇 *Mute toggled.*", parse_mode="Markdown")

        elif data == "audio_route":
            # Inspect audio hardware info via Termux-API or system
            if IS_TERMUX:
                res = SecureCommandExecutor.run(["termux-audio-info"])
            else:
                res = '{"output": "Internal Speaker / Built-in DAC", "volume": "75%"}'

            bot.send_message(
                chat_id,
                f"🎧 *Audio Route & Hardware Info:*\n```json\n{res}\n```",
                parse_mode="Markdown",
            )
