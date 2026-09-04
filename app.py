"""
app.py - Production Entrypoint: Web UI, Remote Telegram Control, and Proactive Daemons.

Enterprise-grade, high-performance, ultra-low-memory local agentic platform for Android/Termux.
Powered by Void ReAct Engine, Waitress production WSGI server, and ReAct state machine.
"""

import os
import sys
import signal
import logging
import argparse
import threading

# Prepend Termux binaries path dynamically
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX_BIN_PATH = os.path.join(PREFIX, "bin") if os.path.exists(PREFIX) else "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

from core.command_executor import IS_TERMUX
from api.web_server import run_web_server, create_app
from daemons.service_runner import global_daemon_supervisor
from telegram.bot_controller import AuthenticatedTelegramController
from security.credential_vault import CredentialVault

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("VoidMain")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Void ReAct Edge Platform for Android/Termux")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--threads", type=int, default=4, help="Waitress WSGI worker threads (default: 4)")
    parser.add_argument("--telegram", type=str, default=None, help="Telegram bot token")
    parser.add_argument("--admin-id", type=str, default=None, help="Whitelisted Admin Telegram User ID")
    parser.add_argument("--no-daemons", action="store_true", help="Disable background proactive daemons")
    parser.add_argument("--no-wake-lock", action="store_true", help="Disable CPU wake-lock (suppresses Termux wake lock notification)")
    parser.add_argument("--vault-pass", type=str, default=None, help="Passphrase to unlock encrypted credential vault")
    return parser.parse_args()


def setup_signal_handlers():
    def handle_shutdown(signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Initiating clean teardown...")
        global_daemon_supervisor.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)


def main():
    args = parse_arguments()
    setup_signal_handlers()

    print("=" * 65)
    print(" ⚡ VOID ADVANCED EDGE PLATFORM (Android/Termux Hardened)")
    print("=" * 65)
    print(f" Environment: {'Native Android (Termux)' if IS_TERMUX else 'Desktop Development Simulator'}")
    print(f" Web Dashboard: http://{args.host}:{args.port}")

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

    # 2. Start Proactive Automation Daemons
    if not args.no_daemons:
        logger.info("Initializing proactive automation daemons...")
        global_daemon_supervisor.set_wake_lock_enabled(not args.no_wake_lock)
        global_daemon_supervisor.start_all()
    else:
        logger.info("Proactive daemons disabled via --no-daemons flag.")

    # 3. Launch Authenticated Telegram Bot (if token provided)
    if telegram_token:
        logger.info("Starting authenticated Telegram bot controller in background thread...")
        admin_set = {int(admin_id)} if admin_id and str(admin_id).isdigit() else None
        tg_controller = AuthenticatedTelegramController(token=telegram_token, admin_ids=admin_set)
        tg_thread = threading.Thread(target=tg_controller.start_polling, name="TelegramBotThread", daemon=True)
        tg_thread.start()
    else:
        logger.info("Telegram remote control disabled (no token provided).")

    # 4. Launch Production Waitress WSGI Web Server with clean lifecycle management
    try:
        run_web_server(host=args.host, port=args.port, threads=args.threads)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down Void platform...")
    except Exception as e:
        logger.error(f"Unexpected web server exception: {e}")
    finally:
        logger.info("Executing clean daemon and wake-lock teardown...")
        global_daemon_supervisor.stop_all()


if __name__ == "__main__":
    main()
