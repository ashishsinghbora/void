"""
api/sse_stream.py - Server-Sent Events (SSE) Real-Time Telemetry & Reasoning Stream.

Streams live agent thoughts, tool observations, and hardware metrics to
browser dashboards with minimal CPU and zero buffer accumulation.
"""

import json
import queue
import logging
from typing import Generator
from core.event_bus import EventBus, global_event_bus

logger = logging.getLogger("VoidAdvancedCore.SSE")


def sse_event_generator(event_bus: EventBus = global_event_bus, timeout: float = 15.0) -> Generator[str, None, None]:
    """
    Yields Server-Sent Events from the EventBus subscriber queue.
    Sends periodic keepalive pings to maintain mobile socket liveness.
    """
    client_queue = event_bus.subscribe(max_depth=64)
    logger.info("New browser client connected to SSE event stream.")

    try:
        # Initial handshake event
        yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Void Live Stream'})}\n\n"

        while True:
            try:
                msg = client_queue.get(timeout=timeout)
                event_type = msg.get("event", "message")
                data = msg.get("data", {})
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            except queue.Empty:
                # Keep-alive heartbeat ping to prevent connection teardown
                yield ": keepalive\n\n"
    except GeneratorExit:
        logger.info("SSE client disconnected.")
    finally:
        event_bus.unsubscribe(client_queue)
