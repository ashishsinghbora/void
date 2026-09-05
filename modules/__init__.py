"""
modules - Advanced Autonomous Mobile Agent Capabilities.

Modules:
- vision_agent: Multimodal screen grounding & app-agnostic dynamic UI navigation
- notification_watcher: Continuous background listener with banking OTP extraction & forwarding
- voice_handler: Voice note transcription (Whisper tiny) & call-screening surrogate
- deep_links: Android intents for payments (UPI/GPay/PhonePe), messaging, ride-hailing & settings
- scraper_vault: Autonomous web monitoring, price drop alerts & Cloud Vault sync
"""

from modules.vision_agent import VisionAgent, global_vision_agent, UIElement, ScreenFrame
from modules.notification_watcher import NotificationWatcher, global_notification_watcher, OTPRegexEngine, ExtractedOTP
from modules.voice_handler import VoiceHandler, global_voice_handler
from modules.deep_links import DeepLinkEngine, global_deep_links
from modules.scraper_vault import ScraperVaultService, global_scraper_vault

__all__ = [
    "VisionAgent",
    "global_vision_agent",
    "UIElement",
    "ScreenFrame",
    "NotificationWatcher",
    "global_notification_watcher",
    "OTPRegexEngine",
    "ExtractedOTP",
    "VoiceHandler",
    "global_voice_handler",
    "DeepLinkEngine",
    "global_deep_links",
    "ScraperVaultService",
    "global_scraper_vault",
]
