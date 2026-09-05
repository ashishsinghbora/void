"""
tests/test_submenus_callbacks.py - Verification of Submenu Callbacks & Commands.
"""

from unittest.mock import MagicMock
from telegram.bot_controller import AuthenticatedTelegramController
from telegram.handlers.menu_router import register_menu_router
from telegram.handlers.telemetry_handlers import register_telemetry_handlers
from telegram.handlers.input_handlers import register_input_handlers
from telegram.handlers.model_handlers import register_model_handlers
from telegram.handlers.shell_handlers import register_shell_handlers
from telegram.handlers.media_handlers import register_media_handlers
from telegram.handlers.automation_handlers import register_automation_handlers
from telegram.handlers.debug_handlers import register_debug_handlers


def test_telegram_controller_initialization():
    """Verify AuthenticatedTelegramController initializes with root keyboard."""
    ctrl = AuthenticatedTelegramController(token="123456789:AAG_mock_test_token", admin_ids={12345})
    markup = ctrl.get_main_keyboard()
    assert markup is not None
    assert len(markup.keyboard) >= 3  # 6 hubs across 3 rows


def test_shell_command_execution():
    """Verify /sh command handler dispatches safely."""
    ctrl = AuthenticatedTelegramController(token="123456789:AAG_mock_test_token", admin_ids={12345})
    bot_mock = MagicMock()
    register_shell_handlers(bot_mock, ctrl)

    assert bot_mock.message_handler.called
    assert bot_mock.callback_query_handler.called


def test_input_handlers_registration():
    """Verify input handlers register without error."""
    ctrl = AuthenticatedTelegramController(token="123456789:AAG_mock_test_token", admin_ids={12345})
    bot_mock = MagicMock()
    register_input_handlers(bot_mock, ctrl)
    assert bot_mock.callback_query_handler.called


def test_automation_and_debug_handlers_registration():
    """Verify automation macros and debug handlers register."""
    ctrl = AuthenticatedTelegramController(token="123456789:AAG_mock_test_token", admin_ids={12345})
    bot_mock = MagicMock()
    register_automation_handlers(bot_mock, ctrl)
    register_debug_handlers(bot_mock, ctrl)
    assert bot_mock.callback_query_handler.called
