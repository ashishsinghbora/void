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


def test_react_agent_ssh_password_query():
    agent = AutonomousReActAgent()
    res = agent.run("what is the password for connecting to ssh", session_id="test_session")
    assert "battery" not in res.conversational_reply.lower()
    assert "ssh" in res.conversational_reply.lower() or "password" in res.conversational_reply.lower()


def test_react_agent_vault_query():
    agent = AutonomousReActAgent()
    res = agent.run("can you send a message to your could vault", session_id="test_session")
    assert "battery" not in res.conversational_reply.lower()
    assert "vault" in res.conversational_reply.lower()


def test_react_agent_youtube_typo_query():
    agent = AutonomousReActAgent()
    res = agent.run("serach and play lofi hip hop on youtube", session_id="test_session")
    assert "battery" not in res.conversational_reply.lower()
    assert "youtube" in res.conversational_reply.lower() or "lofi" in res.conversational_reply.lower()


def test_react_agent_conversational_fallback():
    agent = AutonomousReActAgent()
    res = agent.run("who are you and what can you do", session_id="test_session")
    assert res.steps[0].action != "get_battery_status"
    assert "checked your battery vitals" not in res.conversational_reply.lower()
    assert "void" in res.conversational_reply.lower()


