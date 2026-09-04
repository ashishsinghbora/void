"""
telegram/middleware/auth.py - Enterprise Role-Based Access Control & Feature Gating.
"""

import os
import logging
from typing import Optional, Set
from telegram.database.models import User, UserTier, UserRole
from telegram.database.db_manager import BotDatabaseManager, global_bot_db

logger = logging.getLogger("VoidTelegram.Auth")


class AuthenticationMiddleware:
    """Authenticates users, manages whitelisted admins, and gates tier features."""

    def __init__(self, db: BotDatabaseManager = global_bot_db, admin_ids: Optional[Set[int]] = None):
        self.db = db
        self._admin_ids = admin_ids if admin_ids is not None else self._load_admin_ids()

    def _load_admin_ids(self) -> Set[int]:
        raw = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()
        ids = set()
        if raw:
            for part in raw.split(","):
                clean = part.strip()
                if clean.isdigit():
                    ids.add(int(clean))
        return ids

    def authenticate_user(self, telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> User:
        """Authenticates or creates user and assigns ADMIN role if whitelisted."""
        is_whitelisted = telegram_id in self._admin_ids
        role = UserRole.ADMIN if is_whitelisted else UserRole.USER
        user = self.db.get_or_create_user(telegram_id, username, first_name, default_role=role)
        if is_whitelisted and user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN
            user.tier = UserTier.ENTERPRISE
            self.db.update_user_tier(telegram_id, UserTier.ENTERPRISE)
        return user

    def is_admin(self, telegram_id: int) -> bool:
        if telegram_id in self._admin_ids:
            return True
        user = self.db.get_user(telegram_id)
        return user is not None and user.role == UserRole.ADMIN

    def is_feature_permitted(self, telegram_id: int, feature: str) -> bool:
        """
        Feature gating matrix:
        - "basic": FREE, PRO, ENTERPRISE, ADMIN
        - "multi_device": PRO, ENTERPRISE, ADMIN
        - "local_models": PRO, ENTERPRISE, ADMIN
        - "cloud_bridge": PRO, ENTERPRISE, ADMIN
        - "enterprise_cluster": ENTERPRISE, ADMIN
        """
        if self.is_admin(telegram_id):
            return True

        user = self.db.get_user(telegram_id)
        if not user:
            return feature == "basic"

        tier = user.tier
        if feature == "basic":
            return True
        elif feature in ("multi_device", "local_models", "cloud_bridge"):
            return tier in (UserTier.PRO, UserTier.ENTERPRISE)
        elif feature == "enterprise_cluster":
            return tier == UserTier.ENTERPRISE
        return False

    has_feature_access = is_feature_permitted

