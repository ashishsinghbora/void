"""
telegram/utils/safe_telegram.py - Zero-Failure Telegram Message Dispatcher.

Completely eliminates "Bad Request: can't parse entities" errors by gracefully catching
Telegram API parsing exceptions and immediately falling back to plain-text transmission.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("VoidTelegram.SafeMessenger")


def safe_send_message(
    bot: Any,
    chat_id: int,
    text: str,
    reply_markup: Optional[Any] = None,
    parse_mode: str = "Markdown",
    reply_to_message_id: Optional[int] = None,
) -> Any:
    """
    Sends message with Markdown formatting. If Telegram rejects entity parsing,
    immediately re-transmits as clean unformatted text so the user never sees an error.
    """
    if not bot:
        return None

    try:
        if reply_to_message_id:
            return bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
            )
        return bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception as e:
        err_str = str(e)
        if "can't parse entities" in err_str or "Bad Request" in err_str:
            logger.debug(f"Markdown entity parse failed, falling back to plain text: {e}")
            try:
                # Strip markdown asterisks and backticks for clean plain text
                clean_text = text.replace("*", "").replace("`", "").replace("_", "")
                if reply_to_message_id:
                    return bot.send_message(
                        chat_id,
                        clean_text,
                        reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id,
                    )
                return bot.send_message(
                    chat_id,
                    clean_text,
                    reply_markup=reply_markup,
                )
            except Exception as e2:
                logger.error(f"Fallback send failed: {e2}")
                return None
        logger.error(f"Error in safe_send_message: {e}")
        return None


def safe_reply(
    bot: Any,
    message: Any,
    text: str,
    reply_markup: Optional[Any] = None,
    parse_mode: str = "Markdown",
) -> Any:
    """Safely replies to a message with automatic plain-text entity fallback."""
    if not bot or not message:
        return None
    return safe_send_message(
        bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        reply_to_message_id=message.message_id,
    )


def safe_edit_message_text(
    bot: Any,
    text: str,
    chat_id: int,
    message_id: int,
    reply_markup: Optional[Any] = None,
    parse_mode: str = "Markdown",
) -> Any:
    """
    Edits an existing message with Markdown parsing. On entity parsing mismatch,
    falls back immediately to clean text without parse_mode.
    """
    if not bot:
        return None

    try:
        return bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception as e:
        err_str = str(e)
        if "message is not modified" in err_str:
            return None
        if "can't parse entities" in err_str or "Bad Request" in err_str:
            logger.debug(f"Edit Markdown parse failed, retrying plain text: {e}")
            try:
                clean_text = text.replace("*", "").replace("`", "").replace("_", "")
                return bot.edit_message_text(
                    clean_text,
                    chat_id,
                    message_id,
                    reply_markup=reply_markup,
                )
            except Exception as e2:
                logger.debug(f"Edit plain-text retry failed: {e2}")
                return None
        logger.debug(f"safe_edit_message_text error: {e}")
        return None
