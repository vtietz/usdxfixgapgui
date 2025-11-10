import asyncio
from PySide6.QtCore import QThread
import logging

logger = logging.getLogger(__name__)


class AsyncioThread(QThread):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop

    def run(self):
        logger.debug("Starting asyncio loop")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


# Lazy-start state management
_loop = None
_thread = None
_semaphore = None
_started = False  # Internal flag; not referenced elsewhere, keep for readability


def _ensure_started():
    """Ensure asyncio runtime is started (lazy initialization)."""
    global _loop, _thread, _semaphore, _started
    if _started:
        return

    logger.debug("Initializing asyncio runtime")
    _loop = asyncio.new_event_loop()
    _thread = AsyncioThread(_loop)
    _thread.start()
    _semaphore = asyncio.Semaphore(10)
    _started = True
    logger.info("Asyncio runtime started")


def is_started():
    """Check if asyncio runtime is active."""
    return _started


def run_async(coro, callback=None):
    """Run coroutine in background asyncio thread."""
    _ensure_started()  # Lazy start

    async def task_wrapper():
        async with _semaphore:  # type: ignore[arg-type]
            return await coro  # Execute the coroutine within the semaphore context

    future = asyncio.run_coroutine_threadsafe(task_wrapper(), _loop)
    if callback:
        future.add_done_callback(lambda f: callback(f.result()))


def run_sync(coro):
    """Run coroutine synchronously and return result."""
    _ensure_started()  # Lazy start

    async def sync_wrapper():
        async with _semaphore:  # type: ignore[arg-type]
            return await coro

    future = asyncio.run_coroutine_threadsafe(sync_wrapper(), _loop)
    return future.result()


def shutdown_asyncio():
    """Properly shutdown the asyncio event loop and thread (idempotent)."""
    global _started
    if not _started:
        logger.debug("Asyncio runtime not started, skipping shutdown")
        return

    logger.info("Shutting down asyncio loop")

    # Stop the event loop (will exit run_forever())
    _loop.call_soon_threadsafe(_loop.stop)

    # Wait for thread to finish (with timeout)
    if _thread.isRunning():
        _thread.quit()
        if not _thread.wait(2000):  # 2 second timeout
            logger.warning("Asyncio thread did not stop within timeout")
        else:
            logger.info("Asyncio thread stopped cleanly")

    _started = False
