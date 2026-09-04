"""
telegram/handlers/menu_router.py - Centralized 75-Button Nested Menu Dispatch Router.

Lazy-loads sub-menu handler modules via importlib for memory efficiency (< 30MB target).
Each category callback (menu_*) is dispatched to a get_*_submenu() function in its handler module.
Also handles cb_back_main back-navigation seamlessly.
"""

import importlib
import logging
from typing import Any, Tuple, Optional

logger = logging.getLogger("VoidTelegram.MenuRouter")

try:
    from telebot import types
except ImportError:
    types = None

# Dispatch table: callback_data -> (module_path, function_name)
MENU_DISPATCH = {
    "menu_telemetry": ("telegram.handlers.telemetry_handlers", "get_telemetry_submenu"),
    "menu_input": ("telegram.handlers.input_handlers", "get_input_submenu"),
    "menu_models": ("telegram.handlers.model_handlers", "get_model_submenu"),
    "menu_vault": ("telegram.handlers.vault_handlers", "get_vault_submenu"),
    "menu_security": ("telegram.handlers.security_handlers", "get_security_submenu"),
    "menu_shell": ("telegram.handlers.shell_handlers", "get_shell_submenu"),
    "menu_maintenance": ("telegram.handlers.maintenance_handlers", "get_maintenance_submenu"),
    "menu_media": ("telegram.handlers.media_handlers", "get_media_submenu"),
    "menu_audio": ("telegram.handlers.media_handlers", "get_media_submenu"),
    "menu_notif": ("telegram.handlers.notification_handlers", "get_notification_submenu"),
    "menu_notifications": ("telegram.handlers.notification_handlers", "get_notification_submenu"),
    "menu_macros": ("telegram.handlers.automation_handlers", "get_automation_submenu"),
    "menu_connectivity": ("telegram.handlers.connectivity_handlers", "get_connectivity_submenu"),
    "menu_storage": ("telegram.handlers.storage_handlers", "get_storage_submenu"),
    "menu_debug": ("telegram.handlers.debug_handlers", "get_debug_submenu"),
    "menu_power": ("telegram.handlers.power_handlers", "get_power_submenu"),
    "menu_analytics": ("telegram.handlers.analytics_handlers", "get_analytics_submenu"),
}

# Module cache for lazy imports
_module_cache = {}


def get_root_menu() -> Tuple[str, Any]:
    """
    Renders Level 1: Root Control Center (15 Categories in 2-column layout).
    """
    card = (
        "⚡ *Void Edge Agent Root Control Center*\n\n"
        "Autonomous mobile orchestration platform for Android & Termux.\n"
        "Persistent Telegram Cloud Vault & Hardware Automation Engine.\n\n"
        "👇 *Select a category to navigate sub-menus:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📂 Core & Telemetry", callback_data="menu_telemetry"),
        types.InlineKeyboardButton("🎮 Device Touch & Input", callback_data="menu_input"),
    )
    markup.add(
        types.InlineKeyboardButton("🧠 Model Management", callback_data="menu_models"),
        types.InlineKeyboardButton("☁️ Cloud Vault & Media", callback_data="menu_vault"),
    )
    markup.add(
        types.InlineKeyboardButton("🛡️ Security & Network", callback_data="menu_security"),
        types.InlineKeyboardButton("💻 Shell & Terminal", callback_data="menu_shell"),
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Maintenance & Tools", callback_data="menu_maintenance"),
        types.InlineKeyboardButton("🎵 Media & Audio Hub", callback_data="menu_media"),
    )
    markup.add(
        types.InlineKeyboardButton("🔔 Notifications & Clip", callback_data="menu_notif"),
        types.InlineKeyboardButton("⚡ Automation Macros", callback_data="menu_macros"),
    )
    markup.add(
        types.InlineKeyboardButton("🌐 Connectivity & GPS", callback_data="menu_connectivity"),
        types.InlineKeyboardButton("📁 Storage & Files", callback_data="menu_storage"),
    )
    markup.add(
        types.InlineKeyboardButton("🐞 Debug & Diagnostics", callback_data="menu_debug"),
        types.InlineKeyboardButton("🔄 System Power State", callback_data="menu_power"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Analytics & Logs", callback_data="menu_analytics"),
    )
    return card, markup


def _resolve_submenu(menu_key: str) -> Optional[Tuple[str, Any]]:
    """Lazy-load and call the submenu builder for a given menu key."""
    if menu_key in ("menu_root", "cb_back_main"):
        return get_root_menu()

    entry = MENU_DISPATCH.get(menu_key)
    if not entry:
        return None

    module_path, func_name = entry
    if module_path not in _module_cache:
        try:
            _module_cache[module_path] = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import menu module {module_path}: {e}")
            return None

    module = _module_cache[module_path]
    func = getattr(module, func_name, None)
    if not func:
        logger.error(f"Function {func_name} not found in {module_path}")
        return None

    return func()


def register_menu_router(bot: Any, controller: Any) -> None:
    """Registers the unified menu_* callback dispatcher and root back-navigation."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data and (call.data.startswith("menu_") or call.data in ("cb_back_main", "menu_root")))
    def handle_menu_navigation(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if not controller._is_authorized(user_id):
            bot.answer_callback_query(call.id, "Unauthorized.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        result = _resolve_submenu(call.data)

        if not result:
            bot.answer_callback_query(call.id, "Menu not available yet.", show_alert=True)
            return

        card_text, markup = result
        try:
            bot.edit_message_text(
                card_text,
                chat_id,
                message_id,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        except Exception:
            bot.send_message(chat_id, card_text, reply_markup=markup, parse_mode="Markdown")
