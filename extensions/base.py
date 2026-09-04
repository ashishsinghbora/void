"""
extensions/base.py - Abstract Extension Plugin Architecture for Void Platform.

Enables dynamic, modular, sandboxed extensions to plug directly into the Void
engine and ToolRegistry with zero modification to core platform code.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from tools.base import ToolStrategy


class ExtensionPlugin(ABC):
    """
    Abstract base class for all Void plugins and dynamic extensions.
    Provides standard lifecycle hooks: initialize(), get_strategies(), teardown().
    """
    __slots__ = ("name", "version", "description", "author", "enabled")

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        author: str = "Void Community",
        enabled: bool = True,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.enabled = enabled

    @abstractmethod
    def initialize(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Invoked when the plugin is loaded into the Void runtime.
        Use to establish API connections, configure local state, or register handlers.
        """
        pass

    @abstractmethod
    def get_strategies(self) -> List[ToolStrategy]:
        """
        Returns the list of ToolStrategy instances exposed by this extension.
        These strategies are automatically injected into the global ToolRegistry.
        """
        return []

    def teardown(self) -> None:
        """
        Invoked when plugin is unloaded or platform is gracefully shutting down.
        Use to close sockets, save state, or release resources.
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serializes plugin metadata for API/Web UI display."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "tools": [s.name for s in self.get_strategies()],
        }
