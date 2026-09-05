"""
tests/test_advanced_modules.py - Comprehensive Unit & Integration Tests for Upgraded Modules.

Tests:
- Centralized configuration (config.settings)
- Async background supervisor (utils.async_runner)
- VisionAgent UI grounding & touch simulation (modules.vision_agent)
- NotificationWatcher & OTP Regex Engine (modules.notification_watcher)
- VoiceHandler voice transcription & call-screening (modules.voice_handler)
- DeepLinkEngine URI & intent generation (modules.deep_links)
- ScraperVaultService price tracking & vault mirroring (modules.scraper_vault)
- Advanced tool strategies registered in global_tool_registry
"""

import os
import time
import pytest
from unittest.mock import MagicMock, patch

from config.settings import VoidConfig, global_config
from utils.async_runner import AsyncSupervisor, global_async_supervisor
from modules.vision_agent import VisionAgent, UIElement, ScreenFrame, global_vision_agent
from modules.notification_watcher import NotificationWatcher, OTPRegexEngine, ExtractedOTP, global_notification_watcher
from modules.voice_handler import VoiceHandler, global_voice_handler
from modules.deep_links import DeepLinkEngine, global_deep_links
from modules.scraper_vault import ScraperVaultService, PriceWatchTarget, global_scraper_vault
from tools.registry import global_tool_registry
from agents.react_agent import AutonomousReActAgent
from core.types import AgentResponse


# ---------------------------------------------------------------------------
# 1. Config Settings Tests
# ---------------------------------------------------------------------------
def test_void_config_initialization(tmp_path):
    cfg_file = str(tmp_path / "test_config.env")
    cfg = VoidConfig(config_file=cfg_file)
    assert cfg.is_configured is False
    assert cfg.device_name == "Void-Edge-Node"
    assert cfg.vault_group_id is None

    cfg.update_credentials(token="123456:ABC-DEF", admin_id=987654321)
    assert cfg.is_configured is True
    assert cfg.telegram_token == "123456:ABC-DEF"
    assert 987654321 in cfg.admin_ids

    cfg.set_vault_group(-1001234567890)
    assert cfg.vault_group_id == -1001234567890
    assert os.path.exists(cfg_file)

    # Reload from disk
    cfg_reloaded = VoidConfig(config_file=cfg_file)
    assert cfg_reloaded.telegram_token == "123456:ABC-DEF"
    assert 987654321 in cfg_reloaded.admin_ids
    assert cfg_reloaded.vault_group_id == -1001234567890


# ---------------------------------------------------------------------------
# 2. Async Supervisor Tests
# ---------------------------------------------------------------------------
def test_async_supervisor_lifecycle():
    supervisor = AsyncSupervisor()
    assert supervisor.is_running is False

    supervisor.start()
    assert supervisor.is_running is True

    # Run a simple coroutine
    async def sample_coro():
        return 42

    fut = supervisor.schedule_coroutine(sample_coro())
    assert fut.result(timeout=2.0) == 42

    supervisor.stop()
    assert supervisor.is_running is False


# ---------------------------------------------------------------------------
# 3. Vision Agent Tests
# ---------------------------------------------------------------------------
def test_vision_ui_element_properties():
    elem = UIElement(
        element_id="btn_login",
        label="Log In",
        element_type="button",
        bbox=(100, 200, 300, 260),
        confidence=0.98,
    )
    assert elem.center == (200, 230)


