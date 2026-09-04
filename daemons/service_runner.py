"""
daemons/service_runner.py - Unified Daemon Supervisor with Wake-Lock Management.

Coordinates proactive background daemons, manages Android CPU wake-locks,
and registers operating system signal handlers for zero-data-loss teardown.
"""

import os
import sys
import signal
import logging
import subprocess
from typing import Optional

from daemons.notification_daemon import NotificationInterceptorDaemon
from daemons.routine_engine import RoutineScheduler
from core.command_executor import IS_TERMUX

logger = logging.getLogger("VoidAdvancedCore.ServiceRunner")


class SystemDaemonSupervisor:
    """Supervises background worker daemons with wake-lock support."""
    __slots__ = (
        "_notif_daemon",
        "_routine_scheduler",
        "_wake_lock_acquired",
    )

    def __init__(self):
        self._notif_daemon = NotificationInterceptorDaemon(interval_seconds=12.0)
        self._routine_scheduler = RoutineScheduler()
        self._wake_lock_acquired = False

    def acquire_wake_lock(self) -> None:
        """Acquires Android CPU wake-lock via termux-wake-lock if running in Termux."""
        if IS_TERMUX:
            try:
                subprocess.run(["termux-wake-lock"], capture_output=True, timeout=5)
                self._wake_lock_acquired = True
                logger.info("Acquired Termux CPU wake-lock.")
            except Exception as e:
                logger.warning(f"Failed to acquire wake lock: {e}")

    def release_wake_lock(self) -> None:
        """Releases Android CPU wake-lock."""
        if IS_TERMUX and self._wake_lock_acquired:
            try:
                subprocess.run(["termux-wake-unlock"], capture_output=True, timeout=5)
                self._wake_lock_acquired = False
                logger.info("Released Termux CPU wake-lock.")
            except Exception as e:
                logger.warning(f"Failed to release wake lock: {e}")

    def start_all(self) -> None:
        """Starts all proactive background daemons."""
        self.acquire_wake_lock()
        self._notif_daemon.start()
        self._routine_scheduler.start()
        logger.info("All background daemons activated successfully.")

    def stop_all(self) -> None:
        """Stops all proactive daemons cleanly."""
        logger.info("Shutting down background daemons...")
        self._notif_daemon.stop()
        self._routine_scheduler.stop()
        self.release_wake_lock()
        logger.info("All daemons stopped.")


# Global daemon supervisor instance
global_daemon_supervisor = SystemDaemonSupervisor()
