"""
telegram/handlers/hub_handlers.py - Permanent 6-Hub Control Center & Dynamic Extension Registry.

Provides the future-proof, clutter-free 6-Hub Telegram interface:
1. 📱 Screen & Touch (Vision, Screencap, Gestures, Forms)
2. 🧠 Vault & Brain (Telegram Group DB, Sync, Memory, Search)
3. 💻 Terminal & SSH (OpenSSH daemon, IPs, Bash execution)
4. 🌐 Research & YouTube (YouTube automation, Web research, Notes)
5. 📲 Apps & Intents (UPI Pay, WhatsApp, Maps, Uber, Settings)
6. 🔐 Security & Interceptor (Banking OTP/2FA, Call screening, Clipboard)
"""

import os
import time
import logging
from typing import Tuple, Any, Dict, List, Optional

from config.settings import global_config
from modules.terminal_service import global_terminal_service
from modules.brain_sync import global_brain_sync
from modules.notification_watcher import global_notification_watcher
from modules.vision_agent import global_vision_agent
from modules.deep_links import global_deep_links
from telegram.utils.safe_telegram import safe_send_message, safe_reply, safe_edit_message_text

logger = logging.getLogger("VoidTelegram.HubHandlers")

try:
    from telebot import types
except ImportError:
    types = None


# Dynamic Extension Registry for custom/plugin slots under hubs
HUB_EXTENSIONS: Dict[str, List[Dict[str, str]]] = {
    "screen": [],
    "vault": [],
    "terminal": [],
    "research": [],
    "apps": [],
    "security": [],
}


def register_hub_extension(hub_name: str, label: str, callback_data: str) -> None:
    """Dynamically registers an extension button into any of the 6 hubs without code churn."""
    if hub_name in HUB_EXTENSIONS:
        HUB_EXTENSIONS[hub_name].append({"label": label, "callback": callback_data})