def test_vision_agent_grounding_and_actions():
    agent = VisionAgent()
    agent.set_screen_dimensions(1080, 2400)

    # Ground elements from synthetic dump
    dump_text = (
        'android.widget.Button text="Submit Order" bounds="[100,200][400,300]"\n'
        'android.widget.EditText text="" hint="Search items" bounds="[50,100][800,180]"\n'
        'android.widget.TextView text="Cancel" bounds="[500,200][700,300]"\n'
    )
    elements = agent.ground_elements(dump_text)
    assert len(elements) == 3

    # Find element by query
    found = agent.find_element("submit", elements=elements)
    assert found is not None
    assert found.label == "Submit Order"
    assert found.center == (250, 250)

    # Dynamic tap
    with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
        res = agent.dynamic_tap("Submit Order", elements=elements)
        assert res["success"] is True
        assert res["coordinates"] == (250, 250)

    # Dynamic swipe directions
    with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
        res_up = agent.dynamic_swipe("up")
        assert res_up["success"] is True
        assert res_up["direction"] == "up"

        res_down = agent.dynamic_swipe("down")
        assert res_down["success"] is True

        res_left = agent.dynamic_swipe("left")
        assert res_left["success"] is True

        res_right = agent.dynamic_swipe("right")
        assert res_right["success"] is True

    # Multi-step form sequence
    with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
        seq_res = agent.execute_form_sequence([
            {"action": "tap", "target": "Submit Order"},
            {"action": "type", "target": "Search items", "value": "termux"},
            {"action": "swipe", "direction": "up"},
        ])
        assert seq_res["total_steps"] == 3
        assert seq_res["successful_steps"] == 3


# ---------------------------------------------------------------------------
# 4. Notification Watcher & OTP Regex Tests
# ---------------------------------------------------------------------------
def test_otp_regex_engine():
    # Test Bank SMS patterns
    sample_hdfc = "Your HDFC Bank OTP is 849201 for transaction of Rs. 4,500.00 at Flipkart. Valid for 10 mins."
    otp = OTPRegexEngine.extract_otp("HDFC-Alert", sample_hdfc)
    assert otp is not None
    assert otp.code == "849201"
    assert "hdfc" in otp.service.lower()
    assert otp.amount == "Rs. 4,500.00"

    # Test Google 2FA pattern
    sample_google = "G-392810 is your Google verification code."
    otp_g = OTPRegexEngine.extract_otp("Google", sample_google)
    assert otp_g is not None
    assert "392810" in otp_g.code

    # Test Swiggy order OTP
    sample_swiggy = "Your Swiggy login code is 5729. Do not share with anyone."
    otp_s = OTPRegexEngine.extract_otp("Swiggy", sample_swiggy)
    assert otp_s is not None
    assert otp_s.code == "5729"
    assert "swiggy" in otp_s.service.lower()

    # Non-OTP message
    assert OTPRegexEngine.extract_otp("Friends", "Hey, are we still meeting for lunch today?") is None


def test_notification_watcher_flow():
    mock_bot = MagicMock()
    watcher = NotificationWatcher(bot_instance=mock_bot)

    sample_notifs = [
        {
            "packageName": "com.google.android.apps.messaging",
            "title": "SBI Alert",
            "content": "OTP for your txn of INR 1,299.00 is 938104. Valid for 5 minutes.",
        }
    ]

    with patch.object(watcher, "fetch_notifications", return_value=sample_notifs):
        with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
            otps = watcher.poll_once()
            assert len(otps) == 1
            assert otps[0].code == "938104"
            assert otps[0].service.lower() == "sbi"

            # Polling again immediately should deduplicate and return empty
            otps2 = watcher.poll_once()
            assert len(otps2) == 0


# ---------------------------------------------------------------------------
# 5. Voice Handler Tests
# ---------------------------------------------------------------------------
def test_voice_handler_offline_transcription(tmp_path):
    handler = VoiceHandler()
    dummy_audio = tmp_path / "voice_test.ogg"
    dummy_audio.write_bytes(b"\x00" * 64)

    # Transcription fallback without whisper installed
    text = handler.transcribe_audio_file(str(dummy_audio))
    assert isinstance(text, str)
    assert len(text) > 0


def test_voice_handler_process_telegram_voice():
    handler = VoiceHandler()
    mock_bot = MagicMock()
    mock_bot.download_file.return_value = b"OggS_test_audio_stream"

    mock_msg = MagicMock()
    mock_msg.message_id = 999
    mock_msg.from_user.id = 12345
    mock_msg.voice = MagicMock(file_id="voice_file_abc123")
    mock_msg.audio = None

    mock_resp = AgentResponse(
        status="SUCCESS",
        query="battery",
        reasoning="Checking system battery",
        confidence=0.99,
        results=[],
        steps=[],
        conversational_reply="Battery is at 88% and discharging.",
    )

    with patch.object(AutonomousReActAgent, "run", return_value=mock_resp):
        res = handler.process_telegram_voice_note(mock_bot, mock_msg)
        assert res["success"] is True
        assert "Battery is at 88%" in res["agent_response"]
        assert os.path.exists(res["audio_path"])


