"""
telegram/handlers/vault_handlers.py - Cloud Vault & Media Sub-Menu (7 buttons).

Manages Telegram group cloud storage, persistent multi-step memory, front/rear camera
streaming snapshots, media purging, and cloud file indexing.
"""

import os
import time
import logging
from typing import Any, Optional, Tuple

from telegram.services.cloud_vault import global_cloud_vault
from telegram.database.db_manager import global_bot_db
from tools.registry import global_tool_registry

logger = logging.getLogger("VoidTelegram.VaultHandlers")

try:
    from telebot import types
except ImportError:
    types = None


def get_vault_submenu() -> Tuple[str, Any]:
    """Returns card text and inline keyboard for Cloud Vault & Media sub-menu (7 buttons)."""
    info = global_cloud_vault.get_vault_telemetry()
    configured = info.get("configured", False)
    gid = info.get("group_id", "Not Linked")
    title = info.get("group_title") or "None"
    f_count = info.get("total_files", 0)
    mb_stored = round(info.get("bytes_stored", 0) / (1024 * 1024), 2)

    status_icon = "🟢 Connected" if configured else "🔴 Inactive"

    card = (
        "☁️ *Cloud Vault & Media Center*\n\n"
        f"• *Vault Status:* `{status_icon}`\n"
        f"• *Linked Group:* `{title}` (`{gid}`)\n"
        f"• *Stored Artifacts:* `{f_count}` files (`{mb_stored} MB`)\n\n"
        "Persistent cloud storage & instant camera media pipeline.\n"
        "Select a function below or run `/vault` | `/set_vault <id>`:"
    )

    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🗄️ Open Vault Index", callback_data="vault_index"),
        types.InlineKeyboardButton("📸 Instant Snapshot", callback_data="vault_snap"),
    )
    markup.add(
        types.InlineKeyboardButton("🎥 Front Cam Stream", callback_data="vault_cam_front"),
        types.InlineKeyboardButton("🎥 Rear Cam Stream", callback_data="vault_cam_rear"),
    )
    markup.add(
        types.InlineKeyboardButton("📂 Vault File Explorer", callback_data="vault_explorer"),
        types.InlineKeyboardButton("🧹 Purge Old Media", callback_data="vault_purge"),
    )
    markup.add(types.InlineKeyboardButton("🔙 Root Menu", callback_data="cb_back_main"))
    return card, markup


def get_vault_keyboard(is_configured: bool = False) -> Any:
    """Constructs inline action keyboard for Cloud Vault management."""
    return get_vault_submenu()[1]


def render_vault_status_card() -> str:
    """Generates formatted Markdown card describing the Cloud Vault status."""
    return get_vault_submenu()[0]


