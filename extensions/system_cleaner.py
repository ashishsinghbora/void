"""
extensions/system_cleaner.py - Flash Storage & Memory Cache Cleaner Plugin.

Scans permitted local storage roots and clears stale cache, dangling temporary files,
and orphan __pycache__ directories to conserve flash memory on Android edge devices.
"""

import os
import shutil
import time
import logging
from typing import List, Dict, Any, Optional

from extensions.base import ExtensionPlugin
from tools.base import ToolStrategy
from core.types import ToolExecutionResult
from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidAdvancedCore.Ext.Cleaner")

# Critical extensions / files that must NEVER be touched
PROTECTED_PATTERNS = {
    ".void_agent.db",
    ".void_vault.enc",
    "requirements.txt",
    "README.md",
    "app.py",
    "termux_void.py",
    ".git",
}


class SystemCleanerStrategy(ToolStrategy):
    """Scans and prunes temporary files, orphaned bytecodes, and cache directories."""

    def __init__(self):
        super().__init__(
            name="clean_system",
            description="Scan and clean temporary cache files, .pyc bytecodes, and stale logs to reclaim storage. Supports dry_run mode.",
            schema={
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "description": "If true, simulates cleanup without deleting files (default: true)"},
                    "target_scope": {"type": "string", "description": "Cleanup scope: 'pycache', 'cache', 'temp', or 'all' (default: 'all')"},
                },
            },
        )

    def execute(self, dry_run: bool = True, target_scope: str = "all", **kwargs: Any) -> ToolExecutionResult:
        scope = InputSanitizer.sanitize_string(target_scope, max_length=16).lower() or "all"
        is_dry_run = bool(dry_run)

        # Permitted target search boundaries
        home_dir = os.path.expanduser("~")
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        scan_roots = [project_dir]
        cache_dir = os.path.join(home_dir, ".cache")
        if os.path.isdir(cache_dir):
            scan_roots.append(cache_dir)
            
        termux_cache = "/data/data/com.termux/cache"
        if os.path.isdir(termux_cache):
            scan_roots.append(termux_cache)

        candidates_to_delete: List[str] = []
        directories_to_remove: List[str] = []
        bytes_reclaimed = 0

        for root_dir in scan_roots:
            if not os.path.exists(root_dir):
                continue

            for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
                # Don't recurse into .git or virtual environments
                if ".git" in dirnames:
                    dirnames.remove(".git")
                if "venv" in dirnames:
                    dirnames.remove("venv")
                if ".venv" in dirnames:
                    dirnames.remove(".venv")

                # Scope: Python __pycache__
                if scope in ("pycache", "all"):
                    if os.path.basename(dirpath) == "__pycache__":
                        directories_to_remove.append(dirpath)
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            try:
                                bytes_reclaimed += os.path.getsize(fp)
                            except OSError:
                                pass
                        continue

                # Scope: Temporary / backup files
                if scope in ("temp", "all"):
                    for f in filenames:
                        if f in PROTECTED_PATTERNS:
                            continue
                        if f.endswith((".tmp", ".bak", ".swp", ".pyc", ".pyo")):
                            fp = os.path.join(dirpath, f)
                            try:
                                sz = os.path.getsize(fp)
                                candidates_to_delete.append(fp)
                                bytes_reclaimed += sz
                            except OSError:
                                pass

        # Perform actual deletion if not dry run
        files_removed_count = 0
        dirs_removed_count = 0

        if not is_dry_run:
            for fpath in candidates_to_delete:
                try:
                    os.remove(fpath)
                    files_removed_count += 1
                except OSError as e:
                    logger.warning(f"Could not remove file {fpath}: {e}")

            for dpath in directories_to_remove:
                try:
                    shutil.rmtree(dpath, ignore_errors=True)
                    dirs_removed_count += 1
                except OSError as e:
                    logger.warning(f"Could not remove directory {dpath}: {e}")
        else:
            files_removed_count = len(candidates_to_delete)
            dirs_removed_count = len(directories_to_remove)

        mb_freed = round(bytes_reclaimed / (1024.0 * 1024.0), 3)
        summary = (
            f"System Cleaner ({'PREVIEW / DRY-RUN' if is_dry_run else 'EXECUTED'}): "
            f"Found {files_removed_count} files and {dirs_removed_count} cache directories. "
            f"Potential space reclaimed: {mb_freed} MB."
        )

        output_payload = {
            "dry_run": is_dry_run,
            "scope": scope,
            "files_targeted": files_removed_count,
            "directories_targeted": dirs_removed_count,
            "bytes_reclaimed": bytes_reclaimed,
            "mb_reclaimed": mb_freed,
            "summary": summary,
            "sample_targets": candidates_to_delete[:10],
            "timestamp": time.time(),
        }

        return ToolExecutionResult(
            success=True,
            output=output_payload,
            error=None,
            duration_ms=0,
        )


class SystemCleanerExtension(ExtensionPlugin):
    """Void plugin for clearing temporary cache files and reclaimed flash storage."""

    def __init__(self):
        super().__init__(
            name="system_cleaner",
            version="1.0.0",
            description="Reclaim storage by removing temporary cache files and __pycache__ bytecodes safely.",
            author="Void Core Team",
        )
        self._strategy = SystemCleanerStrategy()

    def initialize(self, context: Optional[Dict[str, Any]] = None) -> None:
        logger.info("Initialized SystemCleanerExtension.")

    def get_strategies(self) -> List[ToolStrategy]:
        return [self._strategy]
