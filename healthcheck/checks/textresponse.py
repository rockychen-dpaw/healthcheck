import logging


logger = logging.getLogger(__name__)


name = "text"

def get_value(res):
    return res.text

