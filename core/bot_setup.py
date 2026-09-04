"""
core/bot_setup.py - Frictionless Telegram Bot Setup Wizard & Auto-Detection Engine.

Automates the complete bot onboarding process:
1. Token format & HTTP API handshake validation with getMe.
2. Zero-effort Telegram Admin ID auto-detection via getUpdates.
3. Instant test ping dispatch to verify end-to-end communication.
4. Secure atomic persistence to ~/.void/config.env with 0600 permissions.
"""

import os
import sys
import time
import logging
from typing import Optional, Tuple, Dict, Any

import requests

logger = logging.getLogger("VoidAdvancedCore.BotSetup")

CONFIG_FILE_PATH = os.path.expanduser("~/.void/config.env")


def load_config_env() -> Dict[str, str]:
    """Loads key-value pairs from ~/.void/config.env into os.environ if present."""
    config = {}
    if not os.path.isfile(CONFIG_FILE_PATH):
        return config

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                config[k] = v
                if k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        logger.warning(f"Could not load {CONFIG_FILE_PATH}: {e}")
    return config


class TelegramSetupWizard:
    """Guided wizard for Telegram Bot onboarding and auto-detection."""

    @staticmethod
    def validate_token_format(token: str) -> bool:
        """Verifies basic Telegram Bot token structure."""
        token = token.strip()
        if not token or ":" not in token or any(c.isspace() for c in token):
            return False
        parts = token.split(":", 1)
        return parts[0].isdigit() and len(parts[1]) >= 16

    @staticmethod
    def verify_bot_token(token: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates token against Telegram API via getMe.
        Returns (success, bot_username, error_message).
        """
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("ok"):
                username = data["result"].get("username", "UnknownBot")
                return True, username, None
            else:
                return False, None, data.get("description", "Unauthorized token")
        except Exception as e:
            return False, None, str(e)

    @staticmethod
    def listen_for_admin_id(token: str, timeout_seconds: int = 30) -> Tuple[Optional[int], Optional[str]]:
        """
        Listens to Telegram getUpdates to auto-detect incoming messages and extract Admin User ID.
        Returns (user_id, username_or_first_name).
        """
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        start_time = time.time()
        
        # Flush any existing unhandled updates first
        try:
            flush_resp = requests.get(f"{url}?offset=-1", timeout=5).json()
            last_id = 0
            if flush_resp.get("ok") and flush_resp.get("result"):
                last_id = flush_resp["result"][-1]["update_id"] + 1
        except Exception:
            last_id = 0

        while time.time() - start_time < timeout_seconds:
            try:
                resp = requests.get(f"{url}?offset={last_id}&timeout=3", timeout=6)
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        last_id = update["update_id"] + 1
                        msg = update.get("message") or update.get("callback_query", {}).get("message")
                        if msg and "from" in msg:
                            from_user = msg["from"]
                            user_id = from_user.get("id")
                            name = from_user.get("username") or from_user.get("first_name", "Admin")
                            if user_id:
                                return user_id, str(name)
            except Exception:
                pass
            time.sleep(1)

        return None, None

    @staticmethod
    def send_confirmation_ping(token: str, chat_id: int) -> bool:
        """Sends a verification greeting message to the newly whitelisted admin."""
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": (
                "⚡ *Void Platform Connected Successfully!*\n\n"
                "Your Telegram User ID is verified and whitelisted.\n"
                "You can now control Void directly using natural language or the interactive `/menu` dashboard."
            ),
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def save_configuration(cls, token: str, admin_id: Optional[int]) -> str:
        """Atomically saves credentials to ~/.void/config.env with 0600 permissions."""
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        content = [
            "# Void Platform Configuration (Auto-Generated by Setup Wizard)",
            f'TELEGRAM_TOKEN="{token}"',
        ]
        if admin_id:
            content.append(f'ADMIN_TELEGRAM_ID="{admin_id}"')

        content_str = "\n".join(content) + "\n"
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(content_str)

        # Restrict permissions: read/write strictly by current user (0600)
        try:
            os.chmod(CONFIG_FILE_PATH, 0o600)
        except Exception:
            pass

        os.environ["TELEGRAM_TOKEN"] = token
        if admin_id:
            os.environ["ADMIN_TELEGRAM_ID"] = str(admin_id)

        return CONFIG_FILE_PATH

    @classmethod
    def run_interactive(cls) -> bool:
        """Runs the complete terminal interactive setup wizard."""
        c_cyan = "\033[0;36m"
        c_green = "\033[0;32m"
        c_yellow = "\033[1;33m"
        c_red = "\033[0;31m"
        c_bold = "\033[1m"
        c_reset = "\033[0m"

        print(f"\n{c_bold}{c_cyan}================================================================")
        print("  🤖 VOID TELEGRAM BOT QUICK SETUP WIZARD")
        print(f"================================================================{c_reset}")
        print("Follow these 2 simple steps to connect your Telegram bot:")
        print(f"  1. Open Telegram, search for {c_bold}@BotFather{c_reset}")
        print(f"  2. Send {c_cyan}/newbot{c_reset}, choose a name & username, and copy the API token.")
        print("-" * 64)

        # Step 1: Input & Validate Token
        token = ""
        while True:
            try:
                raw = input(f"\n{c_bold}Enter Telegram Bot Token:{c_reset} ").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{c_yellow}[INFO] Setup cancelled.{c_reset}")
                return False

            if not raw:
                print(f"{c_red}Token cannot be empty. Please try again.{c_reset}")
                continue

            if not cls.validate_token_format(raw):
                print(f"{c_red}Invalid token format. Tokens usually look like: 123456789:ABCdefGhIJKlmNoP{c_reset}")
                continue

            print(f"{c_cyan}[INFO] Verifying token with Telegram servers...{c_reset}")
            valid, bot_user, err = cls.verify_bot_token(raw)
            if valid:
                token = raw
                print(f"{c_green}[SUCCESS] Connected to bot: @{bot_user}!{c_reset}")
                break
            else:
                print(f"{c_red}[ERROR] Telegram rejected token: {err}. Please re-enter.{c_reset}")

        # Step 2: Auto-Detect Admin ID
        print(f"\n{c_bold}{c_cyan}----------------------------------------------------------------")
        print("  📲 AUTO-DETECTING YOUR TELEGRAM USER ID")
        print(f"----------------------------------------------------------------{c_reset}")
        print(f"Now, open Telegram and send any message or tap {c_bold}/start{c_reset} to your bot: {c_cyan}@{bot_user}{c_reset}")
        print(f"{c_yellow}Listening for incoming message from you (waiting up to 30 seconds)...{c_reset}")

        admin_id, name = cls.listen_for_admin_id(token, timeout_seconds=30)

        if admin_id:
            print(f"\n{c_green}{c_bold}🎉 Detected message from {name} (User ID: {admin_id})!{c_reset}")
            print(f"{c_green}[SUCCESS] User ID {admin_id} whitelisted as primary Administrator.{c_reset}")
            cls.send_confirmation_ping(token, admin_id)
        else:
            print(f"\n{c_yellow}[NOTICE] Did not receive a message within 30 seconds.{c_reset}")
            manual = input("Enter your numeric Telegram User ID manually (or press Enter to skip): ").strip()
            if manual.isdigit():
                admin_id = int(manual)
                print(f"{c_green}[SUCCESS] Admin ID set to {admin_id}.{c_reset}")
            else:
                print(f"{c_yellow}[INFO] Admin ID left open. Anyone with access to your bot can issue commands.{c_reset}")

        # Step 3: Persist Configuration
        saved_path = cls.save_configuration(token, admin_id)
        print(f"\n{c_green}{c_bold}================================================================")
        print("  ⚡ SETUP COMPLETE & SECURELY SAVED!")
        print(f"================================================================{c_reset}")
        print(f"Config saved to: {c_cyan}{saved_path}{c_reset} (permissions 0600)")
        print(f"You can now launch the 24/7 background agent with: {c_cyan}void start-bg{c_reset}\n")
        return True


if __name__ == "__main__":
    TelegramSetupWizard.run_interactive()
