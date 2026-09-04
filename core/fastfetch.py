"""
core/fastfetch.py - Hyper-Fast ASCII & Markdown System Telemetry Generator.

Generates beautiful, neofetch/fastfetch-style system hardware and platform
diagnostics formatted for both interactive terminal sessions and Telegram Bot messages.
"""

import os
import sys
import time
import socket
import platform
import resource
import logging
from typing import Dict, Any, Optional

from core.command_executor import IS_TERMUX, SecureCommandExecutor
from storage.repository import ConversationRepository, ExecutionLogRepository
from daemons.service_runner import global_daemon_supervisor

logger = logging.getLogger("VoidAdvancedCore.FastFetch")


class FastFetchCollector:
    """Collects system, hardware, memory, network, and daemon telemetry."""

    def __init__(self):
        self._convo_repo = ConversationRepository()
        self._log_repo = ExecutionLogRepository()

    def _get_device_model(self) -> str:
        """Retrieves Android device model or host hostname."""
        if IS_TERMUX:
            try:
                mfr = SecureCommandExecutor.run(["getprop", "ro.product.manufacturer"], timeout=2).strip()
                model = SecureCommandExecutor.run(["getprop", "ro.product.model"], timeout=2).strip()
                if mfr and model and not mfr.startswith("Error") and not model.startswith("Error"):
                    return f"{mfr.capitalize()} {model}"
            except Exception:
                pass
        return socket.gethostname() or "Android Device"

    def _get_os_info(self) -> str:
        """Retrieves OS distribution / Android version."""
        if IS_TERMUX:
            try:
                ver = SecureCommandExecutor.run(["getprop", "ro.build.version.release"], timeout=2).strip()
                if ver and not ver.startswith("Error"):
                    return f"Android {ver} (Termux)"
            except Exception:
                pass
            return "Android (Termux Bionic)"
        return f"{platform.system()} {platform.release()}"

    def _get_uptime(self) -> str:
        """Retrieves human-readable uptime from /proc/uptime."""
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0 or days > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m")
            return " ".join(parts)
        except Exception:
            return "Unknown"

    def _get_mem_info(self) -> Dict[str, float]:
        """Reads system RAM stats from /proc/meminfo in MB."""
        info = {"total_mb": 0.0, "available_mb": 0.0, "used_mb": 0.0}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        info["total_mb"] = round(int(line.split()[1]) / 1024.0, 1)
                    elif line.startswith("MemAvailable:"):
                        info["available_mb"] = round(int(line.split()[1]) / 1024.0, 1)
            info["used_mb"] = round(max(0.0, info["total_mb"] - info["available_mb"]), 1)
        except Exception:
            pass
        return info

    def _get_battery_info(self) -> Dict[str, Any]:
        """Retrieves battery status safely."""
        try:
            from tools.registry import global_tool_registry
            res = global_tool_registry.execute("get_battery_status")
            if res.success and isinstance(res.output, dict):
                return {
                    "percentage": res.output.get("percentage", "N/A"),
                    "status": res.output.get("status", "Discharging"),
                    "health": res.output.get("health", "GOOD"),
                    "temperature": res.output.get("temperature", "N/A"),
                }
        except Exception:
            pass
        return {"percentage": "N/A", "status": "Unknown", "health": "GOOD", "temperature": "N/A"}

    def _get_network_info(self) -> Dict[str, str]:
        """Retrieves active IP address and Wi-Fi SSID."""
        net = {"ip": "127.0.0.1", "wifi": "Offline"}
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            net["ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        try:
            from tools.registry import global_tool_registry
            res = global_tool_registry.execute("get_wifi_info")
            if res.success and isinstance(res.output, dict):
                ssid = res.output.get("ssid")
                if ssid and ssid != "<unknown ssid>":
                    net["wifi"] = ssid
                elif res.output.get("supplicant_state") == "COMPLETED":
                    net["wifi"] = "Connected"
        except Exception:
            pass
        return net

    def _get_active_model_name(self) -> str:
        """Retrieves active model name or fallback."""
        try:
            from core.model_manager import global_model_manager
            active = global_model_manager.get_active_model_name()
            if active:
                return active
        except Exception:
            pass
        return "Deterministic ReAct (Zero-Weight Heuristic)"

    def collect(self) -> Dict[str, Any]:
        """Collects all system metrics into structured dictionary."""
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024.0, 2)
        mem = self._get_mem_info()
        battery = self._get_battery_info()
        network = self._get_network_info()

        # Database telemetry
        recent_convo = 0
        recent_logs = 0
        try:
            convo_res = self._convo_repo._db.execute_query("SELECT COUNT(*) as cnt FROM conversations;")
            if convo_res:
                recent_convo = convo_res[0]["cnt"]
        except Exception:
            pass

        try:
            log_res = self._log_repo._db.execute_query("SELECT COUNT(*) as cnt FROM execution_logs;")
            if log_res:
                recent_logs = log_res[0]["cnt"]
        except Exception:
            pass

        # Daemon states
        supervisor_status = global_daemon_supervisor.get_status() if hasattr(global_daemon_supervisor, "get_status") else {}

        return {
            "device": self._get_device_model(),
            "os": self._get_os_info(),
            "kernel": platform.release(),
            "arch": platform.machine(),
            "uptime": self._get_uptime(),
            "shell": os.environ.get("SHELL", "bash").split("/")[-1],
            "python": platform.python_version(),
            "process_rss_mb": rss_mb,
            "system_ram": mem,
            "battery": battery,
            "network": network,
            "active_model": self._get_active_model_name(),
            "daemons": supervisor_status,
            "database": {
                "recent_messages": recent_convo,
                "recent_logs": recent_logs,
            },
        }

    def render_ascii(self, use_color: bool = True, max_width: Optional[int] = None) -> str:
        """Renders fastfetch-style ASCII art and system telemetry for the terminal."""
        data = self.collect()

        if max_width is None:
            try:
                import shutil
                max_width = shutil.get_terminal_size(fallback=(80, 24)).columns
            except Exception:
                max_width = 80

        c_cyan = "\033[0;36m" if use_color else ""
        c_green = "\033[0;32m" if use_color else ""
        c_yellow = "\033[1;33m" if use_color else ""
        c_purple = "\033[0;35m" if use_color else ""
        c_bold = "\033[1m" if use_color else ""
        c_reset = "\033[0m" if use_color else ""

        logo = [
            r"  __     __     _     _ ",
            r"  \ \   / /__  (_) __| |",
            r"   \ \ / / _ \ | |/ _` |",
            r"    \ V / (_) || | (_| |",
            r"     \_/ \___/ |_|\__,_|",
            r"    EDGE AGENTIC DAEMON ",
        ]

        ram = data["system_ram"]
        ram_str = f"{ram['used_mb']} MB / {ram['total_mb']} MB" if ram["total_mb"] else "N/A"
        bat = data["battery"]
        bat_str = f"{bat['percentage']}% [{bat['status']}]" if bat["percentage"] != "N/A" else "Standby"

        daemon_info = []
        if data["daemons"].get("notification_interceptor"):
            daemon_info.append("NotifDaemon")
        if data["daemons"].get("routine_scheduler"):
            daemon_info.append("Cron")
        daemons_str = ", ".join(daemon_info) if daemon_info else "Idle"

        rss_target_met = data['process_rss_mb'] <= 30.0
        rss_tag = f"{c_green}(< 30MB ✅){c_reset}" if rss_target_met else f"{c_yellow}(< 30MB ⚠️){c_reset}"

        info_lines = [
            f"{c_bold}{c_cyan}Host{c_reset}        │ {data['device']}",
            f"{c_bold}{c_cyan}OS{c_reset}          │ {data['os']}",
            f"{c_bold}{c_cyan}Kernel{c_reset}      │ {data['kernel']} ({data['arch']})",
            f"{c_bold}{c_cyan}Uptime{c_reset}      │ {data['uptime']}",
            f"{c_bold}{c_cyan}Python{c_reset}      │ {data['python']} (Shell: {data['shell']})",
            f"{c_bold}{c_green}Void RSS{c_reset}    │ {data['process_rss_mb']} MB {rss_tag}",
            f"{c_bold}{c_cyan}RAM{c_reset}         │ {ram_str}",
            f"{c_bold}{c_yellow}Battery{c_reset}     │ {bat_str}",
            f"{c_bold}{c_cyan}Network{c_reset}     │ {data['network']['ip']} (Wi-Fi: {data['network']['wifi']})",
            f"{c_bold}{c_purple}Model{c_reset}       │ {data['active_model']}",
            f"{c_bold}{c_cyan}Daemons{c_reset}     │ {daemons_str}",
        ]

        # Stacked card layout for mobile / narrow viewports (< 75 columns)
        if max_width < 75:
            box_w = max(38, min(max_width - 1, 56))
            title = " VOID TELEMETRY FASTFETCH "
            dash_count = max(1, box_w - 4 - len(title))
            top_bar = f"{c_bold}{c_purple}╭─{title}{'─' * dash_count}╮{c_reset}"
            bottom_bar = f"{c_bold}{c_purple}╰{'─' * (box_w - 2)}╯{c_reset}"
            sep = f"{c_purple}├{'─' * (box_w - 2)}┤{c_reset}"

            output = [top_bar]
            output.append(f"{c_purple}│{c_reset} {c_bold}{c_cyan}⚡ VOID MOBILE EDGE NODE{c_reset}")
            output.append(sep)
            for line in info_lines:
                output.append(f"{c_purple}│{c_reset} {line}")
            output.append(bottom_bar)
            return "\n".join(output)

        # Standard wide terminal layout (>= 75 columns)
        max_logo_len = max(len(line) for line in logo)
        output = []
        output.append(f"{c_bold}{c_purple}╭───────────────────────────────────────────────────────────╮{c_reset}")
        output.append(f"{c_bold}{c_purple}│                VOID TELEMETRY FASTFETCH                   │{c_reset}")
        output.append(f"{c_bold}{c_purple}╰───────────────────────────────────────────────────────────╯{c_reset}")

        max_rows = max(len(logo), len(info_lines))
        for i in range(max_rows):
            raw_logo = logo[i] if i < len(logo) else " " * max_logo_len
            pad = " " * (max_logo_len - len(raw_logo))
            logo_part = f"{c_cyan}{raw_logo}{pad}{c_reset}"
            info_part = info_lines[i] if i < len(info_lines) else ""
            output.append(f"{logo_part}  {info_part}")

        return "\n".join(output)

    def render_markdown(self) -> str:
        """Renders beautiful Unicode/Markdown card for Telegram messages."""
        data = self.collect()
        ram = data["system_ram"]
        ram_str = f"{ram['used_mb']} MB / {ram['total_mb']} MB" if ram["total_mb"] else "N/A"
        bat = data["battery"]
        bat_str = f"{bat['percentage']}% ({bat['status']})" if bat["percentage"] != "N/A" else "Standby"

        notif_state = "\U0001f7e2 Active" if data["daemons"].get("notification_interceptor") else "\u26aa Inactive"
        cron_state = "\U0001f7e2 Active" if data["daemons"].get("routine_scheduler") else "\u26aa Inactive"
        wake_state = "\U0001f512 Held" if data["daemons"].get("wake_lock_acquired") else "\u26aa Inactive"

        rss_tag = "✅" if data['process_rss_mb'] <= 30.0 else "⚠️"

        return (
            "⚡ *VOID EDGE SYSTEM TELEMETRY*\n"
            "```text\n"
            "  __     __     _     _ \n"
            "  \\ \\   / /__  (_) __| |\n"
            "   \\ \\ / / _ \\ | |/ _` |\n"
            "    \\ V / (_) || | (_| |\n"
            "     \\_/ \\___/ |_|\\__,_|\n"
            "```\n"
            f"📱 *Device:* `{data['device']}`\n"
            f"💻 *OS:* `{data['os']}`\n"
            f"⚙️ *Kernel:* `{data['kernel']} ({data['arch']})`\n"
            f"⏱️ *Uptime:* `{data['uptime']}`\n\n"
            f"🧠 *Agent Engine:* `{data['active_model']}`\n"
            f"💾 *Void RSS:* `{data['process_rss_mb']} MB` (Target < 30MB: {rss_tag})\n"
            f"\U0001f4ca *Host RAM:* `{ram_str}`\n"
            f"\U0001f50b *Battery:* `{bat_str}` (Temp: `{bat['temperature']}\u00b0C`)\n"
            f"\U0001f310 *Network:* `{data['network']['ip']}` | Wi-Fi: `{data['network']['wifi']}`\n\n"
            "\U0001f6e0\ufe0f *Background Daemons:*\n"
            f"\u2022 Notification Interceptor: {notif_state}\n"
            f"\u2022 Routine Cron Scheduler: {cron_state}\n"
            f"\u2022 CPU Wake-Lock: {wake_state}\n\n"
            f"\U0001f5c4\ufe0f *Storage:* SQLite WAL | `{data['database']['recent_messages']}` msgs | `{data['database']['recent_logs']}` logs"
        )


global_fastfetch_collector = FastFetchCollector()
