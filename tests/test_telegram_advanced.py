"""
tests/test_telegram_advanced.py - Enterprise Test Suite for Telegram Ecosystem.

Tests HMAC-SHA256 TMA auth, SQLite WAL operations, tiered rate limiting,
payments & subscriptions, device management, and Mini App micro server routes.
"""

import os
import time
import json
import hmac
import hashlib
import urllib.parse
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from telegram.database.models import (
    User,
    UserTier,
    UserRole,
    Device,
    UserSession,
    Subscription,
    PaymentTransaction,
    UserSettings,
)
from telegram.database.db_manager import BotDatabaseManager
from telegram.middleware.auth import AuthenticationMiddleware
from telegram.middleware.rate_limit import TieredTokenBucketRateLimiter
from telegram.services.tma_auth_service import TelegramMiniAppAuthService
from telegram.services.payment_service import PaymentService, PLAN_CATALOG
from telegram.services.device_service import DeviceService
from telegram.webapp.server import MiniAppServer, MiniAppRequestHandler

TEST_BOT_TOKEN = "123456789:AAG_unit_test_token_secret"


@pytest.fixture
def temp_db():
    """Provides an isolated temporary SQLite database for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = BotDatabaseManager(db_path=db_path)
    yield db
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 1. TMA HMAC-SHA256 Cryptographic Authentication Tests
# ---------------------------------------------------------------------------
def test_tma_auth_valid_signature():
    auth_service = TelegramMiniAppAuthService()
    now = int(time.time())

    # Build valid Telegram initData query string
    params = {
        "auth_date": str(now),
        "query_id": "AAHdF6IQAAAAAN0XohDhrP_V",
        "user": json.dumps({"id": 987654321, "first_name": "Alice", "username": "alice_edge"}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", TEST_BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    correct_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    raw_init_data = f"auth_date={params['auth_date']}&query_id={params['query_id']}&user={urllib.parse.quote(params['user'])}&hash={correct_hash}"

    is_valid, user_data, err = auth_service.validate_init_data(raw_init_data, TEST_BOT_TOKEN)
    assert is_valid is True
    assert err is None
    assert user_data is not None
    assert user_data["id"] == 987654321
    assert user_data["username"] == "alice_edge"


def test_tma_auth_tampered_signature():
    auth_service = TelegramMiniAppAuthService()
    now = int(time.time())

    raw_init_data = f"auth_date={now}&query_id=fake_query&user=%7B%22id%22%3A123%7D&hash=deadbeef00112233445566778899aabbccddeeff"
    is_valid, user_data, err = auth_service.validate_init_data(raw_init_data, TEST_BOT_TOKEN)
    assert is_valid is False
    assert "mismatch" in err.lower()


def test_tma_auth_expired():
    auth_service = TelegramMiniAppAuthService()
    expired_time = int(time.time()) - 100000  # Older than 86400s

    raw_init_data = f"auth_date={expired_time}&hash=anyhash"
    is_valid, _, err = auth_service.validate_init_data(raw_init_data, TEST_BOT_TOKEN, max_age_seconds=86400)
    assert is_valid is False
    assert "expired" in err.lower()


def test_tma_auth_missing_fields():
    auth_service = TelegramMiniAppAuthService()
    is_valid, _, err = auth_service.validate_init_data("", TEST_BOT_TOKEN)
    assert is_valid is False
    assert "missing" in err.lower()


# ---------------------------------------------------------------------------
# 2. Database Operations Tests
# ---------------------------------------------------------------------------
def test_db_user_lifecycle(temp_db):
    user = temp_db.get_or_create_user(
        telegram_id=112233,
        username="node_admin",
        first_name="Admin",
        default_role=UserRole.ADMIN,
    )
    assert user.telegram_id == 112233
    assert user.tier == UserTier.FREE
    assert user.role == UserRole.ADMIN

    # Fetch again
    fetched = temp_db.get_user(112233)
    assert fetched is not None
    assert fetched.username == "node_admin"

    # Update tier
    updated = temp_db.update_user_tier(112233, UserTier.PRO)
    assert updated is True
    assert temp_db.get_user(112233).tier == UserTier.PRO


def test_db_settings_operations(temp_db):
    settings = temp_db.get_user_settings(55555)
    assert settings.notifications_enabled is True
    assert settings.security_level == "HIGH"

    settings.notifications_enabled = False
    settings.security_level = "STRICT"
    temp_db.update_user_settings(settings)

    reloaded = temp_db.get_user_settings(55555)
    assert reloaded.notifications_enabled is False
    assert reloaded.security_level == "STRICT"


def test_db_device_operations(temp_db):
    temp_db.get_or_create_user(999, "dev_user")
    device = Device(
        device_id="node_termux_01",
        user_id=999,
        name="Galaxy S23 Ultra Node",
        battery_level=85,
    )
    temp_db.register_device(device)

    devices = temp_db.get_user_devices(999)
    assert len(devices) == 1
    assert devices[0].device_id == "node_termux_01"
    assert devices[0].battery_level == 85

    # Update heartbeat
    temp_db.update_device_heartbeat("node_termux_01", battery_level=90)
    updated_dev = temp_db.get_user_devices(999)[0]
    assert updated_dev.battery_level == 90


def test_db_subscriptions_and_transactions(temp_db):
    temp_db.get_or_create_user(777, "subscriber")

    # Record transaction
    tx = PaymentTransaction(
        id="tx_test_101",
        user_id=777,
        telegram_payment_charge_id="tg_charge_xyz",
        provider_payment_charge_id="stars_provider",
        invoice_payload="void_sub:777:PRO:1700000000:ref123",
        currency="XTR",
        total_amount=250,
        tier_purchased="PRO",
    )
    temp_db.record_transaction(tx)

    txs = temp_db.get_user_transactions(777)
    assert len(txs) == 1
    assert txs[0].total_amount == 250
    assert txs[0].currency == "XTR"

    # Create subscription
    sub = Subscription(
        id="sub_test_101",
        user_id=777,
        tier=UserTier.PRO,
        status="ACTIVE",
    )
    temp_db.create_or_update_subscription(sub)

    active_sub = temp_db.get_active_subscription(777)
    assert active_sub is not None
    assert active_sub.tier == UserTier.PRO

    # Check that user table tier synced
    user = temp_db.get_user(777)
    assert user.tier == UserTier.PRO


# ---------------------------------------------------------------------------
# 3. Middleware Tests (Auth & Tiered Token Bucket Rate Limiting)
# ---------------------------------------------------------------------------
def test_auth_middleware(temp_db):
    auth = AuthenticationMiddleware(admin_ids={1001, 1002}, db=temp_db)

    # Initial admin
    assert auth.is_admin(1001) is True
    assert auth.is_admin(9999) is False

    # Feature gating
    temp_db.get_or_create_user(2001, tier=UserTier.FREE)
    temp_db.get_or_create_user(2002, tier=UserTier.PRO)
    temp_db.update_user_tier(2002, UserTier.PRO)

    assert auth.has_feature_access(2001, "basic") is True
    assert auth.has_feature_access(2001, "local_models") is False

    assert auth.has_feature_access(2002, "local_models") is True
    assert auth.has_feature_access(2002, "multi_device") is True


def test_tiered_rate_limiter(temp_db):
    limiter = TieredTokenBucketRateLimiter(db=temp_db)

    # Free tier: capacity 5
    temp_db.get_or_create_user(3001, tier=UserTier.FREE)
    for _ in range(5):
        allowed, _ = limiter.check_rate_limit(3001)
        assert allowed is True

    # 6th immediate request should be throttled
    blocked, wait = limiter.check_rate_limit(3001)
    assert blocked is False
    assert wait > 0


# ---------------------------------------------------------------------------
# 4. Payment & Billing Service Tests
# ---------------------------------------------------------------------------
def test_payment_service_lifecycle(temp_db):
    payment_svc = PaymentService(db_manager=temp_db)

    catalog = payment_svc.get_catalog()
    assert UserTier.PRO in catalog
    assert catalog[UserTier.PRO].stars_price == 250
    assert catalog[UserTier.ENTERPRISE].stars_price == 1000

    # Payload generation and parsing
    payload = payment_svc.create_invoice_payload(user_id=4444, target_tier=UserTier.PRO)
    parsed = payment_svc.parse_invoice_payload(payload)
    assert parsed is not None
    assert parsed["user_id"] == 4444
    assert parsed["tier"] == UserTier.PRO

    # Pre-checkout validation
    ok, reason = payment_svc.validate_pre_checkout("query_123", payload)
    assert ok is True

    # Fulfillment
    temp_db.get_or_create_user(4444)
    sub = payment_svc.fulfill_payment(
        user_id=4444,
        telegram_payment_charge_id="tg_charge_4444",
        provider_payment_charge_id="stars_provider",
        invoice_payload=payload,
        currency="XTR",
        total_amount=250,
    )
    assert sub is not None
    assert sub.tier == UserTier.PRO

    # Status check
    status = payment_svc.get_subscription_status(4444)
    assert status["tier"] == "PRO"
    assert status["is_active"] is True
    assert status["days_remaining"] >= 29


# ---------------------------------------------------------------------------
# 5. Device Service Tests
# ---------------------------------------------------------------------------
def test_device_service(temp_db):
    dev_svc = DeviceService(db_manager=temp_db)
    temp_db.get_or_create_user(6001)

    devices = dev_svc.list_user_devices(6001)
    assert len(devices) >= 1
    dev = devices[0]
    assert dev.user_id == 6001

    # Hardware tool dispatch
    from core.types import ToolExecutionResult
    import tools.registry
    with patch.object(tools.registry.ToolRegistry, "execute") as mock_exec:
        mock_exec.return_value = ToolExecutionResult(success=True, output="Flashlight toggled", error=None, duration_ms=10)
        res = dev_svc.dispatch_device_action(6001, dev.device_id, "torch", on=True)
        assert res["success"] is True
        mock_exec.assert_called_once_with("set_torch", on=True)


# ---------------------------------------------------------------------------
# 6. Mini App Micro Server Health & Static Tests
# ---------------------------------------------------------------------------
def test_miniapp_server_routes():
    import urllib.request
    import socket

    # Find free port
    with socket.socket() as s:
        s.bind(("", 0))
        free_port = s.getsockname()[1]

    server = MiniAppServer(host="127.0.0.1", port=free_port, bot_token=TEST_BOT_TOKEN)
    server.start()
    time.sleep(0.3)

    try:
        # GET /health
        url_health = f"http://127.0.0.1:{free_port}/health"
        with urllib.request.urlopen(url_health, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            assert data["status"] == "healthy"

        # GET /
        url_index = f"http://127.0.0.1:{free_port}/"
        with urllib.request.urlopen(url_index, timeout=2.0) as resp:
            html = resp.read().decode()
            assert "Void Edge Orchestrator" in html

        # GET /api/telemetry
        url_telem = f"http://127.0.0.1:{free_port}/api/telemetry"
        with urllib.request.urlopen(url_telem, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            assert "memory" in data
            assert "battery" in data

    finally:
        server.stop()
