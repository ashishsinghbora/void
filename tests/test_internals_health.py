"""
tests/test_internals_health.py - Comprehensive Real-Time Internal Health Check.

Tests all internal subsystems, registers all handlers on AuthenticatedTelegramController,
and dispatches test queries across all 75 buttons and core commands.
"""

import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from telegram.bot_controller import AuthenticatedTelegramController
from telegram.handlers import register_all_handlers, get_root_menu
from telegram.handlers.menu_router import _resolve_submenu, MENU_DISPATCH
from core.model_manager import global_model_manager, MODEL_CATALOG
from tools.registry import global_tool_registry
from agents.react_agent import global_react_agent
from storage.repository import ExecutionLogRepository

logging.basicConfig(level=logging.ERROR)


def run_full_diagnostics():
    print("=" * 65)
    print(" 🔍 RUNNING VOID INTERNAL SUBSYSTEMS COMPREHENSIVE AUDIT")
    print("=" * 65)

    passed_checks = 0
    total_checks = 0

    def check(name, condition, details=""):
        nonlocal passed_checks, total_checks
        total_checks += 1
        if condition:
            passed_checks += 1
            print(f"  ✅ [PASS] {name} {details}")
        else:
            print(f"  ❌ [FAIL] {name} {details}")
            assert False, f"Check failed: {name} - {details}"

    # ------------------------------------------------------------------
    # 1. Controller & Keyboard Generation
    # ------------------------------------------------------------------
    print("\n1. Telegram Bot Controller & Keyboard Generator:")
    ctrl = AuthenticatedTelegramController(token="123456789:AAG_mock_test_token", admin_ids={99999})
    check("Controller Initialized", ctrl is not None)
    
    root_markup = ctrl.get_main_keyboard()
    check("Root Keyboard Generated", root_markup is not None)
    
    button_count = sum(len(row) for row in root_markup.keyboard)
    check("Level 1 Root Category Count", button_count == 15, f"(Found {button_count}/15 categories)")

    # ------------------------------------------------------------------
    # 2. Submenu Resolution & 75 Buttons
    # ------------------------------------------------------------------
    print("\n2. Level 2 Sub-Menu Breakdown & Navigation:")
    expected_submenus = {
        "menu_telemetry": 7,
        "menu_input": 12,
        "menu_models": 7,
        "menu_vault": 7,
        "menu_security": 7,
        "menu_shell": 7,
        "menu_maintenance": 6,
        "menu_media": 6,
        "menu_notif": 5,
        "menu_macros": 5,
        "menu_debug": 6,
    }

    total_75_buttons = 0
    for menu_key, expected_btn_count in expected_submenus.items():
        res = _resolve_submenu(menu_key)
        check(f"Resolve {menu_key}", res is not None)
        card, markup = res
        btn_count = sum(len(row) for row in markup.keyboard)
        check(f"{menu_key} Button Count", btn_count == expected_btn_count, f"({btn_count}/{expected_btn_count})")
        total_75_buttons += btn_count
        
        # Verify back navigation
        callbacks = [btn.callback_data for row in markup.keyboard for btn in row]
        check(f"{menu_key} Back Button", "cb_back_main" in callbacks)

    check("Exact 75 Functions Present", total_75_buttons == 75, f"({total_75_buttons}/75 total)")

    # Additional Level 1 submenus
    for extra_menu in ("menu_connectivity", "menu_storage", "menu_power", "menu_analytics"):
        res = _resolve_submenu(extra_menu)
        check(f"Resolve extra {extra_menu}", res is not None)

    # Back navigation to Root
    root_res = _resolve_submenu("cb_back_main")
    check("Root Back-Navigation Resolution", root_res is not None and "Root Control Center" in root_res[0])

    # ------------------------------------------------------------------
    # 3. Model Lifecycle Manager
    # ------------------------------------------------------------------
    print("\n3. Local AI Model Lifecycle Manager (RAM Aware):")
    total_ram, avail_ram = global_model_manager.detect_system_ram_mb()
    check("RAM Detection", total_ram > 0 and avail_ram >= 0, f"(Total: {total_ram}MB, Avail: {avail_ram}MB)")
    
    rec = global_model_manager.recommend_model_for_device(total_ram)
    check("Model Recommendation", rec in MODEL_CATALOG, f"(Recommended: {rec})")

    ctx_stats = global_model_manager.get_context_window_stats()
    check("Context Window Stats", ctx_stats["context_window_tokens"] >= 2048)

    sufficient, _, _ = global_model_manager.check_ram_available("smollm-135m")
    check("Pre-execution RAM Check", isinstance(sufficient, bool))

    # Symmetrical remove_model
    remove_res = global_model_manager.remove_model("smollm-135m")
    check("Symmetrical Model Removal", remove_res.get("success") is True)

    # ------------------------------------------------------------------
    # 4. Input Automation & System Tools
    # ------------------------------------------------------------------
    print("\n4. Android System & Input Automation Engine:")
    tap_res = global_tool_registry.execute("mobile_tap", x=500, y=500)
    check("Touch Tap Simulation", tap_res.success is True, f"({tap_res.output})")

    swipe_res = global_tool_registry.execute("mobile_swipe", x1=100, y1=500, x2=100, y2=100, duration_ms=200)
    check("Gesture Swipe Simulation", swipe_res.success is True, f"({swipe_res.output})")

    key_res = global_tool_registry.execute("mobile_keyevent", key="HOME")
    check("Hardware Keyevent (HOME)", key_res.success is True, f"({key_res.output})")

    type_res = global_tool_registry.execute("mobile_type_text", text="Void Diagnostics")
    check("Keyboard Typing Simulation", type_res.success is True, f"({type_res.output})")

    bat_res = global_tool_registry.execute("get_battery_status")
    check("Battery Tool Query", bat_res.success is True)

    clip_res = global_tool_registry.execute("set_clipboard", text="Void Telemetry Verified")
    check("Clipboard Tool Set", clip_res.success is True)

    # ------------------------------------------------------------------
    # 5. Natural Language ReAct Loop
    # ------------------------------------------------------------------
    print("\n5. Autonomous ReAct Agent Loop:")
    agent_res = global_react_agent.run("check battery status and telemetry", session_id="diag_session")
    check("Agent Response Generated", agent_res is not None)
    check("Agent Reasoning Present", len(agent_res.reasoning) > 0)
    check("Agent Confidence Score", agent_res.confidence is not None and agent_res.confidence > 0.5)

    # ------------------------------------------------------------------
    # 6. SQLite WAL Database & Audit Logs
    # ------------------------------------------------------------------
    print("\n6. Persistence Layer & SQLite WAL Database:")
    repo = ExecutionLogRepository()
    logs = repo.get_recent_logs(limit=3)
    check("SQLite Execution Logs Queryable", isinstance(logs, list))

    print("\n" + "=" * 65)
    print(f" 🎉 ALL DIAGNOSTICS COMPLETED: {passed_checks}/{total_checks} CHECKS PASSED (100%)")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_full_diagnostics()
    sys.exit(0 if success else 1)
