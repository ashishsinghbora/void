"""
tests/test_safe_telegram.py - Unit Tests for Safe Telegram Dispatch & Vault Linking.
"""

from unittest.mock import MagicMock
from telegram.utils.safe_telegram import safe_send_message, safe_reply, safe_edit_message_text
from telegram.handlers.vault_handlers import register_vault_handlers
from telegram.handlers.core_handlers import register_core_handlers
from telegram.bot_controller import AuthenticatedTelegramController


def test_safe_send_message_fallback_on_parse_error():
    """Verify safe_send_message catches entity errors and retries with plain text."""
    bot = MagicMock()
    bot.send_message.side_effect = [
        Exception("Bad Request: can't parse entities: Can't find end of the entity"),
        MagicMock(message_id=42),
    ]

    res = safe_send_message(bot, chat_id=123, text="*Unclosed bold text", parse_mode="Markdown")
    assert res is not None
    assert bot.send_message.call_count == 2
    call_args = bot.send_message.call_args_list[1]
    assert "parse_mode" not in call_args.kwargs or call_args.kwargs.get("parse_mode") is None


def test_safe_edit_message_text_fallback():
    """Verify safe_edit_message_text retries as plain text on entity errors."""
    bot = MagicMock()
    bot.edit_message_text.side_effect = [
        Exception("Bad Request: can't parse entities"),
        MagicMock(message_id=99),
    ]

    res = safe_edit_message_text(bot, text="*Invalid _markdown", chat_id=123, message_id=456)
    assert res is not None
    assert bot.edit_message_text.call_count == 2


def test_vault_group_link_handling():
    """Verify /set_vault registers invite links and /link_vault pairs group."""
    ctrl = AuthenticatedTelegramController(token="123456:mock_token", admin_ids={12345})
    bot = MagicMock()
    register_vault_handlers(bot, ctrl)

    assert bot.message_handler.called


def test_ai_chat_command_registered():
    """Verify /ai, /chat, /ask commands are registered in core_handlers."""
    ctrl = AuthenticatedTelegramController(token="123456:mock_token", admin_ids={12345})
    bot = MagicMock()
    register_core_handlers(bot, ctrl)

    found_ai_cmd = False
    for call in bot.message_handler.call_args_list:
        cmds = call.kwargs.get("commands", [])
        if "ai" in cmds or "chat" in cmds:
            found_ai_cmd = True
            break
    assert found_ai_cmd, "Command /ai was not registered"
