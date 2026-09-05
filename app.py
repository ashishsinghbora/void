"""
app.py - Production Entrypoint: Autonomous Background Daemon & Telegram Control Hub.

Enterprise-grade, ultra-lightweight (< 30MB RAM), terminal-and-Telegram-native
autonomous edge agent platform for Android/Termux. Zero web server bloat.
"""

import os
import sys
import time
import signal
import logging
import argparse
import threading
import resource

# Prepend Termux binaries path dynamically
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX_BIN_PATH = os.path.join(PREFIX, "bin") if os.path.exists(PREFIX) else "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

from core.command_executor import IS_TERMUX
from daemons.service_runner import global_daemon_supervisor
from utils.async_runner import global_async_supervisor
from modules.notification_watcher import global_notification_watcher
from modules.scraper_vault import global_scraper_vault
from modules.brain_sync import global_brain_sync
from telegram.bot_controller import AuthenticatedTelegramController
from security.credential_vault import CredentialVault
from core.fastfetch import global_fastfetch_collector
from core.bot_setup import load_config_env, TelegramSetupWizard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("VoidMain")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Void Autonomous Edge Platform (Terminal & Telegram Native)")
    parser.add_argument("--telegram", type=str, default=None, help="Telegram bot token")
    parser.add_argument("--admin-id", type=str, default=None, help="Whitelisted Admin Telegram User ID")
    parser.add_argument("--no-daemons", action="store_true", help="Disable background proactive daemons")
    parser.add_argument("--no-wake-lock", action="store_true", help="Disable CPU wake-lock (suppresses Termux wake-lock notification)")
    parser.add_argument("--vault-pass", type=str, default=None, help="Passphrase to unlock encrypted credential vault")
    parser.add_argument("--setup", action="store_true", help="Launch interactive Telegram bot setup wizard")
    return parser.parse_args()


def setup_signal_handlers():
    def handle_shutdown(signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Initiating clean teardown...")
        global_notification_watcher.stop()
        global_scraper_vault.stop()
        global_brain_sync.stop()
        global_async_supervisor.stop()
        global_daemon_supervisor.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def main():
    load_config_env()
    args = parse_arguments()
    setup_signal_handlers()

    if args.setup:
        TelegramSetupWizard.run_interactive()
        return

    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024.0, 2)

    print("=" * 65)
    print(" ⚡ VOID AUTONOMOUS EDGE PLATFORM (Android / Termux Native)")
    print("=" * 65)
    print(f" Environment: {'Native Android (Termux)' if IS_TERMUX else 'Desktop Simulator'}")
    print(f" Memory RSS:  {rss_mb} MB (Target < 30MB)")
    print(f" Control:     Terminal CLI & Telegram Bot Interface")
    print("=" * 65)

    # 1. Resolve Credentials (CLI Arg -> Encrypted Vault -> Environment Variable)
    telegram_token = args.telegram
    admin_id = args.admin_id

    if args.vault_pass:
        try:
            vault_secrets = CredentialVault.load_vault(args.vault_pass)
            if not telegram_token and "TELEGRAM_TOKEN" in vault_secrets:
                telegram_token = vault_secrets["TELEGRAM_TOKEN"]
            if not admin_id and "ADMIN_TELEGRAM_ID" in vault_secrets:
                admin_id = vault_secrets["ADMIN_TELEGRAM_ID"]
            logger.info("Credentials successfully retrieved from AES-256 encrypted vault.")
        except Exception as e:
            logger.warning(f"Could not decrypt vault with provided passphrase: {e}")

    if not telegram_token:
        telegram_token = os.environ.get("TELEGRAM_TOKEN")
    if not admin_id and os.environ.get("ADMIN_TELEGRAM_ID"):
        admin_id = os.environ.get("ADMIN_TELEGRAM_ID")

    if admin_id:
        os.environ["ADMIN_TELEGRAM_ID"] = str(admin_id)

    # 2. Start Proactive Automation Daemons & Async Supervisor
    if not args.no_daemons:
        logger.info("Initializing proactive automation daemons...")
        global_daemon_supervisor.set_wake_lock_enabled(not args.no_wake_lock)
        global_daemon_supervisor.start_all()

        logger.info("Starting asynchronous background monitors (Notification, Scraper & Brain Sync)...")
        global_async_supervisor.start()
        global_async_supervisor.schedule_coroutine(global_notification_watcher.run_async_watcher(interval_seconds=2.0))
        global_async_supervisor.schedule_coroutine(global_scraper_vault.run_async_scraper(interval_seconds=300.0))
        global_async_supervisor.schedule_coroutine(global_brain_sync.run_async_sync(interval_seconds=60.0))
    else:
        logger.info("Proactive daemons disabled via --no-daemons flag.")

    # 3. Launch Authenticated Telegram Bot or Standby Loop
    try:
        if telegram_token:
            logger.info("Starting authenticated Telegram bot controller listener...")
            admin_set = {int(admin_id)} if admin_id and str(admin_id).isdigit() else None
            tg_controller = AuthenticatedTelegramController(token=telegram_token, admin_ids=admin_set)
            if tg_controller._bot:
                global_notification_watcher.bind_bot(tg_controller._bot)
                global_scraper_vault.bind_bot(tg_controller._bot)
                global_brain_sync.bind_bot(tg_controller._bot)
            tg_controller.start_polling()
        else:
            logger.info("Telegram remote control offline (no token configured).")
            logger.info("Void proactive background daemons are active. Press Ctrl+C to stop.")
            logger.info("To enable Telegram control: export TELEGRAM_TOKEN='your_token' or void start --telegram <token>")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down Void platform...")
    except Exception as e:
        logger.error(f"Unexpected service exception: {e}")
    finally:
        logger.info("Executing clean daemon and wake-lock teardown...")
        global_notification_watcher.stop()
        global_scraper_vault.stop()
        global_brain_sync.stop()
        global_async_supervisor.stop()
        global_daemon_supervisor.stop_all()


if __name__ == "__main__":
    main()
