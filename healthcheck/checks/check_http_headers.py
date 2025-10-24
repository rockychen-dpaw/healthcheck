import logging

from django import forms

from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)

name = "check_http_headers"


def _check_headers(res_headers,headers):
    for k,v in headers:
        res_v = res_headers.get(k)
        if not v and not res_v:
            continue
        elif not v:
            return (False,"{}: Not Expected, but got '{}'".format(k,res_v))
        elif not res_v:
            if v.startswith("lambda"):
                return (False,"{}: Expect, but not found".format(k))
            else:
                return (False,"{}: Expect '{}', but not found".format(k,v))

        if v.startswith("lambda"):
            #lambda expression, 
            f_check = eval(v.strip())
            if not f_check(res_v):
                return (False,"{}: '{}' isn't the expected header value".format(k,v,res_v))
        elif v != res_v:
            return (False,"{}: Expect '{}', but got '{}'".format(k,v,res_v))

    return (True,"OK")

def is_valid(response,headers=None,include_response_if_invalid=False):
    if not headers:
        return (True,"OK")

    result =  _check_headers(response.headers,headers)
    if not result[0] and include_response_if_invalid:
        try:
            content = response.text if response else None
        except Exception as ex:
            content = str(ex)
        return (result[0],"{},response={}".format(result[1],content))
    else:
        return result

