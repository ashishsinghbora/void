"""
telegram/handlers/vault_handlers.py - Telegram Group Cloud Storage & Memory Vault Handlers.

Manages group vault auto-detection, manual vault binding, memory backup triggering,
and cloud file indexing for the "Brain-in-Cloud" architecture.
"""

import logging
import time
from typing import Any, Optional

from telegram.services.cloud_vault import global_cloud_vault
from telegram.database.db_manager import global_bot_db

logger = logging.getLogger("VoidTelegram.VaultHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_vault_keyboard(is_configured: bool = False) -> Any:
    """Constructs inline action keyboard for Cloud Vault management."""
    if types is None:
        return None

    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_configured:
        btn_backup = types.InlineKeyboardButton("💾 Backup Memory Now", callback_data="cb_vault_backup")
        btn_files = types.InlineKeyboardButton("📁 Browse Files", callback_data="cb_vault_files")
        markup.add(btn_backup, btn_files)
    btn_refresh = types.InlineKeyboardButton("🔄 Refresh Status", callback_data="cb_vault_status")
    btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main")
    markup.add(btn_refresh, btn_back)
    return markup


def render_vault_status_card() -> str:
    """Generates formatted Markdown card describing the Cloud Vault status."""
    info = global_cloud_vault.get_vault_telemetry()
    configured = info.get("configured", False)

    if not configured:
        return (
            "☁️ *Void Cloud Memory Vault: Inactive*\n\n"
            "Your Void edge agent supports using any private Telegram group as an "
            "infinite, zero-cost cloud storage vault and persistent memory store.\n\n"
            "• *Automated Setup:* Add `@voidtermuxbot` to your private group and grant it **Admin** permissions.\n"
            "• *Manual Setup:* Type `/set_vault <chat_id>` (e.g. `/set_vault -1001234567890`)\n\n"
            "🔒 _All uploads are indexed locally with SHA-256 and tagged `#VOID_VAULT`._"
        )

    gid = info.get("group_id", "N/A")
    title = info.get("group_title") or "Void Vault Group"
    f_count = info.get("total_files", 0)
    bytes_stored = info.get("bytes_stored", 0)
    mb_stored = round(bytes_stored / (1024 * 1024), 2)
    last_up = info.get("last_upload_iso", "Never")

    return (
        f"☁️ *Void Cloud Memory Vault: Connected ✅*\n\n"
        f"• *Vault Group:* `{title}`\n"
        f"• *Group Chat ID:* `{gid}`\n"
        f"• *Stored Files:* `{f_count}` items (`{mb_stored} MB`)\n"
        f"• *Last Backup:* `{last_up}`\n"
        f"• *Status:* 🟢 Mirroring Active (Screenshots, Media, Memories)\n\n"
        "💡 _Commands:_\n"
        "• `/vault` - Inspect vault status\n"
        "• `/vault_files` - View recent vault records\n"
        "• `/set_vault <id>` - Switch to another group"
    )


def register_vault_handlers(bot: Any, controller: Any) -> None:
    """Registers /vault, /set_vault, /vault_files and group auto-detect handlers."""
    if not bot:
        return

    # Ensure vault is bound to bot instance
    global_cloud_vault.bind_bot(bot)

    @bot.message_handler(commands=["vault", "cloud_vault"])
    def handle_vault(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        card = render_vault_status_card()
        is_conf = global_cloud_vault.is_configured()
        bot.reply_to(message, card, reply_markup=get_vault_keyboard(is_conf), parse_mode="Markdown")

    @bot.message_handler(commands=["set_vault"])
    def handle_set_vault(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.reply_to(
                message,
                "⚠️ *Usage:* `/set_vault <group_chat_id>`\nExample: `/set_vault -1001234567890`\n\n"
                "_Tip: Add the bot to your group and it will auto-detect the ID!_",
                parse_mode="Markdown",
            )
            return

        raw_id = parts[1].strip()
        try:
            chat_id = int(raw_id)
        except ValueError:
            bot.reply_to(message, "❌ Invalid chat ID format. Must be an integer (usually starting with `-100`).")
            return

        # Verify chat with Telegram API
        try:
            chat_info = bot.get_chat(chat_id)
            title = getattr(chat_info, "title", "Void Vault Group")
        except Exception as e:
            logger.warning(f"Failed to query chat {chat_id}: {e}")
            title = "Void Vault Group"

        global_cloud_vault.set_vault_group_id(chat_id, group_title=title)

        # Send greeting to vault group
        try:
            bot.send_message(
                chat_id,
                "🚀 *Void Cloud Storage Vault Initialized!*\n\n"
                "This group has been bound as the primary storage and memory vault for Void Edge Agent.\n"
                "• Autonomous memory state backups\n"
                "• Device screenshot and media mirroring\n"
                "• Real-time query retrieval via `#VOID_VAULT` tags.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Could not post announcement to vault group: {e}")

        bot.reply_to(
            message,
            f"✅ *Cloud Vault linked successfully!*\n\n"
            f"• *Group Title:* `{title}`\n"
            f"• *Chat ID:* `{chat_id}`\n\n"
            "All captured media and memory states will now mirror here automatically.",
            reply_markup=get_vault_keyboard(True),
            parse_mode="Markdown",
        )

    @bot.message_handler(commands=["vault_files"])
    def handle_vault_files(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        parts = message.text.strip().split()
        category = parts[1] if len(parts) > 1 else None

        records = global_cloud_vault.query_vault(category=category, limit=8)
        if not records:
            bot.reply_to(
                message,
                "📁 *No vault files recorded yet.*\n"
                "Once you take screenshots, photos, or backup memories, they will appear here.",
                parse_mode="Markdown",
            )
            return

        lines = ["📁 *Recent Cloud Vault Files:*\n"]
        for r in records:
            ts = r.created_at[:16].replace("T", " ")
            mb = round(r.file_size / (1024 * 1024), 2)
            lines.append(f"• `#{r.id}` *{r.file_name}* ({mb} MB)")
            lines.append(f"  Category: `{r.category}` | Telegram Msg: `#{r.telegram_message_id}` | {ts}")

        lines.append("\n_All files are accessible directly in your linked Telegram group vault._")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

    # ----------------------------------------------------------------------
    # Group Vault Auto-Detection Listener
    # ----------------------------------------------------------------------
    @bot.message_handler(
        func=lambda msg: msg.chat.type in ("group", "supergroup"),
        content_types=["text", "new_chat_members"],
    )
    def handle_group_activity(message):
        """Auto-detects groups where bot is added as admin to link as vault."""
        chat_id = message.chat.id
        chat_title = getattr(message.chat, "title", "Telegram Group")

        # If vault is not yet configured, attempt auto-configuration
        if not global_cloud_vault.is_configured():
            try:
                bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
                if bot_member.status in ("administrator", "creator"):
                    global_cloud_vault.set_vault_group_id(chat_id, group_title=chat_title)
                    logger.info(f"Auto-detected and configured group vault: {chat_id} ({chat_title})")
                    bot.send_message(
                        chat_id,
                        "🚀 *Void Cloud Storage Vault Activated!* ☁️\n\n"
                        f"Detected bot as administrator in *{chat_title}*.\n"
                        "This channel is now auto-configured as the persistent memory & media vault.\n"
                        "All autonomous memory snapshots and captured media will mirror here.",
                        parse_mode="Markdown",
                    )
            except Exception as e:
                logger.debug(f"Group check failed for {chat_id}: {e}")
