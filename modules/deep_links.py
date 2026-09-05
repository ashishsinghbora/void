"""
modules/deep_links.py - Android Deep-Link & Intent Automation Engine.

Dispatches direct URI schemes and Android intents via `am start` across:
- Instant Payments & UPI (Google Pay, PhonePe, Paytm, standard UPI)
- Messaging & Social (WhatsApp, Telegram, Signal, SMS)
- Ride-Hailing & Navigation (Google Maps turn-by-turn, Uber, Ola)
- Media & Deep In-App Searches (YouTube, Spotify)
- Native Android System Settings Intents
"""

import urllib.parse
import logging
from typing import Dict, Any, Optional

from core.command_executor import SecureCommandExecutor, IS_TERMUX
from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidModules.DeepLinks")


class DeepLinkEngine:
    """Enterprise-grade deep-link generator and Android intent dispatcher."""

    @staticmethod
    def dispatch_uri(uri: str, package: Optional[str] = None, action: str = "android.intent.action.VIEW") -> Dict[str, Any]:
        """
        Launches an Android deep link or intent URI.
        Attempts `am start` first, falling back cleanly to `termux-open`.
        """
        if not uri or not uri.strip():
            return {"success": False, "error": "Empty URI provided."}

        clean_uri = uri.strip()
        logger.info(f"Dispatching intent URI: {clean_uri[:60]}... (Package: {package or 'auto'})")

        if not IS_TERMUX:
            return {
                "success": True,
                "simulator": True,
                "uri": clean_uri,
                "message": f"[Simulator] Dispatched intent to '{clean_uri}'",
            }

        # 1. Try am start intent vector
        cmd = ["am", "start", "-a", action, "-d", clean_uri]
        if package:
            cmd.extend(["-p", package])

        res = SecureCommandExecutor.run(cmd, timeout=5)
        if not res.startswith("Error") and "Activity not started" not in res:
            return {"success": True, "method": "am_start", "output": res}

        # 2. Fallback to termux-open
        t_res = SecureCommandExecutor.run(["termux-open", clean_uri], timeout=5)
        success = not t_res.startswith("Error")
        return {
            "success": success,
            "method": "termux-open",
            "output": t_res if success else None,
            "error": t_res if not success else None,
        }

    # ------------------------------------------------------------------
    # 1. Payments & UPI Automation
    # ------------------------------------------------------------------
    @classmethod
    def pay_upi(
        cls,
        payee_vpa: str,
        payee_name: str,
        amount: Optional[float] = None,
        note: str = "Payment via Void AI",
        preferred_app: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates standard Indian NPCI UPI deep-link (upi://pay) and launches payment app.
        Supported packages: 'gpay', 'phonepe', 'paytm', or any system default UPI handler.
        """
        params = {
            "pa": payee_vpa.strip(),
            "pn": payee_name.strip(),
            "tn": note.strip(),
            "cu": "INR",
        }
        if amount and amount > 0:
            params["am"] = f"{amount:.2f}"

        query_str = urllib.parse.urlencode(params)
        upi_uri = f"upi://pay?{query_str}"

        pkg_map = {
            "gpay": "com.google.android.apps.nbu.paisa.user",
            "googlepay": "com.google.android.apps.nbu.paisa.user",
            "phonepe": "com.phonepe.app",
            "paytm": "net.one97.paytm",
        }
        pkg = pkg_map.get((preferred_app or "").lower())
        return cls.dispatch_uri(upi_uri, package=pkg)

    # ------------------------------------------------------------------
    # 2. Messaging & Social Automation
    # ------------------------------------------------------------------
    @classmethod
    def send_whatsapp_message(cls, phone_number: str, message: str) -> Dict[str, Any]:
        """Deep-links directly into a WhatsApp 1-on-1 chat with pre-filled message."""
        clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
        encoded_text = urllib.parse.quote(message)
        wa_uri = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"
        return cls.dispatch_uri(wa_uri, package="com.whatsapp")

    @classmethod
    def open_telegram_profile(cls, username_or_id: str) -> Dict[str, Any]:
        """Deep-links to a Telegram channel, group, or user profile."""
        clean_user = username_or_id.replace("@", "").strip()
        tg_uri = f"tg://resolve?domain={clean_user}"
        return cls.dispatch_uri(tg_uri, package="org.telegram.messenger")

    # ------------------------------------------------------------------
    # 3. Ride-Hailing & Navigation Automation
    # ------------------------------------------------------------------
    @classmethod
    def navigate_google_maps(cls, query_or_coords: str, mode: str = "d") -> Dict[str, Any]:
        """
        Launches Google Maps in direct turn-by-turn navigation mode.
        Modes: 'd' (driving), 'w' (walking), 'b' (bicycling).
        """
        encoded_dest = urllib.parse.quote(query_or_coords)
        nav_uri = f"google.navigation:q={encoded_dest}&mode={mode}"
        return cls.dispatch_uri(nav_uri, package="com.google.android.apps.maps")

    @classmethod
    def book_uber(cls, dropoff_address: str) -> Dict[str, Any]:
        """Deep-links into Uber ride selection with destination pre-populated."""
        encoded_dropoff = urllib.parse.quote(dropoff_address)
        uber_uri = f"uber://?action=setPickup&pickup=my_location&dropoff[formatted_address]={encoded_dropoff}"
        return cls.dispatch_uri(uber_uri, package="com.ubercab")

    # ------------------------------------------------------------------
    # 4. Media & In-App Search Automation
    # ------------------------------------------------------------------
    @classmethod
    def search_youtube(cls, search_query: str) -> Dict[str, Any]:
        """Launches YouTube directly with search query results displayed."""
        encoded_query = urllib.parse.quote(search_query)
        yt_uri = f"https://www.youtube.com/results?search_query={encoded_query}"
        return cls.dispatch_uri(yt_uri, package="com.google.android.youtube")

    @classmethod
    def search_spotify(cls, track_or_artist: str) -> Dict[str, Any]:
        """Deep-links into Spotify search results for requested track or artist."""
        encoded_q = urllib.parse.quote(track_or_artist)
        spotify_uri = f"spotify:search:{encoded_q}"
        return cls.dispatch_uri(spotify_uri, package="com.spotify.music")

    # ------------------------------------------------------------------
    # 5. Deep Android System Settings Intents
    # ------------------------------------------------------------------
    @classmethod
    def open_settings_intent(cls, setting_name: str) -> Dict[str, Any]:
        """Dispatches direct Android system settings activities."""
        settings_map = {
            "wifi": "android.settings.WIFI_SETTINGS",
            "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
            "battery": "android.settings.BATTERY_SAVER_SETTINGS",
            "display": "android.settings.DISPLAY_SETTINGS",
            "apps": "android.settings.APPLICATION_SETTINGS",
            "location": "android.settings.LOCATION_SOURCE_SETTINGS",
            "sound": "android.settings.SOUND_SETTINGS",
            "accessibility": "android.settings.ACCESSIBILITY_SETTINGS",
            "security": "android.settings.SECURITY_SETTINGS",
            "main": "android.settings.SETTINGS",
        }
        action = settings_map.get(setting_name.lower().strip(), "android.settings.SETTINGS")
        cmd = ["am", "start", "-a", action]
        res = SecureCommandExecutor.run(cmd, timeout=5)
        success = not res.startswith("Error")
        return {"success": success, "setting": setting_name, "action": action, "output": res}

    # Alias for API ergonomics
    open_settings = open_settings_intent


global_deep_links = DeepLinkEngine()
