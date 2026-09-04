"""
telegram/services/cloud_vault.py - Telegram Group Cloud Storage & Memory Vault ("Brain-in-Cloud").

Routes autonomous agent memory states, vector snapshots, captured photos, audio,
and documents directly to a designated Telegram Group, functioning as a decentralized,
unlimited persistent cloud storage backend for Void.
"""

import os
import io
import json
import time
import uuid
import logging
from typing import Optional, List, Dict, Any

from telegram.database.models import VaultFile
from telegram.database.db_manager import global_bot_db

logger = logging.getLogger("VoidTelegram.CloudVault")

CONFIG_ENV_PATH = os.path.expanduser("~/.void/config.env")


class CloudVaultService:
    """Manages Telegram group cloud vault storage, synchronization, and memory backups."""

    def __init__(self, db: Any = None, bot: Any = None):
        self.db = db if db is not None else global_bot_db
        self._bot_instance = bot

    def set_bot_instance(self, bot: Any) -> None:
        """Binds the active telebot instance for sending and retrieving media."""
        self._bot_instance = bot

    bind_bot = set_bot_instance

    def get_vault_group_id(self) -> Optional[int]:
        """Retrieves configured Telegram group ID from DB or environment."""
        # 1. Environment variable
        env_val = os.environ.get("TELEGRAM_VAULT_GROUP_ID", "").strip()
        if env_val and (env_val.startswith("-") or env_val.isdigit()):
            try:
                return int(env_val)
            except ValueError:
                pass

        # 2. SQLite vault_config
        try:
            db_val = self.db.get_vault_config("group_id")
            if db_val:
                return int(db_val)
        except Exception:
            pass

        return None

    def get_vault_title(self) -> str:
        """Returns the human-friendly title of the active vault group."""
        try:
            return self.db.get_vault_config("group_title") or "Unnamed Cloud Vault"
        except Exception:
            return "Unnamed Cloud Vault"

    def set_vault_group_id(self, chat_id: int, title: str = "", group_title: str = "") -> None:
        """Persists the designated Telegram group vault ID to DB and config.env."""
        actual_title = group_title or title or "Void Vault Group"
        try:
            self.db.set_vault_config("group_id", str(chat_id))
            if actual_title:
                self.db.set_vault_config("group_title", actual_title)
        except Exception as e:
            logger.debug(f"Could not persist vault config to db: {e}")

        os.environ["TELEGRAM_VAULT_GROUP_ID"] = str(chat_id)

        # Update ~/.void/config.env
        try:
            os.makedirs(os.path.dirname(CONFIG_ENV_PATH), exist_ok=True)
            existing_lines = []
            if os.path.exists(CONFIG_ENV_PATH):
                with open(CONFIG_ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.startswith("TELEGRAM_VAULT_GROUP_ID"):
                            existing_lines.append(line.rstrip())

            existing_lines.append(f'TELEGRAM_VAULT_GROUP_ID="{chat_id}"')
            with open(CONFIG_ENV_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(existing_lines) + "\n")
        except Exception as e:
            logger.warning(f"Could not update {CONFIG_ENV_PATH} with vault ID: {e}")

        logger.info(f"Telegram Group Vault configured: ID={chat_id} ('{actual_title}')")

    def is_vault_configured(self) -> bool:
        """Returns True if a valid group vault is configured."""
        return self.get_vault_group_id() is not None

    is_configured = is_vault_configured

    def upload_file(
        self,
        file_path: str,
        category: str = "",
        file_type: str = "document",
        tag: str = "general",
        caption: str = "",
        bot: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Uploads an arbitrary local media file to the Telegram Group Vault,
        tagging it with structured metadata for query retrieval.
        """
        target_bot = bot or self._bot_instance
        vault_chat_id = self.get_vault_group_id()

        if not target_bot or not vault_chat_id:
            logger.debug("Vault upload skipped: bot or group vault not configured.")
            return {"success": False, "error": "Bot or group vault not configured"}

        if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
            logger.warning(f"Vault upload aborted: file '{file_path}' does not exist or is empty.")
            return {"success": False, "error": f"File '{file_path}' does not exist or is empty"}

        filename = os.path.basename(file_path)
        size_bytes = os.path.getsize(file_path)
        meta_id = f"vf_{uuid.uuid4().hex[:12]}"
        timestamp = time.time()
        effective_type = category or file_type
        effective_tag = tag if tag != "general" else (category or "general")

        structured_caption = (
            f"📦 #VOID_VAULT [type:{effective_type}] [tag:{effective_tag}]\n"
            f"📄 `{filename}` ({round(size_bytes / 1024, 1)} KB)\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}\n"
        )
        if caption:
            structured_caption += f"💬 _{caption}_\n"

        try:
            with open(file_path, "rb") as f:
                if effective_type == "photo" or filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    msg = target_bot.send_photo(
                        chat_id=vault_chat_id,
                        photo=f,
                        caption=structured_caption,
                        parse_mode="Markdown",
                    )
                    tg_file_id = msg.photo[-1].file_id if getattr(msg, "photo", None) else "unknown_photo"
                elif effective_type == "audio" or filename.lower().endswith((".3gp", ".mp3", ".ogg", ".wav", ".m4a")):
                    msg = target_bot.send_audio(
                        chat_id=vault_chat_id,
                        audio=f,
                        caption=structured_caption,
                        parse_mode="Markdown",
                    )
                    tg_file_id = msg.audio.file_id if getattr(msg, "audio", None) else "unknown_audio"
                else:
                    msg = target_bot.send_document(
                        chat_id=vault_chat_id,
                        document=f,
                        caption=structured_caption,
                        parse_mode="Markdown",
                    )
                    tg_file_id = msg.document.file_id if getattr(msg, "document", None) else "unknown_doc"

            vf = VaultFile(
                id=meta_id,
                file_id=tg_file_id,
                message_id=getattr(msg, "message_id", 0),
                chat_id=vault_chat_id,
                file_type=effective_type,
                tag=effective_tag,
                filename=filename,
                local_path=os.path.abspath(file_path),
                size_bytes=size_bytes,
                caption=caption,
                created_at=timestamp,
            )
            try:
                self.db.record_vault_file(vf)
            except Exception as dbe:
                logger.debug(f"Could not record vault file: {dbe}")

            logger.info(f"File '{filename}' successfully mirrored to Telegram Vault (msg_id={vf.message_id})")
            return {
                "success": True,
                "vault_file": vf,
                "telegram_message_id": vf.message_id,
                "telegram_file_id": vf.file_id,
                "file_name": vf.filename,
                "category": vf.file_type,
            }

        except Exception as e:
            logger.error(f"Failed to upload '{file_path}' to Telegram Vault: {e}")
            return {"success": False, "error": str(e)}

    def upload_memory_snapshot(
        self,
        session_id: str = "default",
        memory_dict: Optional[Dict[str, Any]] = None,
        bot: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Uploads serialized conversation/agent memory state directly to the vault group."""
        target_bot = bot or self._bot_instance
        vault_chat_id = self.get_vault_group_id()
        if not target_bot or not vault_chat_id:
            return {"success": False, "error": "Bot or group vault not configured"}

        if memory_dict is None:
            memory_dict = {"status": "ok", "timestamp": time.time(), "session": session_id}

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"memory_snapshot_{session_id}_{timestamp}.json"
        raw_json = json.dumps(memory_dict, indent=2)

        buf = io.BytesIO(raw_json.encode("utf-8"))
        buf.name = filename

        caption = (
            f"🧠 #VOID_VAULT [type:memory_snapshot] [tag:session_backup]\n"
            f"🆔 Session: `{session_id}`\n"
            f"📊 State Keys: `{list(memory_dict.keys())}`\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            msg = target_bot.send_document(
                chat_id=vault_chat_id,
                document=buf,
                caption=caption,
                parse_mode="Markdown",
            )
            tg_file_id = msg.document.file_id if getattr(msg, "document", None) else "unknown_doc"
            vf = VaultFile(
                id=f"vf_{uuid.uuid4().hex[:12]}",
                file_id=tg_file_id,
                message_id=getattr(msg, "message_id", 0),
                chat_id=vault_chat_id,
                file_type="memories",
                tag="session_backup",
                filename=filename,
                local_path=None,
                size_bytes=len(raw_json),
                caption=f"Snapshot for {session_id}",
                created_at=time.time(),
            )
            try:
                self.db.record_vault_file(vf)
            except Exception as dbe:
                logger.debug(f"Could not record memory vault file: {dbe}")

            logger.info(f"Memory snapshot for session {session_id} backed up to Vault.")
            return {
                "success": True,
                "vault_file": vf,
                "telegram_message_id": vf.message_id,
                "telegram_file_id": vf.file_id,
                "file_name": vf.filename,
                "category": vf.file_type,
            }
        except Exception as e:
            logger.error(f"Failed to backup memory snapshot: {e}")
            return {"success": False, "error": str(e)}

    def query_vault(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[VaultFile]:
        """Queries local index of vault files."""
        try:
            return self.db.query_vault_files(category=category, tag=tag, file_type=file_type, limit=limit)
        except Exception as e:
            logger.warning(f"query_vault error: {e}")
            return []

    def download_vault_file(
        self,
        file_id: str,
        destination_path: str,
        bot: Optional[Any] = None,
    ) -> Optional[str]:
        """Downloads a file stored in the Telegram Vault to a local path."""
        target_bot = bot or self._bot_instance
        if not target_bot:
            logger.error("Download failed: No bot instance available.")
            return None

        try:
            file_info = target_bot.get_file(file_id)
            downloaded_bytes = target_bot.download_file(file_info.file_path)
            os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
            with open(destination_path, "wb") as f:
                f.write(downloaded_bytes)
            logger.info(f"Downloaded vault file {file_id} to {destination_path}")
            return destination_path
        except Exception as e:
            logger.error(f"Failed to download vault file {file_id}: {e}")
            return None

    def auto_detect_vault_group(self, chat: Any, bot: Optional[Any] = None) -> bool:
        """
        Auto-detects when the bot is in or added to a group/supergroup
        and configures it as the active vault if none is set.
        """
        if not chat:
            return False
        chat_type = getattr(chat, "type", "")
        if chat_type in ("group", "supergroup"):
            title = getattr(chat, "title", "Telegram Group Vault")
            chat_id = getattr(chat, "id", None)
            if chat_id:
                current = self.get_vault_group_id()
                if not current:
                    self.set_vault_group_id(chat_id, title)
                    if bot:
                        try:
                            bot.send_message(
                                chat_id,
                                f"☁️ *Void Cloud Vault Activated!*\n\n"
                                f"This group `{title}` is now configured as your autonomous persistent "
                                f"cloud memory & media storage vault.\n"
                                f"• Group ID: `{chat_id}`\n"
                                f"All camera snaps, screenshots, and memory backups will route here safely.",
                                parse_mode="Markdown",
                            )
                        except Exception:
                            pass
                    return True
        return False

    def get_vault_telemetry(self) -> Dict[str, Any]:
        """Returns statistics on the cloud vault."""
        group_id = self.get_vault_group_id()
        title = self.get_vault_title()
        recent = self.query_vault(limit=100)
        total_files = len(recent)
        bytes_stored = sum(r.size_bytes for r in recent)
        last_upload_iso = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(recent[0].created_at))
            if recent
            else "Never"
        )
        return {
            "configured": group_id is not None,
            "group_id": group_id,
            "group_title": title,
            "title": title,
            "total_files": total_files,
            "total_files_indexed": total_files,
            "bytes_stored": bytes_stored,
            "last_upload_iso": last_upload_iso,
            "recent_files": [f.to_dict() for f in recent[:5]],
        }


global_cloud_vault = CloudVaultService()
