"""
telegram/handlers/billing_handlers.py - Subscription, Telegram Stars Invoicing & Payment Handlers.

Provides commands and callbacks for reviewing plans, issuing Telegram Stars (XTR) invoices,
pre-checkout integrity verification, and instant subscription fulfillment.
"""

import os
import logging
from typing import Any

from telegram.database.models import UserTier
from telegram.services.payment_service import global_payment_service, PLAN_CATALOG
from telegram.database.db_manager import global_bot_db

logger = logging.getLogger("VoidTelegram.BillingHandlers")

try:
    import telebot
    from telebot import types
except ImportError:
    telebot = None
    types = None


def get_billing_keyboard(user_id: int) -> Any:
    """Constructs inline keyboard with plan selection and invoice triggers."""
    if not types:
        return None

    markup = types.InlineKeyboardMarkup(row_width=1)
    status = global_payment_service.get_subscription_status(user_id)
    current_tier = status["tier"]

    if current_tier == "FREE":
        btn_pro = types.InlineKeyboardButton(
            "⭐ Upgrade to PRO (250 Stars / $9.99)",
            callback_data="buy_tier:PRO",
        )
        btn_ent = types.InlineKeyboardButton(
            "👑 Upgrade to ENTERPRISE (1000 Stars / $39.99)",
            callback_data="buy_tier:ENTERPRISE",
        )
        markup.add(btn_pro)
        markup.add(btn_ent)
    elif current_tier == "PRO":
        btn_renew = types.InlineKeyboardButton(
            "🔄 Renew PRO (250 Stars)",
            callback_data="buy_tier:PRO",
        )
        btn_ent = types.InlineKeyboardButton(
            "👑 Upgrade to ENTERPRISE (1000 Stars)",
            callback_data="buy_tier:ENTERPRISE",
        )
        markup.add(btn_renew)
        markup.add(btn_ent)
    else:
        btn_renew = types.InlineKeyboardButton(
            "🔄 Renew ENTERPRISE (1000 Stars)",
            callback_data="buy_tier:ENTERPRISE",
        )
        markup.add(btn_renew)

    btn_history = types.InlineKeyboardButton("📜 Billing Receipt History", callback_data="cb_billing_history")
    btn_back = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main")

    markup.add(btn_history)
    markup.add(btn_back)
    return markup


def render_billing_card(user_id: int) -> str:
    """Renders formatted Markdown plan comparison & subscription summary."""
    status = global_payment_service.get_subscription_status(user_id)
    tier = status["tier"]
    plan = PLAN_CATALOG.get(UserTier(tier))

    lines = [
        "💎 *Void Enterprise Monetization & Subscriptions*\n",
        f"• *Current Status:* `{status['plan_name']}` ({'Active ✅' if status['is_active'] else 'Inactive'})",
    ]

    if tier != "FREE":
        lines.append(f"• *Days Remaining:* `{status['days_remaining']} days`")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📦 *Subscription Tiers Catalog:*\n")

    for t in (UserTier.FREE, UserTier.PRO, UserTier.ENTERPRISE):
        p = PLAN_CATALOG[t]
        prefix = "👉 *Current:* " if t.value == tier else "• "
        price_str = "Free" if p.stars_price == 0 else f"{p.stars_price} ⭐ Stars (~${p.fiat_cents / 100:.2f})/mo"
        lines.append(f"{prefix}*{p.name}* — `{price_str}`")
        for feat in p.features[:3]:
            lines.append(f"  ✓ _{feat}_")
        lines.append("")

    lines.append("Tap below to checkout instantly with *Telegram Stars* or Card:")
    return "\n".join(lines)


