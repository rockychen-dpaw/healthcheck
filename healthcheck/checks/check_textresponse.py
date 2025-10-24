import logging
import re

from django import forms



logger = logging.getLogger(__name__)

name = "check_response_text"

def is_valid(response,pattern=None,case_sensitive=False):
    try:
        content = await response.textdata
    except:
        return (False,"Not text reponse")

    if case_sensitive:
        content_re = re.compile(pattern)
    else:
        content_re = re.compile(pattern,re.IGNORECASE)

    if content_re.search(content):
        return (True,"OK")
    else:
        return (False,"Not match the pattern({}) with {}".format(pattern,"case-sensitive" if case_sensitive else "case-insensitive"))

