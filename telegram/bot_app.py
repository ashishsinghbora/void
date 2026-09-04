"""
telegram/bot_app.py - Master Telegram Bot & Mini App Application Supervisor.

Coordinates SQLite WAL database initialization, authenticated controller lifecycle,
and the ultra-lightweight Telegram Mini App (TMA) background server.
"""

import os
import sys
import time
import signal
import logging
from typing import Optional, Set

from telegram.bot_controller import AuthenticatedTelegramController
from telegram.database.db_manager import global_bot_db
from telegram.webapp.server import MiniAppServer
from telegram.services.payment_service import global_payment_service
from telegram.services.device_service import global_device_service

logger = logging.getLogger("VoidTelegram.App")


class TelegramBotApp:
    """Master orchestrator for Void Telegram Bot and Mini App Ecosystem."""

    def __init__(
        self,
        token: Optional[str] = None,
        admin_ids: Optional[Set[int]] = None,
        enable_webapp: bool = True,
        webapp_port: int = 8080,
    ):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.admin_ids = admin_ids
        self.enable_webapp = enable_webapp
        self.webapp_port = webapp_port

        self.db = global_bot_db
        self.payment_service = global_payment_service
        self.device_service = global_device_service

        self.controller = AuthenticatedTelegramController(
            token=self.token,
            admin_ids=self.admin_ids,
        )
        self.webapp_server = MiniAppServer(
            host="0.0.0.0",
            port=self.webapp_port,
            bot_token=self.token,
        ) if self.enable_webapp else None

        self._running = False

    def start(self) -> None:
        """Starts background Mini App server and begins bot polling."""
        if not self.token:
            logger.error("Cannot start TelegramBotApp: TELEGRAM_BOT_TOKEN not provided.")
            return

        logger.info("Initializing Void Telegram Ecosystem...")
        self._running = True

        # 1. Start Mini App micro server
        if self.webapp_server:
            try:
                self.webapp_server.start()
                logger.info(f"TMA Server active at http://0.0.0.0:{self.webapp_port}")
            except Exception as e:
                logger.warning(f"Failed to start TMA webapp server on port {self.webapp_port}: {e}")

        # 2. Setup signal handlers for graceful shutdown
        def _signal_handler(sig, frame):
            logger.info("Shutdown signal received. Terminating Telegram ecosystem...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except Exception:
            pass

        # 3. Start single-threaded bot polling listener
        try:
            self.controller.start_polling()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Gracefully halts polling and background webapp server."""
        if not self._running:
            return
        self._running = False
        if self.webapp_server:
            self.webapp_server.stop()
        logger.info("Void Telegram Ecosystem stopped cleanly.")


def main():
    """CLI entrypoint for standalone execution."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    app = TelegramBotApp()
    app.start()


if __name__ == "__main__":
    main()
