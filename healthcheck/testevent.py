import asyncio
import random
import sys

from . import settings

class Event(object):
    def __init__(self):
        self.locks = [asyncio.Event() for i in range(settings.ASYNCIO_EVENTS)]
        self._max_index  = len(self.locks) - 1
        self.index = 0
        self._clear = False
        self._counter = 0

    async def wait(self):
        while True:
            try:
                async with asyncio.timeout(1):
                    await self.locks[self.index].wait()
                    print("****************waken up")
                    break
            except TimeoutError as ex:
                print("****************{}: {}".format(ex.__class__.__name__,str(ex)))
                continue


    def set(self):
        i = self.index
        if self.index == self._max_index:
            self.index = 0
            self._clear = True
        else:
            self.index += 1

        if self._clear:
            self.locks[self.index].clear()

        self._counter += 1
        print("The {}th Wake up the tasks which are waiting on {}th lock".format(self._counter,i))
        self.locks[i].set()

class Listener(object):
    count = 0
    listeners = []
    def __init__(self,lock,blocktimes):
        self.__class__.count += 1
        self.name = "Listener {}".format(self.count)
        self.blocktimes = blocktimes
        self.lock = lock
        self.waketimes = 0
        self._task = None
        self._status = "created"

    def __str__(self):
        return self.name

    async def shutdown(self):
        if self._task:
            await self._task
            self._task  = None

    async def _run(self):
        self._status = "running"
        while self.waketimes < self.blocktimes :
            i = self.lock.index
            print("{}: wait on {}th lock".format(self.name,i))
            await self.lock.wait()
            print("{}: wake up on {}th lock, currently lock is {}".format(self.name,i,self.lock.index))
            #print("{}: Wake up and begin to work".format(self.name))
            self.waketimes += 1
            if self.waketimes < self.blocktimes:
                await asyncio.sleep(random.randint(1,5))
            #print("{}: end work".format(self.name))

        self._status = "end"
        try:
            self.listeners.remove(self)
        except ValueError as ex:
            pass
        print("{} exits.".format(self))


    def run(self):
        if  self._task:
            print("The task is already started")
            return
        self._status = "scheduled"
        self.listeners.append(self)
        self._task = asyncio.create_task(self._run())

    def is_alive(self):
        return self._status in ("scheduled","running")

    @classmethod
    async def joinall(cls):
        global shutdown
        while cls.listeners:
            await cls.listeners[0].shutdown()
        shutdown = True

shutdown = False
async def trig_event(lock):
    while not shutdown:
        await asyncio.sleep(3)
        lock.set()

    print("Trig event exits.")


async def main(count,blocktimes):
    global shutdown
    lock = Event()
    listeners = [Listener(lock,blocktimes) for i in range(count)]
    for listener in listeners:
        listener.run()

    trigevent_task = asyncio.create_task(trig_event(lock))
    await Listener.joinall()
    await trigevent_task


if __name__ == '__main__':
    if len(sys.argv) > 1:
        listeners = int(sys.argv[1])
    else:
        listeners = 10

    if len(sys.argv) > 2:
        blocktimes = int(sys.argv[2])
    else:
        blocktimes = 1

    asyncio.run(main(listeners,blocktimes))
    
