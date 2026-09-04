"""
tools/mobile_actions.py - Advanced Human-Like Mobile Action Engine & Deep UI Navigation.

Implements input simulation (taps, swipes, text typing, hardware key events),
deep Android settings intents, in-app search triggers (YouTube, Maps, PlayStore, Browser),
and screen captures saved to the media vault and mirrored to the Telegram Cloud Vault.
"""

import os
import re
import urllib.parse
import logging
from typing import Any, Dict, Optional

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor, IS_TERMUX
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy
from core.media_vault import global_media_vault

logger = logging.getLogger("VoidAdvancedCore.MobileActions")


class MobileTapStrategy(ToolStrategy):
    """Simulates a touch tap gesture at coordinates (X, Y) on the screen."""

    def __init__(self):
        super().__init__(
            name="mobile_tap",
            description="Simulate a touch screen tap at specific coordinates (e.g. x=540, y=1200).",
            schema={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X horizontal coordinate (pixels)"},
                    "y": {"type": "integer", "description": "Y vertical coordinate (pixels)"},
                },
                "required": ["x", "y"],
            },
        )

    def execute(self, x: int = 0, y: int = 0, **kwargs: Any) -> ToolExecutionResult:
        try:
            clean_x = InputSanitizer.validate_integer_range(x, 0, 10000, "x")
            clean_y = InputSanitizer.validate_integer_range(y, 0, 10000, "y")
        except Exception as e:
            return ToolExecutionResult(success=False, output=None, error=str(e), duration_ms=0)

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Tapped screen at coordinates ({clean_x}, {clean_y})",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["input", "tap", str(clean_x), str(clean_y)], timeout=5)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Tapped screen at ({clean_x}, {clean_y})" if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class MobileSwipeStrategy(ToolStrategy):
    """Simulates a swipe / drag gesture from (X1, Y1) to (X2, Y2)."""

    def __init__(self):
        super().__init__(
            name="mobile_swipe",
            description="Simulate a swipe gesture across the screen from start (x1, y1) to end (x2, y2).",
            schema={
                "type": "object",
                "properties": {
                    "x1": {"type": "integer", "description": "Start X coordinate"},
                    "y1": {"type": "integer", "description": "Start Y coordinate"},
                    "x2": {"type": "integer", "description": "End X coordinate"},
                    "y2": {"type": "integer", "description": "End Y coordinate"},
                    "duration_ms": {"type": "integer", "description": "Swipe duration in milliseconds (default: 300)"},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        )

    def execute(self, x1: int = 0, y1: int = 0, x2: int = 0, y2: int = 0, duration_ms: int = 300, **kwargs: Any) -> ToolExecutionResult:
        try:
            cx1 = InputSanitizer.validate_integer_range(x1, 0, 10000, "x1")
            cy1 = InputSanitizer.validate_integer_range(y1, 0, 10000, "y1")
            cx2 = InputSanitizer.validate_integer_range(x2, 0, 10000, "x2")
            cy2 = InputSanitizer.validate_integer_range(y2, 0, 10000, "y2")
            cdur = InputSanitizer.validate_integer_range(duration_ms, 50, 5000, "duration_ms")
        except Exception as e:
            return ToolExecutionResult(success=False, output=None, error=str(e), duration_ms=0)

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Swiped screen from ({cx1}, {cy1}) to ({cx2}, {cy2}) in {cdur}ms",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["input", "swipe", str(cx1), str(cy1), str(cx2), str(cy2), str(cdur)], timeout=5)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Swiped from ({cx1}, {cy1}) to ({cx2}, {cy2}) in {cdur}ms" if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class MobileKeyEventStrategy(ToolStrategy):
    """Simulates Android hardware key events (Home, Back, Recents, Volume, Power, Enter)."""

    KEY_CODES: Dict[str, int] = {
        "home": 3,
        "back": 4,
        "call": 5,
        "endcall": 6,
        "volume_up": 24,
        "volume_down": 25,
        "power": 26,
        "camera": 27,
        "clear": 28,
        "enter": 66,
        "delete": 67,
        "backspace": 67,
        "tab": 61,
        "space": 62,
        "app_switch": 187,
        "recents": 187,
    }

    def __init__(self):
        super().__init__(
            name="mobile_keyevent",
            description="Simulate hardware button presses (e.g., 'home', 'back', 'app_switch', 'volume_up', 'volume_down', 'enter', 'power').",
            schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key name (home, back, app_switch, enter, power, volume_up, volume_down)"},
                },
                "required": ["key"],
            },
        )

    def execute(self, key: str = "home", **kwargs: Any) -> ToolExecutionResult:
        clean_key = InputSanitizer.sanitize_string(key, max_length=32).lower().strip()
        code = self.KEY_CODES.get(clean_key)
        if code is None:
            if clean_key.isdigit():
                code = int(clean_key)
            else:
                return ToolExecutionResult(
                    success=False,
                    output=None,
                    error=f"Unknown key event '{key}'. Supported: {list(self.KEY_CODES.keys())}",
                    duration_ms=0,
                )

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Triggered key event '{clean_key}' (KeyCode: {code})",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["input", "keyevent", str(code)], timeout=5)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Triggered key event '{clean_key}' (KeyCode: {code})" if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class MobileTypeTextStrategy(ToolStrategy):
    """Types alphanumeric text into the currently active input field."""

    def __init__(self):
        super().__init__(
            name="mobile_type_text",
            description="Type text into the currently focused input field on screen.",
            schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
            },
        )

    def execute(self, text: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_text = InputSanitizer.sanitize_string(text, max_length=500)
        if not clean_text:
            return ToolExecutionResult(success=False, output=None, error="Text cannot be empty.", duration_ms=0)

        # Android 'input text' expects spaces encoded as '%s'
        encoded_text = clean_text.replace(" ", "%s")

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Typed text into active field: '{clean_text}'",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["input", "text", encoded_text], timeout=5)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Typed text: '{clean_text}'" if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class OpenSettingsScreenStrategy(ToolStrategy):
    """Opens deep Android system settings panels directly via system intents."""

    SETTINGS_MAP: Dict[str, str] = {
        "wifi": "android.settings.WIFI_SETTINGS",
        "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
        "battery": "android.intent.action.POWER_USAGE_SUMMARY",
        "display": "android.settings.DISPLAY_SETTINGS",
        "apps": "android.settings.APPLICATION_SETTINGS",
        "sound": "android.settings.SOUND_SETTINGS",
        "accessibility": "android.settings.ACCESSIBILITY_SETTINGS",
        "storage": "android.settings.INTERNAL_STORAGE_SETTINGS",
        "security": "android.settings.SECURITY_SETTINGS",
        "date": "android.settings.DATE_SETTINGS",
        "device_info": "android.settings.DEVICE_INFO_SETTINGS",
        "airplane": "android.settings.AIRPLANE_MODE_SETTINGS",
    }

    def __init__(self):
        super().__init__(
            name="open_settings_screen",
            description="Navigate directly to a specific Android settings screen (e.g., 'wifi', 'bluetooth', 'battery', 'display', 'apps', 'sound').",
            schema={
                "type": "object",
                "properties": {
                    "screen": {"type": "string", "description": "Settings screen name (wifi, bluetooth, battery, display, apps, sound, accessibility, storage)"},
                },
                "required": ["screen"],
            },
        )

    def execute(self, screen: str = "wifi", **kwargs: Any) -> ToolExecutionResult:
        clean = InputSanitizer.sanitize_string(screen, max_length=32).lower().strip()
        action = self.SETTINGS_MAP.get(clean)
        if not action:
            # Fallback search
            for k, v in self.SETTINGS_MAP.items():
                if k in clean or clean in k:
                    action = v
                    break

        if not action:
            action = "android.settings.SETTINGS"

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Opened Settings screen: '{screen}' (Action: {action})",
                error=None,
                duration_ms=0,
            )

        cmd = ["am", "start", "-a", action]
        res = SecureCommandExecutor.run(cmd, timeout=5)
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Opened Android {screen.capitalize()} Settings screen." if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class AppSearchStrategy(ToolStrategy):
    """Performs in-app search query across YouTube, Maps, Google Play, or Browser."""

    def __init__(self):
        super().__init__(
            name="app_search",
            description="Search for content inside an app (e.g. app='youtube' query='lofi beats', app='maps' query='coffee', app='browser' query='python termux').",
            schema={
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Target app (youtube, maps, playstore, browser)"},
                    "query": {"type": "string", "description": "Search query terms"},
                },
                "required": ["app", "query"],
            },
        )

    def execute(
        self,
        app: str = "youtube",
        query: str = "",
        target_app: str = "",
        search_query: str = "",
        **kwargs: Any,
    ) -> ToolExecutionResult:
        eff_app = target_app or app or "youtube"
        eff_query = search_query or query or ""
        clean_app = InputSanitizer.sanitize_string(eff_app, max_length=32).lower().strip()
        clean_q = InputSanitizer.sanitize_string(eff_query, max_length=200).strip()
        if not clean_q:
            return ToolExecutionResult(success=False, output=None, error="Search query cannot be empty.", duration_ms=0)

        encoded_q = urllib.parse.quote(clean_q)

        if "youtube" in clean_app:
            url = f"https://www.youtube.com/results?search_query={encoded_q}"
        elif "map" in clean_app:
            url = f"geo:0,0?q={encoded_q}"
        elif "play" in clean_app or "store" in clean_app:
            url = f"market://search?q={encoded_q}"
        else:
            url = f"https://www.google.com/search?q={encoded_q}"

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Searched {clean_app.capitalize()} for '{clean_q}' ({url})",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["termux-open-url", url], timeout=5)
        if res.startswith("Error"):
            # Fallback to Activity Manager view intent
            am_res = SecureCommandExecutor.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url], timeout=5)
            if am_res.startswith("Error"):
                return ToolExecutionResult(success=False, output=None, error=f"Search failed: {am_res}", duration_ms=0)

        return ToolExecutionResult(
            success=True,
            output=f"Searched {clean_app.capitalize()} for: '{clean_q}'",
            error=None,
            duration_ms=0,
        )


