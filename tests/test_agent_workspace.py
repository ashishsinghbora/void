"""
tests/test_agent_workspace.py - Unit Tests for Digital Twin Workspace, Memory, and Tools.
"""

import os
import shutil
import tempfile
import pytest

from modules.agent_workspace import AgentWorkspace
from modules.terminal_service import TerminalService
from modules.vision_agent import VisionAgent
from tools.registry import global_tool_registry


@pytest.fixture
def temp_workspace(monkeypatch):
    """Creates temporary directories for brain, vault, and scripts."""
    tmp_dir = tempfile.mkdtemp(prefix="void_test_workspace_")
    scripts_dir = os.path.join(tmp_dir, "scripts")
    brain_dir = os.path.join(tmp_dir, "brain")

    monkeypatch.setattr("modules.agent_workspace.SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr("modules.agent_workspace.BRAIN_DIR", brain_dir)
    monkeypatch.setattr("modules.agent_workspace.HISTORY_FILE", os.path.join(brain_dir, "tasks_history.json"))
    monkeypatch.setattr("modules.agent_workspace.SKILLS_FILE", os.path.join(brain_dir, "agent_skills.json"))

    ws = AgentWorkspace()
    yield ws
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_agent_workspace_skills_initialization(temp_workspace):
    skills = temp_workspace.get_skills()
    assert isinstance(skills, dict)
    assert "system_control" in skills
    assert "screen_and_touch" in skills
    assert "remote_terminal" in skills
    assert "script_automation" in skills


def test_agent_workspace_profile(temp_workspace):
    profile = temp_workspace.get_agent_profile()
    assert profile["agent_name"] == "Void Digital Twin"
    assert "active_engine" in profile
    assert profile["ram_limit_mb"] <= 2048
    assert profile["status"] == "Online & Autonomous"


def test_agent_workspace_record_and_get_tasks(temp_workspace):
    temp_workspace.record_task(
        query="Turn on flashlight and take photo",
        reasoning="Executing hardware flashlight tool and camera tool",
        tools_used=["torch_control", "take_camera_photo"],
        success=True,
        result_summary="Flashlight turned on and photo archived",
    )

    tasks = temp_workspace.get_recent_tasks(limit=5)
    assert len(tasks) == 1
    t = tasks[0]
    assert t["query"] == "Turn on flashlight and take photo"
    assert t["success"] is True
    assert "torch_control" in t["tools_used"]


def test_agent_workspace_save_and_run_script(temp_workspace):
    # Save a python script
    py_code = 'print("HELLO_FROM_AGENT_SCRIPT")'
    save_res = temp_workspace.save_script("test_job.py", py_code, description="Test job")
    assert save_res["success"] is True

    # List scripts
    scripts = temp_workspace.list_scripts()
    assert len(scripts) == 1
    assert scripts[0]["name"] == "test_job.py"
    assert scripts[0]["type"] == "Python"

    # Run script
    run_res = temp_workspace.run_script("test_job.py")
    assert run_res["success"] is True
    assert "HELLO_FROM_AGENT_SCRIPT" in run_res["output"]


def test_agent_workspace_run_script_not_found(temp_workspace):
    res = temp_workspace.run_script("non_existent_script_xyz.py")
    assert res["success"] is False
    assert "not found" in res["error"].lower()


def test_terminal_service_set_password():
    ts = TerminalService()
    # Test valid password
    res = ts.set_ssh_password("VoidSecurePass123")
    assert res["success"] is True
    assert "Password recorded for" in res["message"]

    # Test invalid short password
    short_res = ts.set_ssh_password("12")
    assert short_res["success"] is False
    assert "at least 4 characters" in short_res["error"]



def test_vision_agent_inspect_screen():
    va = VisionAgent()
    res = va.inspect_active_screen()
    assert res["success"] is True
    assert "image_path" in res
    assert "readable_summary" in res
    assert "Resolution" in res["readable_summary"]


def test_tool_registry_has_inspect_and_run_script():
    assert global_tool_registry.has_tool("inspect_screen")
    assert global_tool_registry.has_tool("see_screen")
    assert global_tool_registry.has_tool("run_automation_script")

    # Test executing inspect_screen tool via registry
    exec_res = global_tool_registry.execute("inspect_screen")
    assert exec_res.success is True
    assert "Resolution" in str(exec_res.output)
