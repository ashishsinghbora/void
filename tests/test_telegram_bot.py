"""
tests/test_telegram_bot.py - Unit Tests for Telegram Control Plane & Keyboards.
"""

import pytest
from unittest.mock import MagicMock, patch
from telegram.bot_controller import AuthenticatedTelegramController

MOCK_BOT_TOKEN = "123456789:AAG_mock_token_for_unit_tests"


def test_telegram_controller_authorization():
    ctrl = AuthenticatedTelegramController(token=MOCK_BOT_TOKEN, admin_ids={123456, 789012})

    assert ctrl._is_authorized(123456) is True
    assert ctrl._is_authorized(789012) is True
    assert ctrl._is_authorized(999999) is False


def test_telegram_controller_open_when_no_admin_configured():
    ctrl = AuthenticatedTelegramController(token=MOCK_BOT_TOKEN, admin_ids=set())
    # When no admin IDs are set, all are allowed (logs warning)
    assert ctrl._is_authorized(123456) is True


def test_telegram_keyboards():
    ctrl = AuthenticatedTelegramController(token=MOCK_BOT_TOKEN, admin_ids={123456})
    main_kb = ctrl.get_main_keyboard()
    assert main_kb is not None

    apps_kb = ctrl.get_apps_keyboard()
    assert apps_kb is not None


def test_telegram_rate_limiting():
    ctrl = AuthenticatedTelegramController(token=MOCK_BOT_TOKEN, admin_ids={123456}, rate_limit_capacity=2)

    # First two requests should pass
    allowed1, _ = ctrl._rate_limiter.allow_request("123456")
    allowed2, _ = ctrl._rate_limiter.allow_request("123456")
    assert allowed1 is True
    assert allowed2 is True

    # Third consecutive burst should be rate-limited
    allowed3, wait_sec = ctrl._rate_limiter.allow_request("123456")
    assert allowed3 is False
    assert wait_sec > 0
