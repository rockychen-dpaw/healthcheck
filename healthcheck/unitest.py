import sys
import traceback
import json
import os
from datetime import datetime,timedelta

from . import checks
from . import settings
from .serializers import JSONFormater

from .response import TestResponse
from . import settings
from .healthcheck import HealthCheck

if __name__ == '__main__':
    if len(sys.argv) > 1:
        jsonfile = sys.argv[1]
    else:
        jsonfile = os.environ.get("HALTHCHECK_CONFIG_FILE")
    if not jsonfile:
        jsonfile = os.path.join(settings.HOME_DIR,"unitests.json")

    if not os.path.exists(jsonfile):
        raise Exception("The json file '{}' doesn't exist.".format(jsonfile))

    with open(jsonfile) as f:
        testdata = json.loads(f.read())
    for testcase,resdata,configs in testdata:
        print("==============================================================================")
        print("Test Case : {}".format(testcase))
        healthcheck = HealthCheck(configs)
    
        if not healthcheck.sections:
            print("All healthcheck sections are skipped.")
            continue
    
        #print("The intialized healthcheck configuration is\n{}".format(json.dumps(configs,indent=4,cls=JSONFormater)))
    
        now = datetime.now().astimezone(settings.TZ)
        add20 = now + timedelta(minutes=20)
        minus20 = now - timedelta(minutes=20)
        if resdata.get("data"):
            if isinstance(resdata["data"],dict):
                resdata["data"]["now"] = now.isoformat()
                resdata["data"]["add20"] = add20.isoformat()
                resdata["data"]["minus20"] = minus20.isoformat()
        res = TestResponse(resdata.get("status_code",200),data=resdata.get("data"),headers=resdata.get("headers"))

        print("Response: status code = {}{}{}".format(
            res.status_code,
            "\n    Headers:\n        ".format("\n        ".join("{}={}".format(key,value) for key,value in res.headers.items())) if res.headers else "",
            ("\n---------------------------\n{}".format( json.dumps(res.jsondata,indent=4)  if res.jsondata else res.data )) if res.data else {}
        ))
    
        for o in healthcheck.sections.values():
            sectionconfig = o
            break
        for o in sectionconfig["services"].values():
            serviceconfig = o
            break
        healthstatus = healthcheck.check_response(serviceconfig,res)
        

