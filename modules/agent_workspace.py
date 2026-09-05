"""
modules/agent_workspace.py - Digital Twin Agent State, History & Automation Scripts Workspace.

Provides:
1. Agent Identity & Active State Tracking (Engine, RAM cap, skills, tasks completed).
2. Persistent Task & Work History (~/.void/brain/tasks_history.json).
3. Agent Skills & Capabilities Registry (~/.void/brain/agent_skills.json).
4. Automation Scripts Workspace (~/.void/scripts/) for custom Python/Bash automation code.
"""

import os
import sys
import time
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional

from config.settings import global_config
from core.model_manager import global_model_manager

logger = logging.getLogger("VoidModules.AgentWorkspace")

SCRIPTS_DIR = os.path.expanduser("~/.void/scripts")
BRAIN_DIR = os.path.expanduser("~/.void/brain")
HISTORY_FILE = os.path.join(BRAIN_DIR, "tasks_history.json")
SKILLS_FILE = os.path.join(BRAIN_DIR, "agent_skills.json")


class AgentWorkspace:
    """Manages AI agent history, memory, loaded skills, and user automation scripts."""

    def __init__(self):
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        os.makedirs(BRAIN_DIR, exist_ok=True)
        self._init_skills_catalog()

    def _init_skills_catalog(self) -> None:
        """Populates default digital twin capabilities if not already present."""
        if not os.path.exists(SKILLS_FILE):
            default_skills = {
                "system_control": "Full Android hardware, flashlight, battery, volume, display controls",
                "screen_and_touch": "Coordinate tap, swipe gestures, typing, hardware keys simulation",
                "remote_terminal": "OpenSSH server management, live bash commands, process inspection",
                "cloud_vault_sync": "Bidirectional brain sync with Telegram group with auto hashtags",
                "media_and_camera": "Camera snapshots, photo archival, TTS, audio recording",
                "social_and_intents": "Direct WhatsApp, Telegram, Google Maps, UPI payments, Android Settings",
                "security_interceptor": "2FA/OTP SMS interceptor with clipboard auto-copy, call screening",
                "research_immersion": "Autonomous YouTube research, note syntheses, article web scraping",
                "script_automation": "Custom Python & Bash automation execution engine",
            }
            try:
                with open(SKILLS_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_skills, f, indent=2)
            except Exception as e:
                logger.debug(f"Could not initialize skills file: {e}")

    def get_agent_profile(self) -> Dict[str, Any]:
        """Returns live profile describing the active AI agent, its engine, and capabilities."""
        active_model = global_model_manager.get_active_model_name() or "Qwen2.5-0.5B / Deterministic ReAct"
        installed_models = global_model_manager.list_installed_models()
        compute = global_config.get_compute_profile()

        # Count completed tasks
        recent_tasks = self.get_recent_tasks(limit=100)

        # Count available scripts
        scripts = self.list_scripts()

        return {
            "agent_name": "Void Digital Twin",
            "active_engine": active_model,
            "installed_models_count": len(installed_models),
            "ram_limit_mb": compute.get("ram_limit_mb", 2048),
            "max_model_size_mb": compute.get("max_model_size_mb", 2000),
            "tasks_completed": len(recent_tasks),
            "automation_scripts_count": len(scripts),
            "workspace_dir": SCRIPTS_DIR,
            "brain_dir": BRAIN_DIR,
            "status": "Online & Autonomous",
        }

    def record_task(
        self,
        query: str,
        reasoning: str = "",
        tools_used: Optional[List[str]] = None,
        success: bool = True,
        result_summary: str = "",
    ) -> Dict[str, Any]:
        """Appends a completed task record to persistent brain history."""
        task_entry = {
            "timestamp": time.time(),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "reasoning": reasoning[:200] if reasoning else "",
            "tools_used": tools_used or [],
            "success": success,
            "result_summary": result_summary[:200] if result_summary else "",
        }

        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        history.append(task_entry)
        # Keep last 150 tasks bounded
        if len(history) > 150:
            history = history[-150:]

        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save task history: {e}")

        return task_entry

    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent task execution records from history."""
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history[-limit:]
        except Exception:
            return []

    def get_skills(self) -> Dict[str, str]:
        """Returns dictionary of all active capabilities."""
        if os.path.exists(SKILLS_FILE):
            try:
                with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    # ------------------------------------------------------------------
    # Automation Scripts Workspace (~/.void/scripts/)
    # ------------------------------------------------------------------
    def list_scripts(self) -> List[Dict[str, Any]]:
        """Scans ~/.void/scripts/ for user automation code."""
        if not os.path.exists(SCRIPTS_DIR):
            return []

        scripts = []
        try:
            for entry in os.scandir(SCRIPTS_DIR):
                if entry.is_file() and not entry.name.startswith("."):
                    stat = entry.stat()
                    scripts.append({
                        "name": entry.name,
                        "path": entry.path,
                        "size_bytes": stat.st_size,
                        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                        "type": "Python" if entry.name.endswith(".py") else ("Shell" if entry.name.endswith(".sh") else "Text"),
                    })
        except Exception as e:
            logger.debug(f"Error scanning scripts: {e}")

        return sorted(scripts, key=lambda s: s["name"])

    def save_script(self, name: str, code: str, description: str = "") -> Dict[str, Any]:
        """Saves an automation script to ~/.void/scripts/."""
        clean_name = os.path.basename(name.strip())
        if not clean_name:
            return {"success": False, "error": "Invalid script name."}

        target_path = os.path.join(SCRIPTS_DIR, clean_name)
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                if description and not code.startswith("#"):
                    f.write(f"# Description: {description}\n\n")
                f.write(code)

            # Make executable if shell script
            if clean_name.endswith(".sh"):
                os.chmod(target_path, 0o755)

            logger.info(f"Saved automation script: {target_path} ({len(code)} bytes)")
            return {
                "success": True,
                "name": clean_name,
                "path": target_path,
                "size_bytes": len(code),
                "message": f"Script '{clean_name}' saved to automation workspace.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_script(self, name: str, timeout: int = 60) -> Dict[str, Any]:
        """Executes a user automation script and captures stdout/stderr."""
        clean_name = os.path.basename(name.strip())
        target_path = os.path.join(SCRIPTS_DIR, clean_name)

        if not os.path.exists(target_path):
            # Try appending .py or .sh
            for ext in (".py", ".sh"):
                if os.path.exists(target_path + ext):
                    target_path = target_path + ext
                    clean_name = clean_name + ext
                    break

        if not os.path.exists(target_path):
            return {"success": False, "error": f"Script '{name}' not found in {SCRIPTS_DIR}."}

        try:
            if clean_name.endswith(".py"):
                cmd = [sys.executable, target_path]
            elif clean_name.endswith(".sh"):
                cmd = ["/bin/bash" if os.path.exists("/bin/bash") else "sh", target_path]
            else:
                cmd = ["sh", target_path]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=SCRIPTS_DIR,
            )

            output = (proc.stdout or "") + ("\n[STDERR]: " + proc.stderr if proc.stderr else "")
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "output": output.strip() or "(Script completed with no output)",
                "script": clean_name,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "returncode": -1, "error": f"Script timed out after {timeout}s."}
        except Exception as e:
            return {"success": False, "returncode": -1, "error": str(e)}


global_agent_workspace = AgentWorkspace()
