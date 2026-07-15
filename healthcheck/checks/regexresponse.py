import logging
import re
from datetime import datetime


logger = logging.getLogger(__name__)


name = "regex"

def transform_factory(self,pattern_re,datatype):
    def _func():
        if self.__regex_value__ is None:
            m = pattern_re.search(self.text)
            if m:
                self.__regex_value__ =  m.groupdict()
                if datatype:
                    default_type = datatype.get("__default__")
                    for k in self.__regex_value__.keys():
                        t = datatype.get(k) or default_type
                        if not t:
                            continue
                        if t == "int":
                            self.__regex_value__[k] = int(self.__regex_value__[k])
                        elif t == "float":
                            self.__regex_value__[k] = float(self.__regex_value__[k])
                        elif t == "bool":
                            self.__regex_value__[k] = self.__regex_value__[k].lower() in ("true","yes","t","y")
                        elif t.startswith("datetime("):
                            self.__regex_value__[k] = datetime.strptime(self.__regex_value__[k],datatype[k][9:-1]).astimezone(settings.TZ)
                        elif t.startswith("date("):
                            self.__regex_value__[k] = datetime.strptime(self.__regex_value__[k],datatype[k][5:-1]).astimezone(settings.TZ).date()
            else:
                self.__regex_value__ = {}
        return self.__regex_value__

    return _func


def transform(res,pattern,ignorecase=None,multiline=None,dotmatchall=None,datatype={}):
    flags = 0
    if ignorecase == True:
        flags |= re.I
    if multiline == True:
        flags |= re.M
    if dotmatchall == True:
        flags |= re.S

    if flags == 0:
        pattern_re = re.compile(pattern)
    else:
        pattern_re = re.compile(pattern,flags)

    setattr(res,"__regex_value__",None)
    setattr(res,"__regex__", transform_factory(res,pattern_re,datatype))
    return res

def get_value(res,key=None):
    """
    key: a list of tuple [True,group]
    """
    if key:
       return res.__regex__().get(key[0][1])
    else:
       return res.__regex__()


