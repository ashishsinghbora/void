"""
telegram/database/db_manager.py - Enterprise SQLite WAL Data Access Layer.

Handles connection pooling, atomic schema migrations, and concurrency hardening
for user profiles, subscriptions, connected edge devices, and payment receipts.
"""

import os
import time
import sqlite3
import threading
import logging
from typing import Optional, List, Dict, Any

from telegram.database.models import (
    User,
    UserTier,
    UserRole,
    Device,
    UserSession,
    Subscription,
    PaymentTransaction,
    UserSettings,
    VaultFile,
)

logger = logging.getLogger("VoidTelegram.Database")

DEFAULT_BOT_DB_PATH = os.path.expanduser("~/.void/telegram_ecosystem.db")


class BotDatabaseManager:
    """Thread-safe SQLite Database Manager with WAL concurrency and auto-migration."""

    def __init__(self, db_path: str = DEFAULT_BOT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Retrieves or creates thread-local SQLite connection with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_path,
                timeout=15.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                conn.execute("PRAGMA busy_timeout = 10000;")
                conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        """Atomically initializes all tables and indices if not present."""
        conn = self._get_connection()
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    tier TEXT NOT NULL DEFAULT 'FREE',
                    role TEXT NOT NULL DEFAULT 'USER',
                    created_at REAL NOT NULL,
                    last_active_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    notifications_enabled INTEGER NOT NULL DEFAULT 1,
                    otp_interception_enabled INTEGER NOT NULL DEFAULT 1,
                    quiet_hours_enabled INTEGER NOT NULL DEFAULT 0,
                    theme TEXT NOT NULL DEFAULT 'cyber_dark',
                    security_level TEXT NOT NULL DEFAULT 'HIGH',
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL DEFAULT 'Android',
                    model TEXT NOT NULL DEFAULT 'Termux Node',
                    battery_level INTEGER NOT NULL DEFAULT 100,
                    is_online INTEGER NOT NULL DEFAULT 1,
                    last_seen_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    last_activity REAL NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    tier TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    started_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    auto_renew INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS payment_transactions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    telegram_payment_charge_id TEXT NOT NULL,
                    provider_payment_charge_id TEXT,
                    invoice_payload TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    tier_purchased TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SUCCESS',
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS vault_files (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    local_path TEXT,
                    size_bytes INTEGER DEFAULT 0,
                    caption TEXT,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vault_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_devices_user ON devices(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_user ON payment_transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_vault_tag ON vault_files(tag);
                CREATE INDEX IF NOT EXISTS idx_vault_type ON vault_files(file_type);
            """)

    # -------------------------------------------------------------------------
    # User Profile Operations
    # -------------------------------------------------------------------------
    def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        default_role: UserRole = UserRole.USER,
        tier: Optional[UserTier] = None,
        default_tier: UserTier = UserTier.FREE,
    ) -> User:
        """Fetches existing user or creates a new one along with default settings."""
        conn = self._get_connection()
        initial_tier = tier or default_tier
        with self._lock:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cur.fetchone()
            if row:
                user = User(
                    telegram_id=row["telegram_id"],
                    username=row["username"],
                    first_name=row["first_name"],
                    tier=UserTier(row["tier"]),
                    role=UserRole(row["role"]),
                    created_at=row["created_at"],
                    last_active_at=row["last_active_at"],
                )
                # Update last active
                cur.execute("UPDATE users SET last_active_at = ? WHERE telegram_id = ?", (time.time(), telegram_id))
                conn.commit()
                return user

            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                tier=initial_tier,
                role=default_role,
            )
            cur.execute(
                """
                INSERT INTO users (telegram_id, username, first_name, tier, role, created_at, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user.telegram_id, user.username, user.first_name, user.tier.value, user.role.value, user.created_at, user.last_active_at),
            )
            # Create default settings
            cur.execute(
                """
                INSERT OR IGNORE INTO user_settings (user_id, notifications_enabled, otp_interception_enabled, quiet_hours_enabled, theme, security_level, updated_at)
                VALUES (?, 1, 1, 0, 'cyber_dark', 'HIGH', ?)
                """,
                (telegram_id, time.time()),
            )
            conn.commit()
            return user

    def get_user(self, telegram_id: int) -> Optional[User]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        if not row:
            return None
        return User(
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            tier=UserTier(row["tier"]),
            role=UserRole(row["role"]),
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
        )

    def update_user_tier(self, telegram_id: int, tier: UserTier) -> bool:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute("UPDATE users SET tier = ? WHERE telegram_id = ?", (tier.value, telegram_id))
            conn.commit()
            return cur.rowcount > 0

    # -------------------------------------------------------------------------
    # Settings Operations
    # -------------------------------------------------------------------------
    def get_user_settings(self, user_id: int) -> UserSettings:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            # Ensure foreign key exists in users table
            self.get_or_create_user(user_id)
            settings = UserSettings(user_id=user_id)
            with self._lock:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO user_settings (user_id, notifications_enabled, otp_interception_enabled, quiet_hours_enabled, theme, security_level, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, int(settings.notifications_enabled), int(settings.otp_interception_enabled), int(settings.quiet_hours_enabled), settings.theme, settings.security_level, settings.updated_at),
                )
                conn.commit()
            return settings

        return UserSettings(
            user_id=row["user_id"],
            notifications_enabled=bool(row["notifications_enabled"]),
            otp_interception_enabled=bool(row["otp_interception_enabled"]),
            quiet_hours_enabled=bool(row["quiet_hours_enabled"]),
            theme=row["theme"],
            security_level=row["security_level"],
            updated_at=row["updated_at"],
        )

    def update_user_settings(self, settings: UserSettings) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_settings
                SET notifications_enabled = ?, otp_interception_enabled = ?, quiet_hours_enabled = ?, theme = ?, security_level = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (int(settings.notifications_enabled), int(settings.otp_interception_enabled), int(settings.quiet_hours_enabled), settings.theme, settings.security_level, time.time(), settings.user_id),
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Device Management Operations
    # -------------------------------------------------------------------------
    def register_device(self, device: Device) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO devices (device_id, user_id, name, platform, model, battery_level, is_online, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (device.device_id, device.user_id, device.name, device.platform, device.model, device.battery_level, int(device.is_online), device.last_seen_at),
            )
            conn.commit()

    def get_user_devices(self, user_id: int) -> List[Device]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM devices WHERE user_id = ? ORDER BY last_seen_at DESC", (user_id,))
        devices = []
        for r in cur.fetchall():
            devices.append(
                Device(
                    device_id=r["device_id"],
                    user_id=r["user_id"],
                    name=r["name"],
                    platform=r["platform"],
                    model=r["model"],
                    battery_level=r["battery_level"],
                    is_online=bool(r["is_online"]),
                    last_seen_at=r["last_seen_at"],
                )
            )
        return devices

    def update_device_heartbeat(self, device_id: str, battery_level: int = 100, is_online: bool = True) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                "UPDATE devices SET battery_level = ?, is_online = ?, last_seen_at = ? WHERE device_id = ?",
                (battery_level, int(is_online), time.time(), device_id),
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # Session Operations
    # -------------------------------------------------------------------------
    def create_session(self, session: UserSession) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO user_sessions (session_id, user_id, created_at, expires_at, last_activity, state_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session.session_id, session.user_id, session.created_at, session.expires_at, session.last_activity, session.state_json),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Optional[UserSession]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        return UserSession(
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_activity=row["last_activity"],
            state_json=row["state_json"],
        )

    def touch_session(self, session_id: str) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute("UPDATE user_sessions SET last_activity = ? WHERE session_id = ?", (time.time(), session_id))
            conn.commit()

    # -------------------------------------------------------------------------
    # Monetization & Payment Operations
    # -------------------------------------------------------------------------
    def record_transaction(self, tx: PaymentTransaction) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO payment_transactions (id, user_id, telegram_payment_charge_id, provider_payment_charge_id, invoice_payload, currency, total_amount, tier_purchased, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tx.id, tx.user_id, tx.telegram_payment_charge_id, tx.provider_payment_charge_id, tx.invoice_payload, tx.currency, tx.total_amount, tx.tier_purchased, tx.created_at, tx.status),
            )
            conn.commit()

    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[PaymentTransaction]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM payment_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        txs = []
        for r in cur.fetchall():
            txs.append(
                PaymentTransaction(
                    id=r["id"],
                    user_id=r["user_id"],
                    telegram_payment_charge_id=r["telegram_payment_charge_id"],
                    provider_payment_charge_id=r["provider_payment_charge_id"],
                    invoice_payload=r["invoice_payload"],
                    currency=r["currency"],
                    total_amount=r["total_amount"],
                    tier_purchased=r["tier_purchased"],
                    created_at=r["created_at"],
                    status=r["status"],
                )
            )
        return txs

    def create_or_update_subscription(self, sub: Subscription) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO subscriptions (id, user_id, tier, status, started_at, expires_at, auto_renew)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sub.id, sub.user_id, sub.tier.value, sub.status, sub.started_at, sub.expires_at, int(sub.auto_renew)),
            )
            # Synchronize users table tier
            cur.execute("UPDATE users SET tier = ? WHERE telegram_id = ?", (sub.tier.value, sub.user_id))
            conn.commit()

    def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM subscriptions WHERE user_id = ? AND status = 'ACTIVE' ORDER BY expires_at DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return Subscription(
            id=row["id"],
            user_id=row["user_id"],
            tier=UserTier(row["tier"]),
            status=row["status"],
            started_at=row["started_at"],
            expires_at=row["expires_at"],
            auto_renew=bool(row["auto_renew"]),
        )

    # -------------------------------------------------------------------------
    # Cloud Storage & Memory Vault Operations
    # -------------------------------------------------------------------------
    def record_vault_file(self, vf: Optional[VaultFile] = None, **kwargs) -> Any:
        """Stores indexed metadata for a file persisted in the Telegram group vault."""
        if vf is None:
            import uuid
            vf_id = kwargs.get("id") or f"vf_{uuid.uuid4().hex[:12]}"
            vf = VaultFile(
                id=vf_id,
                file_id=kwargs.get("telegram_file_id") or kwargs.get("file_id") or "doc_unknown",
                message_id=int(kwargs.get("telegram_message_id") or kwargs.get("message_id") or 0),
                chat_id=int(kwargs.get("group_id") or kwargs.get("chat_id") or 0),
                file_type=kwargs.get("file_type") or kwargs.get("category") or "document",
                tag=kwargs.get("tag") or kwargs.get("category") or "general",
                filename=kwargs.get("file_name") or kwargs.get("filename") or "file.bin",
                local_path=kwargs.get("file_path") or kwargs.get("local_path"),
                size_bytes=int(kwargs.get("file_size") or kwargs.get("size_bytes") or 0),
                caption=kwargs.get("caption"),
                created_at=kwargs.get("created_at") or time.time(),
            )
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO vault_files (id, file_id, message_id, chat_id, file_type, tag, filename, local_path, size_bytes, caption, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (vf.id, vf.file_id, vf.message_id, vf.chat_id, vf.file_type, vf.tag, vf.filename, vf.local_path, vf.size_bytes, vf.caption, vf.created_at),
            )
            conn.commit()
            return cur.lastrowid or 1

    def get_vault_file(self, file_id: str) -> Optional[VaultFile]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM vault_files WHERE file_id = ? OR id = ?", (file_id, file_id))
        r = cur.fetchone()
        if not r:
            return None
        return VaultFile(
            id=r["id"],
            file_id=r["file_id"],
            message_id=r["message_id"],
            chat_id=r["chat_id"],
            file_type=r["file_type"],
            tag=r["tag"],
            filename=r["filename"],
            local_path=r["local_path"],
            size_bytes=r["size_bytes"],
            caption=r["caption"],
            created_at=r["created_at"],
        )

    def query_vault_files(
        self,
        tag: Optional[str] = None,
        file_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[VaultFile]:
        conn = self._get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM vault_files WHERE 1=1"
        params = []
        if category:
            query += " AND (tag = ? OR file_type = ?)"
            params.extend([category, category])
        if tag:
            query += " AND tag = ?"
            params.append(tag)
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, tuple(params))
        results = []
        for r in cur.fetchall():
            results.append(
                VaultFile(
                    id=r["id"],
                    file_id=r["file_id"],
                    message_id=r["message_id"],
                    chat_id=r["chat_id"],
                    file_type=r["file_type"],
                    tag=r["tag"],
                    filename=r["filename"],
                    local_path=r["local_path"],
                    size_bytes=r["size_bytes"],
                    caption=r["caption"],
                    created_at=r["created_at"],
                )
            )
        return results

    def set_vault_config(self, key: str, value: str) -> None:
        conn = self._get_connection()
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO vault_config (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), time.time()),
            )
            conn.commit()

    def get_vault_config(self, key: str) -> Optional[str]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM vault_config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None


global_bot_db = BotDatabaseManager()
