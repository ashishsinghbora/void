"""
storage/repository.py - Typed Data Access Repositories with Embedded Auto-Pruning.
"""

import time
import json
import hashlib
from typing import List, Dict, Any, Optional

from storage.sqlite_db import SQLiteDatabase, global_db
from storage.log_pruner import SlidingWindowLogPruner
from core.types import NotificationRecord, NotificationCategory


class ConversationRepository:
    """Stores chat dialogues and reasoning traces with automatic sliding-window pruning."""
    __slots__ = ("_db", "_pruner")

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db
        self._pruner = SlidingWindowLogPruner(db)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        reasoning: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> int:
        sql = """
            INSERT INTO conversations (session_id, role, content, reasoning, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        row_id = self._db.execute_update(sql, (session_id, role, content, reasoning, confidence, time.time()))
        # Periodic pruning trigger
        self._pruner.prune_table("conversations", "id", 150)
        return row_id

    def get_recent_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
            SELECT role, content, reasoning, confidence, timestamp
            FROM conversations
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        rows = self._db.execute_query(sql, (session_id, limit))
        return [dict(r) for r in reversed(rows)]


class ExecutionLogRepository:
    """Stores step-by-step tool execution telemetry."""
    __slots__ = ("_db", "_pruner")

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db
        self._pruner = SlidingWindowLogPruner(db)

    def log_step(
        self,
        session_id: str,
        step: int,
        tool_name: str,
        tool_input: Any,
        observation: Optional[str],
        status: str,
        duration_ms: float,
    ) -> int:
        sql = """
            INSERT INTO execution_logs (session_id, step, tool_name, tool_input, observation, status, duration_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        input_str = json.dumps(tool_input) if isinstance(tool_input, (dict, list)) else str(tool_input)
        row_id = self._db.execute_update(
            sql,
            (session_id, step, tool_name, input_str, str(observation or ""), status, duration_ms, time.time()),
        )
        self._pruner.prune_table("execution_logs", "id", 500)
        return row_id

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, session_id, step, tool_name, tool_input, observation, status, duration_ms, timestamp
            FROM execution_logs
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        rows = self._db.execute_query(sql, (limit,))
        return [dict(r) for r in rows]


class ClipboardRepository:
    """Deduplicated clipboard history storage."""
    __slots__ = ("_db", "_pruner")

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db
        self._pruner = SlidingWindowLogPruner(db)

    def record_clipboard(self, content: str) -> bool:
        if not content or not content.strip():
            return False
        clean = content.strip()
        chash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        sql = """
            INSERT OR REPLACE INTO clipboard_history (content_hash, content, timestamp)
            VALUES (?, ?, ?);
        """
        res = self._db.execute_update(sql, (chash, clean, time.time()))
        self._pruner.prune_table("clipboard_history", "id", 50)
        return res > 0

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, content, timestamp
            FROM clipboard_history
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        rows = self._db.execute_query(sql, (limit,))
        return [dict(r) for r in rows]


class TelemetryRepository:
    """Device resource consumption and health telemetry history."""
    __slots__ = ("_db", "_pruner")

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db
        self._pruner = SlidingWindowLogPruner(db)

    def record(self, ram_rss_mb: float, cpu_percent: float, battery_percent: Optional[int], wifi_ssid: Optional[str]) -> int:
        sql = """
            INSERT INTO telemetry_history (ram_rss_mb, cpu_percent, battery_percent, wifi_ssid, timestamp)
            VALUES (?, ?, ?, ?, ?);
        """
        res = self._db.execute_update(sql, (ram_rss_mb, cpu_percent, battery_percent, wifi_ssid, time.time()))
        self._pruner.prune_table("telemetry_history", "id", 300)
        return res

    def get_latest(self) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT ram_rss_mb, cpu_percent, battery_percent, wifi_ssid, timestamp
            FROM telemetry_history
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        rows = self._db.execute_query(sql)
        return dict(rows[0]) if rows else None


class NotificationRepository:
    """Stores and indexes incoming push notifications."""
    __slots__ = ("_db", "_pruner")

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db
        self._pruner = SlidingWindowLogPruner(db)

    def upsert(self, notif: NotificationRecord) -> int:
        sql = """
            INSERT OR REPLACE INTO notifications (id, package_name, title, content, category, is_otp, otp_code, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        res = self._db.execute_update(
            sql,
            (
                notif.id,
                notif.package_name,
                notif.title,
                notif.content,
                notif.category.value,
                1 if notif.is_otp else 0,
                notif.otp_code,
                notif.timestamp,
            ),
        )
        self._pruner.prune_table("notifications", "id", 200)
        return res

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, package_name, title, content, category, is_otp, otp_code, timestamp
            FROM notifications
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        rows = self._db.execute_query(sql, (limit,))
        return [dict(r) for r in rows]
