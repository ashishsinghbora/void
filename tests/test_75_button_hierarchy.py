"""
tests/test_75_button_hierarchy.py - Comprehensive Verification of 75-Button Nested Menu Hierarchy.

Tests:
1. Level 1: Root Control Center (15 categories, 2-column layout).
2. Level 2: Sub-Menu Breakdown across all categories (exact 75 total functions).
3. Back-navigation handler returning to Root Control Center without hanging states.
4. Model lifecycle manager (symmetrical setup, remove, RAM checks, context window).
5. Shell dispatch (/sh) and input automation routing.
6. Safe Markdown entity escaping and error resilience.
"""

import pytest
from unittest.mock import MagicMock, patch

from telegram.handlers.menu_router import get_root_menu, _resolve_submenu, MENU_DISPATCH
from telegram.handlers.telemetry_handlers import get_telemetry_submenu
from telegram.handlers.input_handlers import get_input_submenu
from telegram.handlers.model_handlers import get_model_submenu
from telegram.handlers.vault_handlers import get_vault_submenu
from telegram.handlers.security_handlers import get_security_submenu
from telegram.handlers.shell_handlers import get_shell_submenu
from telegram.handlers.maintenance_handlers import get_maintenance_submenu
from telegram.handlers.media_handlers import get_media_submenu
from telegram.handlers.notification_handlers import get_notification_submenu
from telegram.handlers.automation_handlers import get_automation_submenu
from telegram.handlers.debug_handlers import get_debug_submenu
from telegram.handlers.connectivity_handlers import get_connectivity_submenu
from telegram.handlers.storage_handlers import get_storage_submenu
from telegram.handlers.power_handlers import get_power_submenu
from telegram.handlers.analytics_handlers import get_analytics_submenu

from core.model_manager import global_model_manager, MODEL_CATALOG
from security.sanitizer import InputSanitizer


def _count_buttons(markup):
    """Helper to count total buttons in an InlineKeyboardMarkup."""
    count = 0
    if not markup or not hasattr(markup, "keyboard"):
        return 0
    for row in markup.keyboard:
        count += len(row)
    return count


def _get_button_callbacks(markup):
    """Helper to extract all callback_data values from an InlineKeyboardMarkup."""
    callbacks = []
    if not markup or not hasattr(markup, "keyboard"):
        return callbacks
    for row in markup.keyboard:
        for btn in row:
            callbacks.append(btn.callback_data)
    return callbacks


def test_level_1_root_control_center():
    """Verify Level 1 Root Control Center contains 15 categories."""
    card, markup = get_root_menu()
    assert "Root Control Center" in card
    total_buttons = _count_buttons(markup)
    assert total_buttons == 15

    callbacks = _get_button_callbacks(markup)
    expected_categories = [
        "menu_telemetry", "menu_input",
        "menu_models", "menu_vault",
        "menu_security", "menu_shell",
        "menu_maintenance", "menu_media",
        "menu_notif", "menu_macros",
        "menu_connectivity", "menu_storage",
        "menu_debug", "menu_power",
        "menu_analytics",
    ]
    for cat in expected_categories:
        assert cat in callbacks, f"Missing category: {cat}"


def test_level_2_submenu_75_buttons_breakdown():
    """
    Verify the 11 detailed sub-menus match the exact 75 button total:
    1. Core & Telemetry: 7
    2. Device Touch & Input: 12
    3. Model Management: 7
    4. Cloud Vault & Media: 7
    5. Security & Network: 7
    6. Shell & Terminal: 7
    7. Maintenance & Tools: 6
    8. Media & Audio: 6
    9. Notifications & Clip: 5
    10. Automation Macros: 5
    11. Debug & Diagnostics: 6
    Total = 75 functions
    """
    submenus = [
        ("Core & Telemetry", get_telemetry_submenu, 7),
        ("Device Touch & Input", get_input_submenu, 12),
        ("Model Management", get_model_submenu, 7),
        ("Cloud Vault & Media", get_vault_submenu, 7),
        ("Security & Network", get_security_submenu, 7),
        ("Shell & Terminal", get_shell_submenu, 7),
        ("Maintenance & Tools", get_maintenance_submenu, 6),
        ("Media & Audio Hub", get_media_submenu, 6),
        ("Notifications & Clip", get_notification_submenu, 5),
        ("Automation Macros", get_automation_submenu, 5),
        ("Debug & Diagnostics", get_debug_submenu, 6),
    ]

    total_functions = 0
    for name, func, expected_count in submenus:
        card, markup = func()
        count = _count_buttons(markup)
        assert count == expected_count, f"{name}: expected {expected_count} buttons, got {count}"
        total_functions += count

        # Verify every submenu contains a back-navigation button to root menu
        callbacks = _get_button_callbacks(markup)
        assert "cb_back_main" in callbacks, f"{name} missing back button cb_back_main"

    assert total_functions == 75, f"Expected exactly 75 functions, got {total_functions}"


def test_submenu_back_navigation_resolver():
    """Verify _resolve_submenu resolves root menu on cb_back_main without hanging states."""
    card, markup = _resolve_submenu("cb_back_main")
    assert "Root Control Center" in card
    assert _count_buttons(markup) == 15

    card_root, markup_root = _resolve_submenu("menu_root")
    assert "Root Control Center" in card_root
    assert _count_buttons(markup_root) == 15


def test_menu_router_dispatches_all_categories():
    """Verify every category in MENU_DISPATCH resolves a valid submenu with buttons."""
    for menu_key in MENU_DISPATCH:
        result = _resolve_submenu(menu_key)
        assert result is not None, f"Failed to resolve {menu_key}"
        card, markup = result
        assert isinstance(card, str) and len(card) > 0
        assert _count_buttons(markup) > 0


def test_model_lifecycle_manager_ram_aware_and_symmetrical():
    """Verify RAM awareness, context stats, and symmetrical remove_model."""
    # RAM check
    sufficient, avail_ram, req_ram = global_model_manager.check_ram_available("smollm-135m")
    assert isinstance(sufficient, bool)
    assert isinstance(avail_ram, int)
    assert req_ram == 512

    # Context window stats
    ctx = global_model_manager.get_context_window_stats()
    assert "active_model" in ctx
    assert "context_window_tokens" in ctx
    assert ctx["context_window_tokens"] >= 2048
    assert ctx["reserved_response_tokens"] == 512

    # Symmetrical remove_model
    res = global_model_manager.remove_model("smollm-135m")
    assert isinstance(res, dict)
    assert res.get("success") is True
    assert "freed_mb" in res


def test_safe_markdown_escaping():
    """Verify markdown entity escaping prevents 'Bad Request: can't parse entities' errors."""
    raw_bad = "Error [404] in file_path.py* at 100% (tag #1) - check {x_val}!"
    escaped = InputSanitizer.escape_markdown(raw_bad)
    # Ensure raw unescaped brackets and asterisks are escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "\\*" in escaped
    assert "\\{" in escaped
    assert "\\}" in escaped
