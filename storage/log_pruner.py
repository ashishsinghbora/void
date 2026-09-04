"""
storage/log_pruner.py - Sliding-Window Index Log Pruner.

Ensures zero disk and memory bloat on mobile flash storage by pruning
stale execution logs, conversations, and telemetry using sliding-window indexes.
"""

import logging
from typing import Dict, Any

from storage.sqlite_db import SQLiteDatabase, global_db

logger = logging.getLogger("VoidAdvancedCore.Pruner")


class SlidingWindowLogPruner:
    """Automates bounded retention across all operational tables."""
    __slots__ = ("_db",)

    def __init__(self, db: SQLiteDatabase = global_db):
        self._db = db

    def prune_table(self, table_name: str, id_column: str = "id", max_records: int = 500) -> int:
        """
        Deletes records outside the top-N sliding window using index-assisted subqueries.
        Guarantees that database table size never grows beyond max_records.
        """
        sql = f"""
            DELETE FROM {table_name}
            WHERE {id_column} NOT IN (
                SELECT {id_column} FROM {table_name}
                ORDER BY {id_column} DESC
                LIMIT ?
            );
        """
        deleted = self._db.execute_update(sql, (max_records,))
        if deleted > 0:
            logger.debug(f"Pruned {deleted} stale records from {table_name} (cap: {max_records}).")
        return deleted

    def prune_all(
        self,
        max_logs: int = 500,
        max_convos: int = 150,
        max_clipboard: int = 50,
        max_telemetry: int = 300,
        max_notifications: int = 200,
    ) -> Dict[str, int]:
        """Executes full sliding-window pruning across all persistent stores."""
        results = {
            "execution_logs": self.prune_table("execution_logs", "id", max_logs),
            "conversations": self.prune_table("conversations", "id", max_convos),
            "clipboard_history": self.prune_table("clipboard_history", "id", max_clipboard),
            "telemetry_history": self.prune_table("telemetry_history", "id", max_telemetry),
            "notifications": self.prune_table("notifications", "id", max_notifications),
        }
        return results

    def vacuum_db(self) -> None:
        """Reclaims unindexed fragmented disk pages."""
        try:
            conn = self._db.get_connection()
            conn.execute("PRAGMA incremental_vacuum;")
        except Exception as e:
            logger.warning(f"Vacuum error: {e}")
