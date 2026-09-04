"""
security/rate_limiter.py - Token Bucket Rate Limiter and Session Manager.

Guards the mobile device against Denial of Service (DoS) and brute-force
command flooding from unauthorized or compromised remote clients.
"""

import time
import threading
from typing import Dict, Tuple, Optional


class _UserBucket:
    __slots__ = ("tokens", "last_update")

    def __init__(self, capacity: float):
        self.tokens = capacity
        self.last_update = time.time()


class TokenBucketRateLimiter:
    """Thread-safe Token Bucket Rate Limiter for per-user and per-IP throttling."""
    __slots__ = ("_rate", "_capacity", "_buckets", "_lock")

    def __init__(self, rate_per_second: float = 0.5, capacity: int = 5):
        self._rate = rate_per_second
        self._capacity = float(capacity)
        self._buckets: Dict[str, _UserBucket] = {}
        self._lock = threading.Lock()

    def allow_request(self, identifier: str) -> Tuple[bool, float]:
        """
        Determines whether request should be allowed.
        Returns (is_allowed, wait_seconds_needed).
        """
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(identifier)
            if bucket is None:
                bucket = _UserBucket(self._capacity)
                self._buckets[identifier] = bucket

            # Replenish tokens based on elapsed time
            elapsed = now - bucket.last_update
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._rate)
            bucket.last_update = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            else:
                wait_time = (1.0 - bucket.tokens) / self._rate
                return False, round(wait_time, 2)

    def prune_stale(self, max_idle_seconds: float = 3600.0) -> None:
        """Prunes inactive buckets to keep memory footprint strictly flat."""
        now = time.time()
        with self._lock:
            stale_keys = [
                k for k, b in self._buckets.items()
                if (now - b.last_update) > max_idle_seconds
            ]
            for k in stale_keys:
                del self._buckets[k]


class SessionTimeoutManager:
    """Manages active user session timeouts for remote controllers."""
    __slots__ = ("_timeout_seconds", "_sessions", "_lock")

    def __init__(self, timeout_seconds: int = 900):  # 15 minutes default
        self._timeout_seconds = timeout_seconds
        self._sessions: Dict[str, float] = {}
        self._lock = threading.Lock()

    def touch_session(self, user_id: str) -> None:
        """Records active interaction timestamp for user."""
        with self._lock:
            self._sessions[user_id] = time.time()

    def is_session_active(self, user_id: str) -> bool:
        """Checks whether the user's session is still valid."""
        with self._lock:
            last_active = self._sessions.get(user_id)
            if last_active is None:
                return False
            if (time.time() - last_active) > self._timeout_seconds:
                del self._sessions[user_id]
                return False
            return True

    def invalidate_session(self, user_id: str) -> None:
        """Explicitly ends an active user session."""
        with self._lock:
            self._sessions.pop(user_id, None)
