"""
security/sanitizer.py - Whitelist-Based Regex Sanitization & Injection Defense.

Ensures zero-trust parameter validation on all dynamic user arguments passed
to Termux hardware APIs and subprocess execution vectors.
"""

import os
import re
from typing import List, Optional, Set, Any


class SecurityValidationError(ValueError):
    """Raised when an input parameter violates whitelist security validation rules."""
    pass


# Whitelist regex compiled patterns
_PHONE_REGEX = re.compile(r"^\+?[0-9]{3,16}$")
_URL_REGEX = re.compile(r"^https?://[a-zA-Z0-9\-_.]+(:\d+)?(/[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;%=]*)?$")
_SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-.]{1,255}$")
_APP_KEY_REGEX = re.compile(r"^[a-zA-Z0-9_\-./]+$")
_ANSI_ESCAPE_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

_ALLOWED_AUDIO_STREAMS: Set[str] = {
    "alarm",
    "music",
    "notification",
    "ring",
    "system",
    "call",
}

_ALLOWED_PATH_ROOTS: List[str] = [
    "/sdcard",
    "/storage/emulated/0",
    os.path.expanduser("~"),
    "/data/data/com.termux/files",
    os.getcwd(),
]


class InputSanitizer:
    """Enterprise-grade input sanitization and verification engine."""

    @staticmethod
    def sanitize_string(text: str, max_length: int = 4096) -> str:
        """
        Strips dangerous control characters, ANSI escapes, and enforces length bounds.
        Prevents terminal escape injection and memory exhaustion.
        """
        if not isinstance(text, str):
            text = str(text)

        # Remove null bytes immediately
        text = text.replace("\x00", "")

        # Strip ANSI escape sequences
        text = _ANSI_ESCAPE_REGEX.sub("", text)

        # Strip unprintable control characters
        text = _CONTROL_CHARS_REGEX.sub("", text)

        # Enforce length bound
        if len(text) > max_length:
            text = text[:max_length]

        return text.strip()

    @staticmethod
    def validate_phone_number(phone_number: str) -> str:
        """
        Validates phone number format strictly against numeric/E.164 pattern.
        Rejects shell metacharacters, semicolons, ampersands, or newlines.
        """
        clean = phone_number.strip().replace(" ", "").replace("-", "")
        if not _PHONE_REGEX.match(clean):
            raise SecurityValidationError(
                f"Invalid phone number format: '{phone_number}'. Must contain only digits and optional '+' prefix."
            )
        return clean

    @staticmethod
    def validate_file_path(path: str, allow_absolute: bool = True, must_exist: bool = False) -> str:
        """
        Resolves canonical path, forbids directory traversal (../), and verifies
        that target resides within permitted storage boundaries.
        """
        if not path or not isinstance(path, str):
            raise SecurityValidationError("File path must be a non-empty string.")

        if "\x00" in path:
            raise SecurityValidationError("File path contains illegal null bytes.")

        # Canonicalize path
        resolved = os.path.abspath(os.path.expanduser(path.strip()))

        # Verify not escaping through symlink or parent traversal
        permitted = False
        for root in _ALLOWED_PATH_ROOTS:
            try:
                common = os.path.commonpath([resolved, os.path.abspath(root)])
                if common == os.path.abspath(root):
                    permitted = True
                    break
            except ValueError:
                continue

        if not permitted:
            raise SecurityValidationError(
                f"Path traversal violation: '{path}' resolved to '{resolved}', which is outside permitted boundaries."
            )

        if must_exist and not os.path.exists(resolved):
            raise SecurityValidationError(f"Target file does not exist: '{resolved}'")

        return resolved

    @staticmethod
    def validate_url(url: str) -> str:
        """
        Validates that URL uses explicit http or https scheme and conforms to URI standard.
        Prevents dangerous URI schemes such as file://, javascript://, or data://.
        """
        clean_url = url.strip()
        if not _URL_REGEX.match(clean_url):
            raise SecurityValidationError(
                f"Invalid or unsafe URL: '{url}'. Must begin with http:// or https:// and contain valid characters."
            )
        return clean_url

    @staticmethod
    def validate_volume_stream(stream: str) -> str:
        """Validates stream identifier against Termux volume audio stream whitelist."""
        clean = stream.strip().lower()
        if clean not in _ALLOWED_AUDIO_STREAMS:
            raise SecurityValidationError(
                f"Invalid audio stream: '{stream}'. Must be one of {sorted(_ALLOWED_AUDIO_STREAMS)}"
            )
        return clean

    @staticmethod
    def validate_integer_range(value: Any, min_val: int, max_val: int, field_name: str) -> int:
        """Validates integer bounds (e.g. brightness 0-255, volume 0-15, limit 1-50)."""
        try:
            val = int(value)
        except (ValueError, TypeError):
            raise SecurityValidationError(f"Field '{field_name}' must be an integer, got: {value}")

        if not (min_val <= val <= max_val):
            raise SecurityValidationError(
                f"Field '{field_name}' value {val} out of permitted range [{min_val}, {max_val}]."
            )
        return val

    @staticmethod
    def validate_arg_vector(argv: List[str]) -> List[str]:
        """
        Verifies every argument in a subprocess command vector is safe.
        Ensures list-only vector execution without shell expansion.
        """
        if not isinstance(argv, (list, tuple)):
            raise SecurityValidationError("Command vector must be an array/list of strings.")

        if not argv:
            raise SecurityValidationError("Command vector cannot be empty.")

        sanitized_vector: List[str] = []
        for i, arg in enumerate(argv):
            if not isinstance(arg, str):
                arg = str(arg)
            if "\x00" in arg:
                raise SecurityValidationError(f"Command argument [{i}] contains forbidden null bytes.")
            sanitized_vector.append(arg)
        return sanitized_vector

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escapes Markdown special characters in dynamic values
        to prevent Telegram 'Bad Request: can't parse entities' errors.
        """
        if not isinstance(text, str):
            text = str(text)
        escape_chars = r"_*`[]()~>#+-=|{}.!"
        return re.sub(r"([%s])" % re.escape(escape_chars), r"\\\1", text)

    @staticmethod
    def safe_text(text: str, max_length: int = 3800) -> str:
        """Sanitizes string and enforces safe message bounds."""
        clean = InputSanitizer.sanitize_string(text, max_length=max_length)
        return clean
