"""
tests/test_extensions.py - Automated Tests for Zero-Default Extension Architecture & Dynamic Plugin Manager.
"""

import os
import tempfile
import pytest
from typing import List, Dict, Any

from extensions.base import ExtensionPlugin
from extensions.manager import ExtensionManager
from tools.base import ToolStrategy
from tools.registry import ToolRegistry, global_tool_registry
from core.types import ToolExecutionResult


def test_zero_default_extensions_on_startup():
    """Verifies that Void starts completely lean with 0 extensions loaded by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ExtensionManager(custom_dir=tmpdir)
        loaded = manager.discover_and_load_all()
        assert loaded == 0
        assert len(manager.list_extensions()) == 0


def test_custom_plugin_registration_lifecycle():
    """Verifies that user-defined ExtensionPlugin instances register and teardown cleanly."""
    class EchoStrategy(ToolStrategy):
        def __init__(self):
            super().__init__(name="echo_test", description="Echoes text.")

        def execute(self, text: str = "", **kwargs: Any) -> ToolExecutionResult:
            return ToolExecutionResult(success=True, output=f"Echo: {text}", error=None, duration_ms=0)

    class EchoPlugin(ExtensionPlugin):
        def __init__(self):
            super().__init__(name="echo_plugin", version="1.0.0", description="Echo test plugin")
            self._strat = EchoStrategy()

        def initialize(self, context=None): pass
        def get_strategies(self): return [self._strat]

    registry = ToolRegistry()
    manager = ExtensionManager(tool_registry=registry)
    plugin = EchoPlugin()

    # Register
    assert manager.register_extension(plugin) is True
    assert len(manager.list_extensions()) == 1
    assert registry.get("echo_test") is not None

    # Execute registered tool
    res = registry.execute("echo_test", text="Hello Void")
    assert res.success is True
    assert res.output == "Echo: Hello Void"

    # Unregister
    assert manager.unregister_extension("echo_plugin") is True
    assert len(manager.list_extensions()) == 0
    assert registry.get("echo_test") is None


def test_community_catalog_search():
    """Verifies community catalog keyword lookup."""
    manager = ExtensionManager()
    all_cat = manager.search_catalog()
    assert len(all_cat) >= 3

    crypto_matches = manager.search_catalog("crypto")
    assert len(crypto_matches) >= 1
    assert crypto_matches[0]["name"] == "crypto_tracker"

    github_matches = manager.search_catalog("github")
    assert len(github_matches) >= 1
    assert github_matches[0]["name"] == "github_monitor"


def test_dynamic_plugin_install_and_uninstall():
    """Verifies on-demand downloading, AST verification, and uninstallation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry()
        manager = ExtensionManager(tool_registry=registry, custom_dir=tmpdir)

        # 1. Install crypto_tracker on-demand
        install_res = manager.install_plugin("crypto_tracker")
        assert install_res["success"] is True
        assert "track_crypto" in install_res["tools"]
        assert len(manager.list_extensions()) == 1
        assert registry.get("track_crypto") is not None

        # Execute dynamic tool
        tool_res = registry.execute("track_crypto", coin="bitcoin")
        assert tool_res.success is True
        assert "bitcoin" in str(tool_res.output).lower()

        # 2. Uninstall on-demand
        uninst_res = manager.uninstall_plugin("crypto_tracker")
        assert uninst_res["success"] is True
        assert len(manager.list_extensions()) == 0
        assert registry.get("track_crypto") is None


def test_dynamic_plugin_rejects_invalid_code():
    """Verifies AST safety inspection rejects files with invalid syntax."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ExtensionManager(custom_dir=tmpdir)
        invalid_path = os.path.join(tmpdir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write("def broken syntax : {")

        assert manager.load_from_file(invalid_path) == 0


def test_native_storage_cleaner_without_extensions():
    """Verifies core clean_system tool executes without needing any extensions installed."""
    res = global_tool_registry.execute("clean_system", dry_run=True)
    assert res.success is True
    assert "dry_run" in res.output
    assert res.output["dry_run"] is True
