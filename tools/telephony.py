"""
tools/telephony.py - Telephony Strategy Implementations (SMS, Voice, Contacts, Call Log).

Applies whitelist-based phone number sanitization and streaming generator parsing
to eliminate memory spikes on large contact and message databases.
"""

import json
from typing import Any, Dict, List

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy


class SendSmsStrategy(ToolStrategy):
    """Sends SMS text message with strict phone number and body sanitization."""

    def __init__(self):
        super().__init__(
            name="send_sms",
            description="Send an SMS text message to a recipient phone number.",
            schema={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Destination phone number (E.164 or digits)"},
                    "message": {"type": "string", "description": "Text message content"},
                },
                "required": ["recipient", "message"],
            },
        )

    def execute(self, recipient: str = "", message: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_phone = InputSanitizer.validate_phone_number(recipient)
        clean_msg = InputSanitizer.sanitize_string(message, max_length=1000)
        res = SecureCommandExecutor.run(["termux-sms-send", "-n", clean_phone, clean_msg])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class MakeCallStrategy(ToolStrategy):
    """Initiates an outgoing voice call to a verified phone number."""

    def __init__(self):
        super().__init__(
            name="make_phone_call",
            description="Initiate an outgoing voice call to the specified phone number.",
            schema={
                "type": "object",
                "properties": {"phone_number": {"type": "string", "description": "Phone number to dial"}},
                "required": ["phone_number"],
            },
        )

    def execute(self, phone_number: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_phone = InputSanitizer.validate_phone_number(phone_number)
        res = SecureCommandExecutor.run(["termux-telephony-call", clean_phone])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class GetSmsListStrategy(ToolStrategy):
    """Retrieves recent SMS messages with generator streaming to minimize RAM allocations."""

    def __init__(self):
        super().__init__(
            name="get_sms_messages",
            description="Retrieve a list of recent incoming SMS text messages from the phone.",
            schema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Maximum messages to retrieve (1-50)"}},
            },
        )

    def execute(self, limit: int = 5, **kwargs: Any) -> ToolExecutionResult:
        safe_limit = InputSanitizer.validate_integer_range(limit, 1, 50, "limit")
        res = SecureCommandExecutor.run(["termux-sms-list", "-l", str(safe_limit)])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)

        # Stream parse to eliminate redundant object trees
        parsed_items: List[Dict[str, Any]] = list(SecureCommandExecutor.stream_parse_json(res))
        return ToolExecutionResult(success=True, output=parsed_items, error=None, duration_ms=0)


class GetContactsStrategy(ToolStrategy):
    """Retrieves device contact list with low-overhead parsing."""

    def __init__(self):
        super().__init__(
            name="get_contacts",
            description="Retrieve the phone's contact list (names and phone numbers).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-contact-list"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)

        parsed = list(SecureCommandExecutor.stream_parse_json(res))
        return ToolExecutionResult(success=True, output=parsed, error=None, duration_ms=0)


class GetCallLogStrategy(ToolStrategy):
    """Retrieves recent call history."""

    def __init__(self):
        super().__init__(
            name="get_call_log",
            description="Retrieve the recent call log history from the phone.",
            schema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Number of call records (1-50)"}},
            },
        )

    def execute(self, limit: int = 5, **kwargs: Any) -> ToolExecutionResult:
        safe_limit = InputSanitizer.validate_integer_range(limit, 1, 50, "limit")
        res = SecureCommandExecutor.run(["termux-call-log", "-l", str(safe_limit)])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)

        parsed = list(SecureCommandExecutor.stream_parse_json(res))
        return ToolExecutionResult(success=True, output=parsed, error=None, duration_ms=0)


class GetTelephonyInfoStrategy(ToolStrategy):
    """Retrieves telephony network state, operator, and SIM status."""

    def __init__(self):
        super().__init__(
            name="get_telephony_info",
            description="Retrieve device telephony information (network operator, SIM state, network type, IMEI).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-telephony-deviceinfo"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)