def register_vault_handlers(bot: Any, controller: Any) -> None:
    """Registers /vault, /set_vault, /vault_files and vault_* callback handlers."""
    if not bot:
        return

    # Ensure vault is bound to bot instance
    global_cloud_vault.bind_bot(bot)

    @bot.message_handler(commands=["vault", "cloud_vault"])
    def handle_vault(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        card, markup = get_vault_submenu()
        bot.reply_to(message, card, reply_markup=markup, parse_mode="Markdown")

    @bot.message_handler(commands=["link_vault", "bind_vault"])
    def handle_link_vault_in_group(message):
        """Pairs the current group as Cloud Vault directly with one command."""
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        chat_id = message.chat.id
        chat_type = message.chat.type

        if chat_type not in ("group", "supergroup"):
            bot.reply_to(
                message,
                "ℹ️ *Command must be sent inside your Telegram group!*\n\n"
                "1. Add `@voidtermuxbot` to your private group as an **Administrator**.\n"
                "2. Type `/link_vault` inside that group to bind it as your permanent Cloud Vault database.",
                parse_mode="Markdown",
            )
            return

        title = getattr(message.chat, "title", "Void Vault Group")
        global_cloud_vault.set_vault_group_id(chat_id, group_title=title)

        bot.reply_to(
            message,
            f"🚀 *This Group is now Linked as your Persistent Cloud Vault!* ☁️\n\n"
            f"• *Group Title:* `{title}`\n"
            f"• *Chat ID:* `{chat_id}`\n\n"
            "All autonomous memory backups, device screenshots, camera photos, and audit trails "
            "will be mirrored here automatically as a decentralized database.",
            parse_mode="Markdown",
        )

    @bot.message_handler(commands=["set_vault"])
    def handle_set_vault(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        # If user runs /set_vault directly inside a group, bind it immediately
        if message.chat.type in ("group", "supergroup"):
            handle_link_vault_in_group(message)
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.reply_to(
                message,
                "⚠️ *Usage:* `/set_vault <group_link_or_chat_id>`\n\n"
                "*Options:*\n"
                "• In-Group Pairing: Type `/link_vault` directly inside your Telegram group\n"
                "• By Chat ID: `/set_vault -1001234567890`\n"
                "• By Group Link: `/set_vault https://t.me/+YourInviteLink`\n"
                "• By Username: `/set_vault @your_vault_group`",
                parse_mode="Markdown",
            )
            return

        target = parts[1].strip()

        # Case 1: Numeric Chat ID
        if target.startswith("-100") or (target.startswith("-") and target[1:].isdigit()) or target.isdigit():
            try:
                chat_id = int(target)
                try:
                    chat_info = bot.get_chat(chat_id)
                    title = getattr(chat_info, "title", "Void Vault Group")
                except Exception:
                    title = "Void Vault Group"

                global_cloud_vault.set_vault_group_id(chat_id, group_title=title)
                bot.reply_to(
                    message,
                    f"✅ *Cloud Vault linked successfully!*\n\n"
                    f"• *Group Title:* `{title}`\n"
                    f"• *Chat ID:* `{chat_id}`\n\n"
                    "All captured media and memory states will now mirror here automatically.",
                    reply_markup=get_vault_submenu()[1],
                    parse_mode="Markdown",
                )
                return
            except ValueError:
                pass

        # Case 2: Public Username (@group or t.me/group)
        if target.startswith("@") or ("t.me/" in target and "+" not in target and "joinchat" not in target):
            username = target.split("t.me/")[-1] if "t.me/" in target else target
            if not username.startswith("@"):
                username = f"@{username}"
            try:
                chat_info = bot.get_chat(username)
                chat_id = chat_info.id
                title = getattr(chat_info, "title", username)
                global_cloud_vault.set_vault_group_id(chat_id, group_title=title)
                bot.reply_to(
                    message,
                    f"✅ *Cloud Vault linked via Username!*\n\n"
                    f"• *Group Title:* `{title}`\n"
                    f"• *Chat ID:* `{chat_id}`",
                    reply_markup=get_vault_submenu()[1],
                    parse_mode="Markdown",
                )
                return
            except Exception as e:
                logger.warning(f"Could not resolve username {username}: {e}")

        # Case 3: Private Invite Link (e.g. https://t.me/+987ZzHO8PrY3N2Fl)
        if "t.me/" in target:
            # Store target link in vault config
            try:
                global_cloud_vault.db.set_vault_config("pending_invite_link", target)
            except Exception:
                pass

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🚀 Open Group Link", url=target))
            markup.add(types.InlineKeyboardButton("🔄 Refresh Vault Status", callback_data="vault_index"))

            bot.reply_to(
                message,
                "🔗 *Telegram Group Link Registered!*\n\n"
                f"Link: `{target}`\n\n"
                "⚡ *Final Step to Activate Cloud Database:*\n"
                "1. Open your group using the button below.\n"
                "2. Add `@voidtermuxbot` to that group as an **Administrator**.\n"
                "3. Type `/link_vault` directly inside the group chat!\n\n"
                "_As soon as you type `/link_vault` in the group, Void will automatically pair it as your permanent cloud memory vault!_",
                reply_markup=markup,
                parse_mode="Markdown",
            )
            return

        bot.reply_to(
            message,
            "⚠️ Could not automatically parse group link. Please ensure bot is added as Admin to your group and type `/link_vault` inside that group.",
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

    @bot.callback_query_handler(func=lambda call: call.data and (call.data.startswith("vault_") or call.data in ("cb_vault", "cb_vault_status", "cb_vault_backup", "cb_vault_files")))
    def handle_vault_callbacks(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        data = call.data
        bot.answer_callback_query(call.id)

        if data in ("vault_index", "cb_vault", "cb_vault_status"):
            card, markup = get_vault_submenu()
            try:
                bot.edit_message_text(card, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, card, reply_markup=markup, parse_mode="Markdown")

        elif data in ("vault_snap", "cb_screenshot"):
            bot.send_message(chat_id, "📸 *Capturing instant snapshot...*", parse_mode="Markdown")
            if hasattr(controller, "_execute_screenshot_capture"):
                controller._execute_screenshot_capture(chat_id)
            else:
                res = global_tool_registry.execute("capture_screen")
                bot.send_message(chat_id, f"📸 Snapshot: `{res.output or res.error}`", parse_mode="Markdown")

        elif data == "vault_cam_front":
            bot.send_message(chat_id, "🎥 *Capturing Front Camera photo...*", parse_mode="Markdown")
            res = global_tool_registry.execute("take_camera_photo", camera_id="1")
            bot.send_message(chat_id, f"🎥 Front Cam: `{res.output or res.error}`", parse_mode="Markdown")

        elif data == "vault_cam_rear":
            bot.send_message(chat_id, "🎥 *Capturing Rear Camera photo...*", parse_mode="Markdown")
            if hasattr(controller, "_execute_photo_capture"):
                controller._execute_photo_capture(chat_id)
            else:
                res = global_tool_registry.execute("take_camera_photo", camera_id="0")
                bot.send_message(chat_id, f"🎥 Rear Cam: `{res.output or res.error}`", parse_mode="Markdown")

        elif data in ("vault_explorer", "cb_vault_files"):
            records = global_cloud_vault.query_vault(limit=8)
            if not records:
                bot.send_message(chat_id, "📁 *No vault files recorded yet.*", parse_mode="Markdown")
            else:
                lines = ["📂 *Vault File Explorer (Recent 8 Items):*\n"]
                for r in records:
                    ts = r.created_at[:16].replace("T", " ")
                    mb = round(r.file_size / (1024 * 1024), 2)
                    lines.append(f"• `#{r.id}` *{r.file_name}* ({mb} MB) [{r.category}]")
                    lines.append(f"  Telegram Msg: `#{r.telegram_message_id}` | `{ts}`")
                bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif data == "vault_purge":
            # Purge local cache and temp media
            res = global_tool_registry.execute("clean_system", dry_run=False)
            summary = res.output.get("summary", "Old cache cleaned") if isinstance(res.output, dict) else str(res.output)
            bot.send_message(chat_id, f"🧹 *Vault Media Purge Complete:*\n`{summary}`", parse_mode="Markdown")

        elif data == "cb_vault_backup":
            if not global_cloud_vault.is_configured():
                bot.send_message(chat_id, "⚠️ Vault not configured. Add bot to a group as Admin or run `/set_vault <id>`.", parse_mode="Markdown")
            else:
                res = global_cloud_vault.upload_memory_snapshot()
                if res.get("success"):
                    bot.send_message(chat_id, f"✅ *Memory snapshot backed up to Cloud Vault!* (Msg #{res.get('telegram_message_id')})", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, f"❌ Backup failed: {res.get('error')}", parse_mode="Markdown")

    # Group Auto-Detection Listener
    @bot.message_handler(
        func=lambda msg: msg.chat.type in ("group", "supergroup"),
        content_types=["text", "new_chat_members"],
    )
    def handle_group_activity(message):
        """Auto-detects groups where bot is added as admin to link as vault."""
        chat_id = message.chat.id
        chat_title = getattr(message.chat, "title", "Telegram Group")

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
