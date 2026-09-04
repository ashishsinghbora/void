"""
tests/test_cloud_vault.py - Unit tests for Telegram Group Cloud Storage & Memory Vault.
"""

import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from telegram.services.cloud_vault import CloudVaultService
from telegram.database.db_manager import BotDatabaseManager
from telegram.database.models import VaultFile


@pytest.fixture
def temp_db():
    old_env = os.environ.pop("TELEGRAM_VAULT_GROUP_ID", None)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = BotDatabaseManager(db_path=db_path)
    yield db
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
    if old_env is not None:
        os.environ["TELEGRAM_VAULT_GROUP_ID"] = old_env
    else:
        os.environ.pop("TELEGRAM_VAULT_GROUP_ID", None)


def test_vault_config_persistence(temp_db):
    service = CloudVaultService(db=temp_db)
    assert not service.is_configured()

    service.set_vault_group_id(-1001987654321, group_title="Void Test Vault")
    assert service.is_configured()

    telemetry = service.get_vault_telemetry()
    assert telemetry["configured"] is True
    assert telemetry["group_id"] == -1001987654321
    assert telemetry["group_title"] == "Void Test Vault"
    assert telemetry["total_files"] == 0


def test_vault_file_record_and_query(temp_db):
    service = CloudVaultService(db=temp_db)
    service.set_vault_group_id(-1001987654321, group_title="Void Test Vault")

    rec_id = temp_db.record_vault_file(
        group_id=-1001987654321,
        telegram_message_id=42,
        telegram_file_id="tg_file_abc123",
        file_name="screenshot_01.png",
        file_path="/sdcard/Void/screenshot_01.png",
        file_size=1048576,
        category="screenshots",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        metadata={"width": 1080, "height": 2400},
    )
    assert rec_id > 0

    queried = service.query_vault(category="screenshots", limit=5)
    assert len(queried) == 1
    assert queried[0].file_name == "screenshot_01.png"
    assert queried[0].telegram_message_id == 42
    assert queried[0].file_size == 1048576

    telemetry = service.get_vault_telemetry()
    assert telemetry["total_files"] == 1
    assert telemetry["bytes_stored"] == 1048576


def test_vault_upload_file_mock_bot(temp_db):
    mock_bot = MagicMock()
    mock_sent = MagicMock()
    mock_sent.message_id = 999
    mock_sent.document = MagicMock(file_id="doc_xyz789")
    mock_sent.photo = None
    mock_sent.audio = None
    mock_bot.send_document.return_value = mock_sent

    service = CloudVaultService(db=temp_db, bot=mock_bot)
    service.set_vault_group_id(-100111222333, group_title="Vault Lab")

    # Create temporary file to upload
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Hello Void Cloud Vault")
        sample_path = f.name

    try:
        res = service.upload_file(
            file_path=sample_path,
            category="logs",
            caption="Test execution log",
        )
        assert res["success"] is True
        assert res["telegram_message_id"] == 999
        assert res["telegram_file_id"] == "doc_xyz789"
        assert res["file_name"] == os.path.basename(sample_path)
    finally:
        if os.path.exists(sample_path):
            os.remove(sample_path)


def test_vault_memory_snapshot_upload(temp_db):
    mock_bot = MagicMock()
    mock_sent = MagicMock()
    mock_sent.message_id = 1001
    mock_sent.document = MagicMock(file_id="doc_mem123")
    mock_sent.photo = None
    mock_sent.audio = None
    mock_bot.send_document.return_value = mock_sent

    service = CloudVaultService(db=temp_db, bot=mock_bot)
    service.set_vault_group_id(-100555666777, group_title="Memory Bank")

    res = service.upload_memory_snapshot()
    assert res["success"] is True
    assert res["category"] == "memories"
    assert res["telegram_message_id"] == 1001
