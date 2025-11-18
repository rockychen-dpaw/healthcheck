import traceback
import logging
import os
import re
from datetime import datetime,timedelta,date,time
from .. import settings


from .base import datanotfound
from . import httpstatus,jsonresponse,textresponse,httpheaders,redirect
from .. import utils

TZ = settings.TZ

logger = logging.getLogger(__name__)

modules = dict([(mod.name,mod) for mod in [httpstatus,jsonresponse,textresponse,httpheaders,redirect] ])

relativedate_re = re.compile("^\\s*(\\+|\\-)?(\\s*[0-9]+\\s*(days?|hours?|mins?|minutes?|seconds?))+\\s*$")
flags_re = re.compile("(?P<flag>\\+|\\-)")
days_re = re.compile("(?P<days>[0-9]+)\\s*days?")
hours_re = re.compile("(?P<hours>[0-9]+)\\s*hours?")
minutes_re = re.compile("(?P<minutes>[0-9]+)\\s*(min|minute)s?")
seconds_re = re.compile("(?P<seconds>[0-9]+)\\s*seconds?")


def parse_checkingtime(checkingtime):
    if not checkingtime:
        return None
    else:
        if not isinstance(checkingtime,(list,tuple)):
            raise Exception("Checkingtime({}) should be a tuple(starttime,endtime) or a list of tuple(starttime,endtime)".format(checkingtime))
        elif isinstance(checkingtime,tuple):
            #convert tuple to list
            checkingtime = list(checkingtime)

        if isinstance(checkingtime[0],(list,tuple)):
            #checkingtime is a list of tuple(starttime,endtime)
            if any( t for t in checkingtime if not isinstance(t,(list,tuple)) or len(t) != 2):
                raise Exception("Checkingtime({}) should be a tuple(starttime,endtime) or a list of tuple(starttime,endtime)".format(checkingtime))

            #convert tuple to list 
            for i in range(len(checkingtime)):
                if isinstance(checkingtime[i],tuple):
                    checkingtime[i] = list(checkingtime[i])
        elif len(checkingtime) != 2:
            raise Exception("Checkingtime({}) should be a tuple(starttime,endtime) or a list of tuple(starttime,endtime)".format(checkingtime))
        else:
            #checkingtime is a tauple(starttime,endtime), convert to a list of tuple
            checkingtime = [checkingtime]

    previous_range = None
    for timerange in checkingtime:
        timerange.append(timerange[0])
        timerange.append(timerange[1])
        if timerange[0]:
            timerange[0] = utils.parse_time(timerange[0])
            timerange[0] = timerange[0].hour * 3600 + timerange[0].minute * 60 + timerange[0].second
        else:
            timerange[0] = 0

        if timerange[1]:
            timerange[1] = utils.parse_time(timerange[1])
            timerange[1] = timerange[1].hour * 3600 + timerange[1].minute * 60 + timerange[1].second
        else:
            timerange[1] = 86400

        if timerange[0] >= timerange[1]:
            raise Exception("Timerange({0},{1}),Startime({0}) should be less than endtime({1})".format(utils.format_time(timerange[2]),utils.format_time(timerange[3])))

        if previous_range:
            if previous_range[1] >= timerange[0]:
                raise Exception("The timerange({0},{1}) is overlapped with timerange({2},{3})".format(
                    utils.format_time(previous_range[2]),
                    utils.format_time(previous_range[3]),
                    utils.format_time(timerange[2]),
                    utils.format_time(timerange[3])
                ))
        previous_range = timerange

    if checkingtime and len(checkingtime) == 1 and checkingtime[0] == 0 and checkingtime[1] == 86400:
        #checking all day
        return None

    return checkingtime

