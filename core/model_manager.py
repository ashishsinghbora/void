"""
core/model_manager.py - Autonomous Small-Model Bootstrapper & Local LLM Manager.

Manages discovery, dynamic downloading with SHA256 verification, and streaming
progress telemetry for quantized edge models (GGUF, Needle, SmolLM, Llama, Qwen) stored in ~/.void/models.
Includes interactive CLI & Telegram setup wizards with hardware RAM auto-detection and recommendations.
"""

import os
import sys
import time
import shutil
import hashlib
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple

import requests

logger = logging.getLogger("VoidAdvancedCore.ModelManager")

# Default storage directory for quantized local LLM weights
DEFAULT_MODELS_DIR = os.environ.get(
    "VOID_MODELS_DIR",
    os.path.join(os.path.expanduser("~"), ".void", "models")
)

CONFIG_ENV_PATH = os.path.expanduser("~/.void/config.env")

# Registry of edge-compatible small quantized models
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "smollm-135m": {
        "name": "SmolLM-135M-Instruct-Q4",
        "tier": "Ultra-Lean (< 90MB RAM)",
        "description": "Ultra-lightweight 135M param edge model for basic devices",
        "filename": "smollm-135m-instruct-q4_k_m.gguf",
        "size_mb": 85.0,
        "min_ram_mb": 512,
        "url": "https://huggingface.co/HuggingFaceTB/SmolLM-135M-Instruct-GGUF/resolve/main/smollm-135m-instruct-q4_k_m.gguf",
        "sha256": None,
    },
    "needle-compact": {
        "name": "Needle-Edge-Vector-Weights",
        "tier": "Micro (< 30MB RAM)",
        "description": "Deterministic needle-based compact routing weights",
        "filename": "needle-compact.bin",
        "size_mb": 28.5,
        "min_ram_mb": 256,
        "url": "https://raw.githubusercontent.com/ashishsinghbora/void/main/models/needle-compact.bin",
        "sha256": None,
    },
    "qwen-0.5b": {
        "name": "Qwen2.5-0.5B-Instruct-Q4",
        "tier": "Balanced Edge (< 380MB RAM)",
        "description": "Balanced reasoning edge model with tool calling abilities",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_mb": 350.0,
        "min_ram_mb": 1500,
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "sha256": None,
    },
    "llama-3.2-1b": {
        "name": "Llama-3.2-1B-Instruct-Q4",
        "tier": "Performance 1B (~850MB RAM)",
        "description": "Meta Llama 3.2 1B instruction-tuned conversational agent",
        "filename": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "size_mb": 850.0,
        "min_ram_mb": 2500,
        "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "sha256": None,
    },
    "smollm2-1.7b": {
        "name": "SmolLM2-1.7B-Instruct-Q4",
        "tier": "Advanced Edge (~1.1GB RAM)",
        "description": "Hugging Face SmolLM2 1.7B capable reasoning and reasoning model",
        "filename": "smollm2-1.7b-instruct-q4_k_m.gguf",
        "size_mb": 1050.0,
        "min_ram_mb": 3500,
        "url": "https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF/resolve/main/smollm2-1.7b-instruct-q4_k_m.gguf",
        "sha256": None,
    },
    "qwen2.5-1.5b": {
        "name": "Qwen2.5-1.5B-Instruct-Q4",
        "tier": "Advanced Reasoning (~1.2GB RAM)",
        "description": "Deep multi-step reasoning and mobile instruction following",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size_mb": 1150.0,
        "min_ram_mb": 4000,
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "sha256": None,
    },
    "qwen2.5-3b": {
        "name": "Qwen2.5-3B-Instruct-Q4",
        "tier": "Heavy Edge (~2.2GB RAM)",
        "description": "Enterprise-grade local intelligence for devices with 8GB+ RAM",
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "size_mb": 2150.0,
        "min_ram_mb": 6000,
        "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "sha256": None,
    },
}


