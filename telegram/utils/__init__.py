"""
telegram/utils - Telegram Helper Utilities.
"""

from telegram.utils.safe_telegram import safe_send_message, safe_reply, safe_edit_message_text

__all__ = ["safe_send_message", "safe_reply", "safe_edit_message_text"]
