"""
agents/fallback_handler.py - Hardware Permission & Tool Execution Fallback Engine.

Captures Android OS permission denials, sensor timeouts, and hardware API errors,
mapping them deterministically to alternative tools or user remediation advice.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FallbackDecision:
    """Actionable decision envelope produced by fallback evaluation."""
    should_fallback: bool
    fallback_tool_name: Optional[str]
    fallback_arguments: Dict[str, Any]
    remediation_advice: str


class HardwareFallbackHandler:
    """Determines intelligent recovery paths when Termux hardware APIs fail."""

    @staticmethod
    def evaluate(tool_name: str, arguments: Dict[str, Any], error_message: str) -> FallbackDecision:
        err_lower = error_message.lower()

        # 1. Camera permission or sensor lock failure -> fallback to alternate camera or user validation
        if tool_name == "take_camera_photo":
            current_cam = str(arguments.get("camera_id", "0"))
            if current_cam == "0":
                return FallbackDecision(
                    should_fallback=True,
                    fallback_tool_name="take_camera_photo",
                    fallback_arguments={"camera_id": "1", "filename": arguments.get("filename", "void_photo_front.jpg")},
                    remediation_advice="Back camera inaccessible. Automatically retrying with front camera.",
                )
            return FallbackDecision(
                should_fallback=False,
                fallback_tool_name=None,
                fallback_arguments={},
                remediation_advice="Camera permission required. Please grant 'Camera' and 'Files/Storage' in Android App Settings for Termux:API.",
            )

        # 2. SMS Send failure -> fallback to Android Share Sheet intent
        if tool_name == "send_sms":
            msg = arguments.get("message", "")
            return FallbackDecision(
                should_fallback=True,
                fallback_tool_name="share_content",
                fallback_arguments={"text": msg},
                remediation_advice="Direct SMS send blocked by permissions. Falling back to system Share Sheet.",
            )

        # 3. Voice Call failure -> fallback to copying number to clipboard
        if tool_name == "make_phone_call":
            phone = arguments.get("phone_number", "")
            return FallbackDecision(
                should_fallback=True,
                fallback_tool_name="set_clipboard",
                fallback_arguments={"text": phone},
                remediation_advice=f"Call permission absent. Copied phone number '{phone}' to clipboard for manual dialing.",
            )

        # 4. Speech synthesis failure -> fallback to system notification
        if tool_name == "text_to_speech":
            text = arguments.get("text", "")
            return FallbackDecision(
                should_fallback=True,
                fallback_tool_name="show_notification",
                fallback_arguments={"title": "Voice Assistant Alert", "content": text},
                remediation_advice="TTS audio engine unavailable. Falling back to notification drawer popup.",
            )

        # 5. Microphone recording failure -> fallback to toast notification
        if tool_name == "record_audio_start":
            return FallbackDecision(
                should_fallback=True,
                fallback_tool_name="show_toast",
                fallback_arguments={"message": "Microphone permission required for audio recording."},
                remediation_advice="Ensure Termux:API has Microphone permission in Android Settings.",
            )

        # Default fallback
        return FallbackDecision(
            should_fallback=False,
            fallback_tool_name=None,
            fallback_arguments={},
            remediation_advice=f"Hardware execution error: {error_message}",
        )
