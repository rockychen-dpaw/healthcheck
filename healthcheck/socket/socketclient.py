import asyncio
import traceback
import json
import os
import logging

from .. import settings
from .. import serializers
from .. import exceptions
from .. import shutdown
from ..healthcheck import HealthCheck
from .. import utils

from . import status
from . import connectiontype
from . import base

logger = logging.getLogger("healthcheck.socketclient")

class SocketClient(object):
    count = 0
    conn_type = None
    def __init__(self):
        self.host = "127.0.0.1" if settings.HEALTHCHECKSERVER_LOCAL else "0.0.0.0"
        self.port = settings.HEALTHCHECKSERVER_PORT
        self.__class__.count += 1
        self.name = "{} socketclient({}:{})_{}".format(self.conn_type,self.host,self.port,self.count)
        self._conn = None #[reader,writer]
        shutdown.register_service(self)


    def __str__(self):
        return self.name

    def shutdown(self):
        pass

    def post_connected(self):
        """
        Called right after the client is established
        """
        pass

    def request2close(self):
        if not self._conn:
            return
        self._conn.request2close()

    async def close(self):
        if not self._conn:
            return

        await self._conn.close()
        self._conn = None

    async def get_connection(self,reconnect=True):
        """
        Return a connection otherwise throw exception SystemShutdown or SocketClientTypeNotSupport

        """
        if not self._conn:
            while not shutdown.shutdowning and not self._conn:
                #connect to socket server
                connected = False
                conn = None
                reader = None
                writer = None
                try:
                    logger.debug("{}: Try to connect to socket server.".format(self))

                    reader,writer = await asyncio.open_connection(self.host,self.port) 
                    conn = base.BaseConnection(reader,writer)
                    logger.info("{} : Connected".format(self))

                    if shutdown.shutdowning:
                        raise exceptions.SystemShutdown()

                    #send connection type
                    await conn.send(self.conn_type)

                    if shutdown.shutdowning:
                        raise exceptions.SystemShutdown()

                    data = await conn.receive()

                    if not isinstance(data,(list,tuple)) or len(data) < 2:
                        raise exceptions.SocketClientTypeNotSupport("{}: Failed to create the {} socket client".format(self.conn_type))
                    elif data[0] == status.SUCCEED:
                        logger.info("{}: The {} socket client is established".format(self,self.conn_type))
                        self.post_connected()
                        self._conn = conn
                    else:
                       raise exceptions.SocketClientTypeNotSupport(data[1])

                except Exception as ex:
                    logger.error("{} : Failed to connect to socket server.{}:{}".format(self,ex.__class__.__name__,str(ex)))
                    if conn:
                        await conn.close()
                    if isinstance(ex,(exceptions.SystemShutdown,exceptions.SocketClientTypeNotSupport)):
                        raise ex
                    elif not reconnect:
                        raise ex
                    else:
                        await asyncio.sleep(settings.BLOCK_TIMEOUT)
                        continue

        if shutdown.shutdowning:
            raise exceptions.SystemShutdown()

        return self._conn

    async def send(self,data,reconnect_attempts=1):
        """
        Send the data; or throw exceptions 

        """
        reconnect = 0

        while not shutdown.shutdowning : 
            try:
                conn = await self.get_connection(False if reconnect_attempts >= 0 else True)
                await conn.send(data)
                return
            except exceptions.SystemShutdown as ex:
                await self.close()
                raise ex
            except exceptions.SocketClientTypeNotSupport as ex:
                await self.close()
                raise ex
            except Exception as ex:
                logger.error("{}: Failed to send data to socket server.{} : {}".format(self,ex.__class__.__name__,str(ex)))
                await self.close()
                reconnect += 1
                if (reconnect_attempts == -1 or reconnect <= reconnect_attempts): 
                    continue
                else:
                    raise ex

        raise exceptions.SystemShutdown()

    async def receive(self,reconnect_attempts=1):
        """
        reconnect_attempts: -1 means reconnect forever
        Return the received data; or throw exceptions 
        """
        reconnect = 0
        while not shutdown.shutdowning: 
            try:
                data = None
                conn = await self.get_connection(False if reconnect_attempts >= 0 else True)
                data = await conn.receive()
                logger.debug("{}: Succeed to receive the data: {}".format(self,data))
                return data
            except exceptions.SystemShutdown as ex:
                raise ex
            except exceptions.SocketClientTypeNotSupport as ex:
                raise ex
            except exceptions.MalformedData as ex:
                raise ex
            except Exception as ex:
                if not isinstance(ex,exceptions.ConnectionClosed):
                    logger.error("{}: Unexpected exception.\n{}".format(self,traceback.format_exc()))
                await self.close()
                reconnect += 1
                if (reconnect_attempts == -1 or reconnect <= reconnect_attempts):
                    continue
                else:
                    raise ex

        raise exceptions.SystemShutdown()

class CommandClient(SocketClient):
    conn_type = connectiontype.COMMAND
    def __init__(self,conn_type):
        super().__init__()
        self._lock = asyncio.Lock()

    async def exec(self,command,reconnect_attempts=-1):
        async with self._lock:
            reconnect = 0
            while True:
                try:
                    logger.debug("{}: Begin to send command({}) to server".format(self,command))
                    await self.send(command,0)
                    logger.debug("{}: Succeed to send command({}) to server, wait the response".format(self,command))
                    res = await self.receive(0)
                    logger.debug("{0}: Receive the response({2}) of the command({1}) from server".format(self,command,res))
                    if res[0] > 0:
                        return res[1]
                    else:
                        raise exceptions.FailedResponse(res[1])
                except exceptions.SystemShutdown as ex:
                    raise ex
                except exceptions.SocketClientTypeNotSupport as ex:
                    await self.close()
                    raise ex
                except exceptions.MalformedData as ex:
                    raise ex
                except exceptions.FailedResponse as ex:
                    raise ex
                except exceptions.ConnectionClosed as ex:
                    reconnect += 1
                    if (reconnect_attempts == -1 or reconnect <= reconnect_attempts): 
                        continue
                    else:
                        raise ex
                except Exception as ex:
                    logger.error("{}: Unexpected exception.\n{}".format(self,traceback.format_exc()))
                    reconnect += 1
                    if (reconnect_attempts == -1 or reconnect <= reconnect_attempts): 
                        continue
                    else:
                        raise ex

commandclient = CommandClient("command")

async def main():
    try:
        #listener = HealthStatusListenerClient()
        commandclient = CommandClient("command")
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
                    result = await commandclient.exec(command)
                    print("request = {}, response = {}".format(command,json.dumps(result,indent=4)))
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

