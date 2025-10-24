import logging

logger = logging.getLogger(__name__)

name = "httpstatus"

def get_value(res):
    return res.status_code

