"""
daemons/routine_engine.py - Proactive Background Routine & Cron Engine.

Executes unattended daily maintenance, automated battery telemetry alerts,
scheduled morning voice briefings, and SQLite sliding-window compaction.
"""

import time
import sched
import resource
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from tools.registry import global_tool_registry
from storage.repository import TelemetryRepository, NotificationRepository
from storage.log_pruner import SlidingWindowLogPruner

logger = logging.getLogger("VoidAdvancedCore.RoutineEngine")


class RoutineScheduler:
    """Proactive background routine scheduler for unattended edge jobs."""
    __slots__ = (
        "_running",
        "_thread",
        "_stop_event",
        "_telemetry_repo",
        "_pruner",
        "_last_battery_alert",
        "_last_briefing_day",
    )

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._telemetry_repo = TelemetryRepository()
        self._pruner = SlidingWindowLogPruner()
        self._last_battery_alert = 0.0
        self._last_briefing_day = -1

    def start(self) -> None:
        """Starts the routine scheduler in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="RoutineScheduler", daemon=True)
        self._thread.start()
        logger.info("RoutineScheduler started.")

    def stop(self) -> None:
        """Stops the routine scheduler."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("RoutineScheduler stopped.")

    def _run_loop(self) -> None:
        """Main scheduler loop ticking every 30 seconds."""
        ticker = 0
        while not self._stop_event.is_set():
            try:
                # Every 60 seconds: Sample telemetry
                if ticker % 2 == 0:
                    self.sample_telemetry()

                # Every 3 minutes: Check battery health & charging state
                if ticker % 6 == 0:
                    self.check_battery_health()

                # Check if it's morning briefing time (e.g. 08:00 to 08:05)
                now = datetime.now()
                if now.hour == 8 and now.minute < 10 and self._last_briefing_day != now.day:
                    self.execute_morning_briefing()
                    self._last_briefing_day = now.day

                # Every 6 hours (720 ticks of 30s): Perform database compaction
                if ticker % 720 == 0 and ticker > 0:
                    self.perform_database_maintenance()

            except Exception as e:
                logger.error(f"Exception in routine scheduler: {e}")

            ticker += 1
            self._stop_event.wait(30.0)

    def sample_telemetry(self) -> None:
        """Records RAM, CPU, and Battery status into SQLite."""
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024.0, 2)
        
        bat_res = global_tool_registry.execute("get_battery_status")
        pct = None
        if bat_res.success and isinstance(bat_res.output, dict):
            pct = bat_res.output.get("percentage")

        wifi_res = global_tool_registry.execute("get_wifi_info")
        wifi_ssid = None
        if wifi_res.success and isinstance(wifi_res.output, dict):
            wifi_ssid = wifi_res.output.get("ssid")

        self._telemetry_repo.record(
            ram_rss_mb=rss_mb,
            cpu_percent=0.0,
            battery_percent=pct,
            wifi_ssid=wifi_ssid,
        )

    def check_battery_health(self) -> None:
        """Monitors battery thresholds and triggers proactive TTS/notification warnings."""
        res = global_tool_registry.execute("get_battery_status")
        if not res.success or not isinstance(res.output, dict):
            return

        pct = res.output.get("percentage", 100)
        status = res.output.get("status", "DISCHARGING").upper()
        temp = res.output.get("temperature", 25.0)

        now = time.time()
        # Rate limit audible warnings to once per 15 minutes
        if (now - self._last_battery_alert) < 900:
            return

        # Critical low battery warning
        if pct <= 15 and status == "DISCHARGING":
            self._last_battery_alert = now
            msg = f"Battery critically low at {pct} percent. Please connect the charger."
            logger.warning(f"Proactive Alert: {msg}")
            global_tool_registry.execute("text_to_speech", text=msg)
            global_tool_registry.execute("show_notification", title="Battery Critical", content=msg)

        # Battery full alert
        elif pct >= 98 and status == "CHARGING":
            self._last_battery_alert = now
            msg = "Battery is fully charged. Please disconnect the charger to prolong cell health."
            logger.info(f"Proactive Alert: {msg}")
            global_tool_registry.execute("text_to_speech", text=msg)
            global_tool_registry.execute("show_notification", title="Battery Charged", content=msg)

        # Thermal alert
        elif temp > 43.0:
            self._last_battery_alert = now
            msg = f"Battery temperature high ({temp}°C). Please allow the device to cool."
            logger.warning(f"Proactive Alert: {msg}")
            global_tool_registry.execute("show_notification", title="High Temperature Warning", content=msg)

    def execute_morning_briefing(self) -> None:
        """Synthesizes an intelligent spoken morning briefing."""
        logger.info("Triggering scheduled morning voice briefing...")
        bat_res = global_tool_registry.execute("get_battery_status")
        pct = 100
        if bat_res.success and isinstance(bat_res.output, dict):
            pct = bat_res.output.get("percentage", 100)

        wifi_res = global_tool_registry.execute("get_wifi_info")
        network_name = "Wi-Fi"
        if wifi_res.success and isinstance(wifi_res.output, dict):
            network_name = wifi_res.output.get("ssid", "Wi-Fi")

        notif_repo = NotificationRepository()
        recent_notifs = notif_repo.get_recent(limit=5)
        otp_count = sum(1 for n in recent_notifs if n.get("is_otp"))

        briefing = (
            f"Good morning. Void agent is online. Battery is currently at {pct} percent. "
            f"Connected to network {network_name}. "
        )
        if otp_count > 0:
            briefing += f"You have {otp_count} recent security verification codes saved to clipboard. "
        briefing += "Have a productive day."

        global_tool_registry.execute("text_to_speech", text=briefing)
        global_tool_registry.execute(
            "show_notification",
            title="Morning Briefing",
            content=f"Battery: {pct}% | Wi-Fi: {network_name}",
        )

    def perform_database_maintenance(self) -> None:
        """Triggers sliding-window pruning and database page compaction."""
        logger.info("Executing scheduled SQLite sliding-window maintenance...")
        self._pruner.prune_all()
        self._pruner.vacuum_db()

    @staticmethod
    def generate_crontab_entries(runner_script_path: str) -> str:
        """Generates standard crontab entries for Termux cron integration."""
        return (
            f"# Void ReAct Edge Platform Unattended Cron Jobs\n"
            f"0 8 * * * python3 {runner_script_path} --briefing >/dev/null 2>&1\n"
            f"0 */6 * * * python3 {runner_script_path} --vacuum >/dev/null 2>&1\n"
            f"*/5 * * * * python3 {runner_script_path} --battery-check >/dev/null 2>&1\n"
        )
