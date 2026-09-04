"""
telegram/services/device_service.py - Multi-Device Node Registry & Remote Hardware Bridge.

Manages paired Android edge nodes, live telemetry heartbeats, and tool dispatching.
"""

import os
import time
import socket
import logging
from typing import List, Dict, Any, Optional

from telegram.database.models import Device
from telegram.database.db_manager import global_bot_db
from tools.registry import global_tool_registry

logger = logging.getLogger("VoidTelegram.Devices")


class DeviceService:
    """Manages Android edge devices, heartbeats, and telemetry bridging."""

    def __init__(self, db_manager=global_bot_db):
        self.db = db_manager

    def register_local_device(self, user_id: int, custom_name: Optional[str] = None) -> Device:
        """Auto-discovers and registers the local Termux environment as an active device."""
        hostname = socket.gethostname() or "Termux-Node"
        device_id = f"node_{abs(hash(hostname + str(user_id))) % 1000000:06d}"
        device_name = custom_name or f"Android Node ({hostname})"

        # Probe battery status
        bat_res = global_tool_registry.execute("get_battery_status")
        battery_pct = 100
        if bat_res.success and isinstance(bat_res.output, dict):
            battery_pct = bat_res.output.get("percentage", 100)

        device = Device(
            device_id=device_id,
            user_id=user_id,
            name=device_name,
            platform="Android / Termux",
            model=hostname,
            battery_level=battery_pct,
            is_online=True,
            last_seen_at=time.time(),
        )
        self.db.register_device(device)
        return device

    def list_user_devices(self, user_id: int) -> List[Device]:
        """Lists all registered devices for a user, auto-registering local if none exist."""
        devices = self.db.get_user_devices(user_id)
        if not devices:
            local = self.register_local_device(user_id)
            return [local]
        return devices

    def heartbeat(self, device_id: str, battery_level: int = 100) -> None:
        """Updates last seen timestamp and battery level for a node."""
        self.db.update_device_heartbeat(device_id, battery_level=battery_level, is_online=True)

    def dispatch_device_action(self, user_id: int, device_id: str, action: str, **kwargs) -> Dict[str, Any]:
        """
        Dispatches hardware tool action to targeted device.
        In edge Termux standalone deployment, maps directly to local tool registry.
        """
        logger.info(f"Dispatching action '{action}' to device {device_id} for user {user_id}")
        if action == "torch":
            on = kwargs.get("on", False)
            res = global_tool_registry.execute("set_torch", on=on)
            return {"success": res.success, "output": res.output, "error": res.error}
        elif action == "battery":
            res = global_tool_registry.execute("get_battery_status")
            return {"success": res.success, "output": res.output, "error": res.error}
        elif action == "clean":
            res = global_tool_registry.execute("clean_system", dry_run=False)
            return {"success": res.success, "output": res.output, "error": res.error}
        elif action == "photo":
            res = global_tool_registry.execute("take_camera_photo")
            return {"success": res.success, "output": res.output, "error": res.error}
        elif action == "app":
            app_name = kwargs.get("app_name", "")
            res = global_tool_registry.execute("launch_installed_app", app_name=app_name)
            return {"success": res.success, "output": res.output, "error": res.error}
        else:
            return {"success": False, "error": f"Unknown hardware action: {action}"}


global_device_service = DeviceService()
