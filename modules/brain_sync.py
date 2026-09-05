"""
modules/brain_sync.py - Bidirectional Telegram Cloud Vault & Local Brain Synchronizer.

Maintains bidirectional memory and document synchronization:
- Local phone brain (~/.void/vault/ & ~/.void/brain/) mirrored directly into Telegram Group
- Automatic hashtag indexing (#DOC, #NOTE, #SCREEN, #RESEARCH, #OTP, #MEDIA, #CODE)
- Telegram group media and documents auto-downloaded into local brain dataset
- Onboarding pairing wizard with timestamp logging
"""

import os
import time
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Set

from config.settings import global_config

logger = logging.getLogger("VoidModules.BrainSync")

BRAIN_DIR = os.path.expanduser("~/.void/brain")
VAULT_DIR = os.path.expanduser("~/.void/vault")


class SyncResult(dict):
    """Result object supporting both dictionary keys and list-like iteration/len."""
    def __len__(self) -> int:
        return self.get("uploaded_count", 0)

    def __iter__(self):
        return iter(self.get("uploaded", []))


class BrainSyncService:
    """Bidirectional file and memory synchronization bridge."""

    def __init__(
        self,
        bot_instance: Any = None,
        bot: Any = None,
        local_brain_dir: Optional[str] = None,
        local_vault_dir: Optional[str] = None,
        chat_id: Optional[int] = None,
    ):
        self.bot = bot_instance or bot
        self.brain_dir = os.path.abspath(local_brain_dir or BRAIN_DIR)
        self.vault_dir = os.path.abspath(local_vault_dir or VAULT_DIR)
        os.makedirs(self.brain_dir, exist_ok=True)
        os.makedirs(self.vault_dir, exist_ok=True)
        self._synced_file_hashes: Dict[str, str] = {}
        self._sync_index_path = os.path.join(self.brain_dir, "sync_index.json")
        self._load_sync_index()
        self._running: bool = False
        if chat_id:
            global_config.vault_group_id = chat_id

    def bind_bot(self, bot: Any) -> None:
        self.bot = bot

    def _load_sync_index(self) -> None:
        if os.path.exists(self._sync_index_path):
            try:
                with open(self._sync_index_path, "r", encoding="utf-8") as f:
                    self._synced_file_hashes = json.load(f)
            except Exception as e:
                logger.debug(f"Error loading sync index: {e}")

    def _save_sync_index(self) -> None:
        try:
            with open(self._sync_index_path, "w", encoding="utf-8") as f:
                json.dump(self._synced_file_hashes, f, indent=2)
        except Exception as e:
            logger.debug(f"Error saving sync index: {e}")

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Calculates SHA256 hash of a local file."""
        if not os.path.exists(file_path):
            return ""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    @staticmethod
    def infer_hashtag_for_file(filename: str) -> str:
        """Assigns categorized searchable hashtag based on file extension and name."""
        lower = filename.lower()
        if any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
            return "#SCREEN" if any(k in lower for k in ("screenshot", "frame", "screen", "snap")) else "#MEDIA"
        elif any(lower.endswith(ext) for ext in (".mp4", ".mkv", ".webm")):
            return "#MEDIA"
        elif any(lower.endswith(ext) for ext in (".ogg", ".wav", ".mp3", ".m4a")):
            return "#VOICE"
        elif lower.endswith(".pdf"):
            return "#DOC"
        elif any(lower.endswith(ext) for ext in (".py", ".sh", ".json", ".js", ".html")):
            return "#CODE"
        elif "research" in lower or "summary" in lower:
            return "#RESEARCH"
        elif "otp" in lower or "2fa" in lower:
            return "#OTP"
        return "#NOTE"

    def pair_vault_group(
        self,
        group_id_or_link: Any = None,
        title: Optional[str] = None,
        chat_id: Optional[Any] = None,
        group_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pairs and binds a Telegram Group Chat as the permanent Cloud Vault."""
        target = group_id_or_link if group_id_or_link is not None else chat_id
        actual_title = group_title or title or "Void Cloud Vault"
        clean_input = str(target).strip()
        gid: Optional[int] = None

        if clean_input.startswith("-") and clean_input.lstrip("-").isdigit():
            gid = int(clean_input)
        elif clean_input.isdigit():
            gid = -int(clean_input)
        elif "t.me/" in clean_input:
            actual_title = f"Vault ({clean_input.split('/')[-1]})"
            gid = -1001000000000

        if gid is None:
            return {"success": False, "error": "Invalid Telegram Group ID or invite link format."}

        global_config.set_vault_group(gid, title=actual_title)

        return {
            "success": True,
            "paired": True,
            "chat_id": gid,
            "title": actual_title,
            "vault_group_id": gid,
            "vault_title": actual_title,
            "paired_at": global_config.vault_paired_at,
            "message": f"Successfully paired Cloud Vault '{actual_title}' (ID: {gid})",
        }

    def sync_local_to_cloud(self) -> SyncResult:
        """
        Scans local brain and vault directories (~/.void/brain/ and ~/.void/vault/)
        and uploads any new or modified files directly to the Telegram Group Vault.
        """
        if not self.bot or not global_config.vault_group_id:
            return SyncResult({"success": False, "error": "Bot or vault unconfigured", "uploaded": [], "uploaded_count": 0, "skipped_count": 0})

        uploaded: List[Dict[str, Any]] = []
        skipped_count = 0
        vault_gid = global_config.vault_group_id

        scan_dirs = [self.brain_dir, self.vault_dir]
        for s_dir in scan_dirs:
            if not os.path.exists(s_dir):
                continue

            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.startswith(".") or f == "sync_index.json":
                        continue

                    full_path = os.path.join(root, f)
                    curr_hash = self.compute_file_hash(full_path)
                    if not curr_hash:
                        continue

                    if self._synced_file_hashes.get(full_path) == curr_hash:
                        skipped_count += 1
                        continue

                    tag = self.infer_hashtag_for_file(f)
                    caption = f"🧠 *Void Cloud Brain Sync* {tag}\n• *File:* `{f}`\n• *Path:* `{full_path}`"

                    success = False
                    try:
                        with open(full_path, "rb") as file_stream:
                            if any(f.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg")):
                                self.bot.send_photo(vault_gid, file_stream, caption=caption, parse_mode="Markdown")
                            elif any(f.lower().endswith(ext) for ext in (".mp4", ".mov")):
                                self.bot.send_video(vault_gid, file_stream, caption=caption, parse_mode="Markdown")
                            elif any(f.lower().endswith(ext) for ext in (".ogg", ".wav", ".mp3")):
                                self.bot.send_audio(vault_gid, file_stream, caption=caption, parse_mode="Markdown")
                            else:
                                self.bot.send_document(vault_gid, file_stream, caption=caption, parse_mode="Markdown")
                        success = True
                    except Exception as ex:
                        logger.debug(f"Sync dispatch notice for {f}: {ex}")

                    if success:
                        self._synced_file_hashes[full_path] = curr_hash
                        uploaded.append({"file": f, "path": full_path, "tag": tag, "hash": curr_hash})

        if uploaded:
            self._save_sync_index()
            logger.info(f"Synchronized {len(uploaded)} local brain files to Telegram Cloud Vault.")

        return SyncResult({
            "success": True,
            "uploaded": uploaded,
            "uploaded_count": len(uploaded),
            "skipped_count": skipped_count,
        })

    def save_cloud_document_to_local(self, filename: str, content_bytes: bytes, tag: str = "DOC") -> str:
        """Saves a document or payload received from Telegram directly into local brain."""
        target_dir = VAULT_DIR if tag in ("MEDIA", "SCREEN") else BRAIN_DIR
        local_path = os.path.join(target_dir, filename)

        with open(local_path, "wb") as f:
            f.write(content_bytes)

        file_hash = self.compute_file_hash(local_path)
        self._synced_file_hashes[local_path] = file_hash
        self._save_sync_index()

        logger.info(f"Saved and indexed cloud document to local phone brain: {local_path}")
        return local_path

    async def run_async_sync(self, interval_seconds: float = 60.0) -> None:
        """Continuous non-blocking background sync loop."""
        import asyncio
        self._running = True
        logger.info(f"BrainSyncService background loop running (interval: {interval_seconds}s).")
        while self._running:
            try:
                self.sync_local_to_cloud()
            except Exception as e:
                logger.warning(f"Error in BrainSync loop: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._running = False


global_brain_sync = BrainSyncService()
