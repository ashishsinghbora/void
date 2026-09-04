"""
tests/test_termux_void.py - Unit Tests for Mobile-Optimized TUI Engine.
"""

import os
import io
import sys
import pytest
from unittest.mock import patch, MagicMock

import termux_void
from termux_void import (
    strip_ansi,
    visible_width,
    get_card_width,
    wrap_mobile_text,
    render_card_top,
    render_card_bottom,
    render_card_sep,
    render_card_line,
    render_mobile_banner,
    render_telemetry_widget,
    render_quick_actions_menu,
    print_help_screen,
    format_step_cards,
    format_step_table,
    C_CYAN,
    C_RESET,
)
from core.types import ReActStep, AgentState


def test_strip_ansi_and_visible_width():
    colored = f"{C_CYAN}Hello Mobile Void{C_RESET}"
    assert strip_ansi(colored) == "Hello Mobile Void"
    assert visible_width(colored) == len("Hello Mobile Void")


def test_card_width_bounds():
    with patch("shutil.get_terminal_size", return_value=MagicMock(columns=30, lines=20)):
        assert get_card_width() == 36  # Min safe clamp

    with patch("shutil.get_terminal_size", return_value=MagicMock(columns=50, lines=20)):
        assert get_card_width() == 49  # 50 - 1

    with patch("shutil.get_terminal_size", return_value=MagicMock(columns=120, lines=20)):
        assert get_card_width() == 62  # Max clamp for card aesthetic


def test_wrap_mobile_text():
    text = "This is a long directive that must wrap cleanly inside a narrow mobile terminal screen without overflow."
    lines = wrap_mobile_text(text, max_w=30)
    assert len(lines) > 1
    for line in lines:
        assert len(line) <= 30


def test_render_card_borders_alignment():
    width = 44
    top = render_card_top("STATUS", width=width)
    bottom = render_card_bottom(width=width)
    sep = render_card_sep(width=width)
    line = render_card_line("RAM: 18 MB", width=width)

    assert visible_width(top) == width
    assert visible_width(bottom) == width
    assert visible_width(sep) == width
    assert visible_width(line) == width


def test_render_telemetry_widget():
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        render_telemetry_widget(vw=48)
    out = buf.getvalue()
    assert "LIVE TELEMETRY" in out
    assert "RAM RSS" in out
    assert "Battery" in out
    assert "Database" in out


def test_get_process_rss_mb():
    from termux_void import get_process_rss_mb
    rss = get_process_rss_mb()
    assert isinstance(rss, (int, float))
    assert rss > 0


def test_render_quick_actions_menu():
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        render_quick_actions_menu(vw=48, torch_on=True)
    out = buf.getvalue()
    assert "MOBILE COMMAND PALETTE" in out
    assert "[1]" in out
    assert "Torch" in out
    assert "[2]" in out
    assert "Battery" in out
    assert "[4]" in out
    assert "FastFetch" in out


def test_print_help_screen():
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        print_help_screen(vw=48)
    out = buf.getvalue()
    assert "VOID COMMAND DIRECTORY" in out
    assert "/help" in out
    assert "/torch" in out
    assert "/plugins" in out


def test_format_step_cards():
    step = ReActStep(
        step_number=1,
        thought="Querying battery status",
        action="get_battery_status",
        action_input={},
        observation="85% (Discharging)",
        status=AgentState.COMPLETED,
        duration_ms=12.4,
    )
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        format_step_cards([step], vw=48)
    out = buf.getvalue()
    assert "Step 1" in out
    assert "get_battery_status" in out
    assert "COMPLETED" in out
    assert "12.4ms" in out


def test_screen_extensions_exit():
    with patch("builtins.input", return_value="b"):
        termux_void.screen_extensions(vw=48)


def test_screen_audit_logs_exit():
    with patch("builtins.input", return_value="b"):
        termux_void.screen_audit_logs(vw=48)


def test_screen_security_dashboard_exit():
    with patch("builtins.input", return_value="b"):
        termux_void.screen_security_dashboard(vw=48)


def test_screen_bot_control_exit():
    with patch("builtins.input", return_value="b"):
        termux_void.screen_bot_control(vw=48)
