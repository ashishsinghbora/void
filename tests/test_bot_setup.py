"""
tests/test_bot_setup.py - Unit Tests for Telegram Setup Wizard & Environment Loader.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from core.bot_setup import TelegramSetupWizard, load_config_env


def test_validate_token_format():
    valid = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    assert TelegramSetupWizard.validate_token_format(valid) is True

    assert TelegramSetupWizard.validate_token_format("no_colon") is False
    assert TelegramSetupWizard.validate_token_format("abc:def") is False
    assert TelegramSetupWizard.validate_token_format("123:short") is False
    assert TelegramSetupWizard.validate_token_format("123:has space here") is False


def test_verify_bot_token_mock():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "result": {"username": "VoidTestBot"}}
    with patch("requests.get", return_value=mock_resp):
        valid, username, err = TelegramSetupWizard.verify_bot_token("123456789:AAG_mock_token_12345678")
        assert valid is True
        assert username == "VoidTestBot"
        assert err is None


def test_save_and_load_config_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_cfg = os.path.join(tmpdir, "config.env")
        with patch("core.bot_setup.CONFIG_FILE_PATH", test_cfg):
            saved = TelegramSetupWizard.save_configuration("123456:MOCK_TOKEN_VAL", 987654321)
            assert os.path.exists(saved)

            # Check permissions (on POSIX, 0600)
            if hasattr(os, "stat"):
                mode = oct(os.stat(saved).st_mode)[-3:]
                assert mode == "600"

            # Load into env
            cfg = load_config_env()
            assert cfg["TELEGRAM_TOKEN"] == "123456:MOCK_TOKEN_VAL"
            assert cfg["ADMIN_TELEGRAM_ID"] == "987654321"
