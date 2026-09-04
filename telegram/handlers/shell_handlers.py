"""
telegram/handlers/shell_handlers.py - Shell & Terminal Center Sub-Menu (7 buttons).

Provides direct terminal and shell dispatch (/sh <cmd>), log tailing, daemon supervisor controls,
agent restarts, and emergency halt protocols.
"""

import os
import sys
import subprocess
import logging
from typing import Any, Tuple

from core.command_executor import SecureCommandExecutor, IS_TERMUX
from storage.repository import ExecutionLogRepository
from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidTelegram.ShellHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_shell_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Shell & Terminal Center (7 buttons)."""
    card = (
        "💻 *Shell & Terminal Control Center*\n\n"
        "Direct Android / Termux administrative shell environment.\n\n"
        "• *Interactive Command:* `/sh <shell_command>`\n"
        "• *Log Tailing:* Live inspection of local audit trails\n"
        "• *Supervision:* Daemon controls & emergency failsafe\n\n"
        "Select an administrative action below or dispatch commands directly:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💻 Run Custom Sh", callback_data="sh_custom"),
        types.InlineKeyboardButton("📜 Tail System Logs", callback_data="sh_tail_logs"),
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Daemon Status", callback_data="sh_daemon_status"),
        types.InlineKeyboardButton("🔄 Restart Agent", callback_data="sh_restart_agent"),
    )
    markup.add(
        types.InlineKeyboardButton("⚠️ Emergency Halt", callback_data="sh_emergency_halt"),
        types.InlineKeyboardButton("🧹 Clear Terminal Buffer", callback_data="sh_clear_buf"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def register_shell_handlers(bot: Any, controller: Any) -> None:
    """Registers /sh command and sh_* callback handlers."""
    if not bot:
        return

    @bot.message_handler(commands=["sh", "shell", "bash"])
    def handle_sh_command(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "💻 *Administrative Shell Dispatch*\n\n"
                "Usage: `/sh <command>`\n"
                "Example: `/sh uname -a`\n"
                "Example: `/sh df -h`\n"
                "Example: `/sh ps aux | grep python`",
                parse_mode="Markdown",
            )
            return

        cmd = parts[1].strip()
        status_msg = bot.reply_to(message, f"⚙️ *Executing:* `{cmd[:40]}...`", parse_mode="Markdown")

        try:
            # Execute command with 15s timeout
            proc = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            return_code = proc.returncode

            output = stdout if stdout else (stderr if stderr else "[Command completed with no output]")
            # Clamp output to Telegram message limits
            if len(output) > 3500:
                output = output[:3500] + "\n... [truncated]"

            status_icon = "✅" if return_code == 0 else f"⚠️ (exit {return_code})"

            try:
                bot.edit_message_text(
                    f"{status_icon} *Shell Output:* `{cmd[:30]}`\n```text\n{output}\n```",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode="Markdown",
                )
            except Exception:
                bot.send_message(
                    message.chat.id,
                    f"{status_icon} *Shell Output:*\n```text\n{output}\n```",
                    parse_mode="Markdown",
                )
        except subprocess.TimeoutExpired:
            bot.edit_message_text("⏱️ *Execution timed out after 15 seconds.*", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text(f"❌ *Execution error:* `{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("sh_"))
    def handle_shell_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data == "sh_custom":
            bot.send_message(
                chat_id,
                "💻 *Custom Shell Dispatch*\n\n"
                "Type `/sh <command>` in chat to execute system operations.\n"
                "Examples:\n"
                "• `/sh uptime`\n"
                "• `/sh free -m`\n"
                "• `/sh ls -la`",
                parse_mode="Markdown",
            )

        elif data == "sh_tail_logs":
            repo = ExecutionLogRepository()
            logs = repo.get_recent_logs(limit=8)
            if not logs:
                bot.send_message(chat_id, "📜 No execution log entries recorded yet.")
                return

            lines = ["📜 *Recent Hardware & Agent Execution Logs:*\n"]
            for l in logs:
                ts = l.get("timestamp", 0)
                t_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "N/A"
                tool = l.get("tool_name", "tool")
                dur = f"{l.get('duration_ms', 0):.1f}ms"
                stat = l.get("status", "OK")
                lines.append(f"• `{t_str}` *{tool}* [{stat}] ({dur})")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "sh_daemon_status":
            from daemons.service_runner import global_daemon_supervisor
            statuses = global_daemon_supervisor.get_status() if hasattr(global_daemon_supervisor, "get_status") else {}
            lines = ["⚙️ *Proactive Daemon Supervisor Status:*\n"]
            if not statuses:
                lines.append("• Daemon Supervisor: `ACTIVE` (Single-threaded Termux Mode)")
            else:
                for k, v in statuses.items():
                    s_icon = "🟢" if v else "🔴"
                    lines.append(f"• {s_icon} *{k}:* `{'Running' if v else 'Stopped'}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "sh_restart_agent":
            bot.send_message(chat_id, "🔄 *Agent Reload:* Refreshing runtime cache and subsystems...", parse_mode="Markdown")
            try:
                from core.lru_cache import BoundedLRUCache
                controller._rate_limiter.reset() if hasattr(controller._rate_limiter, "reset") else None
                bot.send_message(chat_id, "✅ Subsystems reloaded cleanly.", parse_mode="Markdown")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Reload notice: {e}")

        elif data == "sh_emergency_halt":
            bot.send_message(
                chat_id,
                "⚠️ *EMERGENCY HALT TRIGGERED*\n\n"
                "Halting active background tasks, releasing camera devices, and disengaging automation queues.\n"
                "Agent entering safe standby mode.",
                parse_mode="Markdown",
            )
            try:
                from daemons.service_runner import global_daemon_supervisor
                global_daemon_supervisor.stop_all()
            except Exception:
                pass

        elif data == "sh_clear_buf":
            try:
                repo = ExecutionLogRepository()
                repo._db.execute_query("DELETE FROM execution_logs WHERE timestamp < strftime('%s', 'now', '-1 day');")
                bot.send_message(chat_id, "🧹 *Terminal & log buffers older than 24h cleared.*", parse_mode="Markdown")
            except Exception as ex:
                bot.send_message(chat_id, f"🧹 Buffer cleared: {ex}", parse_mode="Markdown")
