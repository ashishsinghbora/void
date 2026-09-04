"""
tools/system.py - System & Environment Strategy Implementations.

Handles system notifications, toast popups, clipboard management, GPS location,
network status, app launching, and biometric authentication.
"""

import os
import json
import shutil
from typing import Any, Dict, List

from core.types import ToolExecutionResult
from core.command_executor import SecureCommandExecutor
from security.sanitizer import InputSanitizer
from tools.base import ToolStrategy


class ShowToastStrategy(ToolStrategy):
    """Displays a brief toast popup on the screen."""

    def __init__(self):
        super().__init__(
            name="show_toast",
            description="Display a brief toast notification popup on the phone screen.",
            schema={
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Toast message text"}},
                "required": ["message"],
            },
        )

    def execute(self, message: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_msg = InputSanitizer.sanitize_string(message, max_length=200)
        res = SecureCommandExecutor.run(["termux-toast", clean_msg])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class ShowNotificationStrategy(ToolStrategy):
    """Displays a system notification drawer alert."""

    def __init__(self):
        super().__init__(
            name="show_notification",
            description="Display a system notification drawer popup with a title and message content.",
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Notification title"},
                    "content": {"type": "string", "description": "Notification body content"},
                },
                "required": ["title", "content"],
            },
        )

    def execute(self, title: str = "Void Alert", content: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_title = InputSanitizer.sanitize_string(title, max_length=100)
        clean_content = InputSanitizer.sanitize_string(content, max_length=500)
        res = SecureCommandExecutor.run(["termux-notification", "--title", clean_title, "--content", clean_content])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class SetClipboardStrategy(ToolStrategy):
    """Copies text to the Android clipboard."""

    def __init__(self):
        super().__init__(
            name="set_clipboard",
            description="Copy a text string to the device's system clipboard.",
            schema={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Text to place on clipboard"}},
                "required": ["text"],
            },
        )

    def execute(self, text: str = "", **kwargs: Any) -> ToolExecutionResult:
        clean_text = InputSanitizer.sanitize_string(text, max_length=8192)
        res = SecureCommandExecutor.run(["termux-clipboard-set", clean_text])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=f"Copied to clipboard: '{clean_text}'" if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class GetClipboardStrategy(ToolStrategy):
    """Retrieves current text from the Android clipboard."""

    def __init__(self):
        super().__init__(
            name="get_clipboard",
            description="Retrieve the current text stored in the device's system clipboard.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-clipboard-get"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class GetLocationStrategy(ToolStrategy):
    """Retrieves device GPS location coordinates."""

    def __init__(self):
        super().__init__(
            name="get_location",
            description="Retrieve the device's current GPS location coordinates (latitude, longitude, altitude).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-location", "-p", "network", "-r", "last"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class GetWifiInfoStrategy(ToolStrategy):
    """Retrieves active Wi-Fi connection details."""

    def __init__(self):
        super().__init__(
            name="get_wifi_info",
            description="Retrieve details about the active Wi-Fi connection (SSID, IP address, speed, strength).",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-wifi-connectioninfo"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class ScanWifiNetworksStrategy(ToolStrategy):
    """Scans and retrieves list of nearby Wi-Fi SSIDs and signal strengths."""

    def __init__(self):
        super().__init__(
            name="scan_wifi_networks",
            description="Scan and retrieve a list of nearby Wi-Fi networks and their signal strengths.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-wifi-scaninfo"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class DownloadFileStrategy(ToolStrategy):
    """Downloads a file using the Android system download manager."""

    def __init__(self):
        super().__init__(
            name="download_file",
            description="Download a file from a URL using the system's download manager.",
            schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target download URL"},
                    "title": {"type": "string", "description": "Download title notification"},
                },
                "required": ["url"],
            },
        )

    def execute(self, url: str = "", title: str = "Download", **kwargs: Any) -> ToolExecutionResult:
        clean_url = InputSanitizer.validate_url(url)
        clean_title = InputSanitizer.sanitize_string(title, max_length=64)
        res = SecureCommandExecutor.run(["termux-download", "-t", clean_title, clean_url])
        success = not res.startswith("Error")
        return ToolExecutionResult(
            success=success,
            output=res if success else None,
            error=res if not success else None,
            duration_ms=0,
        )


class AuthenticateFingerprintStrategy(ToolStrategy):
    """Prompts for biometric fingerprint authentication."""

    def __init__(self):
        super().__init__(
            name="authenticate_fingerprint",
            description="Prompt for fingerprint authentication on the device to verify user identity.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        res = SecureCommandExecutor.run(["termux-fingerprint"])
        if res.startswith("Error"):
            return ToolExecutionResult(success=False, output=None, error=res, duration_ms=0)
        try:
            return ToolExecutionResult(success=True, output=json.loads(res), error=None, duration_ms=0)
        except Exception:
            return ToolExecutionResult(success=True, output=res, error=None, duration_ms=0)


class OpenAppStrategy(ToolStrategy):
    """Launches an application package, activity, or URL intent."""

    APP_URLS = {
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "whatsapp": "https://api.whatsapp.com",
        "wa": "https://api.whatsapp.com",
        "chrome": "http://google.com",
        "google": "http://google.com",
        "browser": "http://google.com",
        "instagram": "https://instagram.com",
        "insta": "https://instagram.com",
        "spotify": "https://open.spotify.com",
        "telegram": "https://t.me",
        "facebook": "https://facebook.com",
        "fb": "https://facebook.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "gmail": "mailto:",
        "maps": "https://maps.google.com",
        "google maps": "https://maps.google.com",
    }

    APP_PACKAGES = {
        "youtube": "com.google.android.youtube",
        "whatsapp": "com.whatsapp",
        "chrome": "com.android.chrome",
        "instagram": "com.instagram.android",
        "spotify": "com.spotify.music",
        "telegram": "org.telegram.messenger",
        "facebook": "com.facebook.katana",
        "gmail": "com.google.android.gm",
        "maps": "com.google.android.apps.maps",
        "settings": "com.android.settings",
        "calculator": "com.google.android.calculator",
        "camera": "com.android.camera",
    }

    def __init__(self):
        super().__init__(
            name="open_app",
            description="Open an application on the phone screen (e.g. 'whatsapp', 'youtube', 'chrome', 'spotify', 'maps', 'settings').",
            schema={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "Name of app or target URL"}},
                "required": ["app_name"],
            },
        )

    def execute(self, app_name: str = "", **kwargs: Any) -> ToolExecutionResult:
        raw = InputSanitizer.sanitize_string(app_name, max_length=128).lower()
        clean = raw.replace("open", "").replace("the", "").replace("app", "").strip()

        if raw.startswith("http://") or raw.startswith("https://"):
            SecureCommandExecutor.run(["termux-open", raw])
            return ToolExecutionResult(success=True, output=f"Opened URL '{raw}'", error=None, duration_ms=0)

        target_key = None
        for k in (clean, raw):
            if k in self.APP_PACKAGES or k in self.APP_URLS:
                target_key = k
                break

        if not target_key:
            for k in self.APP_PACKAGES:
                if k in clean or clean in k:
                    target_key = k
                    break

        if target_key:
            if target_key in self.APP_PACKAGES:
                pkg = self.APP_PACKAGES[target_key]
                SecureCommandExecutor.run(["monkey", "-p", pkg, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"])
            elif target_key in self.APP_URLS:
                url = self.APP_URLS[target_key]
                SecureCommandExecutor.run(["termux-open", url])
            return ToolExecutionResult(success=True, output=f"Successfully opened {app_name}", error=None, duration_ms=0)

        # Fallback launcher
        pkg_name = raw if "." in raw else f"com.{raw}"
        SecureCommandExecutor.run(["monkey", "-p", pkg_name, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"])
        return ToolExecutionResult(success=True, output=f"Attempted opening '{app_name}'", error=None, duration_ms=0)


class CleanStorageStrategy(ToolStrategy):
    """Safely cleans temporary cache files, orphaned bytecodes, and stale logs."""

    PROTECTED_PATTERNS = {
        ".void_agent.db",
        ".void_vault.enc",
        "requirements.txt",
        "README.md",
        "app.py",
        "termux_void.py",
        ".git",
    }

    def __init__(self):
        super().__init__(
            name="clean_system",
            description="Scan and clean temporary cache files, .pyc bytecodes, and stale logs to reclaim storage. Supports dry_run mode.",
            schema={
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "description": "If true, simulates cleanup without deleting files (default: true)"},
                    "target_scope": {"type": "string", "description": "Cleanup scope: 'pycache', 'cache', 'temp', or 'all' (default: 'all')"},
                },
            },
        )

    def execute(self, dry_run: bool = True, target_scope: str = "all", **kwargs: Any) -> ToolExecutionResult:
        scope = InputSanitizer.sanitize_string(target_scope, max_length=16).lower() or "all"
        is_dry_run = bool(dry_run)

        home_dir = os.path.expanduser("~")
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        scan_roots = [project_dir]
        cache_dir = os.path.join(home_dir, ".cache")
        if os.path.isdir(cache_dir):
            scan_roots.append(cache_dir)

        termux_cache = "/data/data/com.termux/cache"
        if os.path.isdir(termux_cache):
            scan_roots.append(termux_cache)

        candidates_to_delete: List[str] = []
        directories_to_remove: List[str] = []
        bytes_reclaimed = 0

        for root_dir in scan_roots:
            if not os.path.exists(root_dir):
                continue

            for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
                if ".git" in dirnames:
                    dirnames.remove(".git")
                if "venv" in dirnames:
                    dirnames.remove("venv")
                if ".venv" in dirnames:
                    dirnames.remove(".venv")

                if scope in ("pycache", "all"):
                    if os.path.basename(dirpath) == "__pycache__":
                        directories_to_remove.append(dirpath)
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            try:
                                bytes_reclaimed += os.path.getsize(fp)
                            except OSError:
                                pass
                        continue

                if scope in ("temp", "all"):
                    for f in filenames:
                        if f in self.PROTECTED_PATTERNS:
                            continue
                        if f.endswith((".tmp", ".bak", ".swp", ".pyc", ".pyo")):
                            fp = os.path.join(dirpath, f)
                            candidates_to_delete.append(fp)
                            try:
                                bytes_reclaimed += os.path.getsize(fp)
                            except OSError:
                                pass

        if not is_dry_run:
            for fpath in candidates_to_delete:
                try:
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except OSError:
                    pass

            for dpath in directories_to_remove:
                try:
                    if os.path.isdir(dpath):
                        shutil.rmtree(dpath, ignore_errors=True)
                except OSError:
                    pass

        reclaimed_mb = round(bytes_reclaimed / (1024.0 * 1024.0), 3)
        summary = (
            f"Storage cleanup completed ({'DRY RUN' if is_dry_run else 'EXECUTED'}): "
            f"{len(candidates_to_delete)} temporary files, {len(directories_to_remove)} cache dirs identified. "
            f"Reclaimed: {reclaimed_mb} MB ({bytes_reclaimed} bytes)."
        )

        return ToolExecutionResult(
            success=True,
            output={
                "dry_run": is_dry_run,
                "scope": scope,
                "files_count": len(candidates_to_delete),
                "dirs_count": len(directories_to_remove),
                "bytes_reclaimed": bytes_reclaimed,
                "reclaimed_mb": reclaimed_mb,
                "summary": summary,
            },
            error=None,
            duration_ms=0,
        )
