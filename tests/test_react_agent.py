"""
tests/test_react_agent.py - Autonomous ReAct Deliberation Loop & Fallback Tests.
"""

from agents.react_agent import AutonomousReActAgent
from agents.fallback_handler import HardwareFallbackHandler
from core.types import AgentResponse


def test_hardware_fallback_camera():
    decision = HardwareFallbackHandler.evaluate(
        tool_name="take_camera_photo",
        arguments={"camera_id": "0"},
        error_message="Camera error: lacking permission",
    )
    assert decision.should_fallback is True
    assert decision.fallback_tool_name == "take_camera_photo"
    assert decision.fallback_arguments.get("camera_id") == "1"


def test_hardware_fallback_sms():
    decision = HardwareFallbackHandler.evaluate(
        tool_name="send_sms",
        arguments={"message": "Important code"},
        error_message="Error: SMS permission denied",
    )
    assert decision.should_fallback is True
    assert decision.fallback_tool_name == "share_content"
    assert decision.fallback_arguments.get("text") == "Important code"


def test_react_agent_execution():
    agent = AutonomousReActAgent()
    res: AgentResponse = agent.run("check the battery status", session_id="test_session")
    assert res.status in ("success", "no_action")
    assert res.query == "check the battery status"
    assert len(res.steps) >= 1
    assert res.reasoning != ""
