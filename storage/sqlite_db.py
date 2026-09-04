"""
storage/sqlite_db.py - Thread-Safe SQLite Wrapper with Write-Ahead Logging (WAL).

Zero-bloat persistence layer optimized for mobile flash storage.
Enforces WAL journal mode, aggressive busy timeouts, and memory-based temp stores.
"""

import os
import sqlite3
import logging
import threading
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("VoidAdvancedCore.Storage")

DEFAULT_DB_PATH = os.path.expanduser("~/.void_agent.db")


class SQLiteDatabase:
    """Thread-safe SQLite manager with Write-Ahead Logging (WAL) mode."""
    __slots__ = ("_db_path", "_local", "_lock")

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # Ensure parent directory exists
        db_dir = os.path.dirname(os.path.abspath(self._db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Retrieves or establishes a thread-local SQLite connection with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self._db_path,
                timeout=10.0,
                check_same_thread=False,
            )
            # Enable WAL mode for high-concurrency read-write performance
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        """Initializes relational tables and performance indexes."""
        conn = self.get_connection()
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    reasoning TEXT,
                    confidence REAL,
                    timestamp REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_session_ts 
                    ON conversations(session_id, timestamp DESC);

                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_input TEXT NOT NULL,
                    observation TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    timestamp REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                    ON execution_logs(timestamp DESC);

                CREATE TABLE IF NOT EXISTS clipboard_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_clipboard_timestamp 
                    ON clipboard_history(timestamp DESC);

                CREATE TABLE IF NOT EXISTS telemetry_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ram_rss_mb REAL NOT NULL,
                    cpu_percent REAL NOT NULL,
                    battery_percent INTEGER,
                    wifi_ssid TEXT,
                    timestamp REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp 
                    ON telemetry_history(timestamp DESC);

                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    package_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_otp INTEGER NOT NULL,
                    otp_code TEXT,
                    timestamp REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_notifications_timestamp 
                    ON notifications(timestamp DESC);
            """)
        logger.info(f"SQLite database initialized in WAL mode at {self._db_path}")

    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Executes a SELECT query and returns rows."""
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()

    def execute_update(self, sql: str, params: Tuple = ()) -> int:
        """Executes INSERT/UPDATE/DELETE statement within transaction."""
        conn = self.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.rowcount

    def close(self) -> None:
        """Closes thread connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None


# Global database instance
global_db = SQLiteDatabase()
