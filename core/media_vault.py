"""
core/media_vault.py - Unified Media Accessibility & Storage Directory Manager.

Resolves accessible Android/Termux media directories, eliminating permission traps
and ensuring captured photos, recordings, and screenshots are reliably accessible
to both the user and the Telegram Cloud Vault.
"""

import os
import time
import shutil
import logging
from typing import Optional, List, Tuple

from core.command_executor import IS_TERMUX

logger = logging.getLogger("VoidAdvancedCore.MediaVault")


class MediaVaultManager:
    """Manages accessible media storage directories across Android Termux & desktop environments."""

    PRIMARY_CANDIDATES = [
        os.path.expanduser("~/storage/shared/Pictures/Void"),
        os.path.expanduser("~/storage/downloads/Void"),
        os.path.expanduser("~/storage/dcim/Void"),
        os.path.expanduser("~/.void/media"),
    ]

    def __init__(self):
        self._active_media_dir = self._resolve_accessible_directory()

    @property
    def media_dir(self) -> str:
        """Returns the verified accessible media directory."""
        if not os.path.exists(self._active_media_dir):
            self._active_media_dir = self._resolve_accessible_directory()
        return self._active_media_dir

    def _resolve_accessible_directory(self) -> str:
        """Probes storage locations to pick the most accessible path that is readable/writable."""
        for candidate in self.PRIMARY_CANDIDATES:
            try:
                os.makedirs(candidate, exist_ok=True)
                test_file = os.path.join(candidate, ".write_test")
                with open(test_file, "w") as f:
                    f.write("void_test")
                os.remove(test_file)
                logger.debug(f"Resolved active media vault directory: {candidate}")
                return candidate
            except Exception as e:
                logger.debug(f"Media candidate '{candidate}' not writable: {e}")

        # Safe fallback inside ~/.void
        fallback = os.path.expanduser("~/.void/media")
        os.makedirs(fallback, exist_ok=True)
        return fallback

    def generate_media_path(self, prefix: str = "void_media", extension: str = "jpg") -> str:
        """
        Generates a collision-resistant timestamped file path in the media vault.
        Example: /path/to/void/void_photo_20260905_034800_123.jpg
        """
        clean_ext = extension.lstrip(".")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        millis = int((time.time() % 1) * 1000)
        filename = f"{prefix}_{timestamp}_{millis:03d}.{clean_ext}"
        return os.path.join(self.media_dir, filename)

    def list_recent_media(self, limit: int = 10) -> List[Dict_Media]:
        """Lists recently captured photos, videos, and recordings from the vault."""
        if not os.path.exists(self.media_dir):
            return []

        entries = []
        try:
            for entry in os.scandir(self.media_dir):
                if entry.is_file() and not entry.name.startswith("."):
                    stat = entry.stat()
                    entries.append({
                        "filename": entry.name,
                        "path": entry.path,
                        "size_bytes": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": os.path.splitext(entry.name)[1].lower(),
                    })
        except Exception as e:
            logger.warning(f"Error reading media vault: {e}")

        entries.sort(key=lambda x: x["modified"], reverse=True)
        return entries[:limit]


Dict_Media = dict

global_media_vault = MediaVaultManager()
