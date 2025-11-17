import asyncio
import logging

from . import exceptions
from . import shutdown
from . import socket
from .lists import CycleList
from . import settings
from .healthcheck import healthcheck
from . import utils


logger = logging.getLogger("healthcheck.healthcheckclient")

class Event(object):
    def __init__(self):
        self.locks = [asyncio.Event() for i in range(settings.ASYNCIO_EVENTS)]
        self._max_index  = len(self.locks) - 1
        self.index = 0
        self._clear = False

    async def wait(self):
        await self.locks[self.index].wait()

    def set(self):
        i = self.index
        if self.index == self._max_index:
            self.index = 0
            self._clear = True
        else:
            self.index += 1

        if self._clear:
            self.locks[self.index].clear()

        self.locks[i].set()

class BaseHealthStatusListenerClient(socket.SocketClient):
    def __init__(self):
        super().__init__()
        self._statuslist = CycleList(settings.HEALTHSTATUS_BUFFER)
        self._healthstatus_task = None
        self._wait = Event()
        self.continuouscheck_started = False

    async def wait(self):
        """
        Block forever until waked by new healthstatus
        """
        await self._wait.wait()

    async def shutdown(self):
        if not self._healthstatus_task:
            return

        await self._healthstatus_task
        self._wait.set()

        self._healthstatus_task = None

    def get_healthstatusreader(self,startindex=None):
        if startindex is None:
            startindex = self._statuslist.index
        return self._statuslist.get_reader(startindex)

    async def run(self):
        logger.info("{}: Start to listen the health check result".format(self))
        try:
            while not shutdown.shutdowning:
                try:
                    status_code,data = await self.receive(-1)
                    if status_code == socket.HEALTHCONFIG_HAHSCODE:
                        if self.healthcheck.config_hashcode != data:
                            self.healthcheck.reload()
                            self._statuslist.add("reload")
                            self._wait.set()
                    elif status_code == socket.INITIAL_HEALTHSTATUS:
                        service = self.healthcheck.get_service(*data[0])
                        if service.healthstatus and service.healthstatus[0] == data[1][0]:
                            #status is not changed
                            continue
                        if service:
                            service.healthstatus = data[1]
                        else:
                            logger.error("The service({}.{}) doesn't exist".format(*data[0]))
                            continue
                        self._statuslist.add(data)
                        self._wait.set()
                    elif status_code == socket.HEALTHSTATUS:
                        service = self.healthcheck.get_service(*data[0])
                        if service:
                            service.healthstatus = data[1]
                        else:
                            logger.error("The service({}.{}) doesn't exist".format(*data[0]))
                            continue
                        self._statuslist.add(data)
                        self._wait.set()
                    elif status_code == socket.RELOAD_DASHBOARD:
                        self._statuslist.add("reload")
                        self._wait.set()
                    elif status_code == socket.CONTINUOUSCHECK_STARTED:
                        self._statuslist.add("continuouscheck_started")
                        self.continuouscheck_started = True
                        self._wait.set()
                    elif status_code == socket.CONTINUOUSCHECK_STOPPED:
                        self._statuslist.add("continuouscheck_stopped")
                        self.continuouscheck_started = False
                        self._wait.set()
                    elif status_code < 0:
                        logger.error("{}: Get a failed response: {}".format(data))
                    else:
                        logger.error("The status code({}) Not Support".format(status_code))
                except exceptions.SystemShutdown as ex:
                    break
                except Exception as ex:
                    logger.error("{}: Failed to receive the data({},{}).{}: {}".format(self,status_code,data,ex.__class__.__name__,str(ex)))
    
        except Exception as ex:
            pass
        finally:
            logger.info("{}: End to listen the health check result".format(self))
            self._wait.set()


    def start(self):
        self._healthstatus_task = asyncio.create_task(self.run())

class HealthStatusListenerClient(BaseHealthStatusListenerClient):
    conn_type = socket.HEALTHSTATUS_SUBSCRIPTOR

    @property
    def healthcheck(self):
        return healthcheck

class EditingHealthStatusListenerClient(BaseHealthStatusListenerClient):
    conn_type = socket.EDITING_HEALTHSTATUS_SUBSCRIPTOR

    @property
    def healthcheck(self):
        return healthcheck.editing_healthcheck

healthstatuslistener = HealthStatusListenerClient()
editinghealthstatuslistener = EditingHealthStatusListenerClient()

async def main():
    try:
        healthstatuslistener.start()
        client = socket.CommandClient("command")
        while True:
            try:
                command = await utils.ainput("Enter socket command to execute or 'exit' to quit.")
                command = command.strip().lower()
                if not command:
                    continue
                if command == 'exit':
                    break
                else:
                    command = command.split()
                    if len(command) == 1:
                        command = command[0]
                    result = await client.exec(command)
                    print("request = {}, response = {}".format(command,result))
            except KeyboardInterrupt as ex:
                break
            except exceptions.SystemShutdown as ex:
                break
            except exceptions.FailedResponse as ex:
                logger.error("Faield to process request({}). {}: {}".format(command,ex.__class__.__name__,str(ex)))
                continue
    finally:
        await shutdown.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except asyncio.CancelledError as ex:
        pass

