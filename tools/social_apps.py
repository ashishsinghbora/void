"""
tools/social_apps.py - Social Media & Cross-App Automation Strategies.

Enables automated dispatch to WhatsApp (deep-link chat & draft messages),
Telegram (direct user & channel chats), social profiles (Instagram, LinkedIn, GitHub),
and arbitrary Android application launching via package intents.
"""

import re
import urllib.parse
import logging
from typing import Any, Dict, Optional

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor, IS_TERMUX
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy

logger = logging.getLogger("VoidAdvancedCore.SocialTools")


class SendWhatsAppMessageStrategy(ToolStrategy):
    """Dispatches WhatsApp messaging intents and pre-filled chat drafts."""

    def __init__(self):
        super().__init__(
            name="send_whatsapp_message",
            description="Open WhatsApp to send a pre-filled message to a phone number (e.g., phone='+1234567890', message='Hello').",
            schema={
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Phone number with country code (digits only or leading +)"},
                    "message": {"type": "string", "description": "Message body to send or draft"},
                },
                "required": ["phone", "message"],
            },
        )

    def execute(self, phone: str = "", message: str = "", **kwargs: Any) -> ToolExecutionResult:
        # Extract numbers, allowing optional leading '+'
        clean_phone = re.sub(r"[^\d+]", "", str(phone).strip())
        if clean_phone.startswith("+"):
            clean_phone = clean_phone[1:]

        if not clean_phone or not clean_phone.isdigit():
            return ToolExecutionResult(
                success=False,
                output=None,
                error="Invalid phone number. Please provide numbers with international country code (e.g. 15551234567).",
                duration_ms=0,
            )

        sanitized_msg = InputSanitizer.sanitize_string(message, max_length=1000)
        encoded_text = urllib.parse.quote(sanitized_msg)
        wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] WhatsApp message intent dispatched for +{clean_phone} with text: '{sanitized_msg}' (URL: {wa_url})",
                error=None,
                duration_ms=0,
            )

        # On Termux: trigger deep-link intent
        res = SecureCommandExecutor.run(["termux-open-url", wa_url], timeout=5)
        if res.startswith("Error"):
            # Fallback to Android Activity Manager
            am_res = SecureCommandExecutor.run([
                "am", "start", "-a", "android.intent.action.VIEW", "-d", wa_url
            ], timeout=5)
            if am_res.startswith("Error"):
                return ToolExecutionResult(
                    success=False,
                    output=None,
                    error=f"Failed to trigger WhatsApp intent: {am_res}",
                    duration_ms=0,
                )

        return ToolExecutionResult(
            success=True,
            output=f"Dispatched WhatsApp chat draft for +{clean_phone} with message: '{sanitized_msg}'",
            error=None,
            duration_ms=0,
        )


class OpenTelegramChatStrategy(ToolStrategy):
    """Opens a direct Telegram user, group, or channel chat."""

    def __init__(self):
        super().__init__(
            name="open_telegram_chat",
            description="Open a direct Telegram user, channel, or group chat by username (e.g. 'durov' or '@telegram').",
            schema={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Telegram username or channel handle (with or without @)"},
                },
                "required": ["username"],
            },
        )

    def execute(self, username: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_user = InputSanitizer.sanitize_string(username, max_length=64).lstrip("@").strip()
        if not clean_user:
            return ToolExecutionResult(
                success=False,
                output=None,
                error="Username cannot be empty.",
                duration_ms=0,
            )

        tg_url = f"https://t.me/{clean_user}"

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Telegram chat opened for @{clean_user} (URL: {tg_url})",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["termux-open-url", tg_url], timeout=5)
        if res.startswith("Error"):
            am_res = SecureCommandExecutor.run([
                "am", "start", "-a", "android.intent.action.VIEW", "-d", tg_url
            ], timeout=5)
            if am_res.startswith("Error"):
                return ToolExecutionResult(
                    success=False,
                    output=None,
                    error=f"Failed to open Telegram chat: {am_res}",
                    duration_ms=0,
                )

        return ToolExecutionResult(
            success=True,
            output=f"Opened Telegram chat for @{clean_user}",
            error=None,
            duration_ms=0,
        )


class OpenSocialProfileStrategy(ToolStrategy):
    """Navigates directly to user profiles or repos on Instagram, LinkedIn, GitHub, or X."""

    PLATFORM_URLS = {
        "instagram": "https://www.instagram.com/{handle}/",
        "insta": "https://www.instagram.com/{handle}/",
        "linkedin": "https://www.linkedin.com/in/{handle}/",
        "github": "https://github.com/{handle}",
        "x": "https://x.com/{handle}",
        "twitter": "https://x.com/{handle}",
        "youtube": "https://www.youtube.com/@{handle}",
    }

    def __init__(self):
        super().__init__(
            name="open_social_profile",
            description="Open a profile or repository on Instagram, LinkedIn, GitHub, X/Twitter, or YouTube.",
            schema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform name ('instagram', 'linkedin', 'github', 'x', 'twitter', 'youtube')",
                    },
                    "handle": {
                        "type": "string",
                        "description": "Username, handle, or repository path (e.g. 'ashishsinghbora/void')",
                    },
                },
                "required": ["platform", "handle"],
            },
        )

    def execute(self, platform: str = "", handle: str = "", **kwargs: Any) -> ToolExecutionResult:
        plat_clean = InputSanitizer.sanitize_string(platform, max_length=32).lower().strip()
        handle_clean = InputSanitizer.sanitize_string(handle, max_length=128).lstrip("@").strip()

        if plat_clean not in self.PLATFORM_URLS:
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Unsupported platform '{platform}'. Supported: {list(set(self.PLATFORM_URLS.keys()))}",
                duration_ms=0,
            )

        if not handle_clean:
            return ToolExecutionResult(
                success=False,
                output=None,
                error="Handle/target cannot be empty.",
                duration_ms=0,
            )

        url = self.PLATFORM_URLS[plat_clean].format(handle=handle_clean)

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Opened {plat_clean.capitalize()} profile for '{handle_clean}' ({url})",
                error=None,
                duration_ms=0,
            )

        res = SecureCommandExecutor.run(["termux-open-url", url], timeout=5)
        if res.startswith("Error"):
            am_res = SecureCommandExecutor.run([
                "am", "start", "-a", "android.intent.action.VIEW", "-d", url
            ], timeout=5)
            if am_res.startswith("Error"):
                return ToolExecutionResult(
                    success=False,
                    output=None,
                    error=f"Failed to open profile: {am_res}",
                    duration_ms=0,
                )

        return ToolExecutionResult(
            success=True,
            output=f"Opened {plat_clean.capitalize()} profile for '{handle_clean}'",
            error=None,
            duration_ms=0,
        )


