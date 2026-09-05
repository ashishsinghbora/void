"""
utils/async_runner.py - Asynchronous Event Loop Supervisor.

Ensures background monitors (notification watcher, web scrapers, audio surrogates)
run continuously in an isolated, non-blocking asyncio event loop alongside the
Telegram bot command polling thread.
"""

import asyncio
import threading
import logging
from typing import Callable, Coroutine, Any, List, Dict, Optional

logger = logging.getLogger("VoidUtils.AsyncRunner")


class AsyncSupervisor:
    """Manages dedicated background asyncio event loop and scheduled coroutines."""

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running and self._loop is not None and self._loop.is_running()

    def start(self) -> None:
        """Starts the dedicated asyncio worker thread if not already running."""
        with self._lock:
            if self._running:
                return

            self._running = True
            ready_event = threading.Event()

            def _thread_target():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                ready_event.set()
                logger.info("AsyncSupervisor event loop started in background thread.")
                try:
                    self._loop.run_forever()
                finally:
                    # Cancel all remaining tasks cleanly
                    pending = asyncio.all_tasks(self._loop)
                    for task in pending:
                        task.cancel()
                    self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                    self._loop.close()
                    logger.info("AsyncSupervisor event loop closed cleanly.")

            self._thread = threading.Thread(target=_thread_target, name="VoidAsyncSupervisor", daemon=True)
            self._thread.start()
            ready_event.wait(timeout=5)

    def stop(self) -> None:
        """Stops the event loop and cancels all running background tasks."""
        with self._lock:
            if not self._running or not self._loop:
                return

            self._running = False
            for name, task in list(self._tasks.items()):
                try:
                    self._loop.call_soon_threadsafe(task.cancel)
                except Exception:
                    pass
            self._tasks.clear()

            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3)
            logger.info("AsyncSupervisor terminated.")

    def run_coroutine(self, coro: Coroutine, task_name: Optional[str] = None) -> Any:
        """Submits a coroutine into the background event loop."""
        if not self.is_running:
            self.start()

        name = task_name or f"task_{len(self._tasks) + 1}"

        async def _wrapper():
            try:
                return await coro
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in async task '{name}': {e}")
            finally:
                self._tasks.pop(name, None)

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)
            return future
        return None

    schedule_coroutine = run_coroutine

    def schedule_recurring(
        self,
        func: Callable[[], Coroutine],
        interval_seconds: float,
        task_name: str,
    ) -> None:
        """Schedules a coroutine factory to run periodically with guaranteed non-blocking execution."""
        if not self.is_running:
            self.start()

        async def _recurring_loop():
            logger.info(f"Recurring task '{task_name}' initialized (interval: {interval_seconds}s).")
            while self._running:
                try:
                    await func()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Exception in recurring task '{task_name}': {e}")
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break

        if self._loop and self._loop.is_running():
            task = self._loop.create_task(_recurring_loop(), name=task_name)
            self._tasks[task_name] = task


global_async_supervisor = AsyncSupervisor()
