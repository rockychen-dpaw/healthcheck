import json
from datetime import datetime,date,timedelta

from . import settings

class JSONFormater(json.JSONEncoder):
    """ Instead of letting the default encoder convert datetime to string,
        convert datetime objects into a dict, which can be decoded by the
        DateTimeDecoder
    """
        
    def default(self, obj):
        if isinstance(obj, datetime):
            if obj.tzinfo is not None and obj.tzinfo.utcoffset(obj) is not None and obj.tzinfo != settings.TZ:
                #convert to default timezone
                obj = obj.astimezone(settings.TZ)
                
            return obj.strftime("%Y-%m-%dT%H:%M:%S.%f")
        elif isinstance(obj, date):
            return obj.strftime(obj,"%Y-%m-%d")
        elif isinstance(obj, timedelta):
            return obj.total_seconds()
        else:
            return str(obj)

class JSONEncoder(json.JSONEncoder):
    """ Instead of letting the default encoder convert datetime to string,
        convert datetime objects into a dict, which can be decoded by the
        DateTimeDecoder
    """
        
    def default(self, obj):
        if isinstance(obj, datetime):
            return {
                '__type__' : 'datetime',
                'value' : obj.strftime("%Y-%m-%dT%H:%M:%S.%f")
            }   
        elif isinstance(obj, date):
            return {
                '__type__' : 'date',
                'value' : obj.strftime("%Y-%m-%d")
            }   
        elif isinstance(obj, timedelta):
            return {
                '__type__' : 'timedelta',
                'value' : obj.total_seconds()
            }   
        else:
            return super().default(obj)

class JSONDecoder(json.JSONDecoder):

    def __init__(self,*args, **kwargs):
        kwargs["object_hook"] = self.dict_to_object
        json.JSONDecoder.__init__(self, *args, **kwargs)
    
    def dict_to_object(self, d): 
        if '__type__' not in d:
            return d

        if d["__type__"] == "datetime":
            return datetime.strptime(d["value"],"%Y-%m-%dT%H:%M:%S.%f").astimezone(settings.TZ)
        elif d["__type__"] == "date":
            return datetime.strptime(d["value"],"%Y-%m-%d").astimezone(settings.TZ).date()
        elif d["__type__"] == "timedelta":
            return timedelta(d["value"])
        else:
            return d