# ---------------------------------------------------------------------------
# 1. Screen & Touch Hub
# ---------------------------------------------------------------------------
def get_screen_hub() -> Tuple[str, Any]:
    card = (
        "📱 *[ 👁️ Screen & Touch Control Hub ]*\n\n"
        "• *Vision Agent:* Multimodal coordinate-free UI grounding\n"
        "• *Form Sequences:* Multi-step automated text typing & field validation\n"
        "• *Physical Gestures:* Dynamic swipes, taps, and hardware buttons\n\n"
        "👇 *Select a mobile touch action:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📸 Capture Screen", callback_data="cb_screenshot"),
        types.InlineKeyboardButton("👆 Tap Coordinates", callback_data="input_tap"),
    )
    markup.add(
        types.InlineKeyboardButton("↔️ Swipe Gesture", callback_data="input_swipe"),
        types.InlineKeyboardButton("⌨️ Keyboard Type", callback_data="input_type"),
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Home Key", callback_data="key_home"),
        types.InlineKeyboardButton("🔙 Back Key", callback_data="key_back"),
    )

    for ext in HUB_EXTENSIONS["screen"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# 2. Vault & Brain Hub
# ---------------------------------------------------------------------------
def get_vault_hub() -> Tuple[str, Any]:
    paired = bool(global_config.vault_group_id)
    paired_str = f"`{global_config.vault_group_id}`" if paired else "⚠️ Not Paired"
    paired_time = (
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(global_config.vault_paired_at))
        if global_config.vault_paired_at > 0 else "N/A"
    )

    card = (
        "🧠 *[ ☁️ Vault & Brain Control Hub ]*\n\n"
        f"• *Telegram Cloud Vault:* {paired_str}\n"
        f"• *Title:* `{global_config.vault_title}`\n"
        f"• *Paired Timestamp:* `{paired_time}`\n"
        f"• *Local Storage:* `~/.void/vault/` & `~/.void/brain/`\n"
        "• *Indexing:* `#DOC`, `#NOTE`, `#SCREEN`, `#RESEARCH`, `#OTP`, `#CODE`\n\n"
        "👇 *Select a brain or cloud storage action:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Sync Phone Brain", callback_data="hub_vault_sync"),
        types.InlineKeyboardButton("🔗 Pair Group Vault", callback_data="vault_link_guide"),
    )
    markup.add(
        types.InlineKeyboardButton("📊 Brain Vault Stats", callback_data="vault_status"),
        types.InlineKeyboardButton("🔍 Search Documents", callback_data="vault_search_guide"),
    )

    for ext in HUB_EXTENSIONS["vault"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# 3. Terminal & SSH Hub
# ---------------------------------------------------------------------------
def get_terminal_hub() -> Tuple[str, Any]:
    ssh_on = global_terminal_service.is_ssh_running()
    ssh_badge = "🟢 ONLINE (Port 8022)" if ssh_on else "🔴 OFFLINE"

    card = (
        "💻 *[ ⚡ Terminal & Remote SSH Hub ]*\n\n"
        f"• *OpenSSH Daemon:* {ssh_badge}\n"
        "• *Interactive Shell:* Send `/sh <cmd>` or `/bash <cmd>`\n"
        "• *Autonomous AI Shell:* ReAct agent executes inspection commands\n\n"
        "👇 *Select a terminal management action:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ssh = (
        types.InlineKeyboardButton("🛑 Stop OpenSSH", callback_data="hub_ssh_stop")
        if ssh_on else
        types.InlineKeyboardButton("▶️ Start OpenSSH", callback_data="hub_ssh_start")
    )
    markup.add(
        btn_ssh,
        types.InlineKeyboardButton("🌐 Connection Info & IPs", callback_data="hub_ssh_info"),
    )
    markup.add(
        types.InlineKeyboardButton("⚡ FastFetch Specs", callback_data="cb_fastfetch"),
        types.InlineKeyboardButton("📋 System Uptime", callback_data="hub_term_uptime"),
    )

    for ext in HUB_EXTENSIONS["terminal"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# 4. Research & YouTube Hub
# ---------------------------------------------------------------------------
def get_research_hub() -> Tuple[str, Any]:
    card = (
        "🌐 *[ 🔍 Research & YouTube Immersion Hub ]*\n\n"
        "• *YouTube Automation:* Direct queries, video intents, transcript notes\n"
        "• *Web Research:* Multi-hop searches, article scraping, HTML unescape\n"
        "• *Price Tracker:* Differential change detection with vault alerts\n\n"
        "👇 *Select an autonomous research task:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("▶️ Open YouTube", callback_data="app_launch:youtube"),
        types.InlineKeyboardButton("📑 YouTube Note Gen", callback_data="hub_yt_guide"),
    )
    markup.add(
        types.InlineKeyboardButton("🏷️ Price Drop Watches", callback_data="hub_price_status"),
        types.InlineKeyboardButton("🔍 Web Query Guide", callback_data="hub_research_guide"),
    )

    for ext in HUB_EXTENSIONS["research"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# 5. Apps & Intents Hub
# ---------------------------------------------------------------------------
def get_apps_hub() -> Tuple[str, Any]:
    card = (
        "📲 *[ 🚀 Apps & Deep Intents Hub ]*\n\n"
        "• *NPCI UPI Payments:* Launch GPay, PhonePe, Paytm with pre-filled VPA\n"
        "• *Social & Comms:* WhatsApp 1-on-1 chats, Telegram profile intents\n"
        "• *Navigation & Mobility:* Turn-by-turn Maps, Uber ride destination\n"
        "• *Android System:* Jump straight into WiFi, Battery, Sound, Settings\n\n"
        "👇 *Select an application or intent trigger:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💬 WhatsApp", callback_data="app_launch:whatsapp"),
        types.InlineKeyboardButton("✈️ Telegram", callback_data="app_launch:telegram"),
    )
    markup.add(
        types.InlineKeyboardButton("🗺️ Google Maps", callback_data="hub_maps_guide"),
        types.InlineKeyboardButton("💳 UPI Fast Pay", callback_data="hub_upi_guide"),
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ Device Settings", callback_data="app_launch:settings"),
        types.InlineKeyboardButton("📷 Camera App", callback_data="app_launch:camera"),
    )

    for ext in HUB_EXTENSIONS["apps"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# 6. Security & Interceptor Hub
# ---------------------------------------------------------------------------
def get_security_hub() -> Tuple[str, Any]:
    card = (
        "🔐 *[ 🛡️ Security & Interceptor Hub ]*\n\n"
        "• *Banking OTP / 2FA Engine:* Regex interception for HDFC, SBI, ICICI, etc.\n"
        "• *Clipboard Auto-Copy:* Detected passcodes auto-pasted to Android clipboard\n"
        "• *Call-Screening Surrogate:* Missed call detection & automated SMS text-back\n"
        "• *Storage Audit:* AES-256 vault credentials & SQLite WAL logging\n\n"
        "👇 *Select a security action:*"
    )
    if types is None:
        return card, None

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔐 Fetch Latest OTP", callback_data="hub_otp_latest"),
        types.InlineKeyboardButton("📞 Call-Screen Log", callback_data="hub_screen_calls"),
    )
    markup.add(
        types.InlineKeyboardButton("🛡️ Security Dashboard", callback_data="cb_security"),
        types.InlineKeyboardButton("🧹 Clean Storage", callback_data="cb_clean"),
    )

    for ext in HUB_EXTENSIONS["security"]:
        markup.add(types.InlineKeyboardButton(ext["label"], callback_data=ext["callback"]))

    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="cb_back_main"))
    return card, markup