# ---------------------------------------------------------------------------
# 6. Deep Link Engine Tests
# ---------------------------------------------------------------------------
def test_deep_link_engine_upi():
    engine = DeepLinkEngine()
    with patch("core.command_executor.SecureCommandExecutor.run", return_value="") as mock_run:
        res = engine.pay_upi(
            payee_vpa="friend@upi",
            payee_name="Alex",
            amount=500.0,
            preferred_app="gpay",
        )
        assert res["success"] is True
        assert "upi://pay" in res["uri"]


def test_deep_link_engine_apps():
    engine = DeepLinkEngine()
    with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
        # WhatsApp chat
        wa_res = engine.send_whatsapp_message(phone_number="+919876543210", message="Hello from Void")
        assert wa_res["success"] is True
        assert "api.whatsapp.com" in wa_res["uri"]

        # Google Maps navigation
        maps_res = engine.navigate_google_maps("Connaught Place, New Delhi")
        assert maps_res["success"] is True
        assert "google.navigation" in maps_res["uri"]

        # Uber ride
        uber_res = engine.book_uber("Airport Terminal 3")
        assert uber_res["success"] is True
        assert "uber://" in uber_res["uri"]

        # Android settings
        set_res = engine.open_settings("wifi")
        assert set_res["success"] is True


# ---------------------------------------------------------------------------
# 7. Scraper & Vault Sync Tests
# ---------------------------------------------------------------------------
def test_scraper_vault_service(tmp_path):
    service = ScraperVaultService()
    service.price_watches.clear()
    tid = service.add_price_watch(
        url="https://example.com/product/123",
        product_name="Wireless Earbuds",
        target_price=2999.0,
    )
    assert tid in service.price_watches
    assert service.price_watches[tid].product_name == "Wireless Earbuds"

    # Price parsing from HTML
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'<html><body>Price: &#8377; 2,499.00 in stock</body></html>'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        price = service.scrape_url_price("https://example.com/product/123")
        assert price == 2499.0

        # Trigger check_all_watches_once -> should trigger price alert
        alerts = service.check_all_watches_once()
        assert len(alerts) == 1
        assert alerts[0]["current_price"] == 2499.0
        assert alerts[0]["product_name"] == "Wireless Earbuds"

    # Remove watch
    assert service.remove_price_watch(tid) is True
    assert tid not in service.price_watches


# ---------------------------------------------------------------------------
# 8. ToolRegistry Strategy Integration Tests
# ---------------------------------------------------------------------------
def test_advanced_strategies_in_registry():
    from tools.registry import register_advanced_strategies
    register_advanced_strategies(global_tool_registry)

    # Verify the new strategies are in global_tool_registry
    assert global_tool_registry.has_tool("vision_tap")
    assert global_tool_registry.has_tool("vision_form_fill")
    assert global_tool_registry.has_tool("deep_link_pay")
    assert global_tool_registry.has_tool("track_price")
    assert global_tool_registry.has_tool("get_latest_otp")

    # Test track_price execution
    res_track = global_tool_registry.execute(
        "track_price",
        url="https://store.example.com/item",
        product_name="Mechanical Keyboard",
        target_price=4500.0,
    )
    assert res_track.success is True
    assert "Mechanical Keyboard" in str(res_track.output)

    # Test get_latest_otp execution (empty)
    with patch.object(global_notification_watcher, "poll_once", return_value=[]):
        res_otp = global_tool_registry.execute("get_latest_otp")
        assert res_otp.success is True
        assert "No unread" in str(res_otp.output)

    # Test deep_link_pay execution
    with patch("core.command_executor.SecureCommandExecutor.run", return_value=""):
        res_pay = global_tool_registry.execute(
            "deep_link_pay",
            payee_vpa="store@upi",
            payee_name="Superstore",
            amount=250.0,
            note="Groceries",
        )
        assert res_pay.success is True
        assert "₹250.0" in str(res_pay.output)
