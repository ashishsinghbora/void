"""
tools - Strategy Pattern Hardware & Telephony Tool Integrations.
"""

from tools.base import ToolStrategy
from tools.registry import ToolRegistry, global_tool_registry
from tools.simulator import TermuxHardwareSimulator

__all__ = [
    "ToolStrategy",
    "ToolRegistry",
    "global_tool_registry",
    "TermuxHardwareSimulator",
]
