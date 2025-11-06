from .ping import PingMixin
from .shutdown  import ShutdownMixin
from .connections import ConnectionsMixin

class CommandsMixin(PingMixin,ShutdownMixin,ConnectionsMixin):
    pass