def dispatch_invoice(bot: Any, chat_id: int, user_id: int, tier: UserTier) -> None:
    """Dispatches native Telegram Stars invoice directly into the conversation."""
    plan = PLAN_CATALOG.get(tier)
    if not plan or plan.stars_price <= 0:
        bot.send_message(chat_id, "Selected tier is not available for purchase.")
        return

    payload = global_payment_service.create_invoice_payload(user_id, tier)

    # For Telegram Stars: currency="XTR", provider_token="" (or None), prices=[LabeledPrice(label, stars)]
    # For Stripe/PayPal fiat providers: currency="USD", provider_token from env
    provider_token = os.environ.get("TELEGRAM_PAYMENT_PROVIDER_TOKEN", "")

    if provider_token:
        currency = "USD"
        prices = [types.LabeledPrice(label=plan.name, amount=plan.fiat_cents)]
    else:
        # Default to Telegram Stars
        currency = "XTR"
        prices = [types.LabeledPrice(label=plan.name, amount=plan.stars_price)]

    logger.info(f"Issuing invoice to user {user_id} for {plan.name} ({currency} {prices[0].amount})")

    try:
        bot.send_invoice(
            chat_id=chat_id,
            title=f"Void {plan.name}",
            description=f"30-day access to {plan.name}: {plan.description}",
            invoice_payload=payload,
            provider_token=provider_token,
            currency=currency,
            prices=prices,
            start_parameter=f"sub_{tier.value.lower()}",
        )
    except Exception as e:
        logger.error(f"Failed to send invoice: {e}")
        bot.send_message(
            chat_id,
            f"⚠️ *Invoice Generation Error:*\n`{str(e)}`\n\n"
            "Ensure bot payments or Telegram Stars are activated in BotFather.",
            parse_mode="Markdown",
        )


def register_billing_handlers(bot: Any, controller: Any) -> None:
    """Registers /billing command, pre-checkout query, and payment fulfillment."""
    if not bot:
        return

    @bot.message_handler(commands=["billing", "plans", "subscribe"])
    def handle_billing_cmd(message):
        user_id = message.from_user.id
        if not controller._is_authorized(user_id):
            return

        card = render_billing_card(user_id)
        bot.reply_to(message, card, reply_markup=get_billing_keyboard(user_id), parse_mode="Markdown")

    @bot.pre_checkout_query_handler(func=lambda query: True)
    def handle_pre_checkout(pre_checkout_query):
        query_id = pre_checkout_query.id
        payload = pre_checkout_query.invoice_payload
        is_ok, reason = global_payment_service.validate_pre_checkout(query_id, payload)

        if is_ok:
            bot.answer_pre_checkout_query(query_id, ok=True)
            logger.info(f"Pre-checkout query {query_id} approved.")
        else:
            bot.answer_pre_checkout_query(query_id, ok=False, error_message=reason)
            logger.warning(f"Pre-checkout query {query_id} rejected: {reason}")

    @bot.message_handler(content_types=["successful_payment"])
    def handle_successful_payment(message):
        user_id = message.from_user.id
        payment = message.successful_payment

        logger.info(
            f"Received successful payment from user {user_id}: "
            f"{payment.currency} {payment.total_amount} (charge_id={payment.telegram_payment_charge_id})"
        )

        sub = global_payment_service.fulfill_payment(
            user_id=user_id,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id or "telegram_stars",
            invoice_payload=payment.invoice_payload,
            currency=payment.currency,
            total_amount=payment.total_amount,
        )

        plan = PLAN_CATALOG.get(sub.tier) if sub else None
        tier_title = plan.name if plan else "Upgraded"

        confirmation_text = (
            "🎉 *Payment Successful & Subscription Activated!*\n\n"
            f"• *Tier:* `{tier_title}`\n"
            f"• *Status:* `ACTIVE ✅`\n"
            f"• *Currency:* `{payment.currency}`\n"
            f"• *Amount Paid:* `{payment.total_amount}`\n"
            f"• *Telegram Charge ID:* `{payment.telegram_payment_charge_id}`\n\n"
            "🚀 *Unlocked Privileges:*\n"
        )
        if plan:
            for feat in plan.features:
                confirmation_text += f"• {feat}\n"

        confirmation_text += "\nThank you for supporting the Void Autonomous Edge ecosystem!"

        bot.reply_to(
            message,
            confirmation_text,
            reply_markup=controller.get_main_keyboard(),
            parse_mode="Markdown",
        )
