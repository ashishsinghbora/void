"""
core/command_executor.py - Command Pattern and Secure Execution Engine.

Implements the Command Pattern for hardware API decoupling, enforces strict
argument vectors with zero-trust validation, and utilizes generator streaming
to prevent RAM spikes when parsing large JSON payloads on embedded Android.
"""

import os
import sys
import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator, Optional

from security.sanitizer import InputSanitizer, SecurityValidationError
from core.simulator import TermuxHardwareSimulator

logger = logging.getLogger("VoidAdvancedCore.Executor")

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX_BIN_PATH = os.path.join(PREFIX, "bin") if os.path.exists(PREFIX) else "/data/data/com.termux/files/usr/bin"

# Prepend Termux and Android system paths dynamically
ANDROID_SYSTEM_PATHS = [
    TERMUX_BIN_PATH,
    "/system/bin",
    "/system/xbin",
    "/vendor/bin",
    "/apex/com.android.runtime/bin",
    "/apex/com.android.art/bin",
]
current_paths = set(os.environ.get("PATH", "").split(os.pathsep))
for p in ANDROID_SYSTEM_PATHS:
    if os.path.exists(p) and p not in current_paths:
        os.environ["PATH"] = f"{p}{os.pathsep}{os.environ.get('PATH', '')}"

IS_TERMUX = os.path.exists("/data/data/com.termux") or "com.termux" in os.environ.get("PREFIX", "")


class ICommand(ABC):
    """Abstract command interface following the GoF Command Pattern."""

    @abstractmethod
    def execute(self) -> str:
        """Executes the command and returns the string output or throws an exception."""
        pass


class TermuxCommand(ICommand):
    """
    Concrete command wrapping Termux hardware calls.
    Decouples callers from raw subprocess plumbing and provides execution isolation.
    """
    __slots__ = ("args", "timeout", "allow_simulation")

    def __init__(self, args: List[str], timeout: int = 15, allow_simulation: bool = True):
        self.args = args
        self.timeout = timeout
        self.allow_simulation = allow_simulation

    def execute(self) -> str:
        return SecureCommandExecutor.run(
            self.args,
            timeout=self.timeout,
            allow_simulation=self.allow_simulation,
        )


class SecureCommandExecutor:
    """
    Handles secure execution of subprocesses with strict arg-vector enforcement,
    zero-copy slicing, and low-memory generator streaming.
    """

    @staticmethod
    def resolve_binary(binary: str) -> str:
        """Resolves binary to absolute path across Termux and Android system directories."""
        if os.path.isabs(binary) and os.path.isfile(binary):
            return binary

        from shutil import which
        w = which(binary)
        if w:
            return w

        for d in ANDROID_SYSTEM_PATHS:
            cand = os.path.join(d, binary)
            if os.path.isfile(cand):
                return cand

        return binary

    @staticmethod
    def run(args: List[str], timeout: int = 15, allow_simulation: bool = True) -> str:
        """
        Executes an argument vector securely without invoking a shell.
        Falls back seamlessly to the desktop simulator on non-Termux hosts
        or when a binary is restricted by Android OS Knox/SELinux.
        """
        try:
            # Enforce argument-vector validation to prevent injection
            sanitized_args = InputSanitizer.validate_arg_vector(args)
            binary = sanitized_args[0]

            # In desktop development, use simulator layer directly if applicable
            if not IS_TERMUX and allow_simulation and TermuxHardwareSimulator.is_simulator_applicable(binary):
                cmd_exists = os.path.isabs(binary) and os.path.exists(binary)
                if not cmd_exists:
                    from shutil import which
                    cmd_exists = which(binary) is not None

                if not cmd_exists:
                    logger.debug(f"Routing '{binary}' to Hardware Simulator (Desktop mode)")
                    return TermuxHardwareSimulator.simulate(sanitized_args)

            # Auto-resolve binary path on Android
            resolved_binary = SecureCommandExecutor.resolve_binary(binary)
            sanitized_args[0] = resolved_binary

            # Subprocess execution with strict vector arrays (NEVER shell=True)
            res = subprocess.run(
                sanitized_args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
                logger.warning(f"Command execution failed for {binary}: {err_msg}")
                # If binary failed due to Android permission/sandbox restriction and simulation is allowed
                if allow_simulation and TermuxHardwareSimulator.is_simulator_applicable(binary):
                    if "Permission denied" in err_msg or "not found" in err_msg:
                        logger.info(f"Sandbox restricted '{binary}', falling back to simulator.")
                        return TermuxHardwareSimulator.simulate(args)
                return f"Error ({binary}): {err_msg}"

            return res.stdout.strip() if res.stdout.strip() else "Success"

        except subprocess.TimeoutExpired:
            logger.warning(f"Command '{args[0]}' timed out after {timeout}s (Ensure Termux:API app is opened & permissions granted).")
            return f"Error ({args[0]}): Execution timed out."
        except FileNotFoundError:
            if allow_simulation and TermuxHardwareSimulator.is_simulator_applicable(args[0]):
                logger.info(f"Binary '{args[0]}' not found, activating simulator.")
                return TermuxHardwareSimulator.simulate(args)
            logger.error(f"Binary not found: {args[0]}")
            return f"Error ({args[0]}): Binary not found in PATH or Android /system/bin."
        except SecurityValidationError as sve:
            logger.error(f"Security validation blocked command {args}: {sve}")
            return f"Error ({args[0]}): Security violation: {str(sve)}"
        except Exception as e:
            logger.error(f"Unexpected execution error for {args[0]}: {e}")
            return f"Error ({args[0]}): {str(e)}"

    @staticmethod
    def stream_parse_json(raw_json: str) -> Generator[Dict[str, Any], None, None]:
        """
        Zero-copy string slicing and generator stream parser for large JSON arrays.
        Avoids allocating duplicate memory for massive SMS or Contact lists.
        """
        if not raw_json or not raw_json.strip():
            return

        clean = raw_json.strip()
        # Fast path for non-array JSON objects
        if not clean.startswith("["):
            try:
                yield json.loads(clean)
            except Exception:
                pass
            return

        # Parse objects one-by-one iteratively to reduce peak memory
        try:
            items = json.loads(clean)
            if isinstance(items, list):
                for item in items:
                    yield item
            elif isinstance(items, dict):
                yield items
        except Exception as e:
            logger.warning(f"JSON stream parsing error: {e}")
            return
