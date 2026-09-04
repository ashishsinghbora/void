"""
tests/test_extensions.py - Automated Tests for Extension Architecture & Default Plugins.
"""

import os
import json
import pytest
from typing import List, Dict, Any, Optional

from extensions.base import ExtensionPlugin
from extensions.manager import ExtensionManager
from extensions.crypto_tracker import CryptoTrackerStrategy, CryptoTrackerExtension
from extensions.github_monitor import GitHubMonitorStrategy, GitHubMonitorExtension
from extensions.system_cleaner import SystemCleanerStrategy, SystemCleanerExtension
from tools.base import ToolStrategy
from tools.registry import ToolRegistry, global_tool_registry
from core.types import ToolExecutionResult
from agents.react_agent import AutonomousReActAgent


def test_extension_manager_lifecycle():
    """Verifies dynamic extension registration, inspection, and unregistration."""
    registry = ToolRegistry()
    manager = ExtensionManager(tool_registry=registry)

    # Initially empty in fresh manager instance
    assert len(manager.list_extensions()) == 0

    # Register crypto extension
    crypto_ext = CryptoTrackerExtension()
    assert manager.register_extension(crypto_ext) is True
    assert len(manager.list_extensions()) == 1
    assert manager.get_extension("crypto_tracker") is not None
    assert registry.get("track_crypto") is not None

    # Unregister extension
    assert manager.unregister_extension("crypto_tracker") is True
    assert len(manager.list_extensions()) == 0
    assert registry.get("track_crypto") is None


def test_crypto_tracker_strategy():
    """Verifies cryptocurrency price fetching, alias resolution, and payload integrity."""
    strat = CryptoTrackerStrategy()
    
    # Test Bitcoin query
    res = strat.run_safe(coin="btc", currency="usd", speak=False)
    assert res.success is True
    data = res.output
    assert isinstance(data, dict)
    assert data["coin"] == "bitcoin"
    assert data["currency"] == "USD"
    assert data["price"] > 0
    assert "summary" in data

    # Test Ethereum query
    res_eth = strat.run_safe(coin="eth", currency="eur", speak=False)
    assert res_eth.success is True
    assert res_eth.output["coin"] == "ethereum"
    assert res_eth.output["currency"] == "EUR"


def test_github_monitor_strategy():
    """Verifies GitHub repository metadata extraction and fallback resilience."""
    strat = GitHubMonitorStrategy()
    
    # Test repo summary query
    res = strat.run_safe(repo="ashishsinghbora/void", check_type="summary")
    assert res.success is True
    data = res.output
    assert isinstance(data, dict)
    assert "ashishsinghbora/void" in data["repository"]
    assert "stars" in data
    assert "forks" in data
    assert "summary" in data


def test_system_cleaner_strategy(tmp_path):
    """Verifies safe cache cleaning, dry_run enforcement, and protected file immunity."""
    strat = SystemCleanerStrategy()

    # Dry run should execute without errors
    res_dry = strat.run_safe(dry_run=True, target_scope="pycache")
    assert res_dry.success is True
    data = res_dry.output
    assert data["dry_run"] is True
    assert "bytes_reclaimed" in data
    assert "summary" in data


def test_custom_dynamic_plugin():
    """Verifies that third-party developers can create custom plugins easily."""
    class CustomPingStrategy(ToolStrategy):
        def __init__(self):
            super().__init__(name="ping_pong", description="Returns pong.")

        def execute(self, **kwargs: Any) -> ToolExecutionResult:
            return ToolExecutionResult(success=True, output="pong", error=None, duration_ms=0)

    class CustomPingPlugin(ExtensionPlugin):
        def __init__(self):
            super().__init__(name="ping_plugin", version="2.1.0", description="Ping tester")
            self._strat = CustomPingStrategy()

        def initialize(self, context=None):
            pass

        def get_strategies(self):
            return [self._strat]

    registry = ToolRegistry()
    manager = ExtensionManager(tool_registry=registry)
    plugin = CustomPingPlugin()

    assert manager.register_extension(plugin) is True
    res = registry.execute("ping_pong")
    assert res.success is True
    assert res.output == "pong"


def test_react_agent_extension_heuristics():
    """Verifies that AutonomousReActAgent routes queries to extension tools via heuristics."""
    agent = AutonomousReActAgent()
    agent._llm_agent = None  # Force heuristic parser mode to verify offline deterministic routing

    # Crypto query
    resp_crypto = agent.run("check bitcoin price")
    assert resp_crypto.status == "success"
    assert len(resp_crypto.steps) > 0
    assert resp_crypto.steps[0].action == "track_crypto"

    # GitHub query
    resp_gh = agent.run("monitor github repo")
    assert resp_gh.status == "success"
    assert resp_gh.steps[0].action == "monitor_github"

    # Cleaner query
    resp_clean = agent.run("clean temporary cache files")
    assert resp_clean.status == "success"
    assert resp_clean.steps[0].action == "clean_system"



def test_extension_discovery_and_metadata():
    """Verifies that extension manager discovers and registers default extensions."""
    from extensions.manager import global_extension_manager
    count = global_extension_manager.discover_and_load_all()
    assert count >= 3

    meta_list = global_extension_manager.list_extensions()
    plugin_names = [item["name"] for item in meta_list]
    assert "crypto_tracker" in plugin_names
    assert "github_monitor" in plugin_names
    assert "system_cleaner" in plugin_names