def _convert_datatype(val,dt,params=None):
    """
    Convert the val to the desired data type
    """
    if val is None:
        return val
    elif val == datanotfound:
        return val
    elif dt is None:
        return val

    if isinstance(val,dt):
        #sort the list data, if ignore_order is True
        if dt == list and params and params.get("ignore_order",False):
            val.sort()
        elif dt == tuple and params and params.get("ignore_order",False):
            val = list(val)
            val.sort()

        return val

    if isinstance(val,(list,tuple)):
        #val is list type; convert each member to the desired dtype
        return [_convert_datatype(v,dt,params=params) for v in val]

    if dt == int:
        return int(val)
    elif dt == float:
        return float(val)
    elif dt == bool:
        if isinstance(val,str):
            return val.lower() in ("true","yes","on",'t','y')
        else:
            return bool(val)
    elif dt == dict:
        return val
    elif dt == re.Pattern:
        #find all the re flags
        flags = params.get("flags") if params else None
        if flags:
            flags = [f.strip().upper() for f in flags.split("|") if f.strip()]
            if flags:
                reflags = None
                for f in flags:
                    try:
                        if not reflags:
                            reflags = getattr(re,f)
                        else:
                            reflags |= getattr(re,f)
                    except:
                        continue
                if reflags:
                    return re.compile(val,reflags)

        return re.compile(val)
    elif dt in (date,datetime,timedelta):
        if relativedate_re.search(val):
            m = flags_re.search(val)
            if m:
                flag = 1 if m.group("flag") == '+' else -1
            else:
                flag = 1
            
            m = days_re.search(val)
            if m:
                days = int(m.group("days")) * flag
            else:
                days = 0
            
            m = hours_re.search(val)
            if m:
                hours = int(m.group("hours")) * flag
            else:
                hours = 0
            
            m = minutes_re.search(val)
            if m:
                minutes = int(m.group("minutes")) * flag
            else:
                minutes = 0
            
            m = seconds_re.search(val)
            if m:
                seconds = int(m.group("seconds")) * flag
            else:
                seconds = 0
            
            td = timedelta(days=days,hours=hours,minutes=minutes,seconds=seconds)
            if dt == datetime:
                return utils.now()  + td
            elif dt == date:
                return date.today()  + td
            else:
                return td
        else:
            if not params:
                if dt == date:
                    return date.fromisoformat(val)
                elif dt == datetime:
                    return date.fromisoformat(val).astimezone(tz=TZ)
                else:
                    try:
                        v = float(val)
                        return timedelta(seconds=v,microseconds=int((val - v) * 1000000))
                    except Exception as ex:
                        raise Exception("Failed to convert {} to timedelta.{}:{}".format(val,ex.__class__,str(ex)))
            elif isinstance(params,str):
                #params is the pattern
                if dt == date:
                    return datetime.strptime(val,params).date()
                elif dt == datetime:
                    return date.strptime(val,params).astimezone(tz=TZ)
                else:
                    raise Exception("Can't convert {} to timedelta with pattern({})".format(val,params))
            elif isinstance(params,dict):
                tz = ZoneInfo(params['tz']) if 'tz' in params else TZ
                if "pattern" in params:
                    if dt == date:
                        return datetime.strptime(val,params["pattern"]).date()
                    elif dt == datetime:
                        return datetime.strptime(val,params["pattern"]).astimezone(tz=TZ)
                    else:
                        raise Exception("Can't convert {} to timedelta with params({})".format(val,params))
                else:
                    if dt == date:
                        return date.fromisoformat(val)
                    elif dt == datetime:
                        return datetime.fromisoformat(val).astimezone(tz=TZ)
                    else:
                        raise Exception("Can't convert {} to timedelta with params({})".format(val,params))
            else:
                raise Exception("The configures of datetime type only support datetime pattern or dict object with key 'pattern','tz'")
    else:
        return str(val)

index_re = re.compile("\\[(?P<index>[0-9]+)\\]")
def _init_key(key):
    """
     convert the key to a list of  sublist with 2 members: [True for property; False for list index, property or index]
    """
    keys = [[True,prop.strip()] for prop in key.split(".")]
    for i in range(len(keys) - 1,-1,-1):
        prop = keys[i][1]
        begin = 0
        pos = i
        while True:
            m = index_re.search(prop,begin)
            if not m:
                break
            if begin == 0:
                keys[i][1] = prop[:m.start()]
            pos += 1
            keys.insert(pos,[False,int(m.group("index"))])
            begin = m.end()

    return keys

