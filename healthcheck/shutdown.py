import logging
import inspect
import asyncio
import tracemalloc
from . import settings
import signal

from .exceptions import SystemShutdown

logger = logging.getLogger(__name__)

tracemalloc.start()

shutdowning = False


_signal_handlers = {}

def _multi_signal_handlers_factory(signum):
    def _func():
        for handler in _signal_handlers[signum]:
            handler[0](*handler[1])

    return _func

def _add_signal_handler(self,signum, callback, *args):
    if signum in _signal_handlers :
        _signal_handlers[signum].append((callback,args))
    else:
        _signal_handlers[signum] = [(callback,args)]
        self._original_add_signal_handler(signum,_multi_signal_handlers_factory(signum))


def patch_asyncio():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop._original_add_signal_handler = loop.add_signal_handler
    loop.add_signal_handler = _add_signal_handler.__get__(loop,loop.__class__)
    return loop

shutdownevent = asyncio.Event()

services = set()
def register_service(service):
    services.add(service)

def unregister_service(service):
    services.discard(service)

scheduled_tasks = set()

def register_scheduled_task(scheduled_task):
    scheduled_tasks.add(scheduled_task)

def unregister_scheduled_task(scheduled_task):
    scheduled_tasks.discard(scheduled_task)


async def shutdown(block=True):
    global shutdowning
    if not shutdowning:
        logger.info("Start to shutdown")
        shutdowning = True
        shutdownevent.set()

        if scheduled_tasks:
            logger.info("Try to cancel all scheduled tasks.")
            for t in scheduled_tasks:
                logger.info("Try to cancel the scheduled task '{}'.".format(t))
                t.cancel()

        logger.info("Try to cancel all not-finished tasks.")
        for t in asyncio.all_tasks():
            logger.info("Try to cancel all not-finished task '{}'.".format(t))
            t.cancel()

    if services:
        logger.info("Waiting registered service to shutdown.")
        while services:
            service = services.pop()
            logger.info("Waiting registered service({}) to shutdown.".format(service))
            if inspect.iscoroutinefunction(service.shutdown):
                if block:
                    await service.shutdown()
                else:
                    asyncio.create_task(service.shutdown())
            else:
                service.shutdown()
            logger.info("The registered service({}) is already shutdown.".format(service))

async def wait(timeout=settings.BLOCK_TIMEOUT):
    global shutdowning
    try:
        await shutdownevent.wait()
    except asyncio.CancelledError as ex:
        await shutdown(False)
        raise SystemShutdown()
    except KeyboardInterrupt as ex:
        await shutdown(False)
        raise SystemShutdown()


async def process_userinterruption():
    await shutdown(False)
    raise SystemShutdown()

def exithandler():
    asyncio.get_event_loop().call_soon(shutdown,False)