class CaptureScreenStrategy(ToolStrategy):
    """Captures an Android screen screenshot, saving to media vault and syncing to Telegram."""

    def __init__(self):
        super().__init__(
            name="capture_screen",
            description="Take a screenshot of the phone screen, save to media vault, and upload to Telegram Cloud Vault.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        target_path = global_media_vault.generate_media_path(prefix="void_screenshot", extension="png")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if not IS_TERMUX:
            # Create a mock PNG stub for desktop simulator
            try:
                with open(target_path, "wb") as f:
                    # 1x1 pixel PNG header stub
                    f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
            except Exception:
                pass

            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Screen captured and saved to: '{target_path}'",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["screencap", "-p", target_path], timeout=6)
        if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Screenshot capture failed ({res}). Requires Android screencap binary or root/display permission.",
                duration_ms=0,
            )

        # Sync to Telegram Cloud Vault if configured
        vault_synced = False
        try:
            from telegram.services.cloud_vault import global_cloud_vault
            vf = global_cloud_vault.upload_file(
                file_path=target_path,
                file_type="photo",
                tag="screenshot",
                caption="Device screen capture",
            )
            vault_synced = vf is not None
        except Exception:
            pass

        vault_info = " [☁️ Uploaded to Telegram Cloud Vault]" if vault_synced else ""
        return ToolExecutionResult(
            success=True,
            output=f"Screenshot captured and saved to: '{target_path}'{vault_info}",
            error=None,
            duration_ms=0,
        )
