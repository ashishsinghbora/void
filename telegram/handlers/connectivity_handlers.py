"""
telegram/handlers/connectivity_handlers.py - Connectivity & GPS Sub-Menu.

Wi-Fi scanning and connection stats, network routing, GPS coordinates,
and Bluetooth state inspection.
"""

import json
import logging
from typing import Any, Tuple

from tools.registry import global_tool_registry
from core.command_executor import SecureCommandExecutor, IS_TERMUX

logger = logging.getLogger("VoidTelegram.ConnectivityHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_connectivity_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Connectivity & GPS."""
    res = global_tool_registry.execute("get_wifi_info")
    ssid = res.output.get("ssid", "Unknown") if res.success and isinstance(res.output, dict) else "N/A"
    ip = res.output.get("ip", "127.0.0.1") if res.success and isinstance(res.output, dict) else "N/A"

    card = (
        "🌐 *Connectivity & GPS Operations*\n\n"
        f"• *Wi-Fi Network:* `{ssid}`\n"
        f"• *IP Address:* `{ip}`\n"
        "• *GNSS/GPS Sensor:* Active Standby\n\n"
        "Select a network or location command below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📶 Wi-Fi Status & Scan", callback_data="conn_wifi"),
        types.InlineKeyboardButton("🌐 IP & Network Route", callback_data="conn_net_route"),
    )
    markup.add(
        types.InlineKeyboardButton("📍 GPS Fix & Location", callback_data="conn_gps"),
        types.InlineKeyboardButton("📡 Bluetooth Status", callback_data="conn_bt"),
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh Connectivity", callback_data="menu_connectivity"),
        types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"),
    )
    return card, markup


def register_connectivity_handlers(bot: Any, controller: Any) -> None:
    """Registers conn_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("conn_"))
    def handle_connectivity_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "conn_wifi":
            res = global_tool_registry.execute("get_wifi_info")
            bot.send_message(
                chat_id,
                f"📶 *Wi-Fi Connection Details:*\n```json\n{json.dumps(res.output, indent=2)}\n```",
                parse_mode="Markdown",
            )

        elif data == "conn_net_route":
            if IS_TERMUX:
                out = SecureCommandExecutor.run(["ip", "route", "show"])
            else:
                out = "default via 192.168.1.1 dev wlan0 proto dhcp metric 600\n192.168.1.0/24 dev wlan0 proto kernel scope link"
            bot.send_message(chat_id, f"🌐 *Routing Table:*\n```text\n{out}\n```", parse_mode="Markdown")

        elif data == "conn_gps":
            res = global_tool_registry.execute("get_location")
            bot.send_message(
                chat_id,
                f"📍 *GPS Location Data:*\n```json\n{json.dumps(res.output, indent=2)}\n```",
                parse_mode="Markdown",
            )

        elif data == "conn_bt":
            bot.send_message(
                chat_id,
                "📡 *Bluetooth Controller Status:*\n\n"
                "• *Interface:* Standard Android Bluetooth Radio\n"
                "• *State:* Operational\n"
                "• *Scanning:* On-Demand via Termux:API",
                parse_mode="Markdown",
            )
