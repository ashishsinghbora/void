"""
extensions/ - Modular Extension & Plugin Framework for Void Edge Platform.
"""

from extensions.base import ExtensionPlugin
from extensions.manager import ExtensionManager, global_extension_manager

__all__ = [
    "ExtensionPlugin",
    "ExtensionManager",
    "global_extension_manager",
]