def _init_cond(cond):
    """
    cond: a single condition ["httpstatus",200]
    """
    if len(cond) < 2:
        raise Exception("The condition({}) is invalid.{}".format(cond,conds_help))

    if cond[0] not in modules:
        raise Exception("The data category({1}) in the condition({0}) doesn't exist.".format(cond,cond[0]))

    
    if cond[1] in ("and","or"):
        if len(cond) < 3:
            raise Exception("The condition({}) is invalid.logical operator({}) should have at least one logical expression.{}".format(cond,con[1],conds_help))
        newcond=[cond[1]]
        for i in range(2,len(cond),1):
            if isinstance(cond[i],(list,tuple)):
                newcond.append(_init_cond([cond[0],*cond[i]]))
            else:
                newcond.append(_init_cond([cond[0],"","==",cond[i]]))
        return newcond

    elif cond[1] == "not":
        if len(cond) != 3:
            raise Exception("The condition({}) is invalid.logical operator({}) only accept one logical expression.{}".format(cond,con[1],conds_help))
        newcond=[cond[1]]
        if isinstance(cond[2],(list,tuple)):
            newcond.append(_init_cond([cond[0],*cond[2]]))
        else:
            newcond.append(_init_cond([cond[0],"","==",cond[2]]))
        return newcond
    elif len(cond) == 5:
        pass
    elif isinstance(cond[1],str) and cond[1].strip().startswith("lambda "):
        """
        [data category,lambda expression]
        [data category,lambda expression,parameters]
        """
        if len(cond) == 2:
            cond.append(None)
        elif len(cond) > 3:
            raise Exception("The condition({}) is invalid.{}".format(conds,conds_help))
        cond.insert(1,None)
        cond.insert(2,"lambda")
    elif len(cond) >=3 and isinstance(cond[2],str) and cond[2].strip().startswith("lambda "):
        """
        [data category,key,lambda expression]
        [data category,key,lambda expression,parameters]
        """
        if len(cond) == 3:
            cond.append(None)
        elif len(cond) > 4:
            raise Exception("The condition({}) is invalid.{}".format(conds,conds_help))
        cond.insert(2,"lambda")
    elif cond[1] in operators:
        """
        [data category,operator,expected_value]
        [data category,operator,expected_value,parameters]
        """
        if len(cond) == 3:
            cond.append(None)
        elif len(cond) > 4:
            raise Exception("The condition({}) is invalid.{}".format(conds,conds_help))
        cond.insert(1,None)
    elif len(cond) >= 3 and isinstance(cond[2],str) and cond[2] in operators:
        """
        [data category,key,operator]
        [data category,key,operator,expected_value]
        [data category,key,operator,expected_value,parameters]
        """
        if len(cond) == 3:
            cond.append(None)
            cond.append(None)
        elif len(cond) == 4:
            cond.append(None)
        elif len(cond) > 5:
            raise Exception("The condition({}) is invalid.{}".format(cond,conds_help))
    elif len(cond) == 2:
        """
        [data category,expected_value]
        """
        cond.insert(1,None)
        cond.insert(2,"==")
        cond.append(None)
    elif len(cond) == 3 and isinstance(cond[1],str) and isinstance(cond[2],str):
        """
        [data category,key,expected_value]
        """
        cond.insert(2,"==")
        cond.append(None)
    elif len(cond) == 3  and isinstance(cond[2],dict):
        """
        [data category,expected_value,params]
        """
        cond.insert(1,None)
        cond.insert(2,"==")
    else:
        raise Exception("The condition({}) is invalid.{}".format(cond,conds_help))

    

    #validate the operands
    if cond[2] == "lambda":
        try:
            cond[3] = eval(cond[3])
        except Exception as ex:
            raise Exception("The lambda operation in conditon({}) is invalid.{}:{}".format(cond,ex.__class__.__name__,str(ex)))
    elif operators[cond[2]][0] == 0:
        if cond[3] is not None:
            raise Exception("The operator({1}) of the condition({0}) doesn't have any operands".format(cond,cond[2]))
    elif operators[cond[2]][0] == 1:
        if operators[cond[2]][1]:
            if cond[3] is None:
                raise Exception("The operator({1}) of the condition({0}) must have one operand".format(cond,cond[2]))
            elif isinstance(cond[3],(list,tuple,set,dict)):
                raise Exception("The operator({1}) of the condition({0}) only accept one primitive data as operand, but the configured operand is '{2}'".format(cond,cond[2],cond[3]))
    elif not isinstance(cond[3],(list,tuple)) or len(cond[3]) == 0:
        raise Exception("The operator({1}) of the condition({0}) should have at least one operands".format(cond,cond[2]))
    else:
        if any(isinstance(d,(list,tuple,dict,set)) for d in cond[3] ):
            raise Exception("The operator({1}) of the condition({0}) only accept list of primitive data as operand, but the configured operand is '{2}'".format(cond,cond[2],cond[3]))
        if operators[cond[2]][0] > 0 and len(cond[3]) != operators[cond[2]][0]:
            raise Exception("The operator({1}) of the condition({0}) must have {2} operands, but the configured operand is '{3}'".format(cond,cond[2],operators[cond[2]][0],cond[3]))

    if cond[1]:
        #convert the key to a list of  sublist with 2 members: [True for property; False for list index, property or index]
        cond.append("{}.{}".format(cond[0],cond[1]))
        cond[1] = _init_key(cond[1])
    else:
        cond.append(cond[0])


    if isinstance(cond[3],str) and cond[3].strip().startswith("lambda"):
        cond[3] =  eval(cond[3].strip())
    else:
        dt = None
        if cond[4]:
            dt = cond[4].get("dtype")
        if dt is None:
            if cond[2] in ("pattern","mpattern"):
                dt = re.Pattern
                if cond[2] == "pattern":
                    cond[3] = _convert_datatype(cond[3],dt,params=cond[4])
                else:
                    cond[3] = [_convert_datatype(p,dt,params=cond[4]) for p in cond[3]]
            elif cond[2] == "lambda":
                dt = "function"
            elif cond[3] is not None:
                if isinstance(cond[3],str) and relativedate_re.search(cond[3]):
                    dt = datetime
                elif isinstance(cond[3],(list,tuple)) and len(cond[3]) > 0:
                    dt = cond[3][0].__class__
                else:
                    dt = cond[3].__class__
            else:
                dt = None
            if cond[4] is None:
                cond[4] = {"dtype":dt}
            else:
                cond[4]["dtype"] = dt
        else:
            #convert the dtype to data type class object
            cond[4]["dtype"] = eval(dt)


    return cond

