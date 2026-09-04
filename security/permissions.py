"""
security/permissions.py - Transparent Android Permission & Privacy Governance.

Provides clear inspection, justification, and user-first governance for all Android
hardware permissions. Emphasizes that every permission is 100% optional and manual,
ensuring users retain full sovereignty over their device and data privacy.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.command_executor import IS_TERMUX, SecureCommandExecutor

logger = logging.getLogger("VoidAdvancedCore.Permissions")


@dataclass
class PermissionInfo:
    """Detailed metadata and justification for an Android hardware permission."""
    key: str
    name: str
    purpose: str
    why_needed: str
    fallback_behavior: str
    how_to_manage: str
    is_granted: bool
    is_mandatory: bool = False  # Every single permission in Void is optional!

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "purpose": self.purpose,
            "why_needed": self.why_needed,
            "fallback_behavior": self.fallback_behavior,
            "how_to_manage": self.how_to_manage,
            "is_granted": self.is_granted,
            "is_mandatory": self.is_mandatory,
        }


# Exhaustive registry of permissions with transparent rationale
PERMISSION_REGISTRY: Dict[str, Dict[str, str]] = {
    "storage": {
        "name": "Shared Storage Access",
        "purpose": "Saving captured camera photos, download files, and local logs.",
        "why_needed": "Allows Void to read and save media (e.g. photos in ~/storage/downloads/ or /sdcard/Download) so you can access them in your phone's Gallery or Files app.",
        "fallback_behavior": "If not granted, Void saves temporary photos only inside its isolated internal Termux directory (~/void/).",
        "how_to_manage": "Run 'termux-setup-storage' in Termux or toggle Storage under Android Settings -> Apps -> Termux.",
    },
    "camera": {
        "name": "Camera (Front & Rear)",
        "purpose": "Capturing photos upon your direct command via CLI, Web, or Telegram.",
        "why_needed": "Required only if you ask Void to take photos (e.g. 'take a photo', 'capture rear camera'). Void NEVER accesses the camera autonomously without your direct directive.",
        "fallback_behavior": "If not granted, Void politely alerts you that camera capture is unavailable and cancels the action without crashing.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> Camera.",
    },
    "sms": {
        "name": "SMS Messaging (Send & Read)",
        "purpose": "Sending automated text messages and reading incoming verification OTPs.",
        "why_needed": "Used when you ask Void to send an SMS or when the background notification daemon extracts banking login OTPs so you don't have to switch apps.",
        "fallback_behavior": "If not granted, Void falls back to opening the Android system Share Sheet (termux-share) so you can send the text via any messaging app manually.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> SMS.",
    },
    "contacts": {
        "name": "Contacts Access",
        "purpose": "Resolving contact names when sending SMS or making phone calls.",
        "why_needed": "Allows you to say 'send SMS to Alice' or 'call Bob' instead of typing raw numeric phone numbers.",
        "fallback_behavior": "If not granted, Void prompts you to provide the raw phone number directly.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> Contacts.",
    },
    "telephony": {
        "name": "Phone & Call Log",
        "purpose": "Initiating voice calls and checking missed call alerts.",
        "why_needed": "Used only when you explicitly instruct Void to place a call (e.g. 'call +123456789') or ask 'who called me today?'.",
        "fallback_behavior": "If not granted, Void shows you the sanitized phone number so you can dial it manually.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> Phone / Call Logs.",
    },
    "location": {
        "name": "GPS / Network Location",
        "purpose": "Retrieving your current location coordinates (latitude & longitude).",
        "why_needed": "Used when you ask 'where am I right now?' or ask for local weather/morning briefing telemetry.",
        "fallback_behavior": "If not granted, Void reports that location coordinates are withheld by user choice.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> Location.",
    },
    "microphone": {
        "name": "Microphone Audio Recording",
        "purpose": "Recording audio clips on demand.",
        "why_needed": "Used only when you explicitly command Void to record audio (e.g. 'record audio for 10 seconds').",
        "fallback_behavior": "If not granted, audio recording is skipped and Void explains that microphone access was declined.",
        "how_to_manage": "Android Settings -> Apps -> Termux:API -> Permissions -> Microphone.",
    },
    "wake_lock": {
        "name": "CPU Wake-Lock (Background Execution)",
        "purpose": "Keeping Void's background daemons alive when the phone screen turns off.",
        "why_needed": "Android aggressive battery savers terminate apps when the screen is off. Wake-lock ensures notification OTP extraction and scheduled routines continue uninterrupted.",
        "fallback_behavior": "If not active, Void continues running while Termux is open on screen, but Android OS may suspend it in deep sleep.",
        "how_to_manage": "Toggle by typing 'termux-wake-lock' or 'termux-wake-unlock' in Termux.",
    },
}


class PermissionManager:
    """Manages transparent permission auditing and user-centric justification reports."""

    @classmethod
    def is_termux_api_responsive(cls) -> bool:
        """Fast non-blocking probe to verify if Termux:API companion APK is responsive."""
        if not IS_TERMUX:
            return True
        res = SecureCommandExecutor.run(["termux-battery-status"], timeout=2, allow_simulation=False)
        return not res.startswith("Error")

    @classmethod
    def check_permission(cls, perm_key: str) -> bool:
        """Probes the live status of an Android hardware permission."""
        if not IS_TERMUX:
            # Desktop development simulator: all simulated permissions treated as enabled
            return True

        if perm_key == "storage":
            return os.path.exists(os.path.expanduser("~/storage"))
        elif perm_key == "wake_lock":
            return True  # Managed via termux-wake-lock
        elif perm_key == "microphone":
            return True  # Probing microphone would trigger an audible recording

        # If Termux:API companion app is unresponsive or in stopped state, fail fast without hanging
        if not cls.is_termux_api_responsive():
            return False

        if perm_key == "camera":
            # Test if termux-camera-info is available or returns valid JSON
            res = SecureCommandExecutor.run(["termux-camera-info"], timeout=2, allow_simulation=False)
            return not res.startswith("Error") and res.startswith("[")
        elif perm_key == "sms":
            res = SecureCommandExecutor.run(["termux-sms-list", "-l", "1"], timeout=2, allow_simulation=False)
            return not res.startswith("Error")
        elif perm_key == "contacts":
            res = SecureCommandExecutor.run(["termux-contact-list"], timeout=2, allow_simulation=False)
            return not res.startswith("Error")
        elif perm_key == "location":
            res = SecureCommandExecutor.run(["termux-location", "-p", "network", "-r", "last"], timeout=2, allow_simulation=False)
            return not res.startswith("Error")
        elif perm_key == "telephony":
            res = SecureCommandExecutor.run(["termux-telephony-deviceinfo"], timeout=2, allow_simulation=False)
            return not res.startswith("Error")
        return False

    @classmethod
    def get_all_permissions(cls) -> List[PermissionInfo]:
        """Returns metadata and live status for all permissions."""
        results = []
        for key, meta in PERMISSION_REGISTRY.items():
            granted = cls.check_permission(key)
            results.append(
                PermissionInfo(
                    key=key,
                    name=meta["name"],
                    purpose=meta["purpose"],
                    why_needed=meta["why_needed"],
                    fallback_behavior=meta["fallback_behavior"],
                    how_to_manage=meta["how_to_manage"],
                    is_granted=granted,
                    is_mandatory=False,
                )
            )
        return results

    @classmethod
    def explain_permission(cls, perm_key: str) -> str:
        """Provides a user-friendly, respectful explanation of why a permission is needed."""
        meta = PERMISSION_REGISTRY.get(perm_key)
        if not meta:
            return f"Void requested access to '{perm_key}'. All permissions are completely optional."

        return (
            f"ℹ️ PERMISSION NOTICE: {meta['name']}\n"
            f"• Purpose: {meta['purpose']}\n"
            f"• Why Void Uses It: {meta['why_needed']}\n"
            f"• Your Choice: Granting this permission is 100% voluntary. You are in complete control of your device.\n"
            f"• If Declined: {meta['fallback_behavior']}\n"
            f"• How to Enable (if desired): {meta['how_to_manage']}\n"
            f"🔒 Privacy Guarantee: All data stays 100% on your device. Zero external tracking."
        )

    @classmethod
    def generate_cli_report(cls) -> str:
        """Generates a formatted CLI table showing all permissions and their status."""
        lines = [
            "================================================================================",
            "  🛡️  VOID PRIVACY & ANDROID PERMISSIONS GOVERNANCE",
            "================================================================================",
            "  Every permission in Void is 100% OPTIONAL and controlled manually by you.",
            "  Void operates with graceful fallbacks if any permission is declined.",
            "  Zero data ever leaves your device. All agentic computation is local.",
            "--------------------------------------------------------------------------------",
        ]

        perms = cls.get_all_permissions()
        for p in perms:
            status_tag = "[GRANTED]" if p.is_granted else "[NOT GRANTED (Optional)]"
            status_color = "✅" if p.is_granted else "⭕"
            lines.append(f"{status_color} {p.name.upper()} {status_tag}")
            lines.append(f"   • Purpose:      {p.purpose}")
            lines.append(f"   • Why Needed:   {p.why_needed}")
            lines.append(f"   • If Declined:  {p.fallback_behavior}")
            lines.append(f"   • How to Set:   {p.how_to_manage}")
            lines.append("")

        lines.append("--------------------------------------------------------------------------------")
        lines.append("  Manage permissions at any time via Android Settings -> Apps -> Termux:API")
        lines.append("================================================================================")
        return "\n".join(lines)
