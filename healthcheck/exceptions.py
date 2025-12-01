
class SystemShutdown(Exception):
    def __init__(self):
        super().__init__("System is shutdowning")

class SendDataToSocketServerFailed(Exception):
    pass

class ReceiveDataFromSocketServerFailed(Exception):
    pass

class SocketClientTypeNotSupport(Exception):
    pass

class MalformedData(Exception):
    pass

class FailedResponse(Exception):
    pass

class ConnectionClosed(Exception):
    pass
