"""
tests/test_social_apps.py - Unit Tests for Social Media & App Automation Strategies.
"""

import pytest
from tools.social_apps import (
    SendWhatsAppMessageStrategy,
    OpenTelegramChatStrategy,
    OpenSocialProfileStrategy,
    LaunchInstalledAppStrategy,
)


def test_send_whatsapp_message_valid():
    strat = SendWhatsAppMessageStrategy()
    res = strat.run_safe(phone="+15551234567", message="Testing Void Agent")
    assert res.success is True
    assert "15551234567" in str(res.output)


def test_send_whatsapp_message_invalid_phone():
    strat = SendWhatsAppMessageStrategy()
    res = strat.run_safe(phone="invalid_phone", message="Hello")
    assert res.success is False
    assert "Invalid phone number" in res.error


def test_open_telegram_chat():
    strat = OpenTelegramChatStrategy()
    res = strat.run_safe(username="@ashishsinghbora")
    assert res.success is True
    assert "ashishsinghbora" in str(res.output)


def test_open_social_profile():
    strat = OpenSocialProfileStrategy()

    # Instagram
    res_ig = strat.run_safe(platform="instagram", handle="android")
    assert res_ig.success is True
    assert "Instagram" in str(res_ig.output)

    # LinkedIn
    res_li = strat.run_safe(platform="linkedin", handle="ashish-singh-bora")
    assert res_li.success is True
    assert "Linkedin" in str(res_li.output)

    # GitHub
    res_gh = strat.run_safe(platform="github", handle="ashishsinghbora/void")
    assert res_gh.success is True
    assert "Github" in str(res_gh.output)

    # Unsupported platform
    res_bad = strat.run_safe(platform="unsupported_network", handle="user")
    assert res_bad.success is False
    assert "Unsupported platform" in res_bad.error


def test_launch_installed_app():
    strat = LaunchInstalledAppStrategy()

    # Known alias
    res = strat.run_safe(app_name="whatsapp")
    assert res.success is True
    assert "com.whatsapp" in str(res.output)

    # YouTube
    res_yt = strat.run_safe(app_name="youtube")
    assert res_yt.success is True
    assert "com.google.android.youtube" in str(res_yt.output)

    # Custom package name
    res_custom = strat.run_safe(app_name="org.custom.app")
    assert res_custom.success is True
    assert "org.custom.app" in str(res_custom.output)
