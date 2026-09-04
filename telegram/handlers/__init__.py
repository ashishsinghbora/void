"""
telegram/handlers - Modular Command, Billing, Settings, and Callback Handlers.
"""

from telegram.handlers.core_handlers import register_core_handlers
from telegram.handlers.billing_handlers import register_billing_handlers, get_billing_keyboard, render_billing_card
from telegram.handlers.settings_handlers import register_settings_handlers, get_settings_keyboard, render_settings_card
from telegram.handlers.callback_handlers import register_callback_handlers
from telegram.handlers.vault_handlers import register_vault_handlers, render_vault_status_card, get_vault_keyboard
from telegram.handlers.model_handlers import register_model_handlers, render_model_setup_card, get_model_setup_keyboard


def register_all_handlers(bot, controller):
    """Registers all modular command, callback, settings, and billing handlers with telebot."""
    register_billing_handlers(bot, controller)
    register_settings_handlers(bot, controller)
    register_vault_handlers(bot, controller)
    register_model_handlers(bot, controller)
    register_callback_handlers(bot, controller)
    register_core_handlers(bot, controller)


__all__ = [
    "register_all_handlers",
    "register_core_handlers",
    "register_billing_handlers",
    "register_settings_handlers",
    "register_callback_handlers",
    "register_vault_handlers",
    "register_model_handlers",
    "get_billing_keyboard",
    "render_billing_card",
    "get_settings_keyboard",
    "render_settings_card",
    "render_vault_status_card",
    "get_vault_keyboard",
    "render_model_setup_card",
    "get_model_setup_keyboard",
]
