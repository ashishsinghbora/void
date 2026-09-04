"""
tests/test_model_manager.py - Unit Tests for Autonomous Model Bootstrapper.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from core.model_manager import ModelManager, MODEL_CATALOG


def test_model_manager_catalog():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = ModelManager(models_dir=tmpdir)
        available = mm.list_available_models()

        assert "smollm-135m" in available
        assert "needle-compact" in available
        assert "qwen-0.5b" in available
        assert available["smollm-135m"]["installed"] is False


def test_model_manager_installed_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = ModelManager(models_dir=tmpdir)
        assert len(mm.list_installed_models()) == 0

        # Create dummy gguf file
        dummy_model = os.path.join(tmpdir, "smollm-135m-instruct-q4_k_m.gguf")
        with open(dummy_model, "wb") as f:
            f.write(b"GGUF" + b"\x00" * 1024)

        installed = mm.list_installed_models()
        assert len(installed) == 1
        assert installed[0]["filename"] == "smollm-135m-instruct-q4_k_m.gguf"

        active_path = mm.get_active_model_path()
        assert active_path == dummy_model
        assert mm.get_active_model_name() == "SmolLM-135M-Instruct-Q4"


def test_model_manager_unknown_model():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = ModelManager(models_dir=tmpdir)
        res = mm.download_model("nonexistent_model_id")
        assert res["success"] is False
        assert "Unknown model" in res["error"]


def test_model_manager_mock_download():
    with tempfile.TemporaryDirectory() as tmpdir:
        mm = ModelManager(models_dir=tmpdir)

        mock_content = b"TEST_MODEL_DATA_CHUNKS" * 100
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(mock_content))}
        mock_response.iter_content.return_value = [mock_content[:100], mock_content[100:]]

        progress_records = []
        def on_progress(downloaded, total, pct, speed):
            progress_records.append((downloaded, total, pct))

        with patch("requests.get", return_value=mock_response):
            res = mm.download_model("smollm-135m", progress_callback=on_progress)

        assert res["success"] is True
        assert os.path.exists(res["path"])
        assert res["size_mb"] > 0
        assert len(progress_records) > 0
