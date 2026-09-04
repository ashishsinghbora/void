"""
core/types.py - High-Performance Typed Data Structures with __slots__ Optimization.

Provides strictly typed, zero-dict-overhead representations of requests,
agent steps, telemetry, and execution results for mobile edge devices.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


class AgentState(str, Enum):
    """Deterministic ReAct state machine lifecycle states."""
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    OBSERVING = "OBSERVING"
    EVALUATING = "EVALUATING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NotificationCategory(str, Enum):
    """Classification for intercepted Android notifications."""
    OTP = "OTP"
    URGENT = "URGENT"
    MESSAGE = "MESSAGE"
    SYSTEM = "SYSTEM"
    SPAM = "SPAM"
    GENERAL = "GENERAL"


@dataclass
class ToolExecutionRequest:
    """Request envelope for tool execution with strict slots allocation."""
    __slots__ = ("tool_name", "arguments", "timeout")
    tool_name: str
    arguments: Dict[str, Any]
    timeout: int


@dataclass
class ToolExecutionResult:
    """Standardized result envelope returned by tool execution strategies."""
    __slots__ = ("success", "output", "error", "duration_ms")
    success: bool
    output: Any
    error: Optional[str]
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ReActStep:
    """Individual step record inside the ReAct deliberation loop."""
    __slots__ = ("step_number", "thought", "action", "action_input", "observation", "status", "duration_ms")
    step_number: int
    thought: str
    action: Optional[str]
    action_input: Optional[Dict[str, Any]]
    observation: Optional[str]
    status: AgentState
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
        }


@dataclass(slots=True)
class AgentResponse:
    """Final output response emitted by the Advanced Agent Engine."""
    status: str
    query: str
    reasoning: str
    confidence: Optional[float]
    results: List[Any]
    steps: List[ReActStep]
    error: Optional[str] = None
    conversational_reply: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "results": self.results,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
            "conversational_reply": self.conversational_reply,
        }


@dataclass
class TelemetrySnapshot:
    """Device and engine telemetry metrics with minimal RAM footprint."""
    __slots__ = (
        "timestamp",
        "ram_rss_mb",
        "cpu_percent",
        "battery_percent",
        "battery_charging",
        "wifi_ssid",
        "active_daemons",
    )
    timestamp: float
    ram_rss_mb: float
    cpu_percent: float
    battery_percent: Optional[int]
    battery_charging: Optional[bool]
    wifi_ssid: Optional[str]
    active_daemons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "ram_rss_mb": self.ram_rss_mb,
            "cpu_percent": self.cpu_percent,
            "battery_percent": self.battery_percent,
            "battery_charging": self.battery_charging,
            "wifi_ssid": self.wifi_ssid,
            "active_daemons": self.active_daemons,
        }


@dataclass
class NotificationRecord:
    """Lightweight metadata envelope for intercepted push notifications."""
    __slots__ = ("id", "package_name", "title", "content", "timestamp", "category", "is_otp", "otp_code")
    id: str
    package_name: str
    title: str
    content: str
    timestamp: float
    category: NotificationCategory
    is_otp: bool
    otp_code: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "package_name": self.package_name,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "is_otp": self.is_otp,
            "otp_code": self.otp_code,
        }
