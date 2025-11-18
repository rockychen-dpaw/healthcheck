import json

class TestResponse(object):
    jsondata = None
    def __init__(self,status_code,data=None,headers=None):
        self.status_code = status_code
        self.headers = headers
        self.data = data
        if isinstance(self.data,str):
            self.jsondata = json.loads(self.data)
        elif isinstance(self.data,dict):
            self.jsondata = self.data


    def json(self):
        if self.jsondata:
            return self.jsondata
        else:
            raise Exception("Invalid json data")
