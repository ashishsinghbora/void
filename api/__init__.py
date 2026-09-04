"""
api - Web UI Dashboard, REST Endpoints, and SSE Event Streaming.
"""

from api.web_server import create_app, run_web_server
from api.routes import api_bp
from api.sse_stream import sse_event_generator

__all__ = ["create_app", "run_web_server", "api_bp", "sse_event_generator"]
