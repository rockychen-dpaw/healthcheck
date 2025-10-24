import asyncio
import traceback
import json
import logging

from .. import exceptions
from .. import serializers
from .. import shutdown

logger = logging.getLogger(__name__)

class BaseConnection(object):
    conn_type = None
    def __init__(self,reader,writer):
        self.reader = reader
        self.writer = writer

    async def shutdown(self):
        await self.close()

    def request2close(self):
        if not self.writer:
            return
        if self.writer.is_closing():
            return 
        self.writer.close()

    async def close(self):
        if not self.writer:
            return

        try:
            try:
                self.writer.close()
            except Exception as ex:
                pass
            await self.writer.wait_closed()
            logger.debug("{}: Succeed to close the connection.".format(self))
        except Exception as ex:
            logger.error("{}: Failed to close the connection.{}:{}".format(self,ex.__class__.__name__,str(ex)))

        self.writer = None
        self.reader = None

    async def receive(self):
        if shutdown.shutdowning:
            await self.shutdown()
            raise exceptions.SystemShutdown()

        try:
            data = await self.reader.readline()
            if not data:
                await self.close()
                raise exceptions.ConnectionClosed("{}: Connection has been closed".format(self))
            try:
                data = json.loads(data.decode().strip(),cls=serializers.JSONDecoder)
                return data
            except Exception as ex:
                raise exceptions.MalformedData("{}: The received data({}) is corrupted.{}: {}".format(self,data,ex.__class__.__name__,str(ex)))
        except TypeError as ex:
            if self.reader:
                raise ex
        except KeyboardInterrupt as ex:
            await self.shutdown()
            await shutdown.process_userinterruption()
        except InterruptedError as ex:
            await self.shutdown()
            await shutdown.process_userinterruption()


    async def send(self,data):
        if shutdown.shutdowning:
            await self.shutdown()
            raise exceptions.SystemShutdown()
        if not self.writer:
            #already closed
            return

        try:
            data = json.dumps(data,cls=serializers.JSONEncoder)
            data = "{}\n".format(data).encode()
        except Exception as ex:
            raise exceptions.MalformedData("{}: Failed to encode the response.{}: {}".format(self,ex.__class__.__name__,str(ex)))

        try:
            self.writer.write(data)
            await self.writer.drain()
            logger.debug("{}: Succeed to send the data({})".format(self,data))
        except TypeError as ex:
            if self.writer:
                raise ex
        except Exception as ex:
            await self.close()
            raise exceptions.ConnectionClosed("{}: Failed to send the data({}), close the connection. {}: {}".format(self,data,ex.__class__.__name__,str(ex)))

    async def __aenter__(self):
        return self

    async def __aexit__(self,exc_type,exc_val,exc_tb):
        await self.close()
        return False


