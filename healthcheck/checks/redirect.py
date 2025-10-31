import logging


logger = logging.getLogger(__name__)


name = "redirect"

def get_value(res,key=None):
    return res.headers.get("location")

