import asyncio
import inspect
import traceback
import logging
import json
import re
import os

from .. import settings
from .. import shutdown
from .. import serializers
from .commands import CommandsMixin
from .. import exceptions
from .. import lists
from signal import SIGINT, SIGTERM

from . import status
from . import connectiontype
from . import base


logger = logging.getLogger("healthcheck.socket.socketserver")

def exithandler():
    shutdown.shutdowning = True

class Connection(base.BaseConnection):
    connectid = 0
    conn_type = None
    def __init__(self,server,clientaddr,reader,writer):
        super().__init__(reader,writer)
        self.__class__.connectid += 1
        self.server = server
        self.clientaddr = clientaddr
        self.name = "The {0} connection({2} -> {1})".format(self.conn_type,self.server,self.clientaddr)

    def initialize(self):
        pass

    def __str__(self):
        return self.name

    async def shutdown(self):
        await self.close()

    async def close(self):
        if not self.writer:
            logger.debug("{}: Already closed".format(self))
            return
        await super().close()
        self.server.unregister_connection(self)

class CommandConnection(CommandsMixin,Connection):
    conn_type = connectiontype.COMMAND
    def __init__(self,server,clientaddr,reader,writer):
        super().__init__(server,clientaddr,reader,writer)
        self._run_task = None
        self.start()

    async def close(self):
        await super().close()
        if self._run_task:
            self._run_task.cancel()
            self._run_task = None

    async def run(self):
        try:
            logger.debug("{}: The command client is created for client({}).".format(self,self.clientaddr))
            while not shutdown.shutdowning:
                command = None
                args = None
                result = None
                try:
                    data = await self.receive()
                    if isinstance(data,str):
                        command = data.lower()
                        args = None
                    else:
                        command = data[0].lower()
                        args = data[1:]
                    logger.debug("{}: Receive the command '{}'".format(self,command))
                    if hasattr(self,command):
                        try:
                            func = getattr(self,command)
                            if inspect.iscoroutinefunction(func):
                                if args:
                                    result = await func(*args)
                                else:
                                    result = await func()
                            else:
                                if args:
                                    result = func(*args)
                                else:
                                    result = func()

                            result = [status.SUCCEED,result]
                        except Exception as ex:
                            traceback.print_exc()
                            result = [status.FAILED,str(ex)]
                    else:
                        result = [status.FAILED,"Command({}) Not Support".format(command)]
                    await self.send(result)
                except exceptions.ConnectionClosed as ex:
                    raise ex
                except exceptions.SystemShutdown as ex:
                    raise ex
                except Exception as ex:
                    traceback.print_exc()
                    if args:
                        result = [status.FAILED,"Failed to execute the command({}({})). {} : {}".format(command,",".join([str(a) for a in args]),ex.__class__.__name__,str(ex))]
                    else:
                        result = [status.FAILED,"Failed to execute the command({}()). {} : {}".format(command,args,ex.__class__.__name__,str(ex))]
                    await self.send(result)
        except exceptions.ConnectionClosed as ex:
            pass
        except exceptions.SystemShutdown as ex:
            pass
        except Exception as ex:
            logger.error("{}: Unexpected exception.\n{}".format(self,traceback.format_exc()))
        finally:
            await self.close()

    def start(self):
        self._run_task = asyncio.create_task(self.run())

port_in_use_re = re.compile("Errno\\s+98",re.IGNORECASE)
class SocketServer(object):
    def __init__(self,f_get_connection_cls = lambda conn_type:None):
        self.host = "127.0.0.1" if settings.HEALTHCHECKSERVER_LOCAL else "0.0.0.0"
        self.port = settings.HEALTHCHECKSERVER_PORT
        self.name = "Socket Server({}:{})".format(self.host,self.port)
        self.connections = set()
        self.f_get_connection_cls = staticmethod(f_get_connection_cls)
        shutdown.register_service(self)


    def unregister_connection(self,conn):
        self.connections.discard(conn)

    def __str__(self):
        return self.name

    async def shutdown(self):
        logger.debug("{}: Shutdown...")
        while self.connections:
            conn = None
            try:
                conn = self.connections.pop()
                await conn.shutdown()
                logger.debug("{}: Succeed to close the connection".format(conn))
            except Exception as ex:
                if conn:
                    logger.error("{}: Failed to close the connection.{}: {}".format(conn,ex.__class__.__name__,str(ex)))


    async def _create_connection(self,reader,writer):
        conn = base.BaseConnection(reader,writer)
        try:
            clientaddr = writer.get_extra_info('peername')
            logger.debug("The connection({1} -> {0}: Connection is established".format(self,clientaddr))
            conn_type = await conn.receive()
            logger.debug("{}: Receive connection type({}) from client".format(self,conn_type))
            conn_cls = self.f_get_connection_cls(conn_type)
            if not conn_cls:
                if conn_type == connectiontype.COMMAND:
                    #create the connection
                    conn_cls = CommandConnection

            if conn_cls:
                await conn.send([status.SUCCEED,"OK"])
                conn_obj = conn_cls(self,clientaddr,reader,writer)
                if hasattr(conn_obj,"initialize"):
                    if inspect.iscoroutinefunction(conn_obj.initialize):
                        await conn_obj.initialize()
                    else:
                        conn_obj.initialize()
                self.connections.add(conn_obj)
                logger.debug("{}: Succeed to establish the connection({}) from the client({})".format(self,conn_type,clientaddr))
            else:
                #connection type doesn't support
                await conn.send([status.FAILED,"Connection type({}) Not Support".format(conn_type)])
                logger.error("The connection({1} -> {0}): Connection type({2}) Not Support".format(self,clientaddr,conn_type))
                await conn.close()
        except Exception as ex:
            traceback.print_exc()
            #Failed to receive the first message, close the connection
            logger.error("The connection({1} -> {0}): Failed to create the connection.{2}:{3}".format(self,clientaddr,ex.__class__.__name__,str(ex)))
            await conn.close()


    async def start(self):
        await asyncio.start_server(self._create_connection,host = self.host,port = self.port)

async def main():
    try:
        server = SocketServer()
        await server.start()
        await shutdown.wait()
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

