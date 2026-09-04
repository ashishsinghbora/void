"""
core/model_manager.py - Autonomous Small-Model Bootstrapper & Local LLM Manager.

Manages discovery, dynamic downloading with SHA256 verification, and streaming
progress telemetry for quantized edge models (GGUF, Needle, SmolLM) stored in ~/.void/models.
"""

import os
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Callable

import requests

logger = logging.getLogger("VoidAdvancedCore.ModelManager")

# Default storage directory for quantized local LLM weights
DEFAULT_MODELS_DIR = os.environ.get(
    "VOID_MODELS_DIR",
    os.path.join(os.path.expanduser("~"), ".void", "models")
)

# Registry of edge-compatible small quantized models
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    "smollm-135m": {
        "name": "SmolLM-135M-Instruct-Q4",
        "description": "Ultra-lightweight 135M param edge model (< 90MB RAM)",
        "filename": "smollm-135m-instruct-q4_k_m.gguf",
        "size_mb": 85.0,
        "url": "https://huggingface.co/HuggingFaceTB/SmolLM-135M-Instruct-GGUF/resolve/main/smollm-135m-instruct-q4_k_m.gguf",
        "sha256": None,
    },
    "needle-compact": {
        "name": "Needle-Edge-Vector-Weights",
        "description": "Deterministic needle-based compact routing weights (< 30MB RAM)",
        "filename": "needle-compact.bin",
        "size_mb": 28.5,
        "url": "https://raw.githubusercontent.com/ashishsinghbora/void/main/models/needle-compact.bin",
        "sha256": None,
    },
    "qwen-0.5b": {
        "name": "Qwen2.5-0.5B-Instruct-Q4",
        "description": "Balanced reasoning edge model (< 380MB RAM)",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_mb": 350.0,
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "sha256": None,
    },
}


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

    def get_active_model_path(self) -> Optional[str]:
        """Returns the absolute file path to the preferred active local model."""
        # 1. Check explicit environment override
        env_model = os.environ.get("VOID_MODEL_PATH")
        if env_model and os.path.isfile(env_model) and os.path.getsize(env_model) > 0:
            return os.path.abspath(env_model)

        # 2. Check catalog preference order in models_dir
        for key in ("smollm-135m", "needle-compact", "qwen-0.5b"):
            cat_file = MODEL_CATALOG[key]["filename"]
            target = os.path.join(self._models_dir, cat_file)
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                return target

        # 3. Check any installed model in directory
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
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        Streams download of specified model with SHA256 validation and progress updates.

        :param model_id: Catalog key (e.g. 'smollm-135m')
        :param progress_callback: Optional callback(downloaded_bytes, total_bytes, percent, speed_kbps)
        :param timeout: HTTP request timeout
        :return: Result dict with status, path, size_mb, sha256
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
                    # Throttle callbacks to every 0.3s or upon completion
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


# Global singleton instance
global_model_manager = ModelManager()
