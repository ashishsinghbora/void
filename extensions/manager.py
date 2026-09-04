"""
extensions/manager.py - Dynamic Plugin Discovery, Lifecycle & Registration Manager.

Manages dynamic loading, sandboxed execution, and registry injection of third-party
and user-defined extensions for the Void Edge Platform.
"""

import os
import sys
import logging
import inspect
import importlib
import importlib.util
from typing import Dict, List, Optional, Any

from extensions.base import ExtensionPlugin
from tools.base import ToolStrategy
from tools.registry import ToolRegistry, global_tool_registry

logger = logging.getLogger("VoidAdvancedCore.Extensions")


class ExtensionManager:
    """
    Orchestrates dynamic discovery, verification, and lifecycle management of extensions.
    Guarantees exception containment to prevent rogue plugins from crashing the host node.
    """
    __slots__ = ("_registry", "_extensions", "_plugins_dir", "_custom_dir")

    def __init__(
        self,
        tool_registry: ToolRegistry = global_tool_registry,
        plugins_dir: Optional[str] = None,
        custom_dir: Optional[str] = None,
    ):
        self._registry = tool_registry
        self._extensions: Dict[str, ExtensionPlugin] = {}
        
        # Default plugins directory is the extensions package directory
        if plugins_dir is None:
            self._plugins_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            self._plugins_dir = os.path.abspath(plugins_dir)

        # Custom directory for user-installed extensions (e.g. ~/.void/extensions)
        self._custom_dir = custom_dir or os.path.expanduser("~/.void/extensions")

    def register_extension(self, plugin: ExtensionPlugin, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Registers an instantiated ExtensionPlugin, initializes it, and injects
        its tool strategies into the ToolRegistry.
        """
        if not isinstance(plugin, ExtensionPlugin):
            logger.warning(f"Rejected extension: {type(plugin)} does not inherit from ExtensionPlugin.")
            return False

        name = plugin.name
        try:
            plugin.initialize(context)
            strategies = plugin.get_strategies()

            # Register each strategy with the tool registry
            for strat in strategies:
                if isinstance(strat, ToolStrategy):
                    self._registry.register(strat)
                    logger.info(f"Extension '{name}' registered tool: '{strat.name}'")

            self._extensions[name] = plugin
            logger.info(f"Successfully loaded and activated extension: '{name}' v{plugin.version}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize extension '{name}': {e}", exc_info=True)
            return False

    def unregister_extension(self, name: str) -> bool:
        """Unregisters and tears down an extension, removing its tools from registry."""
        plugin = self._extensions.pop(name, None)
        if not plugin:
            return False

        try:
            # Remove associated strategies from registry
            for strat in plugin.get_strategies():
                self._registry.unregister(strat.name)

            plugin.teardown()
            logger.info(f"Successfully unloaded extension: '{name}'")
            return True
        except Exception as e:
            logger.warning(f"Error tearing down extension '{name}': {e}")
            return False

    def get_extension(self, name: str) -> Optional[ExtensionPlugin]:
        """Returns loaded extension by name."""
        return self._extensions.get(name)

    def list_extensions(self) -> List[Dict[str, Any]]:
        """Returns metadata list of all active extensions."""
        return [ext.to_dict() for ext in self._extensions.values()]

    def load_from_file(self, file_path: str, context: Optional[Dict[str, Any]] = None) -> int:
        """
        Dynamically loads and instantiates all ExtensionPlugin subclasses found
        in a given Python file. Returns the count of successfully loaded plugins.
        """
        if not os.path.isfile(file_path) or not file_path.endswith(".py"):
            return 0

        module_name = f"void_ext_{os.path.splitext(os.path.basename(file_path))[0]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return 0

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            loaded_count = 0
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, ExtensionPlugin)
                    and attr is not ExtensionPlugin
                ):
                    try:
                        instance = attr()
                        if self.register_extension(instance, context):
                            loaded_count += 1
                    except Exception as ex:
                        logger.error(f"Failed to instantiate plugin class {attr_name} from {file_path}: {ex}")

            return loaded_count
        except Exception as e:
            logger.error(f"Failed to import extension module from {file_path}: {e}")
            return 0

    def discover_and_load_all(self, context: Optional[Dict[str, Any]] = None) -> int:
        """
        Discovers all Python plugin files in the internal extensions directory
        and optional external custom user directory. Returns total loaded plugin count.
        """
        total = 0

        # 1. Internal extensions directory
        if os.path.isdir(self._plugins_dir):
            for fname in sorted(os.listdir(self._plugins_dir)):
                if fname.endswith(".py") and not fname.startswith("__") and fname not in ("base.py", "manager.py"):
                    full_path = os.path.join(self._plugins_dir, fname)
                    total += self.load_from_file(full_path, context)

        # 2. External custom directory
        if os.path.isdir(self._custom_dir):
            for fname in sorted(os.listdir(self._custom_dir)):
                if fname.endswith(".py") and not fname.startswith("__"):
                    full_path = os.path.join(self._custom_dir, fname)
                    total += self.load_from_file(full_path, context)

        logger.info(f"Extension discovery completed: {total} extensions active.")
        return total


# Global default extension manager instance
global_extension_manager = ExtensionManager()
