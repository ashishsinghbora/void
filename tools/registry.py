"""
tools/registry.py - Hash-Indexed Strategy Pattern Tool Registry.

Enables O(1) dynamic strategy lookups, automated parameter binding,
and bidirectional integration with the Void LLM model runtime.
"""

import functools
import logging
from typing import Dict, Any, List, Optional, Callable

from core.types import ToolExecutionResult
from tools.base import ToolStrategy
from tools.hardware import (
    BatteryStatusStrategy,
    TorchControlStrategy,
    VibrateDeviceStrategy,
    ScreenBrightnessStrategy,
    VolumeControlStrategy,
    VolumeInfoStrategy,
)
from tools.telephony import (
    SendSmsStrategy,
    MakeCallStrategy,
    GetSmsListStrategy,
    GetContactsStrategy,
    GetCallLogStrategy,
    GetTelephonyInfoStrategy,
)
from tools.media import (
    CameraPhotoStrategy,
    TextToSpeechStrategy,
    RecordAudioStartStrategy,
    RecordAudioStopStrategy,
    ShareContentStrategy,
)
from tools.system import (
    ShowToastStrategy,
    ShowNotificationStrategy,
    SetClipboardStrategy,
    GetClipboardStrategy,
    GetLocationStrategy,
    GetWifiInfoStrategy,
    ScanWifiNetworksStrategy,
    DownloadFileStrategy,
    AuthenticateFingerprintStrategy,
    OpenAppStrategy,
)
from tools.social_apps import (
    SendWhatsAppMessageStrategy,
    OpenTelegramChatStrategy,
    OpenSocialProfileStrategy,
    LaunchInstalledAppStrategy,
)

logger = logging.getLogger("VoidAdvancedCore.Registry")

try:
    import needle
    HAS_NEEDLE = True
except ImportError:
    needle = None
    HAS_NEEDLE = False


class ToolRegistry:
    """Hash-indexed registry for ToolStrategy instances with O(1) execution dispatch."""
    __slots__ = ("_tools",)

    def __init__(self):
        self._tools: Dict[str, ToolStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Instantiates and registers all standard Android/Termux hardware strategies."""
        strategies: List[ToolStrategy] = [
            BatteryStatusStrategy(),
            TorchControlStrategy(),
            VibrateDeviceStrategy(),
            ScreenBrightnessStrategy(),
            VolumeControlStrategy(),
            VolumeInfoStrategy(),
            SendSmsStrategy(),
            MakeCallStrategy(),
            GetSmsListStrategy(),
            GetContactsStrategy(),
            GetCallLogStrategy(),
            GetTelephonyInfoStrategy(),
            CameraPhotoStrategy(),
            TextToSpeechStrategy(),
            RecordAudioStartStrategy(),
            RecordAudioStopStrategy(),
            ShareContentStrategy(),
            ShowToastStrategy(),
            ShowNotificationStrategy(),
            SetClipboardStrategy(),
            GetClipboardStrategy(),
            GetLocationStrategy(),
            GetWifiInfoStrategy(),
            ScanWifiNetworksStrategy(),
            DownloadFileStrategy(),
            AuthenticateFingerprintStrategy(),
            OpenAppStrategy(),
            SendWhatsAppMessageStrategy(),
            OpenTelegramChatStrategy(),
            OpenSocialProfileStrategy(),
            LaunchInstalledAppStrategy(),
        ]
        for s in strategies:
            self.register(s)

    def register(self, strategy: ToolStrategy) -> None:
        """Registers a new strategy into the hash table."""
        self._tools[strategy.name] = strategy
        logger.debug(f"Registered tool strategy: {strategy.name}")

    def unregister(self, name: str) -> None:
        """Removes a strategy from registry."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolStrategy]:
        """O(1) hash table lookup."""
        return self._tools.get(name)

    def execute(self, name: str, **kwargs: Any) -> ToolExecutionResult:
        """Dispatches execution to registered strategy."""
        strategy = self.get(name)
        if not strategy:
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Tool '{name}' is not registered in ToolRegistry.",
                duration_ms=0,
            )
        return strategy.run_safe(**kwargs)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns schemas and documentation of all registered tools."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "schema": s.schema,
            }
            for s in self._tools.values()
        ]

    def create_void_callables(self) -> List[Callable]:
        """
        Creates decorated callables compatible with the Void LLM agent runtime.
        Automatically attaches docstrings and parameter signatures.
        """
        callables = []

        for name, strategy in self._tools.items():
            # Build wrapper closure preserving function signature
            def make_handler(strat: ToolStrategy):
                def handler(*args: Any, **kwargs: Any) -> Any:
                    res = strat.run_safe(*args, **kwargs)
                    if res.success:
                        return res.output
                    return f"Error: {res.error}"

                handler.__name__ = strat.name
                handler.__doc__ = strat.description

                if HAS_NEEDLE and hasattr(needle, "tool"):
                    return needle.tool(handler)
                return handler

            callables.append(make_handler(strategy))

        return callables

    # Backward compatibility alias
    create_needle_callables = create_void_callables


# Global default registry instance
global_tool_registry = ToolRegistry()