conds_help="""
A valid condition have the following formats:
    [data category,lambda expression]: the data category only  has single data or means the whole data. validate the data with lambda expression . no parameters
    [data category,lambda expression,parameters]: the data category only  has single data or means the whole data. validate the data with lambda expression. parameters is dict object
    [data category,key,lambda expression]: validate the data with lambda expression . no parameters
    [data category,key,lambda expression,parameters]: validate the data with lambda expression. parameters is dict object

    [data category,expected_value]: the data category only  has single data or means the whole data. operator is '=='. no parameters
    [data category,expected_value,parameters]: the data category only  has single data or means the whole data. operator is '=='. parameters is dict object
    [data category,key,expected_value]: the data category only  has single data or means the whole data. operator is '=='. no parameters

    [data category,operator,expected_value]: the data category only  has single data or means the whole data. no parameters
    [data category,operator,expected_value,parameters]: the data category only  has single data or means the whole data. parameters is a dict object

    [data category,key,operator,expected_value]: the data category is a complx object, the condition is applied on the propertis of the object. no parameters
    [data category,key,operator,expected_value,parameters]: the data category is a complx object, the condition is applied on the propertis of the object. parameters is a dict object
    [data category,'and',[],[],...]: a logical 'and' which all conditions are applied on this data category
    [data category,'or',[],[],...]: a logical 'or' which all conditions are applied on this data category
    [data category,'not',[],[],...]: a logical 'not' which condition are applied on this data category

    ['and',[],[],...]: logical and 
    ['or',[],[],...]: logical or
    ['not',[]]: logical not
"""
def init_conds(conds):
    if not conds or not isinstance(conds,(list,tuple)):
        #no condition, always True
        return []

    #if conds multi dimension array,and the length of outer dimension  is 1, remove the outer dimension,
    #continue the process, until the list type which length is greater than 1
    if len(conds) == 1:
        raise Exception("The condition({}) is invalid.{}".format(conds,conds_help))

    if conds[0] in ("and","or"):
        if len(conds) < 2:
            raise Exception("The condition({}) is invalid, missing logical expressions of the logical operator({})".format(conds,conds[0]))
        elif any(not isinstance(cond,(list,tuple)) for cond in conds[1:]):
            raise Exception("The condition({}) is invalid, The logical expressions of the logical operator({}) must be type list or tuple).{}".format(conds,conds_help))
        for i in range(1,len(conds),1):
            conds[i] = init_conds(conds[i])
        return conds
    elif conds[0] == "not":
        if len(conds) != 2:
            raise Exception("The condition({}) is invalid, the logical operator({}) only accept one logical expression.{}".format(conds,conds[0],conds_help))
        elif not isinstance(conds[1],(list,tuple)):
            raise Exception("The condition({}) is invalid, The logical expression of the logical operator({}) must be type list or tuple).{}".format(conds,conds_help))
        conds[1] = init_conds(conds[1])
        return conds
    else:
        return _init_cond(conds)

