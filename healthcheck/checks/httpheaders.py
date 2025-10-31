import logging



logger = logging.getLogger(__name__)

name = "headers"

def get_value(res,key=None):
    """
    key:[[True,headername]]]

    """
    headers = res.headers
    if not key:
        return headers

    if key:
        return headers.get(key[0][1])
    
