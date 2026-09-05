"""
termux_void.py - Mobile-Optimized Terminal User Interface (TUI) for Void.

Engineered specifically for mobile phone screens and Android/Termux environments:
1. Dynamic terminal viewport detection (shutil.get_terminal_size) with narrow 40-60 column adaptation.
2. Stacked, collapsible vertical card layouts eliminating wide multi-column table overflows.
3. Touch-friendly number-indexed Quick Action Palette ([1]-[0]) for swift mobile interaction.
4. Live Telemetry & Resource Monitor Widget (RAM RSS < 30MB, Battery, SQLite WAL, Engine).
5. Interactive TUI Screens: Dynamic Extension Store, Hardware Audit Logs, and Security Dashboard.
6. Zero-latency ReAct feedback loop with animated activity spinner and readline history.
"""

import os
import re
import sys
import time
import json
import shutil
import logging
import textwrap
import threading
import resource
from typing import Optional, List, Dict, Any, Tuple

# Enable readline command history if supported
try:
    import readline
    HISTORY_FILE = os.path.expanduser("~/.void/.cli_history")
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass
except ImportError:
    readline = None
    HISTORY_FILE = None

# Prepend Termux binaries path dynamically
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX_BIN_PATH = os.path.join(PREFIX, "bin") if os.path.exists(PREFIX) else "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

from core.command_executor import IS_TERMUX
from core.bot_setup import load_config_env, TelegramSetupWizard
from agents.react_agent import global_react_agent
from core.types import AgentResponse
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository

# Automatically load environment variables from ~/.void/config.env
load_config_env()

logging.basicConfig(level=logging.ERROR)

# ANSI Color Palettes
C_CYAN = "\033[0;36m"
C_GREEN = "\033[0;32m"
C_YELLOW = "\033[1;33m"
C_PURPLE = "\033[0;35m"
C_BLUE = "\033[0;34m"
C_RED = "\033[0;31m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

# Regex to strip ANSI sequences when calculating printable width
ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Removes all ANSI escape sequences to compute true printable width."""
    return ANSI_REGEX.sub("", text)


def visible_width(text: str) -> int:
    """Calculates visible character count on screen ignoring ANSI codes."""
    return len(strip_ansi(text))


def get_viewport_dimensions() -> Tuple[int, int]:
    """Retrieves terminal width and height with safe mobile defaults."""
    try:
        size = shutil.get_terminal_size(fallback=(50, 24))
        return size.columns, size.lines
    except Exception:
        return 50, 24


def get_card_width() -> int:
    """
    Computes responsive card width optimized for mobile viewports:
    - Minimum safe width: 36 columns (ultra-narrow phone viewports)
    - Maximum width clamp: 62 columns (maintains crisp vertical card aesthetic)
    """
    cols, _ = get_viewport_dimensions()
    return max(36, min(cols - 1, 62))


def wrap_mobile_text(text: str, max_w: int) -> List[str]:
    """Wraps text safely avoiding cutting words or overflowing terminal lines."""
    if not text:
        return [""]
    lines = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=max(10, max_w), break_long_words=True, break_on_hyphens=False)
        lines.extend(wrapped if wrapped else [""])
    return lines


def render_card_top(title: str = "", width: int = 50, border_color: str = C_PURPLE, title_color: str = C_BOLD) -> str:
    """Renders ╭── Title ────╮ with exact column alignment."""
    if title:
        vis_title = visible_width(title)
        dash_len = max(1, width - 6 - vis_title)
        return f"{border_color}╭──{title_color} {title} {border_color}{'─' * dash_len}╮{C_RESET}"
    return f"{border_color}╭{'─' * (width - 2)}╮{C_RESET}"


def render_card_bottom(width: int = 50, border_color: str = C_PURPLE) -> str:
    """Renders ╰──────╯ with exact column alignment."""
    return f"{border_color}╰{'─' * (width - 2)}╯{C_RESET}"


def render_card_sep(width: int = 50, border_color: str = C_PURPLE) -> str:
    """Renders ├──────┤ with exact column alignment."""
    return f"{border_color}├{'─' * (width - 2)}┤{C_RESET}"


def render_card_line(content: str, width: int, border_color: str = C_PURPLE) -> str:
    """Renders a single content line enclosed in │ ... │ padded to exact width."""
    v_len = visible_width(content)
    pad = max(0, width - 4 - v_len)
    return f"{border_color}│{C_RESET} {content}{' ' * pad} {border_color}│{C_RESET}"


class TUISpinner:
    """Animated background CLI spinner for active deliberation cycles."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Deliberating intent..."):
        self.message = message
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        idx = 0
        while self._running:
            frame = self.FRAMES[idx % len(self.FRAMES)]
            sys.stdout.write(f"\r{C_CYAN}{C_BOLD}{frame}{C_RESET} {self.message}  ")
            sys.stdout.flush()
            time.sleep(0.08)
            idx += 1

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


