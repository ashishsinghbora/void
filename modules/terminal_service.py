"""
modules/terminal_service.py - Remote SSH Daemon Controller & Secure Bash Terminal.

Manages:
- OpenSSH daemon (sshd) lifecycle on Termux / Linux (default port 8022)
- Network interface IP discovery (wlan0, Tailscale, VPN, loopback)
- Interactive and autonomous bash command runner with timeout guardrails
- Formatted connection command cards for Telegram and Terminal TUI
"""

import os
import re
import socket
import logging
import subprocess
from typing import Dict, Any, Optional, List

from core.command_executor import SecureCommandExecutor, IS_TERMUX

logger = logging.getLogger("VoidModules.TerminalService")


class TerminalService:
    """Remote OpenSSH server controller and secure bash command executor."""

    def __init__(self, default_ssh_port: int = 8022):
        self.default_ssh_port: int = default_ssh_port
        self._ssh_process: Optional[subprocess.Popen] = None

    def get_network_ips(self) -> Dict[str, str]:
        """Discovers IPv4 addresses across local Wi-Fi, Tailscale, VPN, and cellular interfaces."""
        ips: Dict[str, str] = {}

        # 1. Check via ip -brief address or ifconfig
        try:
            res = SecureCommandExecutor.run(["ip", "-brief", "address"], timeout=3)
            if not res.startswith("Error"):
                for line in res.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and parts[1].upper() == "UP":
                        iface = parts[0]
                        ip_cidr = parts[2]
                        ip = ip_cidr.split("/")[0]
                        if ip and not ip.startswith("127."):
                            ips[iface] = ip
        except Exception:
            pass

        # 2. Fallback via socket connection routing
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                if ip:
                    ips["wlan0_fallback"] = ip
            except Exception:
                pass

        if "lo" not in ips:
            ips["localhost"] = "127.0.0.1"

        return ips

    def is_ssh_running(self) -> bool:
        """Checks if OpenSSH daemon (sshd) is actively listening."""
        # 1. Check socket port connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", self.default_ssh_port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass

        # 2. Check process table
        try:
            res = SecureCommandExecutor.run(["pgrep", "sshd"], timeout=2)
            return bool(res.strip() and not res.startswith("Error"))
        except Exception:
            return False

    def start_ssh(self, port: Optional[int] = None) -> Dict[str, Any]:
        """Launches the OpenSSH daemon on Termux or Linux."""
        target_port = port or self.default_ssh_port
        if self.is_ssh_running():
            return {
                "success": True,
                "status": "already_running",
                "port": target_port,
                "message": f"OpenSSH daemon is already active on port {target_port}.",
                "connection_info": self.get_connection_card(target_port),
            }

        # Resolve sshd binary path
        sshd_bin = SecureCommandExecutor.resolve_binary("sshd")
        if not sshd_bin:
            return {
                "success": False,
                "error": "OpenSSH daemon ('sshd') not found. Run 'pkg install openssh' in Termux.",
            }

        try:
            # Termux sshd runs in background by default with -p <port>
            cmd = [sshd_bin, "-p", str(target_port)]
            res = SecureCommandExecutor.run(cmd, timeout=5)

            # Wait briefly and verify socket
            import time
            time.sleep(0.5)
            running = self.is_ssh_running()

            return {
                "success": running,
                "status": "started" if running else "failed",
                "port": target_port,
                "output": res,
                "connection_info": self.get_connection_card(target_port) if running else None,
            }
        except Exception as e:
            logger.error(f"Error starting sshd: {e}")
            return {"success": False, "error": str(e)}

    def stop_ssh(self) -> Dict[str, Any]:
        """Terminates the OpenSSH daemon."""
        try:
            pkill_bin = SecureCommandExecutor.resolve_binary("pkill") or "pkill"
            SecureCommandExecutor.run([pkill_bin, "-f", "sshd"], timeout=3)
            import time
            time.sleep(0.3)
            still_running = self.is_ssh_running()
            return {
                "success": not still_running,
                "status": "stopped" if not still_running else "failed",
                "message": "SSH daemon terminated." if not still_running else "Could not stop sshd.",
            }
        except Exception as e:
            logger.error(f"Error stopping sshd: {e}")
            return {"success": False, "error": str(e)}

    def get_connection_card(self, port: Optional[int] = None) -> str:
        """Renders formatted Markdown connection card with discovered IP addresses and SSH command."""
        p = port or self.default_ssh_port
        running = self.is_ssh_running()
        status_badge = "🟢 ACTIVE" if running else "🔴 OFFLINE"

        user = os.environ.get("USER", "u0_a123")
        ips = self.get_network_ips()

        ip_lines = []
        for iface, ip in ips.items():
            if iface != "localhost":
                ip_lines.append(f"• *{iface}:* `{ip}`")

        ip_block = "\n".join(ip_lines) if ip_lines else "• `127.0.0.1` (Localhost only)"
        primary_ip = next((ip for iface, ip in ips.items() if iface != "localhost"), "127.0.0.1")

        return (
            "💻 *Void Remote SSH & Terminal Access*\n\n"
            f"• *Daemon Status:* {status_badge}\n"
            f"• *Port:* `{p}`\n"
            f"• *Username:* `{user}`\n\n"
            "🌐 *Available IP Interfaces:*\n"
            f"{ip_block}\n\n"
            "🔑 *Quick Connect Command:*\n"
            f"```bash\nssh {user}@{primary_ip} -p {p}\n```\n"
            "_Note: Set your Termux password using `passwd` if authenticating via password._"
        )

    def execute_bash(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Executes an arbitrary shell command safely with timeout enforcement
        and stdout/stderr capture.
        """
        if not command or not command.strip():
            return {"success": False, "error": "Empty command provided."}

        clean_cmd = command.strip()
        logger.info(f"Executing bash command: {clean_cmd[:60]}")

        start_time = os.times().elapsed if hasattr(os, "times") else 0.0
        try:
            # Use bash if available, else /system/bin/sh or sh
            shell_bin = SecureCommandExecutor.resolve_binary("bash") or "/bin/sh"
            proc = subprocess.run(
                [shell_bin, "-c", clean_cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.expanduser("~"),
            )

            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            code = proc.returncode

            output = (stdout + ("\n[STDERR]: " + stderr if stderr else "")).strip()
            if not output and code == 0:
                output = "(Command executed successfully with no output)"

            # Cap output to 4000 chars for Telegram safety
            if len(output) > 3800:
                output = output[:3800] + "\n... [truncated output]"

            return {
                "success": code == 0,
                "exit_code": code,
                "returncode": code,
                "output": output,
                "command": clean_cmd,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "returncode": -1,
                "error": f"Command timed out after {timeout} seconds.",
                "command": clean_cmd,
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "returncode": -1,
                "error": str(e),
                "command": clean_cmd,
            }


global_terminal_service = TerminalService()
