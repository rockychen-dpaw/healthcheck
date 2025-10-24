import logging
import re

from django import forms
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)

name = "check_redirecturl"

def _parse_statuscodes(status):
    if not status:
        return None
    statuscodes = []
    for s in status.split(","):
        try:
            s = s.strip()
            if not s:
                continue
            r = [ int(d.strip()) for d in s.split("-",1)]
            for c in r:
                if c >= 300 and c <= 399:
                    continue
                else:
                    raise ValidationError("{} is not a valid redirect http code".format(c))
            if len(r) == 1:
                statuscodes.append(r[0])
            else:
                statuscodes.append(r)
        except Exception as ex:
            raise ValidationError("Invalid statuscode({}).".format(s))
    return statuscodes


def _format_statuscodes(statuscodes):
    if not statuscodes:
        return ""

    if isinstance(statuscodes,(list,tuple)):
        return ",".join("{}-{}".format(s[0],s[1]) if isinstance(s,(list,tuple)) else str(s) for s in statuscodes)
    else:
        return statuscodes

def is_valid(response,statuscode=None,redirecturl=None):
    if not statuscode and not redirecturl :
        raise Exception("Both the parameter 'statuscode' and 'redirecturl' can't be empty at the same time.")
    
    if statuscode:
        if isinstance(statuscode,int):
            statuscode = [statuscode]
        passed = False
        for s in statuscode:
            if isinstance(s,(list,tuple)):
                if response.status_code >= s[0] and response.status_code <= s[1]:
                    passed = True
                    break
            else:
                if s == response.status_code:
                    passed = True
                    break
        if not passed:
            if response.status_code >= 400:
                return (False,"Status code({}) isn't in expected status codes({})".format(response.status_code,statuscode))
            else:
                return (False,"Status code({}) isn't in expected status codes({})".format(response.status_code,statuscode))
    elif response.status_code < 300 or response.status_code >=400:
        return (False,"Not a redirect response")


    if "Location" not in response.headers:
        return (False,"The header 'Location' doesn't exist")

    if redirecturl:
        url_re = re.compile(redirecturl)
        if url_re.search(response.headers["Location"]):
            return (True,"OK")
        else:
            return (False,"The redirect url({}) doesn't match the pattern({})".format(response.headers["Location"],redirecturl))