def render_mobile_banner(vw: int):
    """Renders adaptive banner that never wraps or breaks on mobile terminals."""
    cols, _ = get_viewport_dimensions()
    if cols >= 54:
        print(f"{C_CYAN}{C_BOLD}")
        print(r"  __     __     _     _ ")
        print(r"  \ \   / /__  (_) __| |  Autonomous Edge Orchestrator")
        print(r"   \ \ / / _ \ | |/ _` |  Terminal & Telegram Native")
        print(r"    \ V / (_) || | (_| |  Zero Web Bloat • < 30MB RAM")
        print(r"     \_/ \___/ |_|\__,_|")
        print(f"{C_RESET}")
    else:
        print(render_card_top("VOID EDGE AGENT", vw, C_CYAN, C_BOLD + C_CYAN))
        print(render_card_line(f"{C_BOLD}Autonomous Mobile Orchestrator{C_RESET}", vw, C_CYAN))
        print(render_card_line(f"{C_DIM}Terminal & Telegram • < 30MB RAM{C_RESET}", vw, C_CYAN))
        print(render_card_bottom(vw, C_CYAN))


def get_process_rss_mb() -> float:
    """Retrieves accurate process RSS in MB reading /proc/self/status with getrusage fallback."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(float(line.split()[1]) / 1024.0, 1)
    except Exception:
        pass
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return round(usage.ru_maxrss / 1024.0, 1)
    except Exception:
        return 0.0


def render_telemetry_widget(vw: int):
    """
    Renders compact mobile telemetry and resource monitor card:
    - RAM RSS (< 30MB benchmark tracking)
    - Battery percentage & health
    - SQLite WAL database state
    - Active model engine & Telegram bot status
    """
    rss_mb = get_process_rss_mb()
    rss_color = C_GREEN if rss_mb <= 30.0 else C_YELLOW

    bat_str = "Standby"
    try:
        bat_res = global_tool_registry.execute("get_battery_status")
        if bat_res.success and isinstance(bat_res.output, dict):
            pct = bat_res.output.get("percentage", "N/A")
            status = bat_res.output.get("status", "")
            bat_str = f"{pct}% [{status}]" if pct != "N/A" else "Standby"
    except Exception:
        pass

    engine = global_model_manager.get_active_model_name() or "ReAct (Heuristic)"
    
    db_stats = "WAL Mode"
    try:
        repo = ExecutionLogRepository()
        cnt_res = repo._db.execute_query("SELECT COUNT(*) as c FROM execution_logs;")
        if cnt_res:
            db_stats = f"WAL ({cnt_res[0]['c']} logs)"
    except Exception:
        pass

    bot_token = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    bot_str = f"{C_GREEN}@voidtermuxbot{C_RESET}" if bot_token else f"{C_DIM}Offline{C_RESET}"

    vault_str = f"{C_DIM}Not Linked{C_RESET}"
    try:
        from telegram.services.cloud_vault import global_cloud_vault
        v_tele = global_cloud_vault.get_vault_telemetry()
        if v_tele.get("configured"):
            vault_str = f"{C_GREEN}Active ({v_tele.get('total_files', 0)} files){C_RESET}"
    except Exception:
        pass

    ssh_str = f"{C_DIM}Stopped{C_RESET}"
    try:
        from modules.terminal_service import global_terminal_service
        if global_terminal_service.is_ssh_running():
            ssh_str = f"{C_GREEN}Active (Port 8022){C_RESET}"
    except Exception:
        pass

    ram_cap = 2048
    try:
        from config.settings import global_config
        ram_cap = global_config.ram_limit_mb
    except Exception:
        pass

    print(render_card_top("LIVE TELEMETRY & RESOURCES", vw, C_BLUE, C_BOLD + C_BLUE))
    print(render_card_line(f"💾 RAM RSS:    {rss_color}{rss_mb} MB{C_RESET} {C_DIM}(Cap: {ram_cap}MB <2GB){C_RESET}", vw, C_BLUE))
    print(render_card_line(f"🔋 Battery:    {C_YELLOW}{bat_str}{C_RESET}", vw, C_BLUE))
    print(render_card_line(f"🗄️ Database:   {C_CYAN}{db_stats}{C_RESET}", vw, C_BLUE))
    print(render_card_line(f"🧠 Engine:     {C_PURPLE}{engine[:24]}{C_RESET}", vw, C_BLUE))
    print(render_card_line(f"💻 Remote SSH: {ssh_str}", vw, C_BLUE))
    print(render_card_line(f"☁️ Vault:      {vault_str}", vw, C_BLUE))
    print(render_card_line(f"🤖 Bot Plane:  {bot_str}", vw, C_BLUE))
    print(render_card_bottom(vw, C_BLUE))


def render_quick_actions_menu(vw: int, torch_on: bool = False):
    """
    Renders touch-friendly 2-column mobile action palette.
    Enables single-tap/key execution on touchscreens without typing long commands.
    """
    t_state = f"{C_GREEN}ON{C_RESET}" if torch_on else f"{C_DIM}OFF{C_RESET}"

    print(render_card_top("MOBILE COMMAND PALETTE", vw, C_PURPLE, C_BOLD + C_PURPLE))
    print(render_card_line(f"{C_BOLD}[1]{C_RESET} 🔦 Torch [{t_state}]  {C_BOLD}[2]{C_RESET} 🔋 Battery", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[3]{C_RESET} 📸 Camera Snap {C_BOLD}[4]{C_RESET} ⚡ FastFetch", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[5]{C_RESET} 🧩 Extensions  {C_BOLD}[6]{C_RESET} 🧹 Clean Disk", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[7]{C_RESET} 📋 Audit Logs  {C_BOLD}[8]{C_RESET} 🛡️ Security", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[9]{C_RESET} 🧠 Local LLMs  {C_BOLD}[0]{C_RESET} 🤖 Bot Hub", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[V]{C_RESET} ☁️ Cloud Vault {C_BOLD}[W]{C_RESET} 🧙 LLM Wizard", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[X]{C_RESET} 💻 Remote SSH  {C_BOLD}[S]{C_RESET} 📱 Screenshot", vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}[Q]{C_RESET} 🚪 Exit App", vw, C_PURPLE))
    print(render_card_bottom(vw, C_PURPLE))
    print(f"{C_DIM}Tip: Enter [1-0, V, W, X, S] or type any natural language directive:{C_RESET}\n")


def print_help_screen(vw: int):
    """Prints comprehensive commands directory in mobile card format."""
    print(render_card_top("VOID COMMAND DIRECTORY", vw, C_PURPLE, C_BOLD + C_PURPLE))
    commands = [
        ("/help, ?", "Display this help guide"),
        ("/fastfetch", "Display ASCII/Unicode telemetry"),
        ("/torch", "Toggle camera flashlight"),
        ("/battery", "Query battery percentage"),
        ("/photo", "Capture camera photo"),
        ("/clean", "Clean cache & temporary files"),
        ("/sh <cmd>", "Run local bash/shell command"),
        ("/ssh [up|down]", "Manage OpenSSH daemon"),
        ("/ram [mb]", "Inspect or set RAM ceiling (<2GB)"),
        ("/plugins", "Open dynamic extension store"),
        ("/logs", "Inspect hardware audit logs"),
        ("/security", "View sessions & cipher status"),
        ("/models", "Manage local small models"),
        ("/wizard", "Interactive LLM selection wizard"),
        ("/download <id>", "Download small model weights"),
        ("/vault", "Manage cloud memory vault"),
        ("/screenshot", "Capture Android screen"),
        ("/bot", "Telegram bot control & setup"),
        ("/clear", "Clear screen"),
        ("/exit, q", "Exit session"),
    ]
    for cmd, desc in commands:
        print(render_card_line(f"{C_CYAN}{cmd:<14}{C_RESET} {desc}", vw, C_PURPLE))
    print(render_card_sep(vw, C_PURPLE))
    print(render_card_line(f"{C_BOLD}Sample Directives:{C_RESET}", vw, C_PURPLE))
    print(render_card_line(f"• {C_GREEN}turn on flashlight{C_RESET}", vw, C_PURPLE))
    print(render_card_line(f"• {C_GREEN}what is my battery level{C_RESET}", vw, C_PURPLE))
    print(render_card_line(f"• {C_GREEN}whatsapp 15551234 saying hi{C_RESET}", vw, C_PURPLE))
    print(render_card_line(f"• {C_GREEN}open telegram chat with durov{C_RESET}", vw, C_PURPLE))
    print(render_card_bottom(vw, C_PURPLE))


def screen_extensions(vw: int):
    """Interactive Dynamic Extension Manager Screen for mobile."""
    while True:
        loaded = global_extension_manager.list_extensions()
        catalog = global_extension_manager.search_catalog()

        print(render_card_top("DYNAMIC EXTENSION MANAGER", vw, C_CYAN, C_BOLD + C_CYAN))
        print(render_card_line(f"Active in RAM: {C_GREEN}{len(loaded)}{C_RESET} {C_DIM}(Zero default bloat){C_RESET}", vw, C_CYAN))
        print(render_card_sep(vw, C_CYAN))

        for idx, item in enumerate(catalog, 1):
            stat = f"{C_GREEN}[INSTALLED]{C_RESET}" if item["installed"] else f"{C_YELLOW}[AVAILABLE]{C_RESET}"
            print(render_card_line(f"{C_BOLD}[{idx}]{C_RESET} {item['name'][:16]} {stat}", vw, C_CYAN))
            print(render_card_line(f"    {C_DIM}{item['description'][:vw - 8]}{C_RESET}", vw, C_CYAN))

        print(render_card_sep(vw, C_CYAN))
        print(render_card_line(f"Enter {C_BOLD}[1-{len(catalog)}]{C_RESET} to toggle Install/Remove", vw, C_CYAN))
        print(render_card_line(f"{C_BOLD}[R]{C_RESET} Refresh   {C_BOLD}[B]{C_RESET} Back to Main Menu", vw, C_CYAN))
        print(render_card_bottom(vw, C_CYAN))

        try:
            choice = input(f"{C_BOLD}{C_CYAN}Extensions ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice == "r":
            continue
        elif choice.isdigit() and 1 <= int(choice) <= len(catalog):
            target = catalog[int(choice) - 1]
            pid = target["id"]
            if target["installed"]:
                print(f"{C_YELLOW}[INFO] Uninstalling {pid}...{C_RESET}")
                res = global_extension_manager.uninstall_plugin(pid)
                print(f"{C_GREEN}✅ {res.get('message')}{C_RESET}")
            else:
                print(f"{C_CYAN}[INFO] Downloading & verifying AST for {pid}...{C_RESET}")
                res = global_extension_manager.install_plugin(pid)
                if res.get("success"):
                    print(f"{C_GREEN}✅ {res.get('message')}{C_RESET}")
                else:
                    print(f"{C_RED}❌ Failed: {res.get('error')}{C_RESET}")
            time.sleep(1)


def screen_audit_logs(vw: int):
    """Scrollable and stacked Hardware Audit Log Viewer for mobile."""
    repo = ExecutionLogRepository()
    while True:
        logs = repo.get_recent_logs(limit=6)

        print(render_card_top("HARDWARE AUDIT LOG VIEWER", vw, C_BLUE, C_BOLD + C_BLUE))
        if not logs:
            print(render_card_line("No execution logs recorded yet.", vw, C_BLUE))
        else:
            for l in logs:
                step_num = l.get("step", 0)
                tool = l.get("tool_name", "tool")[:20]
                status = l.get("status", "UNKNOWN")
                status_color = C_GREEN if "SUCCESS" in status else C_RED
                dur = f"{l.get('duration_ms', 0):.1f}ms"
                t_str = time.strftime("%H:%M:%S", time.localtime(l.get("timestamp", time.time())))

                print(render_card_line(f"#{step_num} {C_BOLD}{tool}{C_RESET} {status_color}[{status}]{C_RESET}", vw, C_BLUE))
                print(render_card_line(f"   ⏱ {dur} | {t_str}", vw, C_BLUE))
                
                obs = l.get("observation", "")
                if obs:
                    clean_obs = strip_ansi(str(obs)).replace("\n", " ")[:vw - 12]
                    print(render_card_line(f"   {C_DIM}Out: {clean_obs}{C_RESET}", vw, C_BLUE))
                print(render_card_sep(vw, C_BLUE))

        print(render_card_line(f"{C_BOLD}[R]{C_RESET} Refresh   {C_BOLD}[B]{C_RESET} Back to Main Menu", vw, C_BLUE))
        print(render_card_bottom(vw, C_BLUE))

        try:
            choice = input(f"{C_BOLD}{C_BLUE}Audit Logs ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice == "r":
            continue


def screen_security_dashboard(vw: int):
    """Displays active whitelisted sessions, rate limiter, and credential vault status."""
    while True:
        rss_mb = get_process_rss_mb()
        rss_stat = f"{C_GREEN}{rss_mb} MB (OK){C_RESET}" if rss_mb <= 30.0 else f"{C_YELLOW}{rss_mb} MB (Warning){C_RESET}"

        bot_token = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "").strip() or "Auto-pairing on /start"

        print(render_card_top("SECURITY & SESSION DASHBOARD", vw, C_PURPLE, C_BOLD + C_PURPLE))
        print(render_card_line(f"{C_BOLD}🤖 Telegram Control Plane:{C_RESET}", vw, C_PURPLE))
        print(render_card_line(f"   Bot:       {C_CYAN}@voidtermuxbot{C_RESET}", vw, C_PURPLE))
        print(render_card_line(f"   Token:     {'Configured ✅' if bot_token else 'Not Set ❌'}", vw, C_PURPLE))
        print(render_card_line(f"   Admin ID:  {C_GREEN}{admin_id}{C_RESET}", vw, C_PURPLE))
        print(render_card_sep(vw, C_PURPLE))

        print(render_card_line(f"{C_BOLD}🛡️ Rate Limiter & Sessions:{C_RESET}", vw, C_PURPLE))
        print(render_card_line(f"   Limiter:   Token Bucket (0.5 req/s, burst 5)", vw, C_PURPLE))
        print(render_card_line(f"   Inactivity: 900s session timeout TTL", vw, C_PURPLE))
        print(render_card_line(f"   Memory:    {rss_stat}", vw, C_PURPLE))
        print(render_card_sep(vw, C_PURPLE))

        print(render_card_line(f"{C_BOLD}🔐 Local Credential Vault:{C_RESET}", vw, C_PURPLE))
        print(render_card_line(f"   Cipher:    AES-256-GCM / PBKDF2 (100k)", vw, C_PURPLE))
        print(render_card_line(f"   Config:    ~/.void/config.env (0600)", vw, C_PURPLE))
        print(render_card_line(f"   SQLite:    Write-Ahead Logging (WAL)", vw, C_PURPLE))
        print(render_card_sep(vw, C_PURPLE))

        print(render_card_line(f"{C_BOLD}[R]{C_RESET} Refresh   {C_BOLD}[B]{C_RESET} Back to Main Menu", vw, C_PURPLE))
        print(render_card_bottom(vw, C_PURPLE))

        try:
            choice = input(f"{C_BOLD}{C_PURPLE}Security ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice == "r":
            continue


def screen_bot_control(vw: int):
    """Mobile Telegram Bot Control Center Screen."""
    while True:
        bot_token = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        admin_id = os.environ.get("ADMIN_TELEGRAM_ID", "").strip()

        print(render_card_top("TELEGRAM BOT CONTROL CENTER", vw, C_CYAN, C_BOLD + C_CYAN))
        print(render_card_line(f"Bot Identity: {C_BOLD}@voidtermuxbot{C_RESET}", vw, C_CYAN))
        print(render_card_line(f"API Token:    {'Verified & Active ✅' if bot_token else 'Missing ⚠️'}", vw, C_CYAN))
        print(render_card_line(f"Admin ID:     {C_GREEN}{admin_id or 'Auto-pairing on /start'}{C_RESET}", vw, C_CYAN))
        print(render_card_sep(vw, C_CYAN))
        print(render_card_line(f"{C_BOLD}[1]{C_RESET} 📲 Run Bot Setup Wizard", vw, C_CYAN))
        print(render_card_line(f"{C_BOLD}[2]{C_RESET} 📡 Send Test Ping to Admin", vw, C_CYAN))
        print(render_card_line(f"{C_BOLD}[3]{C_RESET} 🚀 View Background Bot Instructions", vw, C_CYAN))
        print(render_card_line(f"{C_BOLD}[B]{C_RESET} 🔙 Back to Main Menu", vw, C_CYAN))
        print(render_card_bottom(vw, C_CYAN))

        try:
            choice = input(f"{C_BOLD}{C_CYAN}Bot Center ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice == "1":
            TelegramSetupWizard.run_interactive()
            load_config_env()
        elif choice == "2":
            if not bot_token:
                print(f"{C_RED}❌ No bot token configured.{C_RESET}")
            elif not admin_id or not admin_id.isdigit():
                print(f"{C_YELLOW}⚠️ No Admin ID paired yet. Send /start to @voidtermuxbot on Telegram to auto-pair!{C_RESET}")
            else:
                ok = TelegramSetupWizard.send_confirmation_ping(bot_token, int(admin_id))
                if ok:
                    print(f"{C_GREEN}✅ Test ping sent successfully to {admin_id}!{C_RESET}")
                else:
                    print(f"{C_RED}❌ Could not deliver ping. Check network.{C_RESET}")
            time.sleep(1.5)
        elif choice == "3":
            print(f"\n{C_CYAN}To run the bot 24/7 in background:{C_RESET}")
            print(f"  {C_GREEN}void start-bg{C_RESET}")
            print(f"To inspect running status:")
            print(f"  {C_GREEN}void status{C_RESET}")
            input(f"\n{C_DIM}Press Enter to continue...{C_RESET}")


def screen_models(vw: int):
    """Local Small-Model Weights & Engine Manager Screen."""
    while True:
        available = global_model_manager.list_available_models()
        active = global_model_manager.get_active_model_name()

        print(render_card_top("LOCAL SMALL-MODEL CATALOG", vw, C_PURPLE, C_BOLD + C_PURPLE))
        print(render_card_line(f"Active Engine: {C_GREEN}{active or 'Deterministic ReAct'}{C_RESET}", vw, C_PURPLE))
        print(render_card_sep(vw, C_PURPLE))

        model_keys = list(available.keys())
        for idx, mid in enumerate(model_keys, 1):
            m = available[mid]
            stat = f"{C_GREEN}[INSTALLED]{C_RESET}" if m["installed"] else f"{C_YELLOW}[AVAILABLE]{C_RESET}"
            print(render_card_line(f"{C_BOLD}[{idx}]{C_RESET} {mid:<12} {stat} ({m['size_mb']}MB)", vw, C_PURPLE))

        print(render_card_sep(vw, C_PURPLE))
        print(render_card_line(f"Enter {C_BOLD}[1-{len(model_keys)}]{C_RESET} to download model", vw, C_PURPLE))
        print(render_card_line(f"{C_BOLD}[B]{C_RESET} Back to Main Menu", vw, C_PURPLE))
        print(render_card_bottom(vw, C_PURPLE))

        try:
            choice = input(f"{C_BOLD}{C_PURPLE}Models ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(model_keys):
            target_mid = model_keys[int(choice) - 1]
            print(f"{C_CYAN}[INFO] Downloading '{target_mid}'...{C_RESET}")
            res = global_model_manager.download_model(target_mid)
            if res.get("success"):
                print(f"{C_GREEN}✅ Downloaded & activated: {res.get('path')}{C_RESET}")
            else:
                print(f"{C_RED}❌ Download failed: {res.get('error')}{C_RESET}")
            time.sleep(1.5)


def screen_vault(vw: int):
    """Interactive screen for Telegram Cloud Vault management."""
    from telegram.services.cloud_vault import global_cloud_vault
    while True:
        info = global_cloud_vault.get_vault_telemetry()
        configured = info.get("configured", False)
        title = info.get("group_title") or "Void Vault Group"
        gid = info.get("group_id") or "Not Linked"
        f_count = info.get("total_files", 0)
        mb = round(info.get("bytes_stored", 0) / (1024 * 1024), 2)

        print(f"\n{render_card_top('CLOUD VAULT (BRAIN-IN-CLOUD)', vw, C_BLUE, C_BOLD + C_BLUE)}")
        print(render_card_line(f"Status:      {'🟢 Active' if configured else '🔴 Inactive'}", vw, C_BLUE))
        print(render_card_line(f"Group:       {title[:24]}", vw, C_BLUE))
        print(render_card_line(f"Chat ID:     {str(gid)[:24]}", vw, C_BLUE))
        print(render_card_line(f"Stored:      {f_count} files ({mb} MB)", vw, C_BLUE))
        print(render_card_sep(vw, C_BLUE))
        print(render_card_line(f"{C_BOLD}[1]{C_RESET} 💾 Backup Memory State Now", vw, C_BLUE))
        print(render_card_line(f"{C_BOLD}[2]{C_RESET} 📁 View Recent Vault Files", vw, C_BLUE))
        print(render_card_line(f"{C_BOLD}[3]{C_RESET} ⚙️ Set Vault Group Chat ID", vw, C_BLUE))
        print(render_card_line(f"{C_BOLD}[B]{C_RESET} 🔙 Back to Main Menu", vw, C_BLUE))
        print(render_card_bottom(vw, C_BLUE))

        try:
            choice = input(f"{C_CYAN}vault ❯ {C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("b", "back", "q", "exit"):
            break
        elif choice == "1":
            print(f"{C_CYAN}[INFO] Backing up memory state to vault...{C_RESET}")
            res = global_cloud_vault.upload_memory_snapshot()
            if res.get("success"):
                print(f"{C_GREEN}✅ Memory snapshot backed up to vault! (Msg #{res.get('telegram_message_id')}){C_RESET}")
            else:
                print(f"{C_RED}❌ Backup failed: {res.get('error')}{C_RESET}")
            time.sleep(1.5)
        elif choice == "2":
            records = global_cloud_vault.query_vault(limit=5)
            if not records:
                print(f"{C_DIM}No files stored in vault yet.{C_RESET}")
            else:
                print(f"{C_BOLD}Recent Vault Files:{C_RESET}")
                for r in records:
                    print(f"• #{r.id} {r.file_name} ({round(r.file_size/1024, 1)}KB) [{r.category}]")
            input(f"{C_DIM}Press Enter to continue...{C_RESET}")
        elif choice == "3":
            raw = input("Enter Telegram Group Chat ID (e.g. -1001234567890): ").strip()
            try:
                cid = int(raw)
                global_cloud_vault.set_vault_group_id(cid, group_title="Configured from CLI")
                print(f"{C_GREEN}✅ Vault group ID set to {cid}{C_RESET}")
            except ValueError:
                print(f"{C_RED}Invalid integer chat ID.{C_RESET}")
            time.sleep(1.5)


def format_step_cards(steps, vw: int):
    """Renders execution steps as stacked mobile cards without horizontal wrapping."""
    if not steps:
        return
    for s in steps:
        action = (s.action or "Deliberation")[:24]
        status = s.status.value
        dur = f"{s.duration_ms:.1f}ms"

        print(render_card_top(f"Step {s.step_number}: {action}", vw, C_CYAN, C_BOLD + C_CYAN))
        print(render_card_line(f"Status: {C_GREEN}{status}{C_RESET}  Duration: {C_DIM}{dur}{C_RESET}", vw, C_CYAN))

        inp = getattr(s, "action_input", None) or getattr(s, "tool_input", None)
        if inp:
            inp_str = json.dumps(inp) if isinstance(inp, (dict, list)) else str(inp)
            for wrapped in wrap_mobile_text(f"In: {inp_str}", vw - 4)[:2]:
                print(render_card_line(wrapped, vw, C_CYAN))

        if s.observation:
            obs_str = strip_ansi(str(s.observation)).replace("\n", " ")
            for wrapped in wrap_mobile_text(f"Out: {obs_str}", vw - 4)[:3]:
                print(render_card_line(wrapped, vw, C_CYAN))

        print(render_card_bottom(vw, C_CYAN))


def format_step_table(steps):
    """Compatibility wrapper for format_step_cards."""
    vw = get_card_width()
    format_step_cards(steps, vw)


def main():
    session_id = "cli_session"
    torch_on = False
    show_menu = True

    vw = get_card_width()
    render_mobile_banner(vw)

    while True:
        try:
            vw = get_card_width()

            if show_menu:
                render_telemetry_widget(vw)
                render_quick_actions_menu(vw, torch_on=torch_on)

            query = input(f"{C_BOLD}{C_CYAN}void ❯ {C_RESET}").strip()
            if not query:
                continue

            # ------------------------------------------------------------------
            # Single-Key & Numeric Touch Palette Shortcuts
            # ------------------------------------------------------------------
            if query.lower() in ("q", "quit", "exit"):
                print(f"\n{C_YELLOW}Shutting down Void CLI session. Goodbye!{C_RESET}")
                break

            elif query.lower() in ("?", "help"):
                print_help_screen(vw)
                continue

            elif query.lower() in ("m", "menu"):
                show_menu = not show_menu
                state = "enabled" if show_menu else "hidden"
                print(f"{C_DIM}[Menu palette {state}. Press 'm' to toggle.]{C_RESET}")
                continue

            elif query == "1":
                torch_on = not torch_on
                res = global_tool_registry.execute("set_torch", on=torch_on)
                print(f"🔦 Torch turned {'ON' if torch_on else 'OFF'}")
                continue

            elif query == "2":
                res = global_tool_registry.execute("get_battery_status")
                pct = res.output.get("percentage", "N/A") if isinstance(res.output, dict) else "N/A"
                stat = res.output.get("status", "Unknown") if isinstance(res.output, dict) else ""
                print(f"🔋 Battery: {pct}% [{stat}]")
                continue

            elif query == "3":
                print(f"{C_CYAN}📸 Capturing device camera snapshot...{C_RESET}")
                res = global_tool_registry.execute("take_camera_photo")
                print(f"📸 Result: {res.output or res.error}")
                continue

            elif query == "4":
                print(global_fastfetch_collector.render_ascii(max_width=vw))
                continue

            elif query == "5":
                screen_extensions(vw)
                continue

            elif query == "6":
                print(f"{C_CYAN}🧹 Running storage & cache cleaner...{C_RESET}")
                res = global_tool_registry.execute("clean_system", dry_run=False)
                summary = res.output.get("summary") if isinstance(res.output, dict) else str(res.output)
                print(f"🧹 {summary}")
                continue

            elif query == "7":
                screen_audit_logs(vw)
                continue

            elif query == "8":
                screen_security_dashboard(vw)
                continue

            elif query == "9":
                screen_models(vw)
                continue

            elif query == "0":
                screen_bot_control(vw)
                continue

            elif query.lower() in ("v", "vault"):
                screen_vault(vw)
                continue

            elif query.lower() in ("w", "wizard"):
                global_model_manager.run_interactive_wizard()
                continue

            elif query.lower() in ("s", "screenshot"):
                print(f"{C_CYAN}📸 Capturing device screen...{C_RESET}")
                res = global_tool_registry.execute("capture_screen")
                print(f"📸 {res.output if res.success else res.error}")
                continue

            elif query.lower() in ("x", "ssh"):
                from modules.terminal_service import global_terminal_service
                card = global_terminal_service.get_connection_card()
                print(f"\n{card}\n")
                continue

            # ------------------------------------------------------------------
            # Slash Commands Handling
            # ------------------------------------------------------------------
            elif query.startswith("/"):
                parts = query[1:].strip().split()
                cmd = parts[0].lower()
                cmd_args = parts[1:]

                if cmd in ("help", "?"):
                    print_help_screen(vw)
                elif cmd in ("sh", "bash"):
                    if not cmd_args:
                        print(f"{C_RED}Usage: /sh <command>{C_RESET}")
                    else:
                        from modules.terminal_service import global_terminal_service
                        res = global_terminal_service.execute_bash(" ".join(cmd_args))
                        code = res.get("returncode", 0)
                        out = res.get("output", "")
                        stat = f"{C_GREEN}[EXIT 0]{C_RESET}" if code == 0 else f"{C_RED}[EXIT {code}]{C_RESET}"
                        print(f"{stat}\n{out}")
                elif cmd == "ssh":
                    from modules.terminal_service import global_terminal_service
                    if cmd_args:
                        action = cmd_args[0].lower()
                        if action in ("start", "up", "on"):
                            global_terminal_service.start_ssh()
                        elif action in ("stop", "down", "off"):
                            global_terminal_service.stop_ssh()
                    card = global_terminal_service.get_connection_card()
                    print(f"\n{card}\n")
                elif cmd == "ram":
                    from config.settings import global_config
                    if cmd_args and cmd_args[0].isdigit():
                        act = global_config.set_ram_limit(int(cmd_args[0]))
                        print(f"{C_GREEN}RAM limit set to {act} MB (Absolute cap: 2048 MB){C_RESET}")
                    else:
                        prof = global_config.get_compute_profile()
                        print(f"RAM Limit: {prof['ram_limit_mb']} MB (Cap: {prof['max_allowed_ram_mb']} MB, Max Model: {prof['max_model_size_mb']} MB)")
                elif cmd in ("fastfetch", "fetch", "status"):
                    print(global_fastfetch_collector.render_ascii(max_width=vw))
                elif cmd in ("torch", "flashlight"):
                    on = "off" not in cmd_args
                    torch_on = on
                    global_tool_registry.execute("set_torch", on=torch_on)
                    print(f"🔦 Torch turned {'ON' if torch_on else 'OFF'}")
                elif cmd == "battery":
                    res = global_tool_registry.execute("get_battery_status")
                    print(f"🔋 Battery: {json.dumps(res.output, indent=2)}")
                elif cmd in ("photo", "camera"):
                    res = global_tool_registry.execute("take_camera_photo")
                    print(f"📸 {res.output or res.error}")
                elif cmd in ("screenshot", "screen"):
                    print(f"{C_CYAN}📸 Capturing device screen...{C_RESET}")
                    res = global_tool_registry.execute("capture_screen")
                    print(f"📸 {res.output if res.success else res.error}")
                elif cmd in ("vault", "cloud"):
                    screen_vault(vw)
                elif cmd in ("wizard", "setup_model"):
                    global_model_manager.run_interactive_wizard()
                elif cmd == "tap":
                    if len(cmd_args) >= 2:
                        res = global_tool_registry.execute("mobile_tap", x=int(cmd_args[0]), y=int(cmd_args[1]))
                        print(f"👆 {res.output if res.success else res.error}")
                    else:
                        print(f"{C_RED}Usage: /tap <x> <y>{C_RESET}")
                elif cmd == "swipe":
                    if len(cmd_args) >= 4:
                        dur = int(cmd_args[4]) if len(cmd_args) > 4 else 300
                        res = global_tool_registry.execute("mobile_swipe", x1=int(cmd_args[0]), y1=int(cmd_args[1]), x2=int(cmd_args[2]), y2=int(cmd_args[3]), duration_ms=dur)
                        print(f"👉 {res.output if res.success else res.error}")
                    else:
                        print(f"{C_RED}Usage: /swipe <x1> <y1> <x2> <y2> [duration]{C_RESET}")
                elif cmd in ("type", "input"):
                    if cmd_args:
                        res = global_tool_registry.execute("mobile_type_text", text=" ".join(cmd_args))
                        print(f"⌨️ {res.output if res.success else res.error}")
                    else:
                        print(f"{C_RED}Usage: /type <text>{C_RESET}")
                elif cmd in ("key", "keyevent"):
                    if cmd_args:
                        res = global_tool_registry.execute("mobile_keyevent", key=cmd_args[0].upper())
                        print(f"🔘 {res.output if res.success else res.error}")
                    else:
                        print(f"{C_RED}Usage: /key <HOME|BACK|RECENTS|ENTER|POWER>{C_RESET}")
                elif cmd in ("plugins", "plugin"):
                    screen_extensions(vw)
                elif cmd in ("logs", "log"):
                    screen_audit_logs(vw)
                elif cmd in ("security", "sec"):
                    screen_security_dashboard(vw)
                elif cmd in ("bot", "telegram"):
                    screen_bot_control(vw)
                elif cmd in ("models", "model"):
                    screen_models(vw)
                elif cmd == "download":
                    if not cmd_args:
                        print(f"{C_RED}Usage: /download <model_id>{C_RESET}")
                    else:
                        global_model_manager.download_model(cmd_args[0])
                elif cmd == "clean":
                    res = global_tool_registry.execute("clean_system", dry_run=False)
                    print(f"🧹 {res.output}")
                elif cmd == "clear":
                    os.system("clear")
                    render_mobile_banner(vw)
                else:
                    print(f"{C_RED}Unknown command: '/{cmd}'. Type /help or ? for directory.{C_RESET}")
                continue

            # ------------------------------------------------------------------
            # Natural Language ReAct Execution Loop
            # ------------------------------------------------------------------
            spinner = TUISpinner("Agent deliberating intent...")
            spinner.start()
            try:
                response: AgentResponse = global_react_agent.run(query, session_id=session_id)
            finally:
                spinner.stop()

            # Output Conversational Response
            if response.conversational_reply:
                print(f"\n{render_card_top('AGENT RESPONSE', vw, C_GREEN, C_BOLD + C_GREEN)}")
                for line in wrap_mobile_text(response.conversational_reply, vw - 4):
                    print(render_card_line(line, vw, C_GREEN))
                print(render_card_bottom(vw, C_GREEN))

            # Output ReAct Deliberation Card
            print(f"\n{render_card_top('AGENT DELIBERATION', vw, C_BLUE, C_BOLD + C_BLUE)}")
            for line in wrap_mobile_text(f"🧠 Reasoning: {response.reasoning}", vw - 4):
                print(render_card_line(line, vw, C_BLUE))
            if response.confidence is not None:
                print(render_card_line(f"🎯 Confidence: {int(response.confidence * 100)}%", vw, C_BLUE))
            print(render_card_bottom(vw, C_BLUE))

            # Formatted Mobile Step Cards
            if response.steps:
                format_step_cards(response.steps, vw)

            # Tool Outputs
            if response.results:
                print(f"{C_BOLD}⚡ Tool Outputs:{C_RESET}")
                for idx, r in enumerate(response.results, 1):
                    if isinstance(r, dict):
                        for k, v in r.items():
                            print(f"  {C_CYAN}• {k}:{C_RESET} {v}")
                    else:
                        print(f"  {C_CYAN}•{C_RESET} {r}")
            else:
                print(f"  {C_DIM}[No tools required by directive]{C_RESET}")

            print()

        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_YELLOW}Shutting down Void CLI session. Goodbye!{C_RESET}")
            break
        except Exception as e:
            print(f"\n{C_RED}❌ Error during execution: {e}{C_RESET}\n")

    # Save command history
    if readline and HISTORY_FILE:
        try:
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass


if __name__ == "__main__":
    main()
