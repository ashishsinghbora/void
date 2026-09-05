"""
tools/advanced_modules.py - Strategy Wrappers for Advanced Capabilities.

Binds VisionAgent, DeepLinkEngine, ScraperVaultService, and NotificationWatcher
into the hash-indexed ToolRegistry for autonomous ReAct LLM tool calling.
"""

from typing import Any, Dict
from tools.base import ToolStrategy
from core.types import ToolExecutionResult
from modules.vision_agent import global_vision_agent
from modules.deep_links import global_deep_links
from modules.scraper_vault import global_scraper_vault
from modules.notification_watcher import global_notification_watcher


class VisionTapStrategy(ToolStrategy):
    """Dynamically locates a UI element on screen and taps its center."""

    def __init__(self):
        super().__init__(
            name="vision_tap",
            description="Dynamically ground and tap any button, icon, or element on screen by its name (e.g. 'submit', 'search', 'login').",
            schema={
                "type": "object",
                "properties": {"element_query": {"type": "string", "description": "Element name or label to tap"}},
                "required": ["element_query"],
            },
        )

    def execute(self, element_query: str = "", **kwargs: Any) -> ToolExecutionResult:
        res = global_vision_agent.dynamic_tap(element_query)
        return ToolExecutionResult(
            success=res.get("success", False),
            output=res.get("output") or f"Tapped {element_query} at {res.get('coordinates')}",
            error=res.get("error"),
            duration_ms=0,
        )


class VisionFormFillStrategy(ToolStrategy):
    """Focuses a form field dynamically and types text into it."""

    def __init__(self):
        super().__init__(
            name="vision_form_fill",
            description="Locate an input field dynamically on screen and type text into it.",
            schema={
                "type": "object",
                "properties": {
                    "field_name": {"type": "string", "description": "Name or placeholder of the field"},
                    "value": {"type": "string", "description": "Text value to input"},
                },
                "required": ["field_name", "value"],
            },
        )

    def execute(self, field_name: str = "", value: str = "", **kwargs: Any) -> ToolExecutionResult:
        res = global_vision_agent.fill_form_field(field_name, value)
        return ToolExecutionResult(
            success=res.get("success", False),
            output=res.get("output") or f"Filled field '{field_name}' with '{value}'",
            error=res.get("error"),
            duration_ms=0,
        )


class DeepLinkPayStrategy(ToolStrategy):
    """Launches UPI payment apps (GPay, PhonePe, Paytm) with pre-filled details."""

    def __init__(self):
        super().__init__(
            name="deep_link_pay",
            description="Initiate an instant UPI payment to a VPA (e.g. user@okhdfcbank) with amount and note.",
            schema={
                "type": "object",
                "properties": {
                    "payee_vpa": {"type": "string", "description": "UPI ID / VPA address"},
                    "payee_name": {"type": "string", "description": "Name of the merchant or recipient"},
                    "amount": {"type": "number", "description": "Amount in INR"},
                    "note": {"type": "string", "description": "Payment note / remarks"},
                    "app": {"type": "string", "description": "Preferred app: 'gpay', 'phonepe', 'paytm'"},
                },
                "required": ["payee_vpa", "payee_name"],
            },
        )

    def execute(self, payee_vpa: str = "", payee_name: str = "", amount: float = 0.0, note: str = "Payment", app: str = "", **kwargs: Any) -> ToolExecutionResult:
        res = global_deep_links.pay_upi(payee_vpa=payee_vpa, payee_name=payee_name, amount=amount, note=note, preferred_app=app)
        return ToolExecutionResult(
            success=res.get("success", False),
            output=f"Payment intent launched for ₹{amount} to {payee_name} ({payee_vpa})",
            error=res.get("error"),
            duration_ms=0,
        )


class TrackPriceStrategy(ToolStrategy):
    """Monitors a product webpage for price drops."""

    def __init__(self):
        super().__init__(
            name="track_price",
            description="Add a web URL to background monitoring for price drops and cloud vault alert sync.",
            schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Product web URL"},
                    "product_name": {"type": "string", "description": "Name of product"},
                    "target_price": {"type": "number", "description": "Target alert price threshold"},
                },
                "required": ["url", "product_name", "target_price"],
            },
        )

    def execute(self, url: str = "", product_name: str = "", target_price: float = 0.0, **kwargs: Any) -> ToolExecutionResult:
        tid = global_scraper_vault.add_price_watch(url, product_name, target_price)
        return ToolExecutionResult(
            success=True,
            output=f"Price tracking registered: '{product_name}' at threshold <= {target_price} (Rule ID: {tid})",
            error=None,
            duration_ms=0,
        )


class GetLatestOtpStrategy(ToolStrategy):
    """Scans notification drawer and returns latest intercepted banking OTP."""

    def __init__(self):
        super().__init__(
            name="get_latest_otp",
            description="Retrieve the most recent intercepted banking or 2FA authentication OTP from notification history.",
            schema={"type": "object", "properties": {}},
        )

    def execute(self, **kwargs: Any) -> ToolExecutionResult:
        otps = global_notification_watcher.poll_once()
        if not otps:
            return ToolExecutionResult(
                success=True,
                output="No unread 2FA/OTP codes found in active notifications.",
                error=None,
                duration_ms=0,
            )
        latest = otps[-1]
        amt_str = f" (Amount: {latest.amount})" if latest.amount else ""
        return ToolExecutionResult(
            success=True,
            output=f"Latest OTP: {latest.code} for {latest.service}{amt_str}",
            error=None,
            duration_ms=0,
        )
