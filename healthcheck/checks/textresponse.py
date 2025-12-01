import logging


logger = logging.getLogger(__name__)


name = "text"

def get_value(res,key=None):
    return res.text

