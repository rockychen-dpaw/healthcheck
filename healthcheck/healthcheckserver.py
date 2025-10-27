import logging
import asyncio
import threading
import sys
import os

from . import shutdown
from . import settings
from .healthcheck import BaseServiceHealthCheckTask,healthcheck
from . import socket
from . import exceptions
from . import utils

logger = logging.getLogger("healthcheck.healthcheckserver")

class BaseHealthStatusSubscriptor(socket.Connection):
    subscriptors = None
    _lock = None
    def __init__(self,server,clientaddr,reader,writer):
        super().__init__(server,clientaddr,reader,writer)
        self._send_task = None
        self.__class__.subscriptors.append(self)

    async def receive(self):
        raise Exception("Receiving data Not Supported")

    async def close(self):
        await super().close()
        try:
            self.__class__.subscriptors.remove(self)
        except ValueError as ex:
            pass

    @classmethod
    async def _send_data(cls,data):
        try:
            async with cls._lock:
                for index in range(len(cls.subscriptors) - 1,-1,-1):
                    try:
                        subscriptor = cls.subscriptors[index]
                    except IndexError as ex:
                        continue
                    subscriptor._send_task = asyncio.create_task(subscriptor.send(data))
    
                for index in range(len(cls.subscriptors) - 1,-1,-1):
                    try:
                        subscriptor = cls.subscriptors[index]
                        if subscriptor._send_task:
                            try:
                                await subscriptor._send_task
                            finally:
                                subscriptor._send_task = None
                    except IndexError as ex:
                        continue
        except exceptions.ConnectionClosed as ex:
            pass
        except Exception as ex:
            if not shutdown.shutdowning:
                raise ex
            

    @classmethod
    async def send_healthstatus(cls,data):
        await cls._send_data([socket.HEALTHSTATUS,data])
    
class HealthStatusSubscriptor(BaseHealthStatusSubscriptor):
    subscriptors = []
    _lock = asyncio.Lock()
    conn_type = socket.HEALTHSTATUS_SUBSCRIPTOR

    async def initialize(self):
        await self.send([socket.HEALTHCONFIG_HAHSCODE,healthcheck.config_hashcode])
        for section in healthcheck.sections.values():
            for service in section["services"].values():
                if service.get("healthstatus"):
                    await self.send([socket.INITIAL_HEALTHSTATUS,[[service.sectionid,service.serviceid],service["healthstatus"]]])

    @classmethod
    async def healthconfig_changed(cls):
        await cls._send_data([socket.HEALTHCONFIG_HAHSCODE,healthcheck.config_hashcode])
    

class EditingHealthStatusSubscriptor(BaseHealthStatusSubscriptor):
    subscriptors = []
    _lock = asyncio.Lock()
    conn_type = socket.EDITING_HEALTHSTATUS_SUBSCRIPTOR

    async def initialize(self):
        await self.send([socket.HEALTHCONFIG_HAHSCODE,healthcheck.editing_healthcheck.config_hashcode])
        for section in healthcheck.editing_healthcheck.sections.values():
            for service in section["services"].values():
                if service.get("healthstatus"):
                    await self.send([socket.INITIAL_HEALTHSTATUS,[[service.sectionid,service.serviceid],service["healthstatus"]]])

    @classmethod
    async def healthconfig_changed(cls):
        await cls._send_data([socket.HEALTHCONFIG_HAHSCODE,healthcheck.editing_healthcheck.config_hashcode])
    
class ServiceHealthCheckTask(BaseServiceHealthCheckTask):
    def __init__(self,servicehealthcheck,socketserver):
        self.servicehealthcheck = servicehealthcheck
        self.socketserver = socketserver

    async def post_healthcheck(self,healthstatus):
        await HealthStatusSubscriptor.send_healthstatus(healthstatus)

class EditingServiceHealthCheckTask(BaseServiceHealthCheckTask):
    def __init__(self,servicehealthcheck,socketserver):
        self.servicehealthcheck = servicehealthcheck
        self.socketserver = socketserver

    async def post_healthcheck(self,healthstatus):
        await EditingHealthStatusSubscriptor.send_healthstatus(healthstatus)

class CommandConnection(socket.CommandConnection):
    START_PREVIEW_HEALTHCHECK="start_preview_healthcheck"
    STOP_PREVIEW_HEALTHCHECK="stop_preview_healthcheck"
    SAVE_EDITING_HEALTHCHECK="save_editing_healthcheck"
    async def start_preview_healthcheck(self):
        await healthcheck.editing_healthcheck.continuous_check(self.server,taskcls=EditingServiceHealthCheckTask)
        return [True,"OK"]

    def stop_preview_healthcheck(self):
        healthcheck.editing_healthcheck.stop_continuous_check()
        return [True,"OK"]

    async def reload_editing_healthcheck(self):
        changed = healthcheck.editing_healthcheck.reload()
        if changed and healthcheck.editing_healthcheck.is_continuous_check_started:
            healthcheck.editing_healthcheck.stop_continuous_check()  
            await EditingHealthStatusSubscriptor.healthconfig_changed()
            await healthcheck.editing_healthcheck.continuous_check(self.server,taskcls=EditingServiceHealthCheckTask)
        return [True,"OK"]

    async def reload_healthcheck(self):
        changed = healthcheck.reload()
        if changed and healthcheck.is_continuous_check_started:
            healthcheck.stop_continuous_check()  
            await HealthStatusSubscriptor.healthconfig_changed()
            await healthcheck.continuous_check(self.server,taskcls=ServiceHealthCheckTask)
        return [True,"Tested"]

    def healthcheck(self):
        if not healthcheck.is_continuous_check_started:
            return [False,"Continuous Health Check is not running"]
        return [True,"OK"]

def get_connection_cls(conn_type):
    """
    Return the connection class if supporte; otherwise return None
    """

    if conn_type == socket.HEALTHSTATUS_SUBSCRIPTOR:
        return HealthStatusSubscriptor
    elif conn_type == socket.EDITING_HEALTHSTATUS_SUBSCRIPTOR:
        return EditingHealthStatusSubscriptor
    elif conn_type == socket.COMMAND:
        return CommandConnection
    else:
        return None

async def main():
    try:
        server = socket.SocketServer(f_get_connection_cls=get_connection_cls)
        await server.start()
        await healthcheck.continuous_check(server,taskcls=ServiceHealthCheckTask)
        await shutdown.wait()
        while True:
            try:
                command = await utils.ainput("Enter 'exit' to quit.")
                command = command.strip().lower()
                if not command:
                    continue
                if command == 'exit':
                    break
            except KeyboardInterrupt as ex:
                break
    except exceptions.SystemShutdown as ex:
        pass
    except asyncio.CancelledError as ex:
        pass
    finally:
        await shutdown.shutdown()
        pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except asyncio.CancelledError as ex:
        pass

