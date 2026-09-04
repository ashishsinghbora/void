"""
core/event_bus.py - Lightweight Pub-Sub Event Bus for Real-time SSE Streaming.

Provides non-blocking, thread-safe distribution of agent reasoning steps,
tool observations, and telemetry events to browser SSE clients and background listeners.
"""

import json
import queue
import logging
import threading
from typing import Dict, Any, List, Set

logger = logging.getLogger("VoidAdvancedCore.EventBus")


class EventBus:
    """Thread-safe event distributor with subscriber queue isolation."""
    __slots__ = ("_subscribers", "_lock")

    def __init__(self):
        self._subscribers: Set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self, max_depth: int = 128) -> queue.Queue:
        """Subscribes a new client queue to the event stream."""
        q: queue.Queue = queue.Queue(maxsize=max_depth)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        """Removes a client queue from active distribution."""
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Dispatches an event to all active subscriber queues without blocking.
        If a client queue is full, the oldest unread event is dropped to avoid backpressure.
        """
        payload = {
            "event": event_type,
            "data": data,
        }
        with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    # Drop oldest to preserve memory bounds
                    try:
                        q.get_nowait()
                        q.put_nowait(payload)
                    except Exception:
                        pass
                except Exception as e:
                    logger.debug(f"Event dispatch error: {e}")

    def clear(self) -> None:
        """Deregisters all subscribers."""
        with self._lock:
            self._subscribers.clear()


# Global event bus singleton
global_event_bus = EventBus()
