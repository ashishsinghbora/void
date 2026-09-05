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
    # Permanent 6-Hub Control Center
    "menu_screen": ("telegram.handlers.hub_handlers", "get_screen_hub"),
    "menu_vault": ("telegram.handlers.hub_handlers", "get_vault_hub"),
    "menu_terminal": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_research": ("telegram.handlers.hub_handlers", "get_research_hub"),
    "menu_apps": ("telegram.handlers.hub_handlers", "get_apps_hub"),
    "menu_security": ("telegram.handlers.hub_handlers", "get_security_hub"),

    # Backward compatibility mappings for legacy menus
    "menu_input": ("telegram.handlers.hub_handlers", "get_screen_hub"),
    "menu_models": ("telegram.handlers.hub_handlers", "get_vault_hub"),
    "menu_shell": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_media": ("telegram.handlers.hub_handlers", "get_research_hub"),
    "menu_audio": ("telegram.handlers.hub_handlers", "get_research_hub"),
    "menu_notif": ("telegram.handlers.hub_handlers", "get_security_hub"),
    "menu_notifications": ("telegram.handlers.hub_handlers", "get_security_hub"),
    "menu_macros": ("telegram.handlers.hub_handlers", "get_apps_hub"),
    "menu_connectivity": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_storage": ("telegram.handlers.hub_handlers", "get_vault_hub"),
    "menu_debug": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_power": ("telegram.handlers.hub_handlers", "get_apps_hub"),
    "menu_telemetry": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_analytics": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
    "menu_maintenance": ("telegram.handlers.hub_handlers", "get_terminal_hub"),
}

# Module cache for lazy imports
_module_cache = {}


def get_root_menu() -> Tuple[str, Any]:
    """
    Renders Level 1: Consolidated Permanent 6-Hub Control Center.
    """
    card = (
        "⚡ *Void Edge Agent Root Control Center & Hub*\n\n"
        "Autonomous mobile orchestration platform for Android & Termux.\n"
        "Persistent Telegram Cloud Vault & Hardware Automation Engine.\n\n"
        "👇 *Select a control hub from the permanent dashboard:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📱 [ 👁️ Screen & Touch ]", callback_data="menu_screen"),
        types.InlineKeyboardButton("🧠 [ ☁️ Vault & Brain ]", callback_data="menu_vault"),
    )
    markup.add(
        types.InlineKeyboardButton("💻 [ ⚡ Terminal & SSH ]", callback_data="menu_terminal"),
        types.InlineKeyboardButton("🌐 [ 🔍 Research & YouTube ]", callback_data="menu_research"),
    )
    markup.add(
        types.InlineKeyboardButton("📲 [ 🚀 Apps & Intents ]", callback_data="menu_apps"),
        types.InlineKeyboardButton("🔐 [ 🛡️ Security & Interceptor ]", callback_data="menu_security"),
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
