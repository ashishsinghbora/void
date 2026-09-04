"""
tools/base.py - Abstract Strategy Pattern Interface for Hardware Tools.

Defines the ToolStrategy contract for modular hardware and operating system
interactions on Android/Termux edge devices.
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.types import ToolExecutionResult


class ToolStrategy(ABC):
    """Abstract Strategy interface for all phone hardware tools."""
    __slots__ = ("name", "description", "schema")

    def __init__(self, name: str, description: str, schema: Optional[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.schema = schema or {}

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        """
        Executes the hardware strategy with sanitized input parameters.
        Returns a standardized ToolExecutionResult.
        """
        pass

    def run_safe(self, **kwargs: Any) -> ToolExecutionResult:
        """Standardized wrapper measuring execution time and capturing exceptions."""
        start = time.perf_counter()
        try:
            res = self.execute(**kwargs)
            res.duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return res
        except Exception as e:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Error in {self.name}: {str(e)}",
                duration_ms=elapsed,
            )
