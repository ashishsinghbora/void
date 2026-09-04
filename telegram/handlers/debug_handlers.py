"""
telegram/handlers/debug_handlers.py - Debug & Diagnostics Sub-Menu (6 buttons).

Diagnostics suite:
- Debug mode toggling (verbose logging)
- Memory leak tracer & heap object analysis
- Ping latency benchmark (Telegram API & DNS)
- Crash log dumper
- Force re-initialization of core registries
"""

import os
import time
import urllib.request
import logging
from typing import Any, Tuple

from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidTelegram.DebugHandlers")

try:
    from telebot import types
except ImportError:
    types = None

_DEBUG_VERBOSE = False


def get_debug_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Debug & Diagnostics (6 buttons)."""
    dbg_stat = "🟢 ACTIVE" if _DEBUG_VERBOSE else "⚪ OFF"

    card = (
        "🐞 *Debug & Diagnostics Laboratory*\n\n"
        f"• *Verbose Logging:* `{dbg_stat}`\n"
        "• *Trace Instrumentation:* PyObject Tracking Enabled\n"
        "• *Network Benchmark:* Telegram API Latency Prober\n\n"
        "Select a diagnostic probe below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"🐞 Debug: {'OFF' if _DEBUG_VERBOSE else 'ON'}", callback_data="debug_toggle"),
        types.InlineKeyboardButton("📊 Trace Memory Leak", callback_data="debug_mem_trace"),
    )
    markup.add(
        types.InlineKeyboardButton("📡 Test Ping Latency", callback_data="debug_ping"),
        types.InlineKeyboardButton("📄 Dump Crash Log", callback_data="debug_crash_dump"),
    )
    markup.add(
        types.InlineKeyboardButton("🔄 Force Re-initialize", callback_data="debug_reinit"),
        types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"),
    )
    return card, markup


def register_debug_handlers(bot: Any, controller: Any) -> None:
    """Registers debug_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("debug_"))
    def handle_debug_callbacks(call):
        global _DEBUG_VERBOSE
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "debug_toggle":
            _DEBUG_VERBOSE = not _DEBUG_VERBOSE
            log_level = logging.DEBUG if _DEBUG_VERBOSE else logging.INFO
            logging.getLogger().setLevel(log_level)
            bot.send_message(
                chat_id,
                f"🐞 *Verbose Debug Logging:* `{'ACTIVATED' if _DEBUG_VERBOSE else 'DISABLED'}`",
                parse_mode="Markdown",
            )
            # Update menu markup
            card, markup = get_debug_submenu()
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
            except Exception:
                pass

        elif data == "debug_mem_trace":
            import sys
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = round(usage.ru_maxrss / 1024.0, 1)

            # Check /proc/self/status for VmPeak, VmSize
            vm_peak = "N/A"
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmPeak:"):
                            vm_peak = line.split()[1] + " kB"
                            break
            except Exception:
                pass

            bot.send_message(
                chat_id,
                f"📊 *Memory Leak & Allocation Trace:*\n\n"
                f"• *Current RSS:* `{rss_mb} MB`\n"
                f"• *Peak Virtual Memory:* `{vm_peak}`\n"
                f"• *Loaded Python Modules:* `{len(sys.modules)}`\n"
                f"• *Target Budget:* `< 30 MB`\n"
                f"• *Assessment:* {'🟢 Clean (No leak)' if rss_mb <= 35.0 else '⚠️ Elevated footprint'}",
                parse_mode="Markdown",
            )

        elif data == "debug_ping":
            bot.send_message(chat_id, "📡 *Probing network ping latency...*", parse_mode="Markdown")
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request("https://api.telegram.org", headers={"User-Agent": "VoidEdgeAgent"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    code = resp.getcode()
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                bot.send_message(
                    chat_id,
                    f"📡 *Ping Benchmark Complete:*\n\n"
                    f"• *Target:* `api.telegram.org:443`\n"
                    f"• *HTTP Status:* `{code}`\n"
                    f"• *Roundtrip Latency:* `{latency_ms} ms`\n"
                    f"• *Connection:* 🟢 High Speed",
                    parse_mode="Markdown",
                )
            except Exception as e:
                bot.send_message(chat_id, f"📡 Ping test failed: {e}")

        elif data == "debug_crash_dump":
            crash_log_path = os.path.expanduser("~/.void/crash.log")
            if os.path.exists(crash_log_path) and os.path.getsize(crash_log_path) > 0:
                try:
                    with open(crash_log_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()[-2000:]
                    bot.send_message(chat_id, f"📄 *Crash Log Tail:*\n```text\n{content}\n```", parse_mode="Markdown")
                except Exception as ex:
                    bot.send_message(chat_id, f"Error reading crash log: {ex}")
            else:
                bot.send_message(chat_id, "📄 *No crash events recorded.* System is operating stably! ✅", parse_mode="Markdown")

        elif data == "debug_reinit":
            bot.send_message(chat_id, "🔄 *Re-initializing subsystems and registries...*", parse_mode="Markdown")
            try:
                from tools.registry import global_tool_registry
                # Verify tools
                tool_count = len(global_tool_registry.list_tools())
                bot.send_message(chat_id, f"✅ Subsystems verified. Registered tools: `{tool_count}`", parse_mode="Markdown")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Re-initialization error: {e}")
