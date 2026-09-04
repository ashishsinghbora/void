"""
api/web_server.py - Production Flask & Waitress WSGI Server Runner.

Avoids memory leaks inherent to development servers by serving through
Waitress with bounded worker threads and connection limits.
Includes automatic port conflict resolution, stale instance recycling,
and graceful socket fallback.
"""

import os
import sys
import time
import errno
import socket
import logging
from typing import Optional
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


def is_port_available(host: str, port: int) -> bool:
    """Probes if a specific port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_host = "0.0.0.0" if host in ("0.0.0.0", "") else host
            s.bind((bind_host, port))
            return True
        except OSError:
            return False


def terminate_stale_void_processes() -> None:
    """Cleanly halts any previous/orphaned Void app.py process to reclaim ports."""
    my_pid = os.getpid()
    try:
        import subprocess
        res = subprocess.run(["pgrep", "-f", "app.py"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            for p in res.stdout.strip().split():
                if p.isdigit():
                    pid = int(p)
                    if pid != my_pid:
                        logger.warning(f"Reclaiming port: Terminating stale Void process (PID: {pid})...")
                        try:
                            os.kill(pid, 15)  # SIGTERM
                        except ProcessLookupError:
                            pass
            time.sleep(1.0)
    except Exception as e:
        logger.debug(f"Could not scan/kill stale processes: {e}")


def get_effective_port(host: str, preferred_port: int, max_fallback_attempts: int = 10) -> int:
    """
    Ensures an available port by reclaiming stale Void processes first,
    then probing sequential candidate ports if another application occupies it.
    """
    if is_port_available(host, preferred_port):
        return preferred_port

    logger.warning(f"Port {preferred_port} is busy. Checking for stale Void processes...")
    terminate_stale_void_processes()

    if is_port_available(host, preferred_port):
        logger.info(f"Successfully reclaimed port {preferred_port}!")
        return preferred_port

    # If preferred port is held by an external non-Void application, find the next available port
    for offset in range(1, max_fallback_attempts + 1):
        candidate = preferred_port + offset
        if is_port_available(host, candidate):
            logger.warning(
                f"Port {preferred_port} is in use by another application. Automatically falling back to http://{host}:{candidate}"
            )
            return candidate

    return preferred_port


def run_web_server(host: str = "0.0.0.0", port: int = 5000, threads: int = 4) -> int:
    """
    Launches production-grade Waitress server with bounded thread footprint.
    Reclaims stale ports and handles address conflicts gracefully.
    Returns the effective port bound.
    """
    app = create_app()
    effective_port = get_effective_port(host, port)

    logger.info(f"Serving Void Web UI on http://{host}:{effective_port}")

    if HAS_WAITRESS and serve is not None:
        logger.info(f"Starting Waitress WSGI server with {threads} threads on port {effective_port}...")
        try:
            serve(
                app,
                host=host,
                port=effective_port,
                threads=threads,
                channel_timeout=30,
                connection_limit=100,
            )
        except OSError as err:
            if err.errno in (getattr(errno, "EADDRINUSE", 98), 98, 48) or "already in use" in str(err).lower():
                fallback = effective_port + 1
                logger.warning(f"Port {effective_port} busy during bind. Retrying on fallback port {fallback}...")
                serve(
                    app,
                    host=host,
                    port=fallback,
                    threads=threads,
                    channel_timeout=30,
                    connection_limit=100,
                )
                return fallback
            else:
                raise
    else:
        logger.warning("Waitress not installed. Falling back to basic Flask dev server.")
        app.run(host=host, port=effective_port, debug=False, threaded=True)

    return effective_port


if __name__ == "__main__":
    run_web_server()
