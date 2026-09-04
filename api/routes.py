"""
api/routes.py - Flask Web Endpoints & SSE Real-time Streaming Blueprint.
"""

import os
import resource
import logging
from flask import Blueprint, request, jsonify, render_template, Response, send_file

from agents.react_agent import global_react_agent
from tools.registry import global_tool_registry
from storage.repository import ExecutionLogRepository, ClipboardRepository
from api.sse_stream import sse_event_generator
from security.sanitizer import InputSanitizer

logger = logging.getLogger("VoidAdvancedCore.Routes")
api_bp = Blueprint("api_bp", __name__)


@api_bp.after_request
def add_cors_headers(response):
    """Enables Cross-Origin Resource Sharing (CORS) for GitHub Pages remote dashboards."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@api_bp.route("/api/<path:subpath>", methods=["OPTIONS"])
def handle_options(subpath):
    """Handles CORS preflight OPTIONS requests."""
    return jsonify({"status": "ok"}), 200


@api_bp.route("/")
def index():
    """Renders the glassmorphic dashboard."""
    return render_template("dashboard.html")


@api_bp.route("/api/stream")
def sse_stream():
    """Server-Sent Events endpoint streaming live deliberation and telemetry."""
    return Response(
        sse_event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@api_bp.route("/api/chat", methods=["POST"])
def chat():
    """Main conversational and hardware command entrypoint."""
    try:
        data = request.get_json() or {}
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id", "web_default")

        if not user_message:
            return jsonify({"status": "error", "error": "Empty message provided."}), 400

        # Execute deterministic ReAct loop
        response = global_react_agent.run(user_message, session_id=session_id)
        return jsonify(response.to_dict()), 200

    except Exception as e:
        logger.error(f"Chat execution exception: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@api_bp.route("/api/status")
def status():
    """Returns real-time device health, memory footprint, and telemetry."""
    # Measure Resident Set Size (RSS) in MB
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # Linux reports ru_maxrss in Kilobytes
    rss_mb = round(usage.ru_maxrss / 1024.0, 2)

    battery_res = global_tool_registry.execute("get_battery_status")
    battery_info = battery_res.output if battery_res.success else {"percentage": 100, "status": "Simulated"}

    return jsonify({
        "status": "online",
        "ram_rss_mb": rss_mb,
        "ram_target_met": rss_mb < 50.0,
        "battery": battery_info,
        "active_daemons": ["NotificationInterceptor", "RoutineScheduler"],
    })


@api_bp.route("/api/logs")
def logs():
    """Retrieves recent execution audit logs."""
    limit = request.args.get("limit", default=25, type=int)
    safe_limit = min(max(limit, 1), 100)
    repo = ExecutionLogRepository()
    return jsonify(repo.get_recent_logs(limit=safe_limit))


@api_bp.route("/api/clipboard")
def clipboard():
    """Retrieves recent clipboard history."""
    limit = request.args.get("limit", default=10, type=int)
    safe_limit = min(max(limit, 1), 50)
    repo = ClipboardRepository()
    return jsonify(repo.get_recent(limit=safe_limit))


@api_bp.route("/api/tools/execute", methods=["POST"])
def execute_tool():
    """Direct execution endpoint for registered hardware tool strategies."""
    try:
        data = request.get_json() or {}
        tool_name = data.get("tool_name")
        args = data.get("arguments", {})

        if not tool_name:
            return jsonify({"status": "error", "error": "Missing tool_name"}), 400

        res = global_tool_registry.execute(tool_name, **args)
        return jsonify(res.to_dict()), 200 if res.success else 400
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@api_bp.route("/photo")
def get_photo():
    """Serves captured camera photo if present."""
    possible_targets = [
        "/sdcard/Download/void_photo.jpg",
        os.path.expanduser("~/storage/downloads/void_photo.jpg"),
        os.path.expanduser("~/void_photo.jpg"),
    ]
    for p in possible_targets:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return send_file(p, mimetype="image/jpeg")
    return "Photo not found", 404


@api_bp.route("/api/extensions")
def list_extensions():
    """Returns metadata of all loaded extensions."""
    try:
        from extensions.manager import global_extension_manager
        return jsonify(global_extension_manager.list_extensions()), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

