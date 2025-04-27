import asyncio
from PyQt6.QtCore import QThread
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

# Singleton-like management of the asyncio loop
_loop = asyncio.new_event_loop()
_thread = AsyncioThread(_loop)
_thread.start()

# Create a semaphore with a specific limit, e.g., 10 concurrent tasks
_semaphore = asyncio.Semaphore(10)

def run_async(coro, callback=None):
    async def task_wrapper():
        async with _semaphore:
            return await coro  # Execute the coroutine within the semaphore context

    # Schedule the wrapped task and attach callback if provided
    future = asyncio.run_coroutine_threadsafe(task_wrapper(), _loop)
    if callback:
        future.add_done_callback(lambda f: callback(f.result()))

def run_sync(coro):
    # Since run_sync is designed to block, ensure the semaphore is used here as well
    async def sync_wrapper():
        async with _semaphore:
            return await coro

    future = asyncio.run_coroutine_threadsafe(sync_wrapper(), _loop)
    return future.result()
