"""
telegram/handlers/telemetry_handlers.py - Core & Telemetry Sub-Menu (7 buttons).

CPU stats, thermal sensors, battery health, RAM allocation, and quick telemetry dumps.
"""

import logging
import resource
from typing import Any, Tuple

from tools.registry import global_tool_registry
from core.fastfetch import global_fastfetch_collector

logger = logging.getLogger("VoidTelegram.TelemetryHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_telemetry_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Core & Telemetry sub-menu."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024.0, 1)

    bat_res = global_tool_registry.execute("get_battery_status")
    bat_pct = "N/A"
    bat_temp = "N/A"
    if bat_res.success and isinstance(bat_res.output, dict):
        bat_pct = f"{bat_res.output.get('percentage', 'N/A')}%"
        bat_temp = f"{bat_res.output.get('temperature', 'N/A')}°C"

    card = (
        "📂 *Core & Telemetry Dashboard*\n\n"
        f"• *Memory RSS:* `{rss_mb} MB` (Target < 30MB)\n"
        f"• *Battery:* `{bat_pct}` | Temp: `{bat_temp}`\n"
        f"• *Python Process:* `{usage.ru_utime:.1f}s` user / `{usage.ru_stime:.1f}s` sys\n\n"
        "Select a telemetry action below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 CPU Live Graph", callback_data="tel_cpu"),
        types.InlineKeyboardButton("🌡️ Thermal Sensor", callback_data="tel_thermal"),
    )
    markup.add(
        types.InlineKeyboardButton("🔋 Battery Health", callback_data="tel_battery"),
        types.InlineKeyboardButton("🧠 RAM Stats", callback_data="tel_ram"),
    )
    markup.add(
        types.InlineKeyboardButton("⚡ Quick Dump", callback_data="tel_dump"),
        types.InlineKeyboardButton("🔄 Refresh", callback_data="menu_telemetry"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_telemetry_handlers(bot: Any, controller: Any) -> None:
    """Registers tel_* callback handlers for telemetry sub-menu actions."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("tel_"))
    def handle_telemetry_action(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "tel_cpu":
            card = global_fastfetch_collector.render_markdown()
            bot.send_message(chat_id, f"📊 *CPU & System Overview:*\n\n{card}", parse_mode="Markdown")

        elif data == "tel_thermal":
            bat_res = global_tool_registry.execute("get_battery_status")
            if bat_res.success and isinstance(bat_res.output, dict):
                temp = bat_res.output.get("temperature", "N/A")
                health = bat_res.output.get("health", "N/A")
                bot.send_message(
                    chat_id,
                    f"🌡️ *Thermal Sensor Report:*\n\n"
                    f"• *Battery Temperature:* `{temp}°C`\n"
                    f"• *Health Status:* `{health}`\n\n"
                    "_Note: Full SoC thermal data requires root access._",
                    parse_mode="Markdown",
                )
            else:
                bot.send_message(chat_id, f"🌡️ *Thermal check failed:* `{bat_res.error}`", parse_mode="Markdown")

        elif data == "tel_battery":
            bat_res = global_tool_registry.execute("get_battery_status")
            if bat_res.success and isinstance(bat_res.output, dict):
                d = bat_res.output
                bot.send_message(
                    chat_id,
                    f"🔋 *Battery Health & Amperage:*\n\n"
                    f"• *Percentage:* `{d.get('percentage', 'N/A')}%`\n"
                    f"• *Status:* `{d.get('status', 'Unknown')}`\n"
                    f"• *Health:* `{d.get('health', 'N/A')}`\n"
                    f"• *Temperature:* `{d.get('temperature', 'N/A')}°C`\n"
                    f"• *Plugged:* `{d.get('plugged', 'N/A')}`\n"
                    f"• *Current (µA):* `{d.get('current', 'N/A')}`",
                    parse_mode="Markdown",
                )
            else:
                bot.send_message(chat_id, f"🔋 *Battery query failed:* `{bat_res.error}`", parse_mode="Markdown")

        elif data == "tel_ram":
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = round(usage.ru_maxrss / 1024.0, 1)
            # Try to read /proc/meminfo for system-wide stats
            sys_total = sys_avail = "N/A"
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            sys_total = f"{int(line.split()[1]) // 1024} MB"
                        elif line.startswith("MemAvailable:"):
                            sys_avail = f"{int(line.split()[1]) // 1024} MB"
            except Exception:
                pass

            bot.send_message(
                chat_id,
                f"🧠 *RAM Allocation Stats:*\n\n"
                f"• *Void Process RSS:* `{rss_mb} MB`\n"
                f"• *Peak RSS:* `{rss_mb} MB`\n"
                f"• *System Total:* `{sys_total}`\n"
                f"• *System Available:* `{sys_avail}`\n"
                f"• *Context Switches:* `{usage.ru_nvcsw}` vol / `{usage.ru_nivcsw}` invol",
                parse_mode="Markdown",
            )

        elif data == "tel_dump":
            card = global_fastfetch_collector.render_markdown()
            bot.send_message(chat_id, card, parse_mode="Markdown")
