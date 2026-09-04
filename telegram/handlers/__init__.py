"""
telegram/handlers - Complete 75-Button Modular Handler Architecture.

Registers all nested category sub-menus, specific hardware action dispatchers,
shell executors, and natural language fallback routers in optimal precedence order.
"""

from telegram.handlers.menu_router import register_menu_router, get_root_menu
from telegram.handlers.telemetry_handlers import register_telemetry_handlers, get_telemetry_submenu
from telegram.handlers.input_handlers import register_input_handlers, get_input_submenu
from telegram.handlers.model_handlers import register_model_handlers, get_model_submenu, render_model_setup_card, get_model_setup_keyboard
from telegram.handlers.vault_handlers import register_vault_handlers, get_vault_submenu, render_vault_status_card, get_vault_keyboard
from telegram.handlers.security_handlers import register_security_handlers, get_security_submenu
from telegram.handlers.shell_handlers import register_shell_handlers, get_shell_submenu
from telegram.handlers.maintenance_handlers import register_maintenance_handlers, get_maintenance_submenu
from telegram.handlers.media_handlers import register_media_handlers, get_media_submenu
from telegram.handlers.notification_handlers import register_notification_handlers, get_notification_submenu
from telegram.handlers.automation_handlers import register_automation_handlers, get_automation_submenu
from telegram.handlers.debug_handlers import register_debug_handlers, get_debug_submenu
from telegram.handlers.connectivity_handlers import register_connectivity_handlers, get_connectivity_submenu
from telegram.handlers.storage_handlers import register_storage_handlers, get_storage_submenu
from telegram.handlers.power_handlers import register_power_handlers, get_power_submenu
from telegram.handlers.analytics_handlers import register_analytics_handlers, get_analytics_submenu
from telegram.handlers.billing_handlers import register_billing_handlers, get_billing_keyboard, render_billing_card
from telegram.handlers.settings_handlers import register_settings_handlers, get_settings_keyboard, render_settings_card
from telegram.handlers.callback_handlers import register_callback_handlers
from telegram.handlers.core_handlers import register_core_handlers


def register_all_handlers(bot, controller):
    """
    Registers all modular sub-menu and action handlers with telebot.
    Specific category handlers are registered first, followed by the menu router,
    then catch-all callback handlers, and finally message command handlers.
    """
    # 1. Register menu router (menu_* and cb_back_main navigation)
    register_menu_router(bot, controller)

    # 2. Specific Sub-menu Action Handlers (75 total functions)
    register_telemetry_handlers(bot, controller)
    register_input_handlers(bot, controller)
    register_model_handlers(bot, controller)
    register_vault_handlers(bot, controller)
    register_security_handlers(bot, controller)
    register_shell_handlers(bot, controller)
    register_maintenance_handlers(bot, controller)
    register_media_handlers(bot, controller)
    register_notification_handlers(bot, controller)
    register_automation_handlers(bot, controller)
    register_debug_handlers(bot, controller)
    register_connectivity_handlers(bot, controller)
    register_storage_handlers(bot, controller)
    register_power_handlers(bot, controller)
    register_analytics_handlers(bot, controller)

    # 3. Settings & Billing Handlers
    register_settings_handlers(bot, controller)
    register_billing_handlers(bot, controller)

    # 4. Fallback Callback Query Handler
    register_callback_handlers(bot, controller)

    # 5. Core Message & Natural Language ReAct Handlers
    register_core_handlers(bot, controller)


__all__ = [
    "register_all_handlers",
    "register_menu_router",
    "get_root_menu",
    "register_telemetry_handlers",
    "get_telemetry_submenu",
    "register_input_handlers",
    "get_input_submenu",
    "register_model_handlers",
    "get_model_submenu",
    "render_model_setup_card",
    "get_model_setup_keyboard",
    "register_vault_handlers",
    "get_vault_submenu",
    "render_vault_status_card",
    "get_vault_keyboard",
    "register_security_handlers",
    "get_security_submenu",
    "register_shell_handlers",
    "get_shell_submenu",
    "register_maintenance_handlers",
    "get_maintenance_submenu",
    "register_media_handlers",
    "get_media_submenu",
    "register_notification_handlers",
    "get_notification_submenu",
    "register_automation_handlers",
    "get_automation_submenu",
    "register_debug_handlers",
    "get_debug_submenu",
    "register_connectivity_handlers",
    "get_connectivity_submenu",
    "register_storage_handlers",
    "get_storage_submenu",
    "register_power_handlers",
    "get_power_submenu",
    "register_analytics_handlers",
    "get_analytics_submenu",
    "register_billing_handlers",
    "get_billing_keyboard",
    "render_billing_card",
    "register_settings_handlers",
    "get_settings_keyboard",
    "render_settings_card",
    "register_callback_handlers",
    "register_core_handlers",
]
