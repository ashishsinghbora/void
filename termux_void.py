"""
termux_void.py - Immersive High-Performance Terminal User Interface (TUI) for Void.

Features ANSI color styling, real-time activity spinners, structured execution tables,
interactive slash commands (/plugins, /models, /fastfetch), and zero-latency ReAct feedback.
"""

import os
import sys
import time
import json
import logging
import threading
import resource
from typing import Optional, List, Dict, Any

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
from agents.react_agent import global_react_agent
from core.types import AgentResponse
from core.fastfetch import global_fastfetch_collector
from core.model_manager import global_model_manager
from extensions.manager import global_extension_manager
from tools.registry import global_tool_registry

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


def render_status_bar():
    """Renders sleek top status badge."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024.0, 1)
    rss_color = C_GREEN if rss_mb <= 30.0 else C_YELLOW

    engine_name = global_model_manager.get_active_model_name() or "Deterministic ReAct"
    plugin_count = len(global_extension_manager.list_extensions())
    env_str = "Android/Termux" if IS_TERMUX else "Desktop Sim"

    print(
        f"{C_DIM}┌─[{C_RESET}{C_BOLD}{C_CYAN}Void Edge Agent{C_RESET}{C_DIM}]──"
        f"[{C_RESET}Env: {C_BOLD}{env_str}{C_RESET}{C_DIM}]──"
        f"[{C_RESET}RAM: {rss_color}{rss_mb} MB{C_RESET}{C_DIM}]──"
        f"[{C_RESET}Engine: {C_PURPLE}{engine_name}{C_RESET}{C_DIM}]──"
        f"[{C_RESET}Plugins: {C_GREEN}{plugin_count}{C_RESET}{C_DIM}]"
    )


def print_banner():
    """Prints the rich cyber-styled Void terminal banner."""
    print(f"{C_CYAN}{C_BOLD}")
    print(r"  __     __     _     _ ")
    print(r"  \ \   / /__  (_) __| |  Autonomous Edge Orchestrator")
    print(r"   \ \ / / _ \ | |/ _` |  Terminal & Telegram Native")
    print(r"    \ V / (_) || | (_| |  Zero Web Bloat • < 30MB RAM")
    print(r"     \_/ \___/ |_|\__,_|")
    print(f"{C_RESET}")
    render_status_bar()
    print(f"{C_DIM}Type {C_RESET}{C_CYAN}/help{C_RESET}{C_DIM} for commands, or send plain directives (e.g. 'turn on flashlight').{C_RESET}\n")


def print_help():
    """Prints interactive TUI command menu."""
    print(f"\n{C_BOLD}{C_PURPLE}╭── VOID TUI COMMAND DIRECTORY ─────────────────────────────╮{C_RESET}")
    commands = [
        ("/help", "Display this commands directory"),
        ("/fastfetch", "Display visual ASCII/Unicode system & edge telemetry"),
        ("/plugins", "Manage dynamic plugins (/plugins list|search|install|remove)"),
        ("/models", "Inspect and manage local quantized LLM weights"),
        ("/download <id>", "Download small model (e.g. /download smollm-135m)"),
        ("/battery", "Query device battery percentage and health"),
        ("/torch [on|off]", "Toggle device camera flashlight"),
        ("/clean", "Run local storage and cache cleaner"),
        ("/status", "Display active daemons and process telemetry"),
        ("/clear", "Clear terminal screen"),
        ("/exit or q", "Gracefully terminate the session"),
    ]
    for cmd, desc in commands:
        print(f"{C_PURPLE}│{C_RESET}  {C_CYAN}{cmd:<17}{C_RESET} {desc}")
    print(f"{C_BOLD}{C_PURPLE}╰───────────────────────────────────────────────────────────╯{C_RESET}")
    print(f"{C_BOLD}Example Directives:{C_RESET}")
    print(f"  • {C_GREEN}show a toast saying Hello from Void{C_RESET}")
    print(f"  • {C_GREEN}check the battery level{C_RESET}")
    print(f"  • {C_GREEN}whatsapp 15551234567 saying Deployment verified{C_RESET}")
    print(f"  • {C_GREEN}open telegram chat with durov{C_RESET}")
    print(f"  • {C_GREEN}launch camera / open settings{C_RESET}\n")


def handle_plugins_command(args: List[str]):
    """Handles /plugins CLI subcommands."""
    sub = args[0] if args else "list"
    
    if sub == "list":
        loaded = global_extension_manager.list_extensions()
        print(f"\n{C_BOLD}Active Plugins ({len(loaded)}):{C_RESET}")
        if not loaded:
            print(f"  {C_DIM}Zero plugins active. Use '/plugins search' to explore community plugins.{C_RESET}")
        else:
            for p in loaded:
                tools_str = ", ".join(p.get("tools", []))
                print(f"  • {C_GREEN}{p['name']}{C_RESET} v{p['version']} - {p['description']}")
                print(f"    Tools: {C_CYAN}{tools_str}{C_RESET}")

    elif sub in ("search", "find"):
        q = " ".join(args[1:]) if len(args) > 1 else ""
        results = global_extension_manager.search_catalog(q)
        print(f"\n{C_BOLD}Community Catalog Search '{q}':{C_RESET}")
        for r in results:
            stat = f"{C_GREEN}[INSTALLED]{C_RESET}" if r["installed"] else f"{C_YELLOW}[AVAILABLE]{C_RESET}"
            tools = ", ".join(r["tools"])
            print(f"  • {C_BOLD}{r['id']:<16}{C_RESET} {stat} (v{r['version']})")
            print(f"    {r['description']}")
            print(f"    Tools: {C_CYAN}{tools}{C_RESET}")
        print(f"\n{C_DIM}To install: /plugins install <id>{C_RESET}")

    elif sub in ("install", "add"):
        if len(args) < 2:
            print(f"{C_RED}Usage: /plugins install <plugin_id>{C_RESET}")
            return
        pid = args[1]
        print(f"{C_CYAN}[INFO] Downloading and verifying plugin '{pid}'...{C_RESET}")
        res = global_extension_manager.install_plugin(pid)
        if res.get("success"):
            print(f"{C_GREEN}✅ {res['message']}{C_RESET}")
        else:
            print(f"{C_RED}❌ Installation failed: {res.get('error')}{C_RESET}")

    elif sub in ("remove", "uninstall", "delete"):
        if len(args) < 2:
            print(f"{C_RED}Usage: /plugins remove <plugin_id>{C_RESET}")
            return
        pid = args[1]
        res = global_extension_manager.uninstall_plugin(pid)
        print(f"{C_GREEN}✅ {res['message']}{C_RESET}")
    else:
        print(f"{C_RED}Unknown plugins subcommand: '{sub}'. Try list, search, install, or remove.{C_RESET}")


def handle_models_command():
    """Displays local LLM model weights and catalog."""
    installed = global_model_manager.list_installed_models()
    available = global_model_manager.list_available_models()
    active = global_model_manager.get_active_model_name()

    print(f"\n{C_BOLD}{C_PURPLE}╭── LOCAL SMALL-MODEL CATALOG ──────────────────────────────╮{C_RESET}")
    print(f"{C_PURPLE}│{C_RESET} Active Engine: {C_BOLD}{C_GREEN}{active or 'Deterministic ReAct (Zero-Weight)'}{C_RESET}")
    print(f"{C_PURPLE}│{C_RESET} Storage Dir:   {C_DIM}{global_model_manager.models_dir}{C_RESET}")
    print(f"{C_PURPLE}├───────────────────────────────────────────────────────────┤{C_RESET}")
    for mid, m in available.items():
        status = f"{C_GREEN}INSTALLED{C_RESET}" if m["installed"] else f"{C_YELLOW}AVAILABLE{C_RESET}"
        print(f"{C_PURPLE}│{C_RESET} • {C_BOLD}{mid:<14}{C_RESET} [{status}] ({m['size_mb']}MB)")
        print(f"{C_PURPLE}│{C_RESET}   {m['description']}")
    print(f"{C_PURPLE}╰───────────────────────────────────────────────────────────╯{C_RESET}")
    print(f"{C_DIM}To download a model: /download <model_id>{C_RESET}\n")


def handle_download_command(args: List[str]):
    """Downloads model weights with live streaming progress bar."""
    if not args:
        print(f"{C_RED}Usage: /download <model_id> (e.g. /download smollm-135m){C_RESET}")
        return

    mid = args[0]
    print(f"{C_CYAN}[INFO] Initiating streaming download for '{mid}'...{C_RESET}")

    def progress_cb(downloaded, total, pct, speed_kbps):
        bar_len = 25
        filled = int((pct / 100.0) * bar_len) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        d_mb = round(downloaded / (1024 * 1024), 1)
        t_mb = round(total / (1024 * 1024), 1) if total > 0 else 0
        sys.stdout.write(f"\r  [{bar}] {pct:>5.1f}% | {d_mb}MB / {t_mb}MB @ {speed_kbps:>6.1f} KB/s")
        sys.stdout.flush()

    res = global_model_manager.download_model(mid, progress_callback=progress_cb)
    print()  # Newline after progress bar
    if res.get("success"):
        print(f"{C_GREEN}✅ Model downloaded and activated: {res['path']} ({res['size_mb']} MB){C_RESET}")
    else:
        print(f"{C_RED}❌ Download failed: {res.get('error')}{C_RESET}")


def format_step_table(steps):
    """Formats execution steps into a clean Unicode table."""
    if not steps:
        return
    print(f"{C_PURPLE}╭─────┬──────────────────────────┬──────────────┬────────────╮{C_RESET}")
    print(f"{C_PURPLE}│{C_RESET} {C_BOLD}#   {C_RESET}{C_PURPLE}│{C_RESET} {C_BOLD}Tool Action              {C_RESET}{C_PURPLE}│{C_RESET} {C_BOLD}Status       {C_RESET}{C_PURPLE}│{C_RESET} {C_BOLD}Time (ms)  {C_RESET}{C_PURPLE}│{C_RESET}")
    print(f"{C_PURPLE}├─────┼──────────────────────────┼──────────────┼────────────┤{C_RESET}")
    for s in steps:
        action = (s.action or "Deliberation")[:24]
        status = s.status.value[:12]
        dur = f"{s.duration_ms:.1f}"
        print(f"{C_PURPLE}│{C_RESET} {s.step_number:<3} {C_PURPLE}│{C_RESET} {C_CYAN}{action:<24}{C_RESET} {C_PURPLE}│{C_RESET} {C_GREEN}{status:<12}{C_RESET} {C_PURPLE}│{C_RESET} {dur:>10} {C_PURPLE}│{C_RESET}")
    print(f"{C_PURPLE}╰─────┴──────────────────────────┴──────────────┴────────────╯{C_RESET}")


def main():
    print_banner()
    session_id = "cli_session"

    while True:
        try:
            render_status_bar()
            query = input(f"{C_BOLD}{C_CYAN}Void > {C_RESET}").strip()
            if not query:
                continue

            # Command routing
            if query.lower() in ("exit", "quit", "q"):
                print(f"\n{C_YELLOW}Shutting down Void CLI session. Goodbye!{C_RESET}")
                break

            elif query.startswith("/"):
                parts = query[1:].strip().split()
                cmd = parts[0].lower()
                cmd_args = parts[1:]

                if cmd == "help":
                    print_help()
                elif cmd in ("fastfetch", "fetch"):
                    print(global_fastfetch_collector.render_ascii())
                elif cmd in ("plugins", "plugin"):
                    handle_plugins_command(cmd_args)
                elif cmd in ("models", "model"):
                    handle_models_command()
                elif cmd == "download":
                    handle_download_command(cmd_args)
                elif cmd == "battery":
                    res = global_tool_registry.execute("get_battery_status")
                    print(f"🔋 Battery: {json.dumps(res.output, indent=2)}")
                elif cmd == "torch":
                    on = "off" not in cmd_args
                    res = global_tool_registry.execute("set_torch", on=on)
                    print(f"🔦 Torch turned {'ON' if on else 'OFF'}")
                elif cmd == "clean":
                    res = global_tool_registry.execute("clean_system", dry_run=False)
                    summary = res.output.get("summary") if isinstance(res.output, dict) else str(res.output)
                    print(f"🧹 {summary}")
                elif cmd == "status":
                    print(global_fastfetch_collector.render_ascii())
                elif cmd == "clear":
                    os.system("clear")
                    print_banner()
                else:
                    print(f"{C_RED}Unknown command: '/{cmd}'. Type /help for directory.{C_RESET}")
                continue

            # Natural language ReAct Execution with animated spinner
            spinner = TUISpinner("ReAct agent deliberating...")
            spinner.start()
            try:
                response: AgentResponse = global_react_agent.run(query, session_id=session_id)
            finally:
                spinner.stop()

            # Output ReAct Card
            print(f"\n{C_BOLD}{C_BLUE}╭── Agent Deliberation ─────────────────────────────────────╮{C_RESET}")
            print(f"{C_BLUE}│{C_RESET} 🧠 {C_BOLD}Reasoning:{C_RESET} {response.reasoning}")
            if response.confidence is not None:
                print(f"{C_BLUE}│{C_RESET} 🎯 {C_BOLD}Confidence:{C_RESET} {int(response.confidence * 100)}%")
            print(f"{C_BLUE}╰───────────────────────────────────────────────────────────╯{C_RESET}")

            # Formatted Step Table
            if response.steps:
                format_step_table(response.steps)

            # Tool Outputs
            if response.results:
                print(f"{C_BOLD}⚡ Tool Outputs:{C_RESET}")
                for idx, r in enumerate(response.results, 1):
                    if isinstance(r, dict):
                        print(f"  {C_CYAN}[{idx}]{C_RESET} {json.dumps(r, indent=2)}")
                    else:
                        print(f"  {C_CYAN}[{idx}]{C_RESET} {r}")
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