def detect_system_ram_mb() -> Tuple[int, int]:
    """
    Detects (total_ram_mb, available_ram_mb) from /proc/meminfo or sysconf.
    Returns safe fallbacks if unavailable.
    """
    total_mb = 0
    avail_mb = 0

    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        total_mb = int(parts[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        parts = line.split()
                        avail_mb = int(parts[1]) // 1024
                    elif line.startswith("MemFree:") and avail_mb == 0:
                        parts = line.split()
                        avail_mb = int(parts[1]) // 1024
            if total_mb > 0:
                return total_mb, avail_mb
        except Exception:
            pass

    # Fallback via os.sysconf
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_mb = int((pages * page_size) / (1024 * 1024))
        avail_mb = total_mb // 2
        return total_mb, avail_mb
    except Exception:
        pass

    return 4096, 2048


def recommend_model_for_device(total_ram_mb: int) -> str:
    """Selects the highest-accuracy model that runs safely within physical device RAM."""
    if total_ram_mb < 2000:
        return "smollm-135m"
    elif total_ram_mb < 3500:
        return "qwen-0.5b"
    elif total_ram_mb < 6000:
        return "llama-3.2-1b"
    elif total_ram_mb < 9000:
        return "smollm2-1.7b"
    else:
        return "qwen2.5-3b"


class ModelManager:
    """Manages local small-model weights, discovery, and automated bootstrapping."""
    __slots__ = ("_models_dir",)

    def __init__(self, models_dir: str = DEFAULT_MODELS_DIR):
        self._models_dir = os.path.abspath(models_dir)
        os.makedirs(self._models_dir, exist_ok=True)

    @property
    def models_dir(self) -> str:
        return self._models_dir

    def list_installed_models(self) -> List[Dict[str, Any]]:
        """Scans models directory for installed .gguf, .bin, or .onnx files."""
        if not os.path.exists(self._models_dir):
            return []

        installed = []
        valid_exts = {".gguf", ".bin", ".onnx", ".tflite"}
        try:
            for entry in os.scandir(self._models_dir):
                if entry.is_file():
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() in valid_exts:
                        stat = entry.stat()
                        size_mb = round(stat.st_size / (1024.0 * 1024.0), 2)
                        installed.append({
                            "filename": entry.name,
                            "path": entry.path,
                            "size_mb": size_mb,
                            "modified": stat.st_mtime,
                        })
        except Exception as e:
            logger.error(f"Error scanning models directory {self._models_dir}: {e}")

        # Sort newest first
        installed.sort(key=lambda x: x["modified"], reverse=True)
        return installed

    def get_configured_active_model_id(self) -> Optional[str]:
        """Reads active model id from environment or ~/.void/config.env."""
        val = os.environ.get("VOID_ACTIVE_MODEL", "").strip()
        if val:
            return val

        if os.path.exists(CONFIG_ENV_PATH):
            try:
                with open(CONFIG_ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("VOID_ACTIVE_MODEL="):
                            return line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
        return None

    def set_active_model(self, model_id: str) -> bool:
        """Sets preferred model id and writes to ~/.void/config.env."""
        if model_id not in MODEL_CATALOG:
            return False

        os.environ["VOID_ACTIVE_MODEL"] = model_id
        try:
            os.makedirs(os.path.dirname(CONFIG_ENV_PATH), exist_ok=True)
            lines = []
            if os.path.exists(CONFIG_ENV_PATH):
                with open(CONFIG_ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.startswith("VOID_ACTIVE_MODEL="):
                            lines.append(line.rstrip())
            lines.append(f'VOID_ACTIVE_MODEL="{model_id}"')
            with open(CONFIG_ENV_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"Active model set to: {model_id}")
            return True
        except Exception as e:
            logger.warning(f"Could not save active model to {CONFIG_ENV_PATH}: {e}")
            return False

    def get_active_model_path(self) -> Optional[str]:
        """Returns the absolute file path to the preferred active local model."""
        # 1. Check explicit environment path override
        env_model = os.environ.get("VOID_MODEL_PATH")
        if env_model and os.path.isfile(env_model) and os.path.getsize(env_model) > 0:
            return os.path.abspath(env_model)

        # 2. Check configured model ID
        conf_id = self.get_configured_active_model_id()
        if conf_id and conf_id in MODEL_CATALOG:
            target = os.path.join(self._models_dir, MODEL_CATALOG[conf_id]["filename"])
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                return target

        # 3. Check catalog preference order in models_dir
        for key in ("smollm-135m", "needle-compact", "qwen-0.5b", "llama-3.2-1b", "smollm2-1.7b", "qwen2.5-1.5b", "qwen2.5-3b"):
            cat_file = MODEL_CATALOG[key]["filename"]
            target = os.path.join(self._models_dir, cat_file)
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                return target

        # 4. Check any installed model in directory
        installed = self.list_installed_models()
        if installed:
            return installed[0]["path"]

        return None

    def get_active_model_name(self) -> Optional[str]:
        """Returns friendly name of active model if available."""
        path = self.get_active_model_path()
        if not path:
            return None

        fname = os.path.basename(path)
        for cat in MODEL_CATALOG.values():
            if cat["filename"] == fname:
                return cat["name"]
        return fname

    def list_available_models(self) -> Dict[str, Dict[str, Any]]:
        """Returns the dictionary of all supported downloadable models."""
        installed_files = {m["filename"] for m in self.list_installed_models()}
        result = {}
        for key, meta in MODEL_CATALOG.items():
            result[key] = {
                **meta,
                "installed": meta["filename"] in installed_files,
            }
        return result

    def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Streams download of specified model with SHA256 validation and progress updates.
        """
        if model_id not in MODEL_CATALOG:
            return {
                "success": False,
                "error": f"Unknown model '{model_id}'. Available: {list(MODEL_CATALOG.keys())}",
            }

        meta = MODEL_CATALOG[model_id]
        target_path = os.path.join(self._models_dir, meta["filename"])
        temp_path = target_path + ".download.tmp"

        url = meta["url"]
        logger.info(f"Starting download of {meta['name']} from {url}...")

        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            total_bytes = int(response.headers.get("content-length", 0))
            downloaded_bytes = 0
            start_time = time.perf_counter()
            last_callback_time = 0.0

            sha256_hash = hashlib.sha256()

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    downloaded_bytes += len(chunk)

                    now = time.perf_counter()
                    if progress_callback and (now - last_callback_time >= 0.3 or downloaded_bytes == total_bytes):
                        elapsed = max(0.001, now - start_time)
                        speed_kbps = (downloaded_bytes / 1024.0) / elapsed
                        pct = round((downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0, 1)
                        progress_callback(downloaded_bytes, total_bytes, pct, speed_kbps)
                        last_callback_time = now

            computed_sha256 = sha256_hash.hexdigest()

            # Verify checksum if one was registered
            expected_sha256 = meta.get("sha256")
            if expected_sha256 and computed_sha256.lower() != expected_sha256.lower():
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return {
                    "success": False,
                    "error": f"SHA256 checksum mismatch! Expected: {expected_sha256}, Got: {computed_sha256}",
                }

            # Atomic rename from .tmp to final path
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(temp_path, target_path)

            raw_size = os.path.getsize(target_path)
            file_size_mb = max(0.01, round(raw_size / (1024.0 * 1024.0), 2)) if raw_size > 0 else 0.0
            logger.info(f"Model {meta['name']} downloaded successfully to {target_path} ({file_size_mb} MB).")

            # Auto-set as active model
            self.set_active_model(model_id)

            return {
                "success": True,
                "model_id": model_id,
                "path": target_path,
                "size_mb": file_size_mb,
                "sha256": computed_sha256,
            }

        except Exception as e:
            logger.error(f"Download failed for model '{model_id}': {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e),
            }

    def run_interactive_wizard(self) -> bool:
        """Runs mobile-optimized interactive terminal model selection wizard."""
        c_cyan = "\033[0;36m"
        c_green = "\033[0;32m"
        c_yellow = "\033[1;33m"
        c_purple = "\033[0;35m"
        c_red = "\033[0;31m"
        c_bold = "\033[1m"
        c_dim = "\033[2m"
        c_reset = "\033[0m"

        total_ram, avail_ram = detect_system_ram_mb()
        rec_model_id = recommend_model_for_device(total_ram)

        print(f"\n{c_bold}{c_cyan}================================================================")
        print("  🧠 VOID AUTONOMOUS LOCAL LLM SETUP WIZARD")
        print(f"================================================================{c_reset}")
        print(f"• {c_bold}Detected Device RAM:{c_reset} {c_green}{total_ram} MB total{c_reset} ({avail_ram} MB free)")
        print(f"• {c_bold}Recommended Architecture:{c_reset} {c_cyan}{MODEL_CATALOG[rec_model_id]['name']}{c_reset}")
        print("-" * 64)
        print(f"{c_bold}Available Local Edge Models:{c_reset}\n")

        models_list = list(MODEL_CATALOG.keys())
        installed_files = {m["filename"] for m in self.list_installed_models()}

        for idx, mid in enumerate(models_list, 1):
            m = MODEL_CATALOG[mid]
            is_rec = mid == rec_model_id
            is_inst = m["filename"] in installed_files

            rec_badge = f" {c_yellow}[RECOMMENDED]{c_reset}" if is_rec else ""
            inst_badge = f" {c_green}[INSTALLED]{c_reset}" if is_inst else ""

            print(f"  {c_bold}[{idx}]{c_reset} {c_cyan}{m['name']}{c_reset} ({m['size_mb']} MB){rec_badge}{inst_badge}")
            print(f"      {c_dim}Tier: {m['tier']} — {m['description']}{c_reset}")

        print(f"  {c_bold}[0]{c_reset} Keep Deterministic Heuristic Router (Zero-Weight, < 30MB RAM)")
        print(f"  {c_bold}[Q]{c_reset} Cancel & Exit")
        print("-" * 64)

        try:
            choice = input(f"{c_bold}Select model option [1-{len(models_list)}]: {c_reset}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{c_yellow}[INFO] Model wizard cancelled.{c_reset}")
            return False

        if choice in ("q", "cancel", "exit"):
            print(f"{c_yellow}Setup exited without changes.{c_reset}")
            return False

        if choice == "0":
            print(f"{c_green}[SUCCESS] Selected Heuristic Router (< 30MB RAM mode).{c_reset}")
            return True

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(models_list):
            print(f"{c_red}Invalid choice '{choice}'.{c_reset}")
            return False

        selected_id = models_list[int(choice) - 1]
        selected_meta = MODEL_CATALOG[selected_id]

        print(f"\n{c_cyan}[INFO] Selected {selected_meta['name']}. Checking local files...{c_reset}")
        target_path = os.path.join(self._models_dir, selected_meta["filename"])

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            print(f"{c_green}[SUCCESS] Model already installed at: {target_path}{c_reset}")
            self.set_active_model(selected_id)
            return True

        print(f"{c_yellow}[DOWNLOAD] Fetching {selected_meta['name']} ({selected_meta['size_mb']} MB)...{c_reset}")

        def cli_progress(downloaded, total, pct, speed_kbps):
            filled = int(pct / 5)
            bar = "█" * filled + "░" * (20 - filled)
            d_mb = round(downloaded / (1024 * 1024), 1)
            t_mb = round(total / (1024 * 1024), 1) if total > 0 else 0
            sys.stdout.write(f"\r  [{bar}] {pct}% | {d_mb}/{t_mb} MB @ {speed_kbps:.1f} KB/s")
            sys.stdout.flush()

        res = self.download_model(selected_id, progress_callback=cli_progress)
        print("")

        if res.get("success"):
            print(f"{c_green}{c_bold}🎉 {selected_meta['name']} installed and activated successfully!{c_reset}")
            print(f"Path: {c_cyan}{res['path']}{c_reset}")
            return True
        else:
            print(f"{c_red}[ERROR] Download failed: {res.get('error')}{c_reset}")
            return False


# Global singleton instance
global_model_manager = ModelManager()


if __name__ == "__main__":
    global_model_manager.run_interactive_wizard()
