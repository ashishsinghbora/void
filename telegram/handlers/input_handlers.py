"""
telegram/handlers/input_handlers.py - Device Touch & Input Sub-Menu (12 buttons).

Handlers for touch simulation, gesture macros, keyboard typing, physical hardware keys
(Home, Back, Recents, Lock Screen, Volume), app launching, and process termination.
"""

import logging
from typing import Any, Tuple

from tools.registry import global_tool_registry
from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidTelegram.InputHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_input_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Device Touch & Input sub-menu."""
    card = (
        "🎮 *Device Touch & Input Center*\n\n"
        "Direct hardware input automation and touch simulation interface.\n\n"
        "• *Touch & Gestures:* Simulate taps and directional swipes\n"
        "• *Physical Buttons:* Trigger Android hardware keycodes\n"
        "• *Input Simulation:* Keyboard typing and process controls\n\n"
        "Select an action below or use direct commands:\n"
        "`/tap <x> <y>` • `/swipe <x1> <y1> <x2> <y2>` • `/type <text>`"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👆 Tap Coordinates", callback_data="inp_tap"),
        types.InlineKeyboardButton("↔️ Swipe Gesture Macro", callback_data="inp_swipe"),
    )
    markup.add(
        types.InlineKeyboardButton("⌨️ Keyboard Type Input", callback_data="inp_type"),
        types.InlineKeyboardButton("🏠 Home Key", callback_data="inp_key_home"),
    )
    markup.add(
        types.InlineKeyboardButton("🔙 Back Key", callback_data="inp_key_back"),
        types.InlineKeyboardButton("⏹️ Recents Key", callback_data="inp_key_recents"),
    )
    markup.add(
        types.InlineKeyboardButton("🔒 Lock Screen Key", callback_data="inp_key_lock"),
        types.InlineKeyboardButton("🔊 Volume Up Key", callback_data="inp_vol_up"),
    )
    markup.add(
        types.InlineKeyboardButton("🔉 Volume Down Key", callback_data="inp_vol_down"),
        types.InlineKeyboardButton("📲 Launch App", callback_data="inp_launch_app"),
    )
    markup.add(
        types.InlineKeyboardButton("🛑 Kill Running Process", callback_data="inp_kill_proc"),
        types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"),
    )
    return card, markup


def register_input_handlers(bot: Any, controller: Any) -> None:
    """Registers callback handlers for inp_* touch and input actions."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("inp_"))
    def handle_input_action(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "inp_tap":
            bot.send_message(
                chat_id,
                "👆 *Touch Tap Simulation*\n\n"
                "To simulate a tap at coordinates, use:\n"
                "`/tap <x> <y>`\n\n"
                "Example: `/tap 540 1200` (Center screen on 1080x2400 display)",
                parse_mode="Markdown",
            )

        elif data == "inp_swipe":
            res = global_tool_registry.execute("mobile_swipe", x1=500, y1=1500, x2=500, y2=500, duration_ms=350)
            status_text = res.output if res.success else res.error
            bot.send_message(
                chat_id,
                f"↔️ *Swipe Gesture Executed:*\n`{status_text}`\n\n"
                "Custom swipe syntax: `/swipe <x1> <y1> <x2> <y2> [duration_ms]`",
                parse_mode="Markdown",
            )

        elif data == "inp_type":
            bot.send_message(
                chat_id,
                "⌨️ *Keyboard Type Input*\n\n"
                "To simulate typing text on the device, use:\n"
                "`/type <your text here>`\n\n"
                "Example: `/type Hello from Void Edge Agent`",
                parse_mode="Markdown",
            )

        elif data == "inp_key_home":
            res = global_tool_registry.execute("mobile_keyevent", key="HOME")
            bot.send_message(chat_id, f"🏠 *Home Key:* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_key_back":
            res = global_tool_registry.execute("mobile_keyevent", key="BACK")
            bot.send_message(chat_id, f"🔙 *Back Key:* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_key_recents":
            res = global_tool_registry.execute("mobile_keyevent", key="RECENTS")
            bot.send_message(chat_id, f"⏹️ *Recents Key:* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_key_lock":
            res = global_tool_registry.execute("mobile_keyevent", key="POWER")
            bot.send_message(chat_id, f"🔒 *Lock Screen (Power):* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_vol_up":
            res = global_tool_registry.execute("mobile_keyevent", key="VOLUME_UP")
            bot.send_message(chat_id, f"🔊 *Volume Up:* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_vol_down":
            res = global_tool_registry.execute("mobile_keyevent", key="VOLUME_DOWN")
            bot.send_message(chat_id, f"🔉 *Volume Down:* `{res.output if res.success else res.error}`", parse_mode="Markdown")

        elif data == "inp_launch_app":
            try:
                bot.send_message(
                    chat_id,
                    "📲 *Launch Installed Application*\nSelect an application to open directly:",
                    reply_markup=controller.get_apps_keyboard(),
                    parse_mode="Markdown",
                )
            except Exception:
                bot.send_message(chat_id, "📲 Use `/search <app>` or `/open_app <name>` to launch apps.", parse_mode="Markdown")

        elif data == "inp_kill_proc":
            res = global_tool_registry.execute("clean_system", dry_run=False)
            bot.send_message(
                chat_id,
                "🛑 *Process Reclaim & Memory Clean:*\n"
                f"`{res.output.get('summary', 'Memory reclaimed') if isinstance(res.output, dict) else res.output}`",
                parse_mode="Markdown",
            )
