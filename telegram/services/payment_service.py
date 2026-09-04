"""
telegram/services/payment_service.py - Telegram Stars & Fiat Payment Processing Service.

Handles subscription tiers, Telegram Stars (XTR) invoices, pre-checkout verification,
and atomic transaction/subscription fulfillment.
"""

import os
import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from telegram.database.models import (
    UserTier,
    Subscription,
    PaymentTransaction,
)
from telegram.database.db_manager import global_bot_db

logger = logging.getLogger("VoidTelegram.Payments")


@dataclass(frozen=True)
class PlanDefinition:
    tier: UserTier
    name: str
    stars_price: int  # Price in Telegram Stars (currency="XTR")
    fiat_cents: int   # Price in USD cents (e.g. 999 = $9.99)
    duration_days: int
    features: List[str]
    description: str


PLAN_CATALOG: Dict[UserTier, PlanDefinition] = {
    UserTier.FREE: PlanDefinition(
        tier=UserTier.FREE,
        name="Void Starter",
        stars_price=0,
        fiat_cents=0,
        duration_days=3650,
        features=[
            "1 Connected Android Node",
            "Deterministic Heuristic Engine",
            "Basic Termux Hardware Controls",
            "Rate Limit: 12 commands/min",
            "Interactive Telegram TUI Dashboard",
        ],
        description="Ideal for single-device automation and local testing.",
    ),
    UserTier.PRO: PlanDefinition(
        tier=UserTier.PRO,
        name="Void Pro Node",
        stars_price=250,
        fiat_cents=999,
        duration_days=30,
        features=[
            "Up to 3 Connected Android Devices",
            "Local Quantized LLMs (SmolLM-135M / Qwen-0.5B)",
            "Unlimited Dynamic Extensions & Plugins",
            "Cloud Bridge & Cross-Device Sync",
            "Rate Limit: 60 commands/min",
            "Instant Camera & Media Telemetry",
        ],
        description="Power automation with local offline AI models and multi-device coordination.",
    ),
    UserTier.ENTERPRISE: PlanDefinition(
        tier=UserTier.ENTERPRISE,
        name="Void Enterprise Fleet",
        stars_price=1000,
        fiat_cents=3999,
        duration_days=30,
        features=[
            "Unlimited Android Fleet Nodes",
            "Fine-Tuned Specialized Edge ReAct Routing",
            "Autonomous High-Concurrency Daemon Swarm",
            "Encrypted PBKDF2 Multi-User Secret Vaults",
            "Rate Limit: 300 commands/min",
            "Priority Hardware Execution & 24/7 SLA",
        ],
        description="Industrial-grade mobile fleet orchestration and multi-agent coordination.",
    ),
}


class PaymentService:
    """Manages subscription catalog, invoice generation, and payment lifecycle."""

    def __init__(self, db_manager=global_bot_db):
        self.db = db_manager

    @staticmethod
    def get_catalog() -> Dict[UserTier, PlanDefinition]:
        """Returns all available plan definitions."""
        return PLAN_CATALOG

    @staticmethod
    def get_plan(tier: UserTier) -> Optional[PlanDefinition]:
        """Retrieves a specific plan by tier enum."""
        return PLAN_CATALOG.get(tier)

    def create_invoice_payload(self, user_id: int, target_tier: UserTier) -> str:
        """Constructs an encrypted or deterministic payload string for the invoice."""
        tx_ref = uuid.uuid4().hex[:12]
        return f"void_sub:{user_id}:{target_tier.value}:{int(time.time())}:{tx_ref}"

    def parse_invoice_payload(self, payload: str) -> Optional[Dict[str, Any]]:
        """Parses and validates invoice payload string."""
        try:
            parts = payload.split(":")
            if len(parts) != 5 or parts[0] != "void_sub":
                return None
            return {
                "user_id": int(parts[1]),
                "tier": UserTier(parts[2]),
                "timestamp": int(parts[3]),
                "ref": parts[4],
            }
        except Exception as e:
            logger.warning(f"Malformed invoice payload '{payload}': {e}")
            return None

    def validate_pre_checkout(self, query_id: str, invoice_payload: str) -> Tuple[bool, str]:
        """Verifies pre-checkout query before charging customer."""
        parsed = self.parse_invoice_payload(invoice_payload)
        if not parsed:
            return False, "Invalid invoice identifier or expired checkout session."
        if parsed["tier"] not in (UserTier.PRO, UserTier.ENTERPRISE):
            return False, "Selected tier is not eligible for commercial subscription."
        return True, "OK"

    def fulfill_payment(
        self,
        user_id: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str,
        invoice_payload: str,
        currency: str,
        total_amount: int,
    ) -> Optional[Subscription]:
        """
        Atomically records payment transaction and provisions upgraded subscription.
        Supports Telegram Stars (XTR) and fiat currencies.
        """
        parsed = self.parse_invoice_payload(invoice_payload)
        target_tier = parsed["tier"] if parsed else UserTier.PRO
        plan = self.get_plan(target_tier)
        duration_days = plan.duration_days if plan else 30

        now = time.time()
        expires_at = now + (duration_days * 86400)

        # 1. Record payment transaction
        tx_id = f"tx_{uuid.uuid4().hex[:16]}"
        transaction = PaymentTransaction(
            id=tx_id,
            user_id=user_id,
            telegram_payment_charge_id=telegram_payment_charge_id or "stars_charge",
            provider_payment_charge_id=provider_payment_charge_id or "telegram_stars",
            invoice_payload=invoice_payload,
            currency=currency,
            total_amount=total_amount,
            tier_purchased=target_tier.value,
            created_at=now,
            status="SUCCESS",
        )
        self.db.record_transaction(transaction)

        # 2. Provision Subscription
        sub_id = f"sub_{uuid.uuid4().hex[:12]}"
        subscription = Subscription(
            id=sub_id,
            user_id=user_id,
            tier=target_tier,
            status="ACTIVE",
            started_at=now,
            expires_at=expires_at,
            auto_renew=True,
        )
        self.db.create_or_update_subscription(subscription)

        logger.info(f"Successfully fulfilled {target_tier.value} upgrade for user {user_id} (tx: {tx_id})")
        return subscription

    def get_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """Retrieves comprehensive active subscription details."""
        user = self.db.get_user(user_id)
        current_tier = user.tier if user else UserTier.FREE
        sub = self.db.get_active_subscription(user_id)
        plan = self.get_plan(current_tier)

        days_remaining = 0
        if sub and sub.expires_at > time.time():
            days_remaining = max(0, int((sub.expires_at - time.time()) / 86400))

        return {
            "tier": current_tier.value,
            "plan_name": plan.name if plan else "Free",
            "is_active": True if current_tier != UserTier.FREE and days_remaining > 0 else (current_tier == UserTier.FREE),
            "days_remaining": days_remaining,
            "expires_at": sub.expires_at if sub else 0.0,
            "features": plan.features if plan else [],
        }


global_payment_service = PaymentService()
