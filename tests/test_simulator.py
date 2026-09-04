"""
tests/test_simulator.py - Automated Tests for Desktop Hardware Simulator.
"""

import json
from core.simulator import TermuxHardwareSimulator


def test_simulator_hardware_status():
    """Verifies that simulator outputs valid JSON schemas for telemetry tools."""
    # Battery status
    batt_raw = TermuxHardwareSimulator.simulate(["termux-battery-status"])
    batt_data = json.loads(batt_raw)
    assert batt_data["health"] == "GOOD"
    assert batt_data["percentage"] == 88

    # Location
    loc_raw = TermuxHardwareSimulator.simulate(["termux-location"])
    loc_data = json.loads(loc_raw)
    assert "latitude" in loc_data
    assert "longitude" in loc_data

    # Wi-Fi
    wifi_raw = TermuxHardwareSimulator.simulate(["termux-wifi-connectioninfo"])
    wifi_data = json.loads(wifi_raw)
    assert wifi_data["ssid"] == "Termux_Agent_Secure_5G"
    assert "ip" in wifi_data


def test_simulator_actions():
    """Verifies simulated actions like torch, vibrate, tts, and wake-lock."""
    # Torch
    assert "ON" in TermuxHardwareSimulator.simulate(["termux-torch", "on"])
    assert "OFF" in TermuxHardwareSimulator.simulate(["termux-torch", "off"])

    # Vibrate
    vib = TermuxHardwareSimulator.simulate(["termux-vibrate", "-d", "800"])
    assert "800ms" in vib

    # Notification & Toast
    toast = TermuxHardwareSimulator.simulate(["termux-toast", "Hello World"])
    assert "Hello World" in toast

    # Wake Lock
    wl = TermuxHardwareSimulator.simulate(["termux-wake-lock"])
    assert "wake lock" in wl.lower()

    # Wake Unlock
    wul = TermuxHardwareSimulator.simulate(["termux-wake-unlock"])
    assert "released" in wul.lower()

    # Termux Open
    topen = TermuxHardwareSimulator.simulate(["termux-open", "https://github.com"])
    assert "https://github.com" in topen
