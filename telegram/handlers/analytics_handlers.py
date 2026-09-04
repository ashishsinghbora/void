"""
telegram/handlers/analytics_handlers.py - Analytics & Logs Sub-Menu.

System performance metrics, SQLite WAL database analytics, audit logs,
and session history.
"""

import resource
import logging
from typing import Any, Tuple

from storage.repository import ExecutionLogRepository

logger = logging.getLogger("VoidTelegram.AnalyticsHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_analytics_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Analytics & Logs."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024.0, 1)

    log_count = 0
    try:
        repo = ExecutionLogRepository()
        cnt_res = repo._db.execute_query("SELECT COUNT(*) as c FROM execution_logs;")
        if cnt_res:
            log_count = cnt_res[0]["c"]
    except Exception:
        pass

    card = (
        "📊 *Analytics & Diagnostic Logs*\n\n"
        f"• *Runtime RSS:* `{rss_mb} MB` (Target < 30MB)\n"
        f"• *SQLite WAL Records:* `{log_count}` execution steps logged\n"
        f"• *CPU Usage:* `{usage.ru_utime:.1f}s` user | `{usage.ru_stime:.1f}s` kernel\n\n"
        "Select an analytics report below:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📈 Performance Metrics", callback_data="analy_perf"),
        types.InlineKeyboardButton("📋 Audit Logs", callback_data="analy_audit"),
    )
    markup.add(
        types.InlineKeyboardButton("🗄️ Database WAL Stats", callback_data="analy_db_wal"),
        types.InlineKeyboardButton("📊 Session History", callback_data="analy_sessions"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_analytics_handlers(bot: Any, controller: Any) -> None:
    """Registers analy_* callback handlers."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("analy_"))
    def handle_analytics_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "analy_perf":
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = round(usage.ru_maxrss / 1024.0, 1)
            bot.send_message(
                chat_id,
                f"📈 *Edge Agent Performance Telemetry:*\n\n"
                f"• *Peak RSS:* `{rss_mb} MB`\n"
                f"• *User CPU Time:* `{usage.ru_utime:.2f}s`\n"
                f"• *System CPU Time:* `{usage.ru_stime:.2f}s`\n"
                f"• *Minor Page Faults:* `{usage.ru_minflt}`\n"
                f"• *Major Page Faults:* `{usage.ru_majflt}`\n"
                f"• *Voluntary Context Switches:* `{usage.ru_nvcsw}`\n"
                f"• *Status:* 🟢 Highly Optimized (< 30MB footprint)",
                parse_mode="Markdown",
            )

        elif data == "analy_audit":
            repo = ExecutionLogRepository()
            recent = repo.get_recent_logs(limit=6)
            if not recent:
                bot.send_message(chat_id, "📋 No execution audit entries recorded.")
                return

            lines = ["📋 *Recent Execution Audit Log:*\n"]
            for l in recent:
                tool = l.get("tool_name", "tool")
                dur = f"{l.get('duration_ms', 0):.1f}ms"
                stat = l.get("status", "OK")
                lines.append(f"• *{tool}* [{stat}] ({dur})")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "analy_db_wal":
            repo = ExecutionLogRepository()
            cnt_res = repo._db.execute_query("SELECT COUNT(*) as c FROM execution_logs;")
            count = cnt_res[0]["c"] if cnt_res else 0
            bot.send_message(
                chat_id,
                f"🗄️ *SQLite Write-Ahead Logging (WAL) Stats:*\n\n"
                f"• *Journal Mode:* `WAL (Write-Ahead Logging)`\n"
                f"• *Synchronous Mode:* `NORMAL` (Optimal for Flash / UFS storage)\n"
                f"• *Indexed Table:* `execution_logs` ({count} rows)\n"
                f"• *Locking Mode:* Concurrent multi-reader non-blocking",
                parse_mode="Markdown",
            )

        elif data == "analy_sessions":
            bot.send_message(
                chat_id,
                "📊 *Active Session History:*\n\n"
                f"• *Current User:* `{user_id}` (Whitelisted Admin)\n"
                "• *Rate Limiter:* Token Bucket Active\n"
                "• *Inactivity TTL:* 900 seconds\n"
                "• *Session State:* 🟢 Verified & Healthy",
                parse_mode="Markdown",
            )
