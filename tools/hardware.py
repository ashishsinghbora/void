"""
tools/hardware.py - Hardware Strategy Implementations (Battery, Torch, Haptics, Display, Audio).
"""

import json
from typing import Any, Dict

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy


class BatteryStatusStrategy(ToolStrategy):
    """Retrieves real-time battery percentage, health, temperature, and charging state."""

    def __init__(self):
        super().__init__(
            name="get_battery_status",
            description="Retrieve details about the phone's battery (percentage, status, health, temperature).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-battery-status"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)

        try:
            parsed = json.loads(res)
            return ToolExecutionResult(success=True, output=parsed, error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class TorchControlStrategy(ToolStrategy):
    """Turns the camera flash / flashlight ON or OFF."""

    def __init__(self):
        super().__init__(
            name="set_torch",
            description="Turn the phone device's camera flash / torch ON (True) or OFF (False).",
            schema={
                "type": "object",
                "properties": {"on": {"type": "boolean", "description": "True to activate, False to turn off"}},
                "required": ["on"],
            },
        )

    def execute(self, on: bool = False, **kwargs: Any) -> ToolExecutionResult:
        state = "on" if on else "off"
        res = SecureCommandExecutor.run(["termux-torch", state])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class VibrateDeviceStrategy(ToolStrategy):
    """Vibrates the mobile device for a specified duration in milliseconds."""

    def __init__(self):
        super().__init__(
            name="vibrate_device",
            description="Vibrate the phone device for a duration specified in milliseconds.",
            schema={
                "type": "object",
                "properties": {"duration_ms": {"type": "integer", "description": "Vibration time in ms (100-5000)"}},
            },
        )

    def execute(self, duration_ms: int = 500, **kwargs: Any) -> ToolExecutionResult:
        duration = InputSanitizer.validate_integer_range(duration_ms, 50, 10000, "duration_ms")
        res = SecureCommandExecutor.run(["termux-vibrate", "-d", str(duration)])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class ScreenBrightnessStrategy(ToolStrategy):
    """Adjusts device screen brightness (0-255 or 'auto')."""

    def __init__(self):
        super().__init__(
            name="set_screen_brightness",
            description="Adjust the screen brightness. Provide a value between 0 and 255, or 'auto'.",
            schema={
                "type": "object",
                "properties": {"level": {"type": "string", "description": "Brightness value 0-255 or 'auto'"}},
                "required": ["level"],
            },
        )

    def execute(self, level: Any = "auto", **kwargs: Any) -> ToolExecutionResult:
        str_val = str(level).strip().lower()
        if str_val != "auto":
            int_val = InputSanitizer.validate_integer_range(str_val, 0, 255, "level")
            str_val = str(int_val)

        res = SecureCommandExecutor.run(["termux-brightness", str_val])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class VolumeControlStrategy(ToolStrategy):
    """Gets volume information or adjusts a specific audio stream level."""

    def __init__(self):
        super().__init__(
            name="set_volume",
            description="Set the volume level of a specific audio stream (alarm, music, notification, ring, system, call).",
            schema={
                "type": "object",
                "properties": {
                    "stream": {"type": "string", "description": "Audio stream: music, ring, alarm, notification, system, call"},
                    "volume": {"type": "integer", "description": "Volume level (0-15)"},
                },
                "required": ["stream", "volume"],
            },
        )

    def execute(self, stream: str = "music", volume: int = 5, **kwargs: Any) -> ToolExecutionResult:
        valid_stream = InputSanitizer.validate_volume_stream(stream)
        valid_volume = InputSanitizer.validate_integer_range(volume, 0, 100, "volume")
        res = SecureCommandExecutor.run(["termux-volume", valid_stream, str(valid_volume)])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class VolumeInfoStrategy(ToolStrategy):
    """Retrieves current volume levels across all streams."""

    def __init__(self):
        super().__init__(
            name="get_volume_info",
            description="Retrieve the current volume levels of all audio streams (music, ring, alarm, etc.).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-volume"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)
