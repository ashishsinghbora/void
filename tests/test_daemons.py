"""
tests/test_daemons.py - Proactive Automation & Notification Daemon Tests.
"""

from daemons.notification_daemon import NotificationInterceptorDaemon
from daemons.routine_engine import RoutineScheduler
from core.types import NotificationCategory
from storage.repository import NotificationRepository


def test_notification_otp_classification():
    daemon = NotificationInterceptorDaemon()

    # Case 1: OTP Notification
    daemon._evaluate_single_notification(
        notif_id="101",
        pkg="com.bank.secure",
        title="Bank Alert",
        content="Your OTP verification passcode is 739201. Valid for 5 minutes.",
    )

    repo = NotificationRepository()
    records = repo.get_recent(limit=5)
    match = [r for r in records if r["id"] == "101"]
    assert len(match) == 1
    assert match[0]["category"] == NotificationCategory.OTP.value
    assert match[0]["is_otp"] == 1
    assert match[0]["otp_code"] == "739201"


def test_notification_spam_classification():
    daemon = NotificationInterceptorDaemon()

    # Case 2: Spam Notification
    daemon._evaluate_single_notification(
        notif_id="102",
        pkg="com.spam.marketing",
        title="Exclusive Promo Offer!",
        content="Claim free cash discount and winner prize now!",
    )

    repo = NotificationRepository()
    records = repo.get_recent(limit=5)
    match = [r for r in records if r["id"] == "102"]
    assert len(match) == 1
    assert match[0]["category"] == NotificationCategory.SPAM.value


def test_routine_crontab_generation():
    crontab = RoutineScheduler.generate_crontab_entries("/data/data/com.termux/files/home/app.py")
    assert "--briefing" in crontab
    assert "--vacuum" in crontab
    assert "--battery-check" in crontab
