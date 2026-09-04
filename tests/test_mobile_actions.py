"""
tests/test_mobile_actions.py - Unit tests for Mobile Action Engine & App Navigation.
"""

from unittest.mock import patch, MagicMock
import pytest

from tools.mobile_actions import (
    MobileTapStrategy,
    MobileSwipeStrategy,
    MobileKeyEventStrategy,
    MobileTypeTextStrategy,
    OpenSettingsScreenStrategy,
    AppSearchStrategy,
    CaptureScreenStrategy,
)
from tools.registry import global_tool_registry


def test_mobile_tap_execution():
    strategy = MobileTapStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(x=500, y=1200)
        assert res.success is True
        assert "500" in res.output and "1200" in res.output

    # Invalid coordinates
    bad_res = strategy.execute(x=-5, y=100)
    assert bad_res.success is False


def test_mobile_swipe_execution():
    strategy = MobileSwipeStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(x1=500, y1=1500, x2=500, y2=500, duration_ms=400)
        assert res.success is True
        assert "Swiped" in res.output

    # Invalid duration
    bad_res = strategy.execute(x1=100, y1=100, x2=200, y2=200, duration_ms=5)
    assert bad_res.success is False


def test_mobile_keyevent_execution():
    strategy = MobileKeyEventStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(key="HOME")
        assert res.success is True
        assert "home" in res.output.lower()

        res_back = strategy.execute(key="BACK")
        assert res_back.success is True
        assert "back" in res_back.output.lower()

    bad_key = strategy.execute(key="UNKNOWN_SUPER_KEY_XYZ")
    assert bad_key.success is False


def test_mobile_type_text_execution():
    strategy = MobileTypeTextStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(text="hello world")
        assert res.success is True
        assert "Typed" in res.output

    # Empty text
    empty_res = strategy.execute(text="")
    assert empty_res.success is False


def test_open_settings_screen_execution():
    strategy = OpenSettingsScreenStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(screen="wifi")
        assert res.success is True
        assert "WIFI_SETTINGS" in res.output

        res_bat = strategy.execute(screen="battery")
        assert res_bat.success is True


def test_app_search_execution():
    strategy = AppSearchStrategy()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute(target_app="youtube", search_query="lofi hip hop")
        assert res.success is True
        assert "youtube" in res.output.lower()

        res_maps = strategy.execute(target_app="maps", search_query="coffee shop")
        assert res_maps.success is True
        assert "maps" in res_maps.output.lower()


def test_capture_screen_execution():
    strategy = CaptureScreenStrategy()
    with patch("subprocess.run") as mock_run, patch("os.path.exists", return_value=True), patch("os.path.getsize", return_value=51200):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = strategy.execute()
        assert res.success is True
        assert "Screen captured" in res.output


def test_mobile_tools_registered_in_global_registry():
    expected_tools = [
        "mobile_tap",
        "mobile_swipe",
        "mobile_keyevent",
        "mobile_type_text",
        "open_settings_screen",
        "app_search",
        "capture_screen",
    ]
    for tool_name in expected_tools:
        assert global_tool_registry.has_tool(tool_name), f"Tool {tool_name} not found in global registry"