operators = {
    "exists":(0,True), #(the number of operands, True means the individual operand only accept primitive data; false means the individual operand can be primitive data or compound data) 
    "exist":(0,True),
    "not_exists":(0,True),
    "not_exist":(0,True),
    "is_null":(0,True),
    "is_not_null":(0,True),
    "==":(1,False),
    "=":(1,False),
    ">":(1,True),
    ">=":(1,True),
    "<":(1,True),
    "<=":(1,True),
    "!=":(1,False),
    "<>":(1,False),
    "between":(2,True),
    "in":(-1,True),
    "not_in":(-1,True),
    "startswith":(1,True),
    "mstartswith":(-1,True),
    "endswith":(1,True),
    "mendswith":(-1,True),
    "contain":(1,True),
    "mcontain":(-1,True),
    "pattern":(1,True),
    "mpattern":(-1,True)
}
def _check_cond(val,operator,expected_val=None,params=None):
    if params:
        dt = params.get("dtype")

    if dt and dt != re.Pattern and dt != "function":
        val = _convert_datatype(val,dt,params=params)
    if operator not in ("lambda","pattern"):
        expected_val = _convert_datatype(expected_val,dt,params=params)

    if  operator == "lambda":
        return expected_val(val)
    elif operator in ("exists","exist"):
        return val != datanotfound
    elif operator in ("not_exists","not_exist"):
        return val == datanotfound
    elif operator == "is_null":
        if val == datanotfound:
            return True
        else:
            return val is None
    elif operator == "is_not_null":
        if val == datanotfound:
            return False
        else:
            return val is not None
    elif val == datanotfound or val is None:
        return False
    elif operator in ("==","="):
        return val == expected_val
    elif operator in ("!=","<>"):
        return val != expected_val
    elif operator == "<":
        return val < expected_val
    elif operator == "<=":
        return val <= expected_val
    elif operator == ">":
        return val > expected_val
    elif operator == ">=":
        return val >= expected_val
    elif operator == "between":
        return val >= expected_val[0] and val < expected_val[1]
    elif operator == "in":
        return val in expected_val
    elif operator == "not_in":
        return val not in expected_val
    elif operator == "startswith":
        return val.startswith(expected_val)
    elif operator == "mstartswith":
        return any(val.startswith(v) for v in expected_val)
    elif operator == "endswith":
        return val.endswith(expected_val)
    elif operator == "mendswith":
        return any(val.endswith(v) for v in expected_val)
    elif operator == "pattern":
        return True if expected_val.search(val) else False
    elif operator == "mpattern":
        return any(True if v.search(val) else False for v in expected_val)
    elif operator == "contain":
        return expected_val in val
    elif operator == "mcontain":
        return any(v in val for v in expected_val)
    else:
        raise Exception("The operation({} {} {}) with data type({}) Not Support".format(val,operator,expected_val,dt))

