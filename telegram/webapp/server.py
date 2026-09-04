"""
telegram/webapp/server.py - Ultra-Lightweight Telegram Mini App (TMA) Micro Server.

Zero-dependency HTTP daemon built on standard library http.server, maintaining
< 30MB memory footprint while serving TMA static assets and JSON API routes.
"""

import os
import json
import time
import logging
import resource
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

from telegram.services.tma_auth_service import global_tma_auth_service
from telegram.services.device_service import global_device_service
from telegram.services.payment_service import global_payment_service, PLAN_CATALOG
from telegram.database.db_manager import global_bot_db
from telegram.database.models import UserTier
from core.model_manager import global_model_manager

logger = logging.getLogger("VoidTelegram.MiniAppServer")

INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")


class MiniAppRequestHandler(BaseHTTPRequestHandler):
    """Handles static web app files and JSON API routes for Telegram Mini App."""

    bot_token: str = ""

    def log_message(self, format, *args):
        # Suppress verbose standard HTTP server logging to terminal
        logger.debug("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        url_path = self.path.split("?")[0]

        if url_path in ("/", "/index.html", "/mini-app"):
            self._serve_index_html()
        elif url_path == "/api/telemetry":
            self._handle_telemetry()
        elif url_path == "/api/devices":
            self._handle_devices()
        elif url_path == "/api/billing":
            self._handle_billing()
        elif url_path == "/health":
            self._set_headers(200)
            self.wfile.write(b'{"status":"healthy","service":"void-tma"}')
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error":"Not Found"}')

    def do_POST(self):
        url_path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        if url_path == "/api/auth/validate":
            self._handle_auth_validate(payload)
        elif url_path == "/api/actions":
            self._handle_action(payload)
        elif url_path == "/api/billing/create-invoice":
            self._handle_create_invoice(payload)
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error":"Not Found"}')

    def _serve_index_html(self):
        if not os.path.exists(INDEX_HTML_PATH):
            self._set_headers(404, "text/plain")
            self.wfile.write(b"index.html not found")
            return

        with open(INDEX_HTML_PATH, "rb") as f:
            content = f.read()

        self._set_headers(200, "text/html; charset=utf-8")
        self.wfile.write(content)

    def _handle_auth_validate(self, payload: Dict[str, Any]):
        init_data = payload.get("init_data", "")
        if not init_data:
            # Fallback for dev / local testing
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "success": True,
                "dev_mode": True,
                "user": {"id": 0, "username": "LocalDevUser"},
                "tier": "PRO",
            }).encode("utf-8"))
            return

        is_valid, user_data, err = global_tma_auth_service.validate_init_data(
            init_data_raw=init_data,
            bot_token=self.bot_token,
        )

        if not is_valid:
            self._set_headers(401)
            self.wfile.write(json.dumps({"success": False, "error": err}).encode("utf-8"))
            return

        user_id = user_data.get("id") if isinstance(user_data, dict) else 0
        user = global_bot_db.get_user(user_id) if user_id else None
        tier = user.tier.value if user else "FREE"

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "success": True,
            "user": user_data,
            "tier": tier,
        }).encode("utf-8"))

    def _handle_telemetry(self):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024.0, 1)

        from tools.registry import global_tool_registry
        bat_res = global_tool_registry.execute("get_battery_status")
        battery_data = bat_res.output if bat_res.success and isinstance(bat_res.output, dict) else {"percentage": 100, "status": "Unknown"}

        response = {
            "battery": battery_data,
            "memory": {"rss_mb": rss_mb, "cap_mb": 30.0},
            "active_model": global_model_manager.get_active_model_name() or "Deterministic ReAct",
            "timestamp": time.time(),
        }
        self._set_headers(200)
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def _handle_devices(self):
        # Default user 0 or local devices
        devices = global_device_service.list_user_devices(0)
        data = [d.to_dict() for d in devices]
        self._set_headers(200)
        self.wfile.write(json.dumps({"devices": data}).encode("utf-8"))

    def _handle_billing(self):
        catalog = {}
        for t, p in PLAN_CATALOG.items():
            catalog[t.value] = {
                "name": p.name,
                "stars_price": p.stars_price,
                "fiat_cents": p.fiat_cents,
                "features": p.features,
                "description": p.description,
            }
        self._set_headers(200)
        self.wfile.write(json.dumps({"catalog": catalog}).encode("utf-8"))

    def _handle_action(self, payload: Dict[str, Any]):
        action = payload.get("action", "")
        device_id = payload.get("device_id", "local")
        user_id = payload.get("user_id", 0)

        kwargs = {k: v for k, v in payload.items() if k not in ("action", "device_id", "user_id")}
        res = global_device_service.dispatch_device_action(user_id, device_id, action, **kwargs)

        self._set_headers(200 if res.get("success") else 400)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def _handle_create_invoice(self, payload: Dict[str, Any]):
        tier_str = payload.get("tier", "PRO")
        user_id = payload.get("user_id", 0)

        try:
            tier = UserTier(tier_str)
            plan = PLAN_CATALOG.get(tier)
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "success": True,
                "tier": tier.value,
                "stars_price": plan.stars_price if plan else 0,
                "message": f"Invoice prepared for {tier.value}. Dispatching to Telegram chat.",
            }).encode("utf-8"))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))


class MiniAppServer:
    """Daemon supervisor for hosting Telegram Mini App server in background thread."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, bot_token: str = ""):
        self.host = host
        self.port = port
        self.bot_token = bot_token
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the lightweight HTTP server in a background daemon thread."""
        MiniAppRequestHandler.bot_token = self.bot_token
        self._server = HTTPServer((self.host, self.port), MiniAppRequestHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="VoidMiniAppServer")
        self._thread.start()
        logger.info(f"Telegram Mini App HTTP server running at http://{self.host}:{self.port}")

    def stop(self) -> None:
        """Stops the HTTP server gracefully."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            logger.info("Telegram Mini App HTTP server stopped.")


global_miniapp_server = MiniAppServer()
