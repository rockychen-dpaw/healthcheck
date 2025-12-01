import os
import signal
import asyncio

class ShutdownMixin(object):
    SHUTDOWN="shutdown"
    async def _shutdown(self):
        os.kill(os.getpid(), signal.SIGTERM)

    def shutdown(self):
        asyncio.create_task(self._shutdown())
        return "Shutdowning"


