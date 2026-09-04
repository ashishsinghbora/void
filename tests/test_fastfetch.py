"""
tests/test_fastfetch.py - Unit Tests for FastFetch Telemetry Generator.
"""

import pytest
from core.fastfetch import FastFetchCollector


def test_fastfetch_collector_data():
    collector = FastFetchCollector()
    data = collector.collect()

    assert "device" in data
    assert "os" in data
    assert "kernel" in data
    assert "arch" in data
    assert "uptime" in data
    assert "process_rss_mb" in data
    assert isinstance(data["process_rss_mb"], (int, float))
    assert "battery" in data
    assert "network" in data
    assert "daemons" in data
    assert "database" in data


def test_fastfetch_render_ascii():
    collector = FastFetchCollector()
    ascii_out = collector.render_ascii(use_color=False)

    assert "VOID TELEMETRY FASTFETCH" in ascii_out
    assert "Host" in ascii_out
    assert "Void RSS" in ascii_out
    assert "Battery" in ascii_out


def test_fastfetch_render_markdown():
    collector = FastFetchCollector()
    md_out = collector.render_markdown()

    assert "VOID EDGE SYSTEM TELEMETRY" in md_out
    assert "Void RSS:" in md_out
    assert "Battery:" in md_out
    assert "Background Daemons:" in md_out
