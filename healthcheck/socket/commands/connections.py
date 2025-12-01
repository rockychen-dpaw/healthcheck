class ConnectionsMixin(object):
    CONNECTIONS="connections"
    def connections(self):
        return [str(conn) for conn in self.server.connections]
