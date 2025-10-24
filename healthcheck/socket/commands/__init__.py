from .ping import PingMixin
from .connections import ConnectionsMixin

class CommandsMixin(PingMixin,ConnectionsMixin):
    pass
