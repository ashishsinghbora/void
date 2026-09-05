"""
modules/scraper_vault.py - Autonomous Background Web Scraping & Cloud Vault Sync.

Implements:
- Autonomous background tracking of web prices, data streams, and documents
- Differential change detector (price drop alerts, stock availability)
- Instant synchronization of alerts, data payloads, and documents directly to
  the Telegram Group Cloud Vault with searchable hashtag indexing (#PRICE_ALERT, #DATA_STREAM)
"""

import os
import re
import time
import json
import logging
import urllib.request
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from config.settings import global_config

logger = logging.getLogger("VoidModules.ScraperVault")

VAULT_SCRAPES_DIR = os.path.expanduser("~/.void/scrapes")


@dataclass
class PriceWatchTarget:
    """Represents an active web price tracking rule."""
    target_id: str
    url: str
    product_name: str
    target_price: float
    last_price: float = 0.0
    last_checked: float = 0.0
    active: bool = True


class ScraperVaultService:
    """Autonomous scraper, price tracker, and Cloud Vault syncer."""

    def __init__(self, bot_instance: Any = None):
        self.bot = bot_instance
        os.makedirs(VAULT_SCRAPES_DIR, exist_ok=True)
        self.price_watches: Dict[str, PriceWatchTarget] = {}
        self._load_saved_watches()

    def bind_bot(self, bot: Any) -> None:
        self.bot = bot

    def _load_saved_watches(self) -> None:
        p = os.path.join(VAULT_SCRAPES_DIR, "price_watches.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        t = PriceWatchTarget(**item)
                        self.price_watches[t.target_id] = t
            except Exception as e:
                logger.debug(f"Error loading price watches: {e}")

    def _save_watches(self) -> None:
        p = os.path.join(VAULT_SCRAPES_DIR, "price_watches.json")
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump([vars(v) for v in self.price_watches.values()], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving price watches: {e}")

    def add_price_watch(self, url: str, product_name: str, target_price: float) -> str:
        """Registers a new URL to monitor for price drops."""
        tid = f"watch_{int(time.time())}"
        watch = PriceWatchTarget(
            target_id=tid,
            url=url,
            product_name=product_name,
            target_price=target_price,
        )
        self.price_watches[tid] = watch
        self._save_watches()
        logger.info(f"Registered price watch '{product_name}' at target <= {target_price}")
        return tid

    def remove_price_watch(self, target_id: str) -> bool:
        """Removes an active price watch rule."""
        if target_id in self.price_watches:
            del self.price_watches[target_id]
            self._save_watches()
            logger.info(f"Removed price watch rule: {target_id}")
            return True
        return False

    def scrape_url_price(self, url: str) -> Optional[float]:
        """Fetches web page and extracts monetary figure using regex scanner."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Linux; Android 15) VoidEdgeAgent/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            import html as html_lib
            html = html_lib.unescape(html)

            # Look for price patterns ($99.99, Rs. 1,499, ₹1,299, 499.00)
            matches = re.findall(r"(?:₹|rs\.?|\$|inr)\s*([\d,]+(?:\.\d{2})?)", html, re.IGNORECASE)
            if matches:
                clean_num = matches[0].replace(",", "").strip()
                return float(clean_num)
        except Exception as e:
            logger.debug(f"Scraping notice for {url[:40]}: {e}")
        return None

    def check_all_watches_once(self) -> List[Dict[str, Any]]:
        """Executes a check cycle on all active price targets."""
        alerts = []
        for tid, watch in list(self.price_watches.items()):
            if not watch.active:
                continue

            current_price = self.scrape_url_price(watch.url)
            watch.last_checked = time.time()

            if current_price is not None:
                watch.last_price = current_price
                if current_price <= watch.target_price:
                    # Trigger price drop alert
                    alert_info = {
                        "target_id": tid,
                        "product_name": watch.product_name,
                        "current_price": current_price,
                        "target_price": watch.target_price,
                        "url": watch.url,
                    }
                    alerts.append(alert_info)
                    self._sync_alert_to_vault(alert_info)

        self._save_watches()
        return alerts

    def _sync_alert_to_vault(self, alert: Dict[str, Any]) -> None:
        """Syncs the scrape price alert directly into Telegram Group Vault."""
        card = (
            "🏷️ *PRICE DROP ALERT DETECTED* #PRICE_ALERT\n\n"
            f"• *Product:* `{alert['product_name']}`\n"
            f"• *Current Price:* `₹{alert['current_price']}`\n"
            f"• *Target Threshold:* `₹{alert['target_price']}`\n"
            f"• *Status:* 🟢 Below Target Price!\n"
            f"• *URL:* {alert['url']}\n\n"
            "_Mirrored to Telegram Cloud Vault._"
        )

        vault_gid = global_config.vault_group_id
        if vault_gid and self.bot:
            try:
                from telegram.utils.safe_telegram import safe_send_message
                safe_send_message(self.bot, chat_id=vault_gid, text=card, parse_mode="Markdown")
            except Exception as e:
                logger.debug(f"Vault sync notice: {e}")

    def organize_and_sync_document(self, file_path: str, tag: str = "document") -> Dict[str, Any]:
        """Uploads and indexes any local document or scrape log into Cloud Vault."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File '{file_path}' not found."}

        # Use global_cloud_vault
        from telegram.services.cloud_vault import global_cloud_vault
        res = global_cloud_vault.upload_file(
            file_path=file_path,
            file_type="document",
            tag=tag,
            caption=f"Vault Auto-Sync: {os.path.basename(file_path)} #{tag.upper()}",
        )
        return {
            "success": res is not None,
            "vault_file": res,
            "path": file_path,
        }

    async def run_async_scraper(self, interval_seconds: float = 300.0) -> None:
        """Continuous non-blocking asynchronous scraping and price monitoring loop."""
        import asyncio
        self._running = True
        logger.info(f"ScraperVaultService background loop running (interval: {interval_seconds}s).")
        while self._running:
            try:
                self.check_all_watches_once()
            except Exception as e:
                logger.warning(f"Error in ScraperVault loop: {e}")
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        """Stops the asynchronous scraping loop."""
        self._running = False


global_scraper_vault = ScraperVaultService()
