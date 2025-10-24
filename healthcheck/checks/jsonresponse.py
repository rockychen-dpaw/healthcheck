import logging
import os
from datetime import datetime,timedelta

from .. import settings

from .base import datanotfound

logger = logging.getLogger(__name__)

TZ = settings.TZ

name = "jsonresponse"

def get_value(res,key=None):
    try:
        data = res.json()
    except:
        raise Exception("Invalid json data.")

    if not key:
        return  data

    for k in key:
        if not data:
            return datanotfound

        if k[0]:
            if isinstance(data,dict):
                if k[1] in data:
                    data = data[k[1]]
                else:
                    return datanotfound
            elif hasattr(data,k):
                data = getattr(data,k)
            else:
                return datanotfound
        elif isinstance(data,(list,tuple,str)):
            if len(data) > k[1]:
                data = data[k[1]]
            else:
                return datanotfound
        else:
            raise Exception("The data({}({})) is not subscriptable;".format(data.__class__.__name__,data))

    return data