def _get_value(mod,res,key=None):
    try:
        if key:
            return mod.get_value(res,key)
        else:
            return mod.get_value(res)
    except KeyError as ex:
        return datanotfound
    except IndexError as ex:
        return datanotfound

def _cond_and(res,conds,messages = None):
    for cond in conds:
        if not check(res,cond,messages = messages):
            return False

    return True

def _cond_or(res,conds,messages = None):
    for cond in conds:
        if check(res,cond,messages = messages):
            return True

    return False

def _cond_not(res,conds,messages = None):
    return not check(res,conds,messages = messages)

def check(res,conds,messages=None):
    valid = None
    if not conds:
        return True
    elif conds[0] == "and":
        return _cond_and(res,conds[1:],messages = messages)
    elif conds[0] == "or":
        return _cond_or(res,conds[1:],messages = messages)
    elif conds[0] == "not":
        return _cond_not(res,conds[1:],messages = messages)
    else:
        val = _get_value(modules[conds[0]],res,key=conds[1])
        checkresult = _check_cond(val,conds[2],conds[3],conds[4])
        if messages is not None:
            if conds[2] == "lambda":
                messages.append("{} : lambda({}({}))".format("True " if checkresult else "False",conds[5],val))
            elif operators[conds[2]][0] == 0:
                messages.append("{} : {}({}) {}".format("True " if checkresult else "False",conds[5],val,conds[2]))
            else:
                messages.append("{} : {}({}) {} {}".format("True " if checkresult else "False",conds[5],val,conds[2],conds[3]))
        return checkresult

get_message_help = """Only support the following retrieving message configurations
1. constant message string
2. lambda express with parameter response
3. [data category, lambda expression]
4. [data category, keys]
5. [data category, keys, lambda expression]
6. [pattern,[],...]"""
def _get_value_factory(config):
    f_get_value = getattr(modules[config[0]],"get_value")
    _f = None
    if len(config) < 2:
        _f = None
        params = None
    elif len(config) == 2:
        if config[1].startswith("lambda"):
            _f = eval(config[1])
            params = None
        else:
            _f = None
            params = _init_key(config[1])
    elif len(config) == 3:
        params =_init_key(config[1])
        if config[2].startswith("lambda"):
            _f = eval(config[2])
        else:
            raise Exception(get_message_help)
    else:
        raise Exception(get_message_help)

    def _func(res):
        try:
            if params:
                data = f_get_value(res,params)
            else:
                data = f_get_value(res)
            return _f(data) if _f else data
        except Exception as ex:
            return "N/A"
        
    return _func

def _format_message_factory(config):
    pattern = config[0]
    f_params = []
    for c in config[1:]:
        f_params.append(get_message_factory(c))

    def _func1(res):
        return pattern.format(*[f_param(res) for f_param in f_params ])

    def _func2(res):
        return pattern
    return _func1 if f_params else _func2

def get_message_factory(config):
    if not config:
        def _func(res):
            if res.status_code >=200 and res.status_code < 300:
                return "OK"
            else:
                return res.text
        return _func

    if isinstance(config,str):
        if config.startswith("lambda"):
            return eval(config)
        else:
            config = [config]
    elif not isinstance(config,(tuple,list)):
        raise Exception("Healthcheck message parameters should be string or list type")

    if config[0] in modules:
        #single message,
        return _get_value_factory(config)
    else:
        #message pattern
        return _format_message_factory(config)

