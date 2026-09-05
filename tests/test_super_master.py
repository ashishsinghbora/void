"""
tests/test_super_master.py - Verification of Super Master Architecture.

Covers:
1. Strict Under-2GB Model Constraints & RAM Ceilings (Android LMK immunity).
2. Remote OpenSSH & Bash Execution Engine (TerminalService).
3. Dual Brain & Bidirectional Cloud Vault Sync (BrainSyncService).
4. YouTube Immersion & Deep Link Engine (DeepLinkEngine).
5. Advanced ReAct Autonomous Strategies (ExecuteBash, ManageSsh, BrainSync, ResearchYouTube).
6. 6-Hub Telegram Control Center & Dynamic Extension Registry.
"""

import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock

from config.settings import global_config, MAX_MODEL_SIZE_MB, MAX_ALLOWED_RAM_MB
from core.model_manager import global_model_manager, MODEL_CATALOG
from modules.terminal_service import TerminalService, global_terminal_service
from modules.brain_sync import BrainSyncService, global_brain_sync
from modules.deep_links import global_deep_links
from tools.registry import global_tool_registry
from telegram.handlers.hub_handlers import (
    get_screen_hub,
    get_vault_hub,
    get_terminal_hub,
    get_research_hub,
    get_apps_hub,
    get_security_hub,
    register_hub_extension,
    HUB_EXTENSIONS,
)


# --------------------------------------------------------------------------
# 1. Strict Under-2GB Model Constraints & RAM Ceilings
# --------------------------------------------------------------------------
def test_all_models_strictly_under_2gb():
    """Verify that every model cataloged is strictly under 2000 MB."""
    assert MAX_MODEL_SIZE_MB <= 2000.0
    assert MAX_ALLOWED_RAM_MB <= 2048

    for model_id, meta in MODEL_CATALOG.items():
        assert meta["size_mb"] <= 2000.0, f"Model {model_id} ({meta['size_mb']} MB) exceeds 2GB ceiling!"
        assert meta["size_mb"] < 2048.0


def test_ram_limit_clamping():
    """Verify set_ram_limit clamps requests to MAX_ALLOWED_RAM_MB (2048 MB)."""
    # Exceeding request
    clamped = global_config.set_ram_limit(8192)
    assert clamped == 2048
    assert global_config.ram_limit_mb == 2048

    # Safe lower request
    safe = global_config.set_ram_limit(1024)
    assert safe == 1024
    assert global_config.ram_limit_mb == 1024

    # Restore default
    global_config.set_ram_limit(2048)


def test_model_manager_recommendations_under_2gb():
    """Verify model recommendations always select models under 2GB."""
    recs = global_model_manager.get_recommended_models(available_ram_mb=4096)
    assert len(recs) > 0
    for rec in recs:
        assert rec["size_mb"] <= 2000.0


# --------------------------------------------------------------------------
# 2. Remote OpenSSH & Bash Execution Engine
# --------------------------------------------------------------------------
def test_terminal_service_network_ips():
    """Verify get_network_ips returns dictionary of interface -> IP."""
    svc = TerminalService()
    ips = svc.get_network_ips()
    assert isinstance(ips, dict)
    assert len(ips) > 0
    assert any("." in ip for ip in ips.values())


def test_terminal_service_connection_card():
    """Verify connection card generates formatted instructions."""
    svc = TerminalService()
    card = svc.get_connection_card()
    assert "Remote SSH" in card
    assert "Port:" in card
    assert "8022" in card
    assert "ssh " in card


def test_terminal_service_execute_bash():
    """Verify execute_bash runs commands and captures exit codes & stdout/stderr."""
    svc = TerminalService()
    res = svc.execute_bash("echo 'super-master-test'")
    assert res["success"] is True
    assert res["returncode"] == 0
    assert "super-master-test" in res["output"]

    # Test nonzero return code
    err_res = svc.execute_bash("echo 'failure-output' >&2; exit 7")
    assert err_res["success"] is False
    assert err_res["returncode"] == 7
    assert "failure-output" in err_res["output"]


# --------------------------------------------------------------------------
# 3. Dual Brain & Bidirectional Cloud Vault Sync
# --------------------------------------------------------------------------
def test_brain_sync_hashing_and_hashtags():
    """Verify SHA-256 computation and hashtag inference."""
    svc = BrainSyncService()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "report.pdf")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test content for hashing")

        h = svc.compute_file_hash(test_file)
        assert len(h) == 64  # SHA256 hex length

        # Hashtags
        assert svc.infer_hashtag_for_file("doc.pdf") == "#DOC"
        assert svc.infer_hashtag_for_file("note.txt") == "#NOTE"
        assert svc.infer_hashtag_for_file("video.mp4") == "#MEDIA"
        assert svc.infer_hashtag_for_file("script.py") == "#CODE"
        assert svc.infer_hashtag_for_file("snap.jpg") == "#SCREEN"


