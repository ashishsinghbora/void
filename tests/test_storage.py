"""
tests/test_storage.py - SQLite WAL Persistence & Sliding-Window Pruning Tests.
"""

from storage.sqlite_db import SQLiteDatabase
from storage.log_pruner import SlidingWindowLogPruner
from storage.repository import (
    ConversationRepository,
    ExecutionLogRepository,
    ClipboardRepository,
)


def test_sqlite_wal_mode(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = SQLiteDatabase(db_path=db_file)

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


def test_sliding_window_log_pruning(tmp_path):
    db_file = str(tmp_path / "test_prune.db")
    db = SQLiteDatabase(db_path=db_file)
    pruner = SlidingWindowLogPruner(db=db)

    # Insert 50 execution logs
    for i in range(50):
        db.execute_update(
            """INSERT INTO execution_logs 
               (session_id, step, tool_name, tool_input, observation, status, duration_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
            ("s1", i, "test_tool", "{}", "obs", "COMPLETED", 10.0, 1000.0 + i),
        )

    rows_before = db.execute_query("SELECT COUNT(*) as count FROM execution_logs;")[0]["count"]
    assert rows_before == 50

    # Prune keeping only last 15
    pruner.prune_table("execution_logs", "id", max_records=15)

    rows_after = db.execute_query("SELECT COUNT(*) as count FROM execution_logs;")[0]["count"]
    assert rows_after == 15


def test_clipboard_repository_deduplication(tmp_path):
    db_file = str(tmp_path / "test_clip.db")
    db = SQLiteDatabase(db_path=db_file)
    repo = ClipboardRepository(db=db)

    # Adding same text twice should replace/deduplicate
    repo.record_clipboard("Hello Void")
    repo.record_clipboard("Hello Void")

    items = repo.get_recent(limit=10)
    assert len(items) == 1
    assert items[0]["content"] == "Hello Void"
