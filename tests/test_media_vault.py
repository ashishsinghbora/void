"""
tests/test_media_vault.py - Unit tests for Unified Media Vault Manager.
"""

import os
import tempfile
from unittest.mock import patch
import pytest

from core.media_vault import MediaVaultManager


def test_media_vault_directory_resolution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.object(MediaVaultManager, "PRIMARY_CANDIDATES", [tmp_dir]):
            mgr = MediaVaultManager()
            assert mgr.media_dir == tmp_dir


def test_media_vault_generate_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.object(MediaVaultManager, "PRIMARY_CANDIDATES", [tmp_dir]):
            mgr = MediaVaultManager()
            path = mgr.generate_media_path(prefix="test_snap", extension="png")
            assert path.startswith(tmp_dir)
            assert "test_snap" in path
            assert path.endswith(".png")


def test_media_vault_list_recent():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.object(MediaVaultManager, "PRIMARY_CANDIDATES", [tmp_dir]):
            mgr = MediaVaultManager()
            # Create two files
            f1 = os.path.join(tmp_dir, "file1.jpg")
            f2 = os.path.join(tmp_dir, "file2.mp4")
            with open(f1, "w") as f:
                f.write("image data")
            with open(f2, "w") as f:
                f.write("video data")

            recent = mgr.list_recent_media(limit=10)
            assert len(recent) == 2
            filenames = [r["filename"] for r in recent]
            assert "file1.jpg" in filenames
            assert "file2.mp4" in filenames