def test_brain_sync_pairing():
    """Verify pair_vault_group sets config state."""
    svc = BrainSyncService()
    res = svc.pair_vault_group(chat_id=-100987654321, group_title="My Digital Brain")
    assert res["paired"] is True
    assert res["chat_id"] == -100987654321
    assert res["title"] == "My Digital Brain"
    assert res["paired_at"] > 0
    assert global_config.is_vault_enabled() is True


def test_brain_sync_local_to_cloud_mock():
    """Verify local files sync with Telegram bot mock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = os.path.join(tmpdir, "vault")
        brain_dir = os.path.join(tmpdir, "brain")
        os.makedirs(vault_dir, exist_ok=True)
        os.makedirs(brain_dir, exist_ok=True)

        # Create dummy file
        f_path = os.path.join(brain_dir, "summary.txt")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("Digital Twin Memory Entry #1")

        mock_bot = MagicMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 999
        mock_bot.send_document.return_value = mock_msg

        svc = BrainSyncService(
            local_vault_dir=vault_dir,
            local_brain_dir=brain_dir,
            bot=mock_bot,
            chat_id=-10011223344,
        )

        res = svc.sync_local_to_cloud()
        assert res["success"] is True
        assert res["uploaded_count"] == 1
        assert mock_bot.send_document.called

        # Second run should skip since hash is tracked
        res2 = svc.sync_local_to_cloud()
        assert res2["uploaded_count"] == 0
        assert res2["skipped_count"] == 1


# --------------------------------------------------------------------------
# 4. YouTube Immersion & Deep Link Engine
# --------------------------------------------------------------------------
def test_deep_link_play_youtube():
    """Verify play_youtube_video handles URLs and video IDs."""
    res = global_deep_links.play_youtube_video("dQw4w9WgXcQ")
    assert res["success"] is True
    assert "dQw4w9WgXcQ" in res["uri"]


def test_deep_link_research_youtube_topic():
    """Verify research_youtube_topic queries and saves structured notes to brain."""
    res = global_deep_links.research_youtube_topic("quantum computing basics")
    assert res["success"] is True
    assert "research_note" in res
    assert os.path.exists(res["research_note"])

    with open(res["research_note"], "r", encoding="utf-8") as f:
        content = f.read()
    assert "#RESEARCH" in content
    assert "#MEDIA" in content
    assert "quantum computing basics" in content


# --------------------------------------------------------------------------
# 5. Advanced ReAct Strategies
# --------------------------------------------------------------------------
def test_advanced_strategies_registered():
    """Verify execute_bash, manage_ssh, brain_sync, and research_youtube in tool registry."""
    names = [t["name"] for t in global_tool_registry.list_tools()]
    assert "execute_bash" in names
    assert "manage_ssh" in names
    assert "brain_sync" in names
    assert "research_youtube" in names


def test_strategy_execute_bash():
    """Verify execute_bash tool execution."""
    res = global_tool_registry.execute("execute_bash", command="echo 'void-strategy'")
    assert res.success is True
    assert "void-strategy" in res.output


def test_strategy_manage_ssh():
    """Verify manage_ssh tool execution."""
    res = global_tool_registry.execute("manage_ssh", action="status")
    assert res.success is True
    assert "OpenSSH" in res.output or "Terminal" in res.output or "SSH" in res.output


def test_strategy_brain_sync():
    """Verify brain_sync tool execution."""
    res = global_tool_registry.execute("brain_sync", action="sync")
    assert res.success is True


def test_strategy_research_youtube():
    """Verify research_youtube tool execution."""
    res = global_tool_registry.execute("research_youtube", topic="neural interfaces")
    assert res.success is True
    assert "archived" in res.output


# --------------------------------------------------------------------------
# 6. 6-Hub Telegram Control Center & Dynamic Extension Registry
# --------------------------------------------------------------------------
def test_all_six_hubs_render():
    """Verify each of the 6 hubs renders markdown card and back button."""
    hubs = [
        ("Screen & Touch", get_screen_hub),
        ("Vault & Brain", get_vault_hub),
        ("Terminal & SSH", get_terminal_hub),
        ("Research & YouTube", get_research_hub),
        ("Apps & Intents", get_apps_hub),
        ("Security & Interceptor", get_security_hub),
    ]

    for name, builder in hubs:
        card, markup = builder()
        assert isinstance(card, str) and len(card) > 0
        assert markup is not None
        # Must contain cb_back_main
        callbacks = [btn.callback_data for row in markup.keyboard for btn in row if btn.callback_data]
        assert "cb_back_main" in callbacks, f"{name} hub missing back button"


def test_dynamic_extension_registry():
    """Verify external extensions can dynamically attach to hubs without modifying router."""
    initial_ext_count = len(HUB_EXTENSIONS["terminal"])
    register_hub_extension("terminal", "⚡ Fast Diagnostic", "cb_fast_diag")
    assert len(HUB_EXTENSIONS["terminal"]) == initial_ext_count + 1

    card, markup = get_terminal_hub()
    callbacks = [btn.callback_data for row in markup.keyboard for btn in row if btn.callback_data]
    assert "cb_fast_diag" in callbacks
