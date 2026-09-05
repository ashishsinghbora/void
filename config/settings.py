"""
config/settings.py - Centralized Configuration & Environment Settings.

Manages application configuration, persistent environment variables (~/.void/config.env),
device RAM limits, admin whitelists, and model inference profiles.
"""

import os
import json
import logging
from typing import Set, Dict, Any, Optional

logger = logging.getLogger("VoidConfig")

CONFIG_ENV_PATH = os.path.expanduser("~/.void/config.env")
CONFIG_DIR = os.path.expanduser("~/.void")


class VoidConfig:
    """Singleton configuration manager with atomic persistence."""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file: str = config_file or CONFIG_ENV_PATH
        self._load_defaults()
        self._load_from_file()
        if not config_file:
            self._load_from_env()

    def _load_defaults(self) -> None:
        self.app_name: str = "Void Edge Agent"
        self.version: str = "2.0.0-pro"
        self.device_name: str = "Void-Edge-Node"
        self.bot_token: str = ""
        self.admin_ids: Set[int] = set()
        self.vault_group_id: Optional[int] = None
        self.vault_title: str = "Void Cloud Vault"
        self.active_model_id: str = "qwen-0.5b"
        self.max_ram_mb: int = 50
        self.whisper_model: str = "tiny"
        self.ocr_engine: str = "local"
        self.rate_limit_free: float = 0.5
        self.rate_limit_pro: float = 5.0
        self.polling_interval: float = 1.0

    def _load_from_file(self) -> None:
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")

                    if k == "TELEGRAM_BOT_TOKEN":
                        self.bot_token = v
                    elif k in ("TELEGRAM_ADMIN_IDS", "ADMIN_IDS"):
                        self.admin_ids = {int(x.strip()) for x in v.split(",") if x.strip().isdigit()}
                    elif k in ("TELEGRAM_VAULT_GROUP_ID", "VAULT_GROUP_ID"):
                        try:
                            self.vault_group_id = int(v)
                        except ValueError:
                            pass
                    elif k == "VOID_ACTIVE_MODEL":
                        self.active_model_id = v
                    elif k == "VOID_MAX_RAM_MB":
                        try:
                            self.max_ram_mb = int(v)
                        except ValueError:
                            pass
        except Exception as e:
            logger.warning(f"Error reading {CONFIG_ENV_PATH}: {e}")

    def _load_from_env(self) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
        if token:
            self.bot_token = token

        admins = os.environ.get("TELEGRAM_ADMIN_IDS") or os.environ.get("ADMIN_IDS")
        if admins:
            self.admin_ids = {int(x.strip()) for x in admins.split(",") if x.strip().isdigit()}

        vault = os.environ.get("TELEGRAM_VAULT_GROUP_ID") or os.environ.get("VAULT_GROUP_ID")
        if vault:
            try:
                self.vault_group_id = int(vault)
            except ValueError:
                pass

        model = os.environ.get("VOID_ACTIVE_MODEL")
        if model:
            self.active_model_id = model

    def save(self) -> bool:
        """Persists key configuration parameters back to config file."""
        try:
            target_dir = os.path.dirname(self.config_file)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            lines = [
                "# Void Autonomous Edge Agent Configuration",
                f'TELEGRAM_BOT_TOKEN="{self.bot_token}"',
                f'TELEGRAM_ADMIN_IDS="{",".join(map(str, sorted(self.admin_ids)))}"',
                f'TELEGRAM_VAULT_GROUP_ID="{self.vault_group_id or ""}"',
                f'VOID_ACTIVE_MODEL="{self.active_model_id}"',
                f'VOID_MAX_RAM_MB="{self.max_ram_mb}"',
            ]
            with open(self.config_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to write config to {self.config_file}: {e}")
            return False

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.admin_ids)

    @property
    def telegram_token(self) -> str:
        return self.bot_token

    def update_credentials(self, token: str, admin_id: int) -> None:
        self.bot_token = token
        self.admin_ids.add(admin_id)
        self.save()

    def set_vault_group(self, group_id: int) -> None:
        self.vault_group_id = group_id
        self.save()


global_config = VoidConfig()
