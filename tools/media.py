"""
tools/media.py - Media Strategy Implementations (Camera, Text-to-Speech, Audio Recording, Share).
"""

import os
import subprocess
from typing import Any, Dict

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor, IS_TERMUX
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy


class CameraPhotoStrategy(ToolStrategy):
    """Captures photo using back/front camera with multi-target directory fallbacks."""

    def __init__(self):
        super().__init__(
            name="take_camera_photo",
            description="Capture a photo using the phone's camera and save it to storage.",
            schema={
                "type": "object",
                "properties": {
                    "camera_id": {"type": "string", "description": "Camera ID (0 for back, 1 for front)"},
                    "filename": {"type": "string", "description": "Output filename (optional)"},
                },
            },
        )

    def execute(self, camera_id: str = "0", filename: str = "void_photo.jpg", **kwargs: Any) -> ToolExecutionResult:
        clean_cam = "1" if str(camera_id) == "1" else "0"
        sanitized_name = os.path.basename(InputSanitizer.sanitize_string(filename, max_length=64)) or "void_photo.jpg"

        home_dir = os.path.expanduser("~")
        candidate_paths = [
            os.path.join("/sdcard/Download", sanitized_name),
            os.path.join(home_dir, "storage", "downloads", sanitized_name),
            os.path.join(home_dir, sanitized_name),
        ]

        last_err = ""
        for target in candidate_paths:
            try:
                parent = os.path.dirname(target)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)

                res = SecureCommandExecutor.run(["termux-camera-photo", "-c", clean_cam, target])
                if not res.startswith("Error") and os.path.exists(target) and os.path.getsize(target) > 0:
                    return ToolExecutionResult(
                        success=True,
                        output=f"Photo captured with camera {clean_cam} and saved to: '{target}'",
                        error=None,
                        duration_ms=0,
                    )
                last_err = res
            except Exception as ex:
                last_err = str(ex)

        if not IS_TERMUX:
            # On desktop simulator, provide simulated success
            return ToolExecutionResult(
                success=True,
                output=f"[Simulated Camera] Photo captured with camera {clean_cam} and saved to: '{candidate_paths[0]}'",
                error=None,
                duration_ms=0,
            )

        return ToolExecutionResult(
            success=False,
            output=None,
            error=f"Camera capture failed ({last_err}). Ensure Termux:API has 'Camera' and 'Storage' permissions in Android Settings.",
            duration_ms=0,
        )


class TextToSpeechStrategy(ToolStrategy):
    """Speaks a text string aloud using the phone's Text-to-Speech (TTS) engine."""

    def __init__(self):
        super().__init__(
            name="text_to_speech",
            description="Speak a text string aloud using the phone's Text-to-Speech (TTS) engine.",
            schema={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Text to speak"}},
                "required": ["text"],
            },
        )

    def execute(self, text: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_text = InputSanitizer.sanitize_string(text, max_length=2000)
        try:
            if not IS_TERMUX:
                return ToolExecutionResult(
                    success=True,
                    output=f"[Simulated Text-To-Speech] Spoke aloud: '{clean_text}'",
                    error=None,
                    duration_ms=0,
                )

            res = subprocess.run(
                ["termux-tts-speak"],
                input=clean_text,
                capture_output=True,
                text=True,
                timeout=12,
            )
            if res.returncode != 0:
                err = res.stderr.strip() or f"Exit code {res.returncode}"
                return ToolExecutionResult(success=False, output=None, error=f"TTS error: {err}", duration_ms=0)
            return ToolExecutionResult(
                success=True,
                output=res.stdout.strip() if res.stdout else "Speech synthesized successfully.",
                error=None,
                duration_ms=0,
            )
        except Exception as e:
            return ToolExecutionResult(success=False, output=None, error=str(e), duration_ms=0)


class RecordAudioStartStrategy(ToolStrategy):
    """Starts microphone audio recording into target file."""

    def __init__(self):
        super().__init__(
            name="record_audio_start",
            description="Begin recording audio from the microphone to a file. Optionally set duration limit.",
            schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Target audio filename (e.g. recording.3gp)"},
                    "limit_seconds": {"type": "integer", "description": "Auto-stop limit in seconds (0 for manual stop)"},
                },
            },
        )

    def execute(self, file_path: str = "recording.3gp", limit_seconds: int = 0, **kwargs: Any) -> ToolExecutionResult:
        sanitized_path = InputSanitizer.sanitize_string(file_path, max_length=128) or "recording.3gp"
        limit = InputSanitizer.validate_integer_range(limit_seconds, 0, 3600, "limit_seconds")
        
        cmd = ["termux-microphone-record", "-f", sanitized_path]
        if limit > 0:
            cmd.extend(["-l", str(limit)])

        res = SecureCommandExecutor.run(cmd)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class RecordAudioStopStrategy(ToolStrategy):
    """Stops the ongoing microphone audio recording."""

    def __init__(self):
        super().__init__(
            name="record_audio_stop",
            description="Stop the ongoing microphone audio recording and save the file.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-microphone-record", "-q"])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class ShareContentStrategy(ToolStrategy):
    """Shares text or a file using the Android system share sheet."""

    def __init__(self):
        super().__init__(
            name="share_content",
            description="Share text content or a file using the Android system share sheet.",
            schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text content to share"},
                    "file_path": {"type": "string", "description": "Absolute file path to share"},
                },
            },
        )

    def execute(self, text: str = "", file_path: str = "", **kwargs: Any) -> ToolExecutionResult:
        if file_path:
            clean_path = InputSanitizer.validate_file_path(file_path, must_exist=False)
            res = SecureCommandExecutor.run(["termux-share", "-a", "send", clean_path])
            success = not res.startswith("Error")
            return ToolExecutionResult(
                success=success,
                output=res if success else None,
                error=res if not success else None,
                duration_ms=0,
            )
        elif text:
            clean_text = InputSanitizer.sanitize_string(text, max_length=2000)
            if not IS_TERMUX:
                return ToolExecutionResult(
                    success=True,
                    output=f"[Simulated Share] Shared text via system share sheet: '{clean_text}'",
                    error=None,
                    duration_ms=0,
                )
            try:
                res = subprocess.run(
                    ["termux-share", "-a", "send"],
                    input=clean_text,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode != 0:
                    return ToolExecutionResult(success=False, output=None, error=res.stderr.strip(), duration_ms=0)
                return ToolExecutionResult(success=True, output="Content shared successfully.", error=None, duration_ms=0)
            except Exception as e:
                return ToolExecutionResult(success=False, output=None, error=str(e), duration_ms=0)
        else:
            return ToolExecutionResult(
                success=False,
                output=None,
                error="Either text or file_path must be provided to share_content.",
                duration_ms=0,
            )
