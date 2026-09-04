"""
tests/test_security.py - Security Hardening & Cryptographic Verification.
"""

import os
import pytest
from security.sanitizer import InputSanitizer, SecurityValidationError
from security.credential_vault import CredentialVault
from security.rate_limiter import TokenBucketRateLimiter, SessionTimeoutManager


def test_phone_number_sanitization():
    # Valid phone formats
    assert InputSanitizer.validate_phone_number("+1234567890") == "+1234567890"
    assert InputSanitizer.validate_phone_number("1234567") == "1234567"
    assert InputSanitizer.validate_phone_number("  +1-800-555-0199  ") == "+18005550199"

    # Malicious injection payloads must be blocked
    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_phone_number("+1234; rm -rf /")

    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_phone_number("12345\ncat /etc/passwd")

    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_phone_number("1234`reboot`")


def test_url_sanitization():
    assert InputSanitizer.validate_url("https://google.com") == "https://google.com"
    assert InputSanitizer.validate_url("http://192.168.1.1:8080/file.zip") == "http://192.168.1.1:8080/file.zip"

    # Dangerous protocol schemes must be rejected
    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_url("file:///etc/passwd")

    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_url("javascript:alert(1)")


def test_string_sanitizer():
    # Strip null bytes and ANSI injection
    raw = "Hello\x00 World!\x1b[31m Red Text\x1b[0m"
    clean = InputSanitizer.sanitize_string(raw)
    assert "\x00" not in clean
    assert "\x1b" not in clean
    assert "Hello World!" in clean
    assert "Red Text" in clean


def test_arg_vector_validation():
    # Safe vector
    safe_vec = ["termux-toast", "Hello World"]
    assert InputSanitizer.validate_arg_vector(safe_vec) == safe_vec

    # Injections via null bytes
    with pytest.raises(SecurityValidationError):
        InputSanitizer.validate_arg_vector(["termux-toast", "test\x00inject"])


def test_aes256_credential_vault(tmp_path):
    vault_file = str(tmp_path / "test_vault.enc")
    passphrase = "MasterSecurePassword!123"

    secrets = {
        "TELEGRAM_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "ADMIN_TELEGRAM_ID": "987654321",
        "API_KEY": "sk-local-device-secure-key",
    }

    # Save to vault
    CredentialVault.save_vault(secrets, passphrase, vault_path=vault_file)
    assert os.path.exists(vault_file)

    # Load from vault
    loaded = CredentialVault.load_vault(passphrase, vault_path=vault_file)
    assert loaded == secrets

    # Wrong passphrase should raise error
    with pytest.raises(ValueError):
        CredentialVault.load_vault("WrongPassphrase", vault_path=vault_file)


def test_rate_limiter():
    limiter = TokenBucketRateLimiter(rate_per_second=1.0, capacity=2)

    # 2 immediate requests should succeed
    allowed1, _ = limiter.allow_request("user1")
    allowed2, _ = limiter.allow_request("user1")
    assert allowed1 is True
    assert allowed2 is True

    # 3rd immediate request must be throttled
    allowed3, wait_sec = limiter.allow_request("user1")
    assert allowed3 is False
    assert wait_sec > 0.0


def test_session_timeout_manager():
    mgr = SessionTimeoutManager(timeout_seconds=2)
    mgr.touch_session("user1")
    assert mgr.is_session_active("user1") is True

    mgr.invalidate_session("user1")
    assert mgr.is_session_active("user1") is False


def test_permission_manager_governance():
    """Verifies that all permissions are marked optional and produce valid justification."""
    from security.permissions import PermissionManager, PERMISSION_REGISTRY

    # Verify all permissions exist in registry
    assert "camera" in PERMISSION_REGISTRY
    assert "storage" in PERMISSION_REGISTRY
    assert "sms" in PERMISSION_REGISTRY
    assert "location" in PERMISSION_REGISTRY

    perms = PermissionManager.get_all_permissions()
    assert len(perms) >= 7

    # Ensure every single permission is marked optional (user sovereignty)
    for p in perms:
        assert p.is_mandatory is False
        assert p.why_needed != ""
        assert p.fallback_behavior != ""
        assert p.how_to_manage != ""

    # Verify explanation generation
    explanation = PermissionManager.explain_permission("camera")
    assert "PERMISSION NOTICE" in explanation
    assert "Camera" in explanation
    assert "100% voluntary" in explanation

    # Verify CLI report generation
    report = PermissionManager.generate_cli_report()
    assert "VOID PRIVACY & ANDROID PERMISSIONS GOVERNANCE" in report
    assert "100% OPTIONAL" in report