class LaunchInstalledAppStrategy(ToolStrategy):
    """Launches an installed Android application via package intent or deep-link fallback."""

    KNOWN_PACKAGES: Dict[str, str] = {
        "whatsapp": "com.whatsapp",
        "telegram": "org.telegram.messenger",
        "instagram": "com.instagram.android",
        "youtube": "com.google.android.youtube",
        "chrome": "com.android.chrome",
        "camera": "com.android.camera",
        "settings": "com.android.settings",
        "spotify": "com.spotify.music",
        "gmail": "com.google.android.gm",
        "maps": "com.google.android.apps.maps",
        "twitter": "com.twitter.android",
        "x": "com.twitter.android",
        "linkedin": "com.linkedin.android",
        "github": "com.github.android",
        "calculator": "com.google.android.calculator",
        "photos": "com.google.android.apps.photos",
        "gallery": "com.google.android.apps.photos",
        "clock": "com.google.android.deskclock",
        "playstore": "com.android.vending",
        "files": "com.google.android.documentsui",
    }

    def __init__(self):
        super().__init__(
            name="launch_installed_app",
            description="Launch any installed Android application on the phone (e.g., 'whatsapp', 'youtube', 'camera', 'settings', 'chrome').",
            schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "App name or package name to launch"},
                },
                "required": ["app_name"],
            },
        )

    def execute(self, app_name: str = "", **kwargs: Any) -> ToolExecutionResult:
        raw = InputSanitizer.sanitize_string(app_name, max_length=128).lower().strip()
        clean = re.sub(r"^(open|launch|start)\s+(the\s+)?", "", raw).replace("app", "").strip()

        # Find package
        package = self.KNOWN_PACKAGES.get(clean) or self.KNOWN_PACKAGES.get(raw)
        if not package:
            # Fuzzy check in known aliases
            for alias, pkg in self.KNOWN_PACKAGES.items():
                if alias in clean or clean in alias:
                    package = pkg
                    break

        # If still not found, treat as literal package name or guess com.<name>
        if not package:
            package = raw if "." in raw else f"com.{clean}"

        if not IS_TERMUX:
            return ToolExecutionResult(
                success=True,
                output=f"[Simulator] Launched Android application: '{app_name}' (Package: {package})",
                error=None,
                duration_ms=0,
            )

        # Universal Camera Intent Fallback for OnePlus/Samsung/Pixel
        if clean in ("camera", "cam"):
            cam_intent = SecureCommandExecutor.run(["am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA"], timeout=5)
            if not cam_intent.startswith("Error"):
                return ToolExecutionResult(success=True, output="Successfully launched Device Camera", error=None, duration_ms=0)
            # Try alternate OEM camera packages
            for oem_pkg in ("com.oneplus.camera", "com.oplus.camera", "com.google.android.GoogleCamera", "com.sec.android.app.camera"):
                res_oem = SecureCommandExecutor.run(["monkey", "-p", oem_pkg, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"], timeout=5)
                if not res_oem.startswith("Error") and "No activities found" not in res_oem:
                    return ToolExecutionResult(success=True, output=f"Successfully launched Camera ({oem_pkg})", error=None, duration_ms=0)

        # Launch via monkey launcher
        cmd = ["monkey", "-p", package, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"]
        res = SecureCommandExecutor.run(cmd, timeout=5)

        if "No activities found to run" in res or res.startswith("Error"):
            # Try am start intent fallback
            am_cmd = ["am", "start", "-p", package]
            am_res = SecureCommandExecutor.run(am_cmd, timeout=5)
            if am_res.startswith("Error"):
                return ToolExecutionResult(
                    success=False,
                    output=None,
                    error=f"Could not launch app '{app_name}' with package '{package}': {am_res}",
                    duration_ms=0,
                )

        return ToolExecutionResult(
            success=True,
            output=f"Successfully launched '{app_name}' (Package: {package})",
            error=None,
            duration_ms=0,
        )
