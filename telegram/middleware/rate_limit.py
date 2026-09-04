"""
telegram/middleware/rate_limit.py - Tiered Token-Bucket Rate Limiter.
"""

import time
import threading
from typing import Dict, Tuple
from telegram.database.models import UserTier
from telegram.database.db_manager import BotDatabaseManager, global_bot_db


class TieredTokenBucketRateLimiter:
    """Dynamic rate limiter enforcing tier-based capacity and refill rates."""

    TIER_CONFIG = {
        UserTier.FREE: {"capacity": 5.0, "refill_per_sec": 0.2},         # ~12 requests / min
        UserTier.PRO: {"capacity": 20.0, "refill_per_sec": 1.0},        # ~60 requests / min
        UserTier.ENTERPRISE: {"capacity": 50.0, "refill_per_sec": 5.0}, # ~300 requests / min
    }

    def __init__(self, db: BotDatabaseManager = global_bot_db):
        self.db = db
        self._buckets: Dict[int, Dict[str, float]] = {}
        self._lock = threading.Lock()

    def check_rate_limit(self, telegram_id: int) -> Tuple[bool, float]:
        """
        Returns (allowed, wait_seconds).
        If allowed is True, tokens were consumed.
        If False, wait_seconds indicates time until next token.
        """
        now = time.monotonic()
        user = self.db.get_user(telegram_id)
        tier = user.tier if user else UserTier.FREE

        cfg = self.TIER_CONFIG.get(tier, self.TIER_CONFIG[UserTier.FREE])
        capacity = cfg["capacity"]
        refill_rate = cfg["refill_per_sec"]

        with self._lock:
            if telegram_id not in self._buckets:
                self._buckets[telegram_id] = {
                    "tokens": capacity - 1.0,
                    "last_refill": now,
                }
                return True, 0.0

            bucket = self._buckets[telegram_id]
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(capacity, bucket["tokens"] + (elapsed * refill_rate))
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True, 0.0

            deficit = 1.0 - bucket["tokens"]
            wait_sec = round(deficit / refill_rate, 1) if refill_rate > 0 else 1.0
            return False, max(0.1, wait_sec)

    def allow_request(self, user_id_str: str, tier: UserTier = None) -> Tuple[bool, float]:
        """Convenience wrapper for rate limiting by string user_id."""
        try:
            uid = int(user_id_str)
        except Exception:
            uid = 0
        return self.check_rate_limit(uid)


global_rate_limiter = TieredTokenBucketRateLimiter()