# ---------------------------------------------------------------------------
# Action Handlers Registration for 6 Hubs
# ---------------------------------------------------------------------------
def register_hub_handlers(bot: Any, controller: Any) -> None:
    """Registers callback queries dispatched from the 6 permanent hubs."""
    if not bot:
        return

    @bot.callback_query_handler(func=lambda call: call.data.startswith("hub_"))
    def handle_hub_actions(call):
        user_id = call.from_user.id
        if not controller._is_authorized(user_id):
            return

        data = call.data
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        if data == "hub_vault_sync":
            uploaded = global_brain_sync.sync_local_to_cloud()
            count = len(uploaded)
            safe_edit_message_text(
                bot,
                f"🧠 *Brain Vault Synchronized:*\nUploaded {count} new files to Telegram Cloud Vault.",
                chat_id,
                msg_id,
                reply_markup=get_vault_hub()[1],
                parse_mode="Markdown",
            )

        elif data == "hub_ssh_start":
            res = global_terminal_service.start_ssh()
            card = res.get("connection_info") or (f"✅ OpenSSH daemon started on port {res.get('port', 8022)}." if res.get("success") else f"⚠️ Error: {res.get('error')}")
            safe_edit_message_text(bot, card, chat_id, msg_id, reply_markup=get_terminal_hub()[1], parse_mode="Markdown")

        elif data == "hub_ssh_stop":
            res = global_terminal_service.stop_ssh()
            status_txt = "🛑 OpenSSH daemon terminated." if res.get("success") else "⚠️ Error stopping SSH."
            safe_edit_message_text(bot, status_txt, chat_id, msg_id, reply_markup=get_terminal_hub()[1], parse_mode="Markdown")

        elif data == "hub_ssh_info":
            card = global_terminal_service.get_connection_card()
            safe_edit_message_text(bot, card, chat_id, msg_id, reply_markup=get_terminal_hub()[1], parse_mode="Markdown")

        elif data == "hub_term_uptime":
            res = global_terminal_service.execute_bash("uptime")
            out = res.get("output", "N/A")
            safe_edit_message_text(bot, f"⚡ *System Uptime:*\n`{out}`", chat_id, msg_id, reply_markup=get_terminal_hub()[1], parse_mode="Markdown")

        elif data == "hub_otp_latest":
            otps = global_notification_watcher.poll_once()
            if otps:
                top = otps[-1]
                txt = f"🔐 *Latest Intercepted OTP:*\n• *Service:* `{top.service}`\n• *Code:* `{top.code}`\n• *Amount:* `{top.amount or 'N/A'}`"
            else:
                txt = "🔐 *No active banking/2FA OTPs found in notification drawer.*"
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_security_hub()[1], parse_mode="Markdown")

        elif data == "hub_screen_calls":
            from modules.voice_handler import global_voice_handler
            screened = global_voice_handler.check_and_screen_recent_calls()
            txt = f"📞 *Call-Screening Log:*\nProcessed {len(screened)} recent missed calls." if screened else "📞 *No unhandled missed calls found.*"
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_security_hub()[1], parse_mode="Markdown")

        elif data == "hub_yt_guide":
            txt = "▶️ *YouTube Automation Guide:*\nSend `/ai search and play lo-fi hip hop on youtube` or `/ai research machine learning on youtube`."
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_research_hub()[1], parse_mode="Markdown")

        elif data == "hub_price_status":
            from modules.scraper_vault import global_scraper_vault
            count = len(global_scraper_vault.price_watches)
            txt = f"🏷️ *Price Watch Targets:* `{count} active rules`\nTo add a tracker: `/ai track price of <url> below <price>`."
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_research_hub()[1], parse_mode="Markdown")

        elif data == "hub_upi_guide":
            txt = "💳 *UPI Fast Pay Guide:*\nSend: `/ai pay 250 to friend@okhdfcbank for lunch`."
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_apps_hub()[1], parse_mode="Markdown")

        elif data == "hub_maps_guide":
            txt = "🗺️ *Google Maps Guide:*\nSend: `/ai navigate to airport in google maps`."
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_apps_hub()[1], parse_mode="Markdown")

        elif data == "hub_research_guide":
            txt = "🔍 *Autonomous Research Guide:*\nSend: `/ai research quantum computing breakthroughs and save note`."
            safe_edit_message_text(bot, txt, chat_id, msg_id, reply_markup=get_research_hub()[1], parse_mode="Markdown")
