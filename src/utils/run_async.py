import asyncio
from PyQt6.QtCore import QThread
import logging

logger = logging.getLogger(__name__)

class AsyncioThread(QThread):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        print("=====")

    def run(self):
        print("------")
        logger.debug("Starting asyncio loop")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

# Singleton-like management of the asyncio loop
_loop = asyncio.new_event_loop()
_thread = AsyncioThread(_loop)
_thread.start()

def run_async(coro, callback=None):
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    if callback:
        future.add_done_callback(lambda f: callback(f.result()))