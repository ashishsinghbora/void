"""
api/web_server.py - Production Flask & Waitress WSGI Server Runner.

Avoids memory leaks inherent to development servers by serving through
Waitress with bounded worker threads and connection limits.
"""

import os
import logging
from flask import Flask
from api.routes import api_bp

logger = logging.getLogger("VoidAdvancedCore.Server")

try:
    from waitress import serve
    HAS_WAITRESS = True
except ImportError:
    serve = None
    HAS_WAITRESS = False


def create_app() -> Flask:
    """Factory creating and configuring the Flask WSGI instance."""
    template_folder = os.path.join(os.path.dirname(__file__), "templates")
    app = Flask(__name__, template_folder=template_folder)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max payload
    app.register_blueprint(api_bp)
    return app


def run_web_server(host: str = "0.0.0.0", port: int = 5000, threads: int = 4) -> None:
    """Launches production-grade Waitress server with bounded thread footprint."""
    app = create_app()
    logger.info(f"Serving Void Web UI on http://{host}:{port}")

    if HAS_WAITRESS and serve is not None:
        logger.info(f"Starting Waitress WSGI server with {threads} threads...")
        serve(
            app,
            host=host,
            port=port,
            threads=threads,
            channel_timeout=30,
            connection_limit=100,
        )
    else:
        logger.warning("Waitress not installed. Falling back to basic Flask dev server.")
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_web_server()
