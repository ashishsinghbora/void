"""
core/simulator.py - High-Fidelity Hardware Simulator for Desktop Hosts.

Provides realistic mock responses for Termux hardware and telephony APIs
when running on developer workstations (Linux/macOS/Windows) outside Android.
"""

import json
from typing import List, Dict, Any


class TermuxHardwareSimulator:
    """Simulates Android hardware endpoints without native Termux dependencies."""

    @staticmethod
    def is_simulator_applicable(binary_name: str) -> bool:
        """Determines if a command binary is a recognized Termux API command."""
        return binary_name.startswith("termux-") or binary_name in ("monkey", "am")

    @classmethod
    def simulate(cls, args: List[str]) -> str:
        """Dispatches command to simulated hardware handler."""
        cmd = args[0]

        if cmd == "termux-battery-status":
            return json.dumps({
                "health": "GOOD",
                "percentage": 88,
                "plugged": "UNPLUGGED",
                "status": "DISCHARGING",
                "temperature": 29.4,
                "current": -210,
            })

        if cmd == "termux-toast":
            msg = args[1] if len(args) > 1 else ""
            return f"[Simulated Toast] Displayed popup: '{msg}'"

        if cmd == "termux-notification":
            title = "System Alert"
            content = "Alert triggered."
            for i in range(len(args) - 1):
                if args[i] == "--title":
                    title = args[i + 1]
                elif args[i] == "--content":
                    content = args[i + 1]
            return f"[Simulated Notification] Sent alert - Title: '{title}', Content: '{content}'"

        if cmd == "termux-tts-speak":
            text = args[1] if len(args) > 1 else ""
            return f"[Simulated Text-To-Speech] Spoke aloud: '{text}'"

        if cmd == "termux-clipboard-set":
            text = args[1] if len(args) > 1 else ""
            return f"[Simulated Clipboard] Copied to clipboard: '{text}'"

        if cmd == "termux-clipboard-get":
            return "Simulated clipboard payload: Hello from Void Agentic Core."

        if cmd == "termux-vibrate":
            dur = "500"
            for i in range(len(args) - 1):
                if args[i] == "-d":
                    dur = args[i + 1]
            return f"[Simulated Haptic] Vibrated device for {dur}ms"

        if cmd == "termux-torch":
            state = args[1] if len(args) > 1 else "off"
            return f"[Simulated Hardware] Flashlight switched {state.upper()}"

        if cmd == "termux-location":
            return json.dumps({
                "latitude": 37.7749,
                "longitude": -122.4194,
                "altitude": 18.2,
                "accuracy": 15.0,
                "provider": "gps",
            })

        if cmd == "termux-sms-send":
            recipient = args[args.index("-n") + 1] if "-n" in args else "Unknown"
            msg = args[-1] if len(args) > 1 else ""
            return f"[Simulated Network] SMS Sent to {recipient} containing: '{msg}'"

        if cmd == "termux-telephony-call":
            num = args[1] if len(args) > 1 else ""
            return f"[Simulated Dial] Dialed voice connection call to: {num}"

        if cmd == "termux-wifi-connectioninfo":
            return json.dumps({
                "ssid": "Termux_Agent_Secure_5G",
                "ip": "192.168.1.108",
                "link_speed_mbps": 866,
                "rssi": -48,
                "supplicant_state": "COMPLETED",
            })

        if cmd == "termux-camera-photo":
            filename = args[-1] if len(args) > 1 else "void_photo.jpg"
            return f"[Simulated Camera] Photo captured and saved to: {filename}"

        if cmd == "termux-sms-list":
            return json.dumps([
                {"address": "+1234567890", "body": "Void engine initialized.", "date": "2026-09-04 12:00:00", "read": True, "type": "inbox"},
                {"address": "AUTH-ALERT", "body": "Your verification code is 829410.", "date": "2026-09-04 11:45:00", "read": False, "type": "inbox"},
                {"address": "SPAM-PROMO", "body": "Win $1000 today click here now!", "date": "2026-09-04 10:00:00", "read": False, "type": "inbox"},
            ])

        if cmd == "termux-contact-list":
            return json.dumps([
                {"name": "Alice Smith", "number": "+1987654321"},
                {"name": "Bob Jones", "number": "+15550199"},
                {"name": "Security Team", "number": "+18005550100"},
            ])

        if cmd == "termux-download":
            url = args[-1] if len(args) > 1 else ""
            return f"[Simulated Download] Downloading URL: {url}"

        if cmd == "termux-brightness":
            val = args[1] if len(args) > 1 else "128"
            return f"[Simulated Screen] Set screen brightness to {val}"

        if cmd == "termux-volume":
            if len(args) > 2:
                stream = args[1]
                volume = args[2]
                return f"[Simulated Audio] Set volume stream '{stream}' to {volume}"
            else:
                return json.dumps([
                    {"stream": "music", "volume": 11, "max_volume": 15},
                    {"stream": "ring", "volume": 5, "max_volume": 7},
                    {"stream": "alarm", "volume": 6, "max_volume": 7},
                    {"stream": "notification", "volume": 5, "max_volume": 7},
                    {"stream": "system", "volume": 7, "max_volume": 7},
                    {"stream": "call", "volume": 4, "max_volume": 5},
                ])

        if cmd == "termux-share":
            target = args[-1] if len(args) > 1 else "content"
            return f"[Simulated Share] Shared content via system share sheet: '{target}'"

        if cmd == "termux-call-log":
            return json.dumps([
                {"name": "Alice Smith", "number": "+1987654321", "duration": "2m 14s", "date": "2026-09-04 10:15:22", "type": "incoming"},
                {"name": "John Doe", "number": "+14155552671", "duration": "0s", "date": "2026-09-03 18:44:10", "type": "missed"},
            ])

        if cmd == "termux-fingerprint":
            return json.dumps({"auth_result": "AUTH_SUCCESS", "errors": None})

        if cmd == "termux-microphone-record":
            if "-q" in args:
                return "[Simulated Recording] Microphone recording stopped and saved."
            return "[Simulated Recording] Microphone recording started into 'recording.3gp'"

        if cmd == "termux-telephony-deviceinfo":
            return json.dumps({
                "data_activity": "DATA_ACTIVITY_NONE",
                "data_state": "DATA_CONNECTED",
                "device_id": "864209753197531",
                "device_software_version": "01",
                "network_operator": "Google Fi",
                "network_operator_name": "Google Fi",
                "network_type": "LTE",
                "phone_type": "PHONE_TYPE_GSM",
                "sim_country_iso": "us",
                "sim_operator": "310260",
                "sim_operator_name": "Google Fi",
                "sim_state": "SIM_STATE_READY",
            })

        if cmd == "termux-wifi-scaninfo":
            return json.dumps([
                {"bssid": "aa:bb:cc:dd:ee:ff", "frequency_mhz": 5240, "rssi": -55, "ssid": "Home-Network_5G"},
                {"bssid": "11:22:33:44:55:66", "frequency_mhz": 2412, "rssi": -72, "ssid": "Cafe_Free_Wifi"},
            ])

        if cmd == "termux-notification-list":
            return json.dumps([
                {
                    "id": "1001",
                    "tag": "sms",
                    "packageName": "com.google.android.apps.messaging",
                    "title": "Bank Security",
                    "content": "Your login OTP is 482910. Do not share this code.",
                    "when": "2026-09-04 12:30:00",
                },
                {
                    "id": "1002",
                    "tag": "promo",
                    "packageName": "com.spam.marketing",
                    "title": "Limited Deal!",
                    "content": "Claim 50% discount on shoes right now!",
                    "when": "2026-09-04 12:28:00",
                },
            ])

        if cmd == "termux-notification-remove":
            notif_id = args[1] if len(args) > 1 else ""
            return f"[Simulated Action] Removed notification with ID {notif_id}"

        if cmd == "termux-open":
            target = args[1] if len(args) > 1 else ""
            return f"[Simulated Intent] Opened URL/App: '{target}'"

        if cmd == "termux-wake-lock":
            return "[Simulated Power] Acquired CPU wake lock (background execution sustained)."

        if cmd == "termux-wake-unlock":
            return "[Simulated Power] Released CPU wake lock."

        if cmd == "termux-setup-storage":
            return "[Simulated Storage] Storage permissions linked to ~/storage."

        if cmd in ("monkey", "am"):
            return f"[Simulated Android Intent] Dispatched {' '.join(args)}"

        return f"[Simulated Execution] {' '.join(args)}"

