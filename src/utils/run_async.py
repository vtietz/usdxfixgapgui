import asyncio
from PyQt6.QtCore import QThread
import logging

logger = logging.getLogger(__name__)

class AsyncioThread(QThread):
    def __init__(self, loop):
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

def run_async(coro):
    asyncio.run_coroutine_threadsafe(coro, _loop)
