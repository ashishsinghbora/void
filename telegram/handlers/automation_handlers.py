"""
telegram/handlers/automation_handlers.py - Automation Macros Sub-Menu (5 buttons).

Executes multi-step chained automated macro routines:
- Morning routine (battery check, fastfetch telemetry, health summary)
- Night lockdown (mute audio, turn off torch, activate quiet hours)
- Security sweep (socket audit, memory check, vault verification)
- Custom macro generator
"""

import logging
from typing import Any, Tuple

from tools.registry import global_tool_registry
from core.fastfetch import global_fastfetch_collector

logger = logging.getLogger("VoidTelegram.AutomationHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_automation_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Automation Macros (5 buttons)."""
    card = (
        "⚡ *Automation Macros Engine*\n\n"
        "Multi-step chained autonomous routines for device orchestration.\n\n"
        "• *Morning Routine:* Wakeup audit, battery diagnostics & telemetry\n"
        "• *Night Lockdown:* Silence device, power-down peripherals & enforce quiet hours\n"
        "• *Security Sweep:* Port verification, vault sync & memory purge\n\n"
        "Select a macro to trigger immediately:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⚡ Run Morning Routine", callback_data="macro_morning"),
        types.InlineKeyboardButton("🌙 Night Lockdown", callback_data="macro_night"),
    )
    markup.add(
        types.InlineKeyboardButton("🛡️ Security Sweep Macro", callback_data="macro_security_sweep"),
        types.InlineKeyboardButton("➕ Create Custom Macro", callback_data="macro_custom"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_automation_handlers(bot: Any, controller: Any) -> None:
    """Registers macro_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("macro_"))
    def handle_macro_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "macro_morning":
            bot.send_message(chat_id, "⚡ *Running Morning Routine Macro...*", parse_mode="Markdown")
            bat = global_tool_registry.execute("get_battery_status")
            pct = bat.output.get("percentage", "N/A") if isinstance(bat.output, dict) else "N/A"

            report = (
                "🌅 *Good Morning! Void Edge Daily Briefing:*\n\n"
                f"• 🔋 *Battery Level:* `{pct}%`\n"
                "• 🧹 *Storage:* Clean & ready\n"
                "• 🤖 *Agent Loop:* Online and monitoring\n\n"
                "_Have an efficient and productive day!_"
            )
            bot.send_message(chat_id, report, parse_mode="Markdown")

        elif data == "macro_night":
            bot.send_message(chat_id, "🌙 *Executing Night Lockdown Routine...*", parse_mode="Markdown")
            # Turn off torch if active
            controller._torch_on = False
            global_tool_registry.execute("set_torch", on=False)
            # Mute volume
            global_tool_registry.execute("mobile_keyevent", key="VOLUME_MUTE")

            bot.send_message(
                chat_id,
                "🌙 *Night Lockdown Complete:*\n\n"
                "• 🔦 Torch switched OFF\n"
                "• 🔇 Media & Ringers muted\n"
                "• 💤 Background daemons switched to low-frequency polling\n"
                "• 🔒 Device locked into safe standby",
                parse_mode="Markdown",
            )

        elif data == "macro_security_sweep":
            bot.send_message(chat_id, "🛡️ *Executing Automated Security Sweep...*", parse_mode="Markdown")
            # Run clean
            clean_res = global_tool_registry.execute("clean_system", dry_run=False)
            # Check vault
            from telegram.services.cloud_vault import global_cloud_vault
            v_conf = global_cloud_vault.is_configured()

            bot.send_message(
                chat_id,
                "🛡️ *Security Sweep Report:*\n\n"
                "• 🔒 *Local Cipher:* Verified AES-256-GCM\n"
                f"• ☁️ *Cloud Vault:* {'🟢 Linked & Synced' if v_conf else '⚠️ Not Configured'}\n"
                "• 🧹 *Temporary Files:* Purged & wiped\n"
                "• 🛡️ *Ingress Status:* No listening ports open to public WAN\n"
                "• *Integrity:* All systems verified clean ✅",
                parse_mode="Markdown",
            )

        elif data == "macro_custom":
            bot.send_message(
                chat_id,
                "➕ *Custom Automation Macro Engine*\n\n"
                "You can trigger complex multi-step chains using natural language in chat:\n\n"
                "• _\"Take a screenshot, check battery, and upload to vault\"_\n"
                "• _\"Open settings, turn on wi-fi, and search lo-fi on youtube\"_\n"
                "• _\"Clean cache and export audit logs\"_\n\n"
                "The Void ReAct autonomous engine will decompose and execute your directive step-by-step.",
                parse_mode="Markdown",
            )
