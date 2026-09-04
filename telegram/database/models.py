"""
telegram/database/models.py - Strongly Typed Domain Models for Telegram Control Plane.
"""

import time
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class UserTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


@dataclass
class User:
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    tier: UserTier = UserTier.FREE
    role: UserRole = UserRole.USER
    created_at: float = 0.0
    last_active_at: float = 0.0

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_active_at:
            self.last_active_at = now
        if isinstance(self.tier, str) and not isinstance(self.tier, UserTier):
            self.tier = UserTier(self.tier)
        if isinstance(self.role, str) and not isinstance(self.role, UserRole):
            self.role = UserRole(self.role)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        d["role"] = self.role.value
        return d


@dataclass
class Device:
    device_id: str
    user_id: int
    name: str
    platform: str = "Android"
    model: str = "Termux Node"
    battery_level: int = 100
    is_online: bool = True
    last_seen_at: float = 0.0

    def __post_init__(self):
        if not self.last_seen_at:
            self.last_seen_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserSession:
    session_id: str
    user_id: int
    created_at: float = 0.0
    expires_at: float = 0.0
    last_activity: float = 0.0
    state_json: str = "{}"

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.last_activity:
            self.last_activity = now
        if not self.expires_at:
            self.expires_at = now + 86400  # Default 24h

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Subscription:
    id: str
    user_id: int
    tier: UserTier
    status: str = "ACTIVE"  # ACTIVE, EXPIRED, CANCELLED
    started_at: float = 0.0
    expires_at: float = 0.0
    auto_renew: bool = True

    def __post_init__(self):
        now = time.time()
        if not self.started_at:
            self.started_at = now
        if not self.expires_at:
            self.expires_at = now + 30 * 86400  # 30 days
        if isinstance(self.tier, str) and not isinstance(self.tier, UserTier):
            self.tier = UserTier(self.tier)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        return d


@dataclass
class PaymentTransaction:
    id: str
    user_id: int
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
    invoice_payload: str
    currency: str
    total_amount: int
    tier_purchased: str
    created_at: float = 0.0
    status: str = "SUCCESS"  # PENDING, SUCCESS, REFUNDED

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserSettings:
    user_id: int
    notifications_enabled: bool = True
    otp_interception_enabled: bool = True
    quiet_hours_enabled: bool = False
    theme: str = "cyber_dark"
    security_level: str = "HIGH"  # STANDARD, HIGH, STRICT
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
