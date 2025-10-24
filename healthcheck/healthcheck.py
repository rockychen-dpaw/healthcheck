import sys
import hashlib
import shutil
import traceback
import inspect
import asyncio
import json
import os
import time
import logging
import httpx
#import urllib3
from datetime import datetime,timedelta
from collections import UserDict,OrderedDict

from . import checks
from . import settings

from . import exceptions
from . import settings
from . import utils
from . import serializers
from . import shutdown
from .locks import FileLock

logger = logging.getLogger("healthcheck.healthcheck")

#urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BaseServiceHealthCheckTask(object):
    def __init__(self,servicehealthcheck):
        self.servicehealthcheck = servicehealthcheck

    async def post_healthcheck(self,healthstatus):
        print(str(healthstatus))
        logger.debug("Health Check({0}.{1}) : {4}{6}  Running from {2} to {3}. {5}".format(
            healthstatus[0][0],
            healthstatus[0][1],
            healthstatus[1][1][0].strftime("%Y-%m-%d %H:%M:%S.%f"),
            healthstatus[1][1][1].strftime("%Y-%m-%d %H:%M:%S.%f"),
            healthstatus[1][1][2],
            healthstatus[1][1][3],
            "(Details Avaiable)" if healthstatus[1][1][4] else "(Detail Not Available)"
        ))
        pass

    async def run(self):
        starttime = datetime.now().astimezone(settings.TZ)
        res = None
        try:
            try:
                res = None
                data = None
                logger.debug("{} : Start to run the healthcheck task({})".format(self.servicehealthcheck,self.__class__.__name__))
                async with httpx.AsyncClient(auth=self.servicehealthcheck.auth,timeout=self.servicehealthcheck.timeout,verify=self.servicehealthcheck.sslverify,headers=self.servicehealthcheck.headers) as client:
                    if self.servicehealthcheck.method == "GET":
                        func = client.get
                    elif self.servicehealthcheck.method == "POST":
                        func = client.post
                        data = self.servicehealthcheck.formdata
                    elif self.servicehealthcheck.method == "PUT":
                        func = client.put
                        data = self.servicehealthcheck.formdata
                    elif self.servicehealthcheck.method == "DELETE":
                        func = client.delete
                    else:
                        #Not support
                        raise Exception("Http method({}) Not Support".format(self.method))
                    if data:
                        res = await func(self.servicehealthcheck.url,data=data)
                    else:
                        res = await func(self.servicehealthcheck.url)
            finally:
                endtime = datetime.now().astimezone(settings.TZ)

            healthstatus = HealthCheck.check_response(self.servicehealthcheck,res)
        except Exception as ex:
            healthstatus = ["error","{} : {}".format(ex.__class__.__name__,str(ex))]

        healthstatus.insert(0,starttime)
        healthstatus.insert(1,endtime)
        
        healthstatus.append(healthstatus[2] in self.servicehealthcheck.healthdetailpersistent)
        self.servicehealthcheck["healthstatus"][1] = healthstatus

        try:
            self.servicehealthcheck.update_checkingstatusindex(healthstatus,res)
        except Exception as ex:
            logger.error("Failed to update the healthcheck status index({2}) of service({0}.{1}). {3}".format(self.servicehealthcheck.sectionid,self.servicehealthcheck.serviceid,healthstatus,str(ex)))
        if healthstatus[-1]:
            try:
                await self.servicehealthcheck.save_checkingstatus(healthstatus,res)
            except Exception as ex:
                logger.error("Failed to save the healthcheck status details({2}) of service({0}.{1}). {3}".format(self.servicehealthcheck.sectionid,self.servicehealthcheck.serviceid,healthstatus,str(ex)))

        if inspect.iscoroutinefunction(self.post_healthcheck):
            await self.post_healthcheck([[self.servicehealthcheck.sectionid,self.servicehealthcheck.serviceid],[self.servicehealthcheck["healthstatus"][0],healthstatus]])
        else:
            self.post_healthcheck([[self.servicehealthcheck.sectionid,self.servicehealthcheck.serviceid],[self.servicehealthcheck["healthstatus"][0],healthstatus]])


class SectionHealthCheck(UserDict):

    @property
    def sectionid(self):
        return self["id"]

    @property
    def servicelist(self):
        return self["services"].values()

class ServiceHealthCheck(UserDict):
    def __init__(self,healthcheck,data):
        super().__init__(data)
        self.healthcheck = healthcheck
        self.next_history_management_time = None


    def __str__(self):
        return "{}.{}.{}".format(self.healthcheck,self.sectionid,self.serviceid)

    @property
    def sectionid(self):
        return self['section']["id"]

    @property
    def serviceid(self):
        return self['id']

    @property
    def method(self):
        return self['method']

    @property
    def url(self):
        return self['location']

    @property
    def headers(self):
        return self.get("headers")

    _auth = None
    @property
    def auth(self):
        if not self._auth:
            if self.get("user"):
                self._auth = (self["user"],self.get("password"))
            else:
                return None

        return self._auth

    @property
    def timeout(self):
        return self.get("timeout")

    @property
    def sslverify(self):
        return self["sslverify"]

    @property
    def interval(self):
        return self["interval"]

    @property
    def formdata(self):
        """
        Return the request data
        """
        return self.get("data")

    @property
    def healthstatus_nextcheck(self):
        status = self.healthstatus
        return status[0].strftime("%Y-%m-%d %H:%M:%S") if status else ""

    @property
    def healthstatus_name(self):
        status = self.healthstatus
        return status[1][2] if status and status[1] else ""

    @property
    def healthstatus_info(self):
        status = self.healthstatus
        return status[1][3] if status and status[1] else ""

    @property
    def healthstatus_persistent(self):
        status = self.healthstatus
        return status[1][4] if status and status[1] else ""

    @property
    def healthstatus_message(self):
        status = self.healthstatus
        if not status or not status[1]:
            return ""

        return """Health Status : {}
Check Start Time : {}
Check End Time : {}
Health Status Message : {}
Next Check Time : {}
""".format(self.healthstatus_name,
           self.healthstatus_checkstart,
           self.healthstatus_checkend,
           self.healthstatus_info,
           self.healthstatus_nextcheck
    )

    @property
    def healthstatus_alertmessage(self):
        return self.healthstatus_message.replace("\n","\\n")
        
    @property
    def healthstatus_checkstart(self):
        status = self.healthstatus
        return status[1][0].strftime("%Y-%m-%d %H:%M:%S.%f") if status and status[1] else ""

    @property
    def healthstatus_checkend(self):
        status = self.healthstatus
        return status[1][1].strftime("%Y-%m-%d %H:%M:%S.%f") if status and status[1] else ""

    _folder = None
    @property
    def checkingstatusdir(self):
        if not self._folder:
            folder = os.path.join(settings.HEALTHCHECK_DATA_DIR,os.path.splitext(os.path.basename(self.healthcheck.configfile))[0],self.sectionid,self.serviceid)
            if not os.path.exists(folder):
                os.makedirs(folder)
            self._folder = folder

        return self._folder

    @property
    def historyexpire(self):
        return self["historyexpire"]

    @property
    def historyenabled(self):
        return self.historyexpire > 0

    @property
    def earliest_healthstatus(self):
        return self.get("earliest_healthstatus")

    @earliest_healthstatus.setter
    def earliest_healthstatus(self,val):
        self["earliest_healthstatus"] = val

    @property
    def healthstatus(self):
        """
        return healthstatus [next checktime,[starttime,endtime,health status,health status message,health checking persistent?]] 
        """
        return self.get("healthstatus")

    @healthstatus.setter
    def healthstatus(self,val):
        self["healthstatus"] = val

    @property
    def healthdetailpersistent(self):
        return self["healthdetailpersistent"]

    @property
    def checkingstatusindexfile(self):
        return os.path.join(self.checkingstatusdir,"checkingstatusindex.json")

    def checkingstatusfile(self,healthstatus):
        return os.path.join(self.checkingstatusdir,"{}.json".format(healthstatus[0].strftime("%Y%m%dT%H%M%S")))

    def update_checkingstatusindex(self,healthstatus,res):
        if self.historyexpire == 0:
            #history feature is disabled
            #remove the previous checking status file if have
            if self.earliest_healthstatus and self.earliest_healthstatus[-1]:
                utils.remove_file(self.checkingstatusfile(self.earliest_healthstatus))
            with open(self.checkingstatusindexfile,'w') as f:
                f.write(json.dumps(healthstatus,cls=serializers.JSONEncoder))
        else:
            now = datetime.now().astimezone(settings.TZ)
            if self.next_history_management_time and now < self.next_history_management_time:
                manage_history = False
            else :
                manage_history = True
                if self.next_history_management_time:
                    self.next_history_management_time += timedelta(days=1)
                else:
                    self.next_history_management_time = datetime(now.year,now.month,now.day).astimezone(settings.TZ) + timedelta(days=1)


            if manage_history:
                ealiest_checkingstatustime = datetime(now.year,now.month,now.day).astimezone(settings.TZ)
                if self.historyexpire > 1:
                    ealiest_checkingstatustime -= timedelta(days=self.historyexpire - 1)

                if self.earliest_healthstatus and self.earliest_healthstatus[0] < ealiest_checkingstatustime:
                    #some history data is expired
                    firstline = True
                    line = None
                    with open("{}.tmp".format(self.checkingstatusindexfile),'w') as f1:
                        #manage the history checking status
                        with open(self.checkingstatusindexfile) as f:
                            while True:
                                try:
                                    line = f.readline()
                                    if not line:
                                        break
                                    line = line.strip()
                                    if not line:
                                        continue

                                    if firstline:
                                        historycheckingstatus = json.loads(line,cls=serializers.JSONDecoder)
                                        if historycheckingstatus[0] < ealiest_checkingstatustime:
                                            #expired
                                            if historycheckingstatus[-1]:
                                               utils.remove_file(self.checkingstatusfile(historycheckingstatus))
                                        else:
                                            #not expired
                                            self.earliest_healthstatus = historycheckingstatus
                                            firstline = False
                                            f1.write(line)
                                    else:
                                        f1.write(os.linesep)
                                        f1.write(line)
                                except Exception as ex:
                                    logger.error("{}: Failed to update the healthstatus index data({}).{}".format(self,line,str(ex)))
                                    continue
                        #write the new checking status
                        if firstline:
                            self.earliest_healthstatus = healthstatus
                            firstline = False
                        else:
                            f1.write(os.linesep)
                        f1.write(json.dumps(healthstatus,cls=serializers.JSONEncoder))
                        #replace the checking status index file with new file
                        os.rename("{}.tmp".format(self.checkingstatusindexfile),self.checkingstatusindexfile)
                else:
                    manage_history = False

            if not manage_history:
                #no need to manage the history file
                with open(self.checkingstatusindexfile,'a') as f:
                    if self.earliest_healthstatus :
                        #history status exists
                        f.write(os.linesep)
                    f.write(json.dumps(healthstatus,cls=serializers.JSONEncoder))

            if not self.earliest_healthstatus:
                self.earliest_healthstatus = healthstatus

    def load_checkinghistory(self):
        file = self.checkingstatusindexfile
        latest_checkingstatus = None
        if os.path.exists(file):
            firstline = True
            latest_checkingstatus = None
            line = None
            with open(file) as f:
                while True:
                    try:
                        line = f.readline()
                        if not line:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        historycheckingstatus = json.loads(line,cls=serializers.JSONDecoder)
                        if firstline:
                            firstline = False
                            self.earliest_healthstatus = historycheckingstatus
                        latest_checkingstatus = historycheckingstatus
                    except Exception as ex:
                        logger.error("{}: Failed to parse the healthstatus index data({}).{}".format(self,line,str(ex)))
                        continue

        now = datetime.now().astimezone(settings.TZ)
        today = datetime(year = now.year,month=now.month,day=now.day).astimezone(settings.TZ)
        tomorrow = today + timedelta(days=1)
        seconds_in_day = int((now - today).total_seconds())

        next_checkingtime = today + timedelta(seconds=seconds_in_day - (seconds_in_day % self.interval))
        if latest_checkingstatus and next_checkingtime <= latest_checkingstatus[0]:
            next_checkingtime += timedelta(seconds=self.interval)
            if next_checkingtime >= tomorrow:
                self["healthstatus"] = [tomorrow,latest_checkingstatus] #[next checking time,[latest checking starttime ,endtime,health status,msg]]
            else:
                self["healthstatus"] = [next_checkingtime,latest_checkingstatus] 
        else:
            self["healthstatus"] = [next_checkingtime,latest_checkingstatus] 
                             
    def get_checkingdetails(self,healthstatus=None):
        if not healthstatus:
            healthstatus = self.healthstatus

        if healthstatus:
            file = self.checkingstatusfile(healthstatus)
            if os.path.exists(file):
                with open(self.checkingstatusfile(healthstatus)) as f:
                    return json.loads(f.read(),cls=serializers.JSONEncoder)
            else:
                return None
        else:
            return None

    async def save_checkingstatus(self,healthstatus,res):
        details = {
            "request": {
                "url": self.url,
                "method": self.method,
                "sslverify" :self.sslverify
            },
            "healthstatus":healthstatus,
        }
        if self.headers:
            details["request"]["headers"] = self.headers

        if self.timeout:
            details["request"]["timeout"] = self.timeout

        if self.method in ("POST","PUT"):
            details["request"]["data"] = self.formdata

        if res:
            try:
                content_type = res.headers.get("Content-Type")
                if "json" in content_type:
                    body = res.json()
                elif any(key in content_type for key in ("text","html","xml")):
                    body = res.text()
                else:
                    body = "Non text repsonse"
            except Exception as ex:
                body = "Failed to get body.{}: {}".format(ex.__class__.__name__,str(ex))
            details["response"] = {
                "status_code" :  res.status_code,
                "headers": [],
                "body": body
            }
            for name,val in res.headers.items():
                if name.lower() in ("connection","server","x-frame-options","x-content-type-options","access-control-allow-methods","content-encoding","accept-ranges","date","via","vary","transfer-encoding"):
                    continue
                details["response"]["headers"].append([name,val])

        file = self.checkingstatusfile(healthstatus)
        with open(file,"w") as f:
            f.write(json.dumps(details,indent=4,cls=serializers.JSONEncoder))

class HealthCheck(object):
    configfile = None
    _checkingstatus_loaded = False
    def __init__(self,configfile=settings.HEALTHCHECK_CONFIG_FILE):
        """
        configs : a json file or list object
        """
        self.config_hashcode = None
        self.sections = None
        self.configfile = configfile
        self._continuous_check_task = None
        self.load_configs()

    def __str__(self):
        return "{}({})".format(self.__class__.__name__,self.configfile)


    @property
    def sectionlist(self):
        return self.sections.values() if self.sections else []

    def get_service(self,section,service):
        return self.sections.get(section,{}).get("services",{}).get(service)

    def reload(self):
        """
        Reload the configuration 
        """
        sections = self.sections
        changed = self.load_configs()
        if not changed:
            return False

        now = datetime.now().astimezone(settings.TZ)
        today = datetime(year = now.year,month=now.month,day=now.day).astimezone(settings.TZ)
        tomorrow = today + timedelta(days=1)
        seconds_in_day = int((now - today).total_seconds())
        for section in self.sectionlist:
            for service in section.servicelist:
                existing_service = sections.get(section.sectionid,{}).get("services",{}).get(service.serviceid)
                next_checkingtime = today + timedelta(seconds=seconds_in_day - (seconds_in_day % service.interval))
                if existing_service:
                    service.healthstatus = existing_service.healthstatus
                    if service.healthstatus[0] < next_checkingtime:
                        service.healthstatus[0] = next_checkingtime
                    else:
                        service.healthstatus[0] = next_checkingtime + timedelta(seconds=service.interval)
                else:
                    service.healthstatus = [next_checkingtime,None] 

        return True


    def load_configs(self,force=False):
        """
        Return True if loaded; False if not changed.

        """
        if not self.configfile:
            raise Exception("The configuration is not loaded from a json file, no need to load")
        if not os.path.exists(self.configfile):
            raise Exception("The config file({}) doesn't exist".format(self.configfile))
        try:
            logger.debug("Begin to load health check configurations({})".format(self.configfile))
            with open(self.configfile,'rb') as f:
                configs = f.read()
            config_hashcode = hashlib.sha256(configs).hexdigest()
            if not force and config_hashcode == self.config_hashcode:
                return False

            self.config_hashcode = config_hashcode
            self.sections,errors = self.init_configs(json.loads(configs.decode()))
            if errors:
                logger.warning("""Found {1} issues in healthcheck configuration file({0})
    {2}
""".format(self.configfile,len(errors),"\n    ".join(errors)))

            return True
        except Exception as ex:
            raise Exception("The config file({}) is an invalid jason file. {} : {}".format(self.configfile,ex.__class__.__name__,str(ex)))

    def load_checkingstatus(self):
        logger.debug("Begin to load health checking status")
        for section in self.sections.values():
            for service in section["services"].values():
                service.load_checkinghistory()
        self._checkingstatus_loaded = True


    def init_configs(self,configs):
        #initialize the configs
        now = datetime.now().astimezone(settings.TZ)
        today = datetime(year = now.year,month=now.month,day=now.day).astimezone(settings.TZ)
        tomorrow = today + timedelta(days=1)
        seconds_in_day = int((now - today).total_seconds())
        if not configs:
            return {}
        
        if not isinstance(configs,(list,tuple)):
            raise Exception("Healthcheck configurations should be a list object.{}".format(configs))

        sections = OrderedDict()

        errors = []

        sectionindex = 0
        for config in configs:
            sectionindex += 1
            sectionid = config.get("id")
            if not sectionid:
                errors.append("Section {}: Missing property(id)".format(sectionindex))
                continue
            
            if not config.get("services"):
                errors.append("Section {}({}): No services are configured".format(sectionindex,sectionid))
                continue
            baseurl = config.get("baseurl")
            baseurl = baseurl.strip() if baseurl else None
            if baseurl and baseurl.endswith("/"):
                baseurl = baseurl[:-1]
            if baseurl:
                config["baseurl"] = baseurl
    
            try:
                baseinterval = config.get("interval")
                if baseinterval and not isinstance(baseinterval,int):
                    baseinterval = int(str(baseinterval).strip())
                    config["interval"] = baseinterval
            except Exception as ex:
                errors.append("Section {}({}): The interval({}) is not an integer.".format(sectionindex,sectionid,config.get("interval")))
                continue
    
            try:
                basetimeout = config.get("timeout")
                if basetimeout is not None and not isinstance(basetimeout,int):
                    basetimeout = int(str(basetimeout).strip())
                    config["timeout"] = basetimeout
                config["timeout"] = basetimeout
            except Exception as ex:
                errors.append("Section {}({}): The timeout({}) is not an integer.".format(sectionindex,sectionid,config.get("timeout")))
                continue

            try:
                basehistoryexpire = config.get("historyexpire")
                if basehistoryexpire is not None and not isinstance(basethistoryexpire,int):
                    basethistoryexpire = int(str(basethistoryexpire).strip())
                else:
                    basehistoryexpire = 0
    
                if basehistoryexpire < 0:
                    basehistoryexpire = 0
            except Exception as ex:
                errors.append("Section {}({}): The historyexpire({}) is not an integer.".format(sectionindex,sectionid,config.get("historyexpire")))
                continue

            config["historyexpire"] = basehistoryexpire

            basehealthdetailpersistent = config.get("healthdetailpersistent")
            if basehealthdetailpersistent:
                if isinstance(basehealthdetailpersistent,str) and basehealthdetailpersistent == "__all__":
                    basehealthdetailpersistent = set(["green","yellow","red","error"])
                else:
                    if isinstance(basehealthdetailpersistent,str):
                        basehealthdetailpersistent = [s for s in basehealthdetailpersistent.split(",")]
                    data = set()
                    for s in basehealthdetailpersistent:
                        s = s.strip().lower()
                        if not s:
                            continue
                        if s not in ["green","yellow","red","error"]:
                            errors.append("Section {}({}): The health status({}) in property('healthdetailpersistent') doesn't' support".format(sectionindex,sectionid,s))
                        else:
                            data.add(s)
                    basehealthdetailpersistent = data
            else:
                basehealthdetailpersistent = set(["yellow","red","error"])
            config["healthdetailpersistent"] = basehealthdetailpersistent


            if "sslverify" not in config:
                config["sslverify"] = True
            elif not isinstance(config["sslverify"],bool):
                config["sslverify"] = str(config["sslverify"]).lower() == "true"
    
            if not config.get("name"):
                config["name"] = sectionid

            if not config.get("services"):
                errors.append("Section {}({}): No service are configured".format(sectionindex,sectionid))
                continue

            services = OrderedDict()
            serviceindex = 0
            for service in config["services"]:
                serviceindex += 1
                serviceid = service.get("id")
                if not serviceid:
                    errors.append("Service {0}({1}).{2}: Missing property(id)".format(sectionindex,sectionid,serviceindex))
                    continue

                location = service.get("location")
                location = location.strip() if location else None
                if not location and not baseurl:
                    errors.append("Service {0}({1}).{2}({3}): Missing property(location)".format(sectionindex,sectionid,serviceindex,serviceid))
                    continue
                elif not location:
                    location = baseurl
                elif not location.startswith("http"):
                    if baseurl:
                        if location.startswith("/"):
                            location = "{}{}".format(baseurl,location)
                        else:
                            location = "{}/{}".format(baseurl,location)
                    else:
                        errors.append("Service {0}({1}).{2}({3}): Location({4}) is not a valid http url".format(sectionindex,sectionid,serviceindex,serviceid,location))
                        continue
                service["location"] = location

                if not service.get("healthchecks"):
                    errors.append("Service {0}({1}).{2}({3}): Missing healthcheck configuration".format(sectionindex,sectionid,serviceindex,serviceid))
                    continue
                
                if not isinstance(service["healthchecks"],dict):
                    errors.append("Service {0}({1}).{2}({3}): Healthcheck is not a dictionary object".format(sectionindex,sectionid,serviceindex,serviceid))
                    continue
    
                try:
                    interval = service.get("interval")
                    if interval:
                        if not isinstance(interval,int):
                            interval = int(str(interval).strip())
                            service["interval"] = interval
                    elif not baseinterval:
                        errors.append("Service {0}({1}).{2}({3}): Missing property(interval)".format(sectionindex,sectionid,serviceindex,serviceid))
                        continue
                    else:
                        service["interval"] = baseinterval
                except Exception as ex:
                    errors.append("Service {0}({1}).{2}({3}): The interval({4}) is not an integer".format(sectionindex,sectionid,serviceindex,serviceid,service.get("interval")))
                    continue

                try:
                    timeout = service.get("timeout")
                    if timeout is not None:
                        if not isinstance(timeout,int):
                            timeout = int(str(timeout).strip())
                            service["timeout"] = timeout
                    else:
                        service["timeout"] = basetimeout
                except Exception as ex:
                    errors.append("Service {0}({1}).{2}({3}): The timeout({4}) is not an integer".format(sectionindex,sectionid,serviceindex,serviceid,service.get("timeout")))
                    continue

                try:
                    historyexpire = service.get("historyexpire")
                    if historyexpire is not None:
                        if not isinstance(historyexpire,int):
                            historyexpire = int(str(historyexpire).strip())
 
                        if historyexpire < 0:
                            historyexpire = 0
                        service["historyexpire"] = historyexpire
                    else:
                        service["historyexpire"] = basehistoryexpire
                except Exception as ex:
                    errors.append("Service {0}({1}).{2}({3}): The historyexpire({4}) is not an integer".format(sectionindex,sectionid,serviceindex,serviceid,service.get("historyexpire")))
                    continue

                if not service["healthchecks"]:
                    errors.append("Service {0}({1}).{2}({3}): Missing healthcheck configuration".format(sectionindex,sectionid,serviceindex,serviceid))
                    continue
    
                for key in list(service["healthchecks"].keys()):
                    try:
                        if key not in ("green","yellow","red","error"):
                            errors.append("Service {0}({1}).{2}({3}): The health status({4}) in healthchecks is not in ('green','yellow','red','error')".format(sectionindex,sectionid,serviceindex,serviceid,key))
                            del config["services"][serviceid]["healthchecks"][key]
                            continue
                        if isinstance(service["healthchecks"][key],(list,tuple)):
                            service["healthchecks"][key] = [checks.init_conds(service["healthchecks"][key]),checks.get_message_factory(None)]
                        else:
                            service["healthchecks"][key] = [checks.init_conds(service["healthchecks"][key].get("condition")),checks.get_message_factory(service["healthchecks"][key].get('message'))]
                    except Exception as ex:
                        errors.append("Service {0}({1}).{2}({3}): The config({4}) in healthchecks is in valid.{5}: {6}".format(sectionindex,sectionid,serviceindex,serviceid,key,ex.__class__.__name__,str(ex)))
                        continue
    
                if not service["healthchecks"]:
                    continue
    
                if not service.get("user") and config.get("user"):
                    service["user"] = config["user"]
    
                if not service.get("password") and config.get("password"):
                    service["password"] = config["password"]
    
                if "sslverify" not in service:
                    service["sslverify"] = config["sslverify"]
                elif not isinstance(service["sslverify"],bool):
                    service["sslverify"] = str(service["sslverify"]).lower() == "true"
    
    
                if not service.get("name"):
                    service["name"] = serviceid

                method = service.get("method")
                if method:
                    method = method.upper()
                    if method not in ["GET","POST","DELETE","PUT"]:
                        errors.append("Service {0}({1}).{2}({3}): The method({}) doesn't support".format(sectionindex,sectionid,serviceindex,serviceid,method))
                        continue
                else:
                    method = "GET"
                service["method"] = method


                healthdetailpersistent = service.get("healthdetailpersistent")
                if healthdetailpersistent:
                    if isinstance(healthdetailpersistent,str) and healthdetailpersistent == "__all__":
                        healthdetailpersistent = ["green","yellow","red","error"]
                    else:
                        if isinstance(healthdetailpersistent,str):
                            healthdetailpersistent = [s for s in healthdetailpersistent.split(",")]
                        data = set()
                        for s in healthdetailpersistent:
                            s = s.strip().lower()
                            if not s:
                                continue
                            if s not in ["green","yellow","red","error"]:
                                errors.append("Service {0}({1}).{2}({3}): The health status({4}) in property('healthdetailpersistent') doesn't' support".format(sectionindex,sectionid,serviceindex,serviceid,s))
                            else:
                                data.add(s)
                        healthdetailpersistent = data
                else:
                    healthdetailpersistent = basehealthdetailpersistent
                service["healthdetailpersistent"] = healthdetailpersistent

                service["section"] = config

                services[serviceid] = ServiceHealthCheck(self,service)

            if not services:
                continue

            config["services"] = services
            sections[sectionid] = SectionHealthCheck(config)
            
        return (sections,errors)



    def check(self,runner,taskcls,*args):
        if not self._checkingstatus_loaded:
            self.load_checkingstatus()

        for section in self.sections.values():
            for service in section["services"].values():
                runner.add_task(taskcls(service,*args,**kwargs))

    def _schedule_continuous_check(self,taskcls,*args):
        shutdown.unregister_scheduled_task(self._continuous_check_task)
        asyncio.create_task(self._continuous_check(taskcls,*args))

    def stop_continuous_check(self):
        if not self._continuous_check_task:
            logger.debug("{}: The continuous health check has already been stopped.".format(self))
            return

        shutdown.unregister_scheduled_task(self._continuous_check_task)
        self._continuous_check_task.cancel()
        self._continuous_check_task = None
        logger.debug("{}: Stop continuous health check".format(self))

    async def _continuous_check(self,taskcls,*args):
        if shutdown.shutdowning:
            logger.info("The continuous health checking is end.")
            self._continuous_check_task = None
            return
        
        if not self._continuous_check_task:
            #already stopped
            return

        now = datetime.now().astimezone(settings.TZ)
        self._next_runtime = None
        for section in self.sections.values():
            for service in section["services"].values():
                if now >= service["healthstatus"][0]:
                    #check this service now
                    logger.debug("{} : Run a task to check the service({}.{})  to task runner.".format(self,service.sectionid,service.serviceid))
                    task = taskcls(service,*args)
                    asyncio.create_task(task.run())
                    next_checktime = service["healthstatus"][0] + timedelta(seconds=service.interval)
                    if next_checktime.day != service["healthstatus"][0].day:
                        #next checktime is in tomorrow. reset next checktime to midnight
                        next_checktime = datetime(service["healthstatus"][0].year,service["healthstatus"][0].monthl,service["healthstatus"][0].day + 1).astimezone(settings.TZ)
                    service["healthstatus"][0] = next_checktime
                else:
                    next_checktime = service["healthstatus"][0]
                if not self._next_runtime or self._next_runtime > next_checktime:
                    self._next_runtime = next_checktime

        if not self._continuous_check_task:
            #already stopped
            return

        if self._next_runtime:
            seconds = (self._next_runtime - datetime.now().astimezone(settings.TZ)).total_seconds()
            if seconds > 0:
                logger.debug("Waiting {} seconds to begin the next batch of service health check.".format(seconds))
                self._continous_check_task = asyncio.get_running_loop().call_later(seconds,self._schedule_continuous_check,taskcls,*args)
                shutdown.register_scheduled_task(self._continuous_check_task)
            else:
                self._continuous_check_task = asyncio.create_task(self._continuous_check(taskcls,*args))
        else:
            logger.info("The continuous health checking is end.")
            self._continuous_check_task = None

    @property
    def is_continuous_check_started(self):
        return self._continuous_check_task != None

    _continuous_check_task = None
    async def continuous_check(self,*args,taskcls=BaseServiceHealthCheckTask):
        if not self._checkingstatus_loaded:
            self.load_checkingstatus()
        if self._continuous_check_task:
            logger.info("The continuous health checking is already started.")
            return 
        logger.info("{}: Start to run the continuous health checking".format(self))
        self._continuous_check_task = asyncio.create_task(self._continuous_check(taskcls,*args))


    @classmethod
    def check_response(cls,serviceconfig,res):
        healthstatus = None
        messages = [] if settings.DEBUG else None
        for key in ("green","yellow","red","error"):
            if key not in serviceconfig["healthchecks"]:
                continue
            checkconditions,get_checkmessage = serviceconfig["healthchecks"][key]
            try:
                if settings.DEBUG:
                    messages.clear()
                checkresult =  checks.check(res,checkconditions,messages=messages)
                if checkresult:
                    checkmsg = get_checkmessage(res)
                    if not isinstance(checkmsg,str):
                        checkmsg = json.dumps(checkmsg,indent=4,cls=serializers.JSONFormater)
                    if settings.DEBUG and messages:
                        msg = "{}\nThe following conditions are checked.\n    {}".format(checkmsg,"\n    ".join(messages))
                    else:
                        msg = checkmsg
                    healthstatus = [key,msg]
                    break
                else:
                    """
                    if settings.DEBUG:
                        msg = "The healthstatus({}) are not satified.\n    {}\n    The following conditions are checked.\n        {}".format(key,get_checkmessage(res),"\n        ".join(messages))
                    else:
                        msg = "The healthstatus({}) are not satified.\n    {}".format(key,get_checkmessage(res))
                    logger.debug(msg)
                    """
                    pass

            except Exception as ex:
                traceback.print_exc()
                healthstatus = ["error","Failed to check health status '{}'.{}:{}".format(key,ex.__class__.__name__,str(ex))]
                break
    
        if not healthstatus:
            if res:
                contenttype = res.headers.get("Content-Type","").lower()
                if any( (key in contenttype) for key in ("text","json","xml")):
                    message = res.text
                else:
                    message = "non-text response"
                healthstatus = ["error","Status Code:{}, Message:{}".format(res.status_code,message)]
            else:
                healthstatus = ["error","All healthstatus configured in {} are not satisfied.".format(serviceconfig)]
    
        return healthstatus

class EditingHealthCheck(HealthCheck):

    def __init__(self,healthcheck,configfile=settings.HEALTHCHECK_CONFIG_FILE):
        super().__init__(configfile=configfile)
        self.healthcheck = healthcheck
        self._lock = FileLock("{}.lock".format(self.configfile))
        

    def __str__(self):
        return "EditingHealthCheck"

    def reset(self):
        """
        Return True if changed; otherwise return False
        """
        with self._lock:
            if os.path.exists(self.healthcheck.configfile):
                shutil.copyfile(self.healthcheck.configfile,self.configfile)
            else:
                with open(self.configfile,'w') as f:
                    f.write("[]")

            with open(self.configfile,'rb') as f:
                configs = f.read()
            return config_hashcode != self.config_hashcode

    def save(self,configtxt):
        """
        Return True if changed; otherwise return False
        """
        #parse
        with self._lock:
            try:
                configs = json.loads(configtxt)
            except Exception as ex:
                raise Exception("Health check configuration is not a correct json object")
            #check the configuration
            data,errors = self.init_configs(configs)
            if errors:
                raise Exception("""Found {1} issues in healthcheck configuration file({0})
        {2}
    """.format(self.configfile,len(errors),"\n    ".join(errors)))
    
            with open(self.configfile,'w') as f:
                f.write(configtxt)
    
            with open(self.configfile,'rb') as f:
                configs = f.read()
            config_hashcode = hashlib.sha256(configs).hexdigest()
            return config_hashcode != self.config_hashcode

    def publish(self,user,comments):
        #validate the healthcheck configuration file
        with self._lock:
            try:
                with open(self.configfile,'rb') as f:
                    configtxt = f.read()
    
                config_hashcode = hashlib.sha256(configtxt).hexdigest()
                if config_hashcode == self.healthcheck.config_hashcode:
                    #not changed
                    changed = False
                    utils.remove_file(self.configfile)
                    return False
                    
                configs = json.loads(configtxt.decode())
            except Exception as ex:
                raise Excepton("Health check configuration is not a correct json object")
    
            data,errors = self.init_configs(configs)
            if errors:
                raise Exception("""Found {1} issues in healthcheck configuration file({0})
        {2}
    """.format(self.configfile,len(errors),"\n    ".join(errors)))
    
            #save the publish config file

            now = datetime.now()
            publishedfile = "{1}.{0}{2}".format(now.strftime("%Y%m%dT%H%M%S"),*os.path.splitext(self.healthcheck.configfile))
            shutil.copyfile(self.configfile,publishedfile)
    
            #update the publish history
            count = 0
            tmpfile = "{}.tmp".format(self.healthcheck.publishhistoriesfile)
            with open(tmpfile,'w') as fw:
                count += 1
                fw.write(json.dumps([now.strftime("%Y-%m-%d %H:%M:%S"),os.path.basename(publishedfile),user,comments]))
                with open(self.healthcheck.publishhistoriesfile,'r') as fr:
                    while True:
                        line = fr.readline()
                        if not line:
                            break
                        else:
                            count += 1
                            if count == 2:
                                fw.write(os.linesep)
                            if count <= settings.HEALTHCHECK_PUBLISH_HISTORIES:
                                fw.write(line)
                            else:
                                #remove the publish history
                                publisheddata = json.loads(line.strip())
                                if publisheddata[1]:
                                    utils.remove_file(publisheddata[1])
            shutil.copyfile(tmpfile,self.healthcheck.publishhistoriesfile)
    
            #update the current healthceck config file
            shutil.copyfile(self.configfile,self.healthcheck.configfile)
    
            return True

class ReleasedHealthCheck(HealthCheck):

    def __str__(self):
        return "ReleasedHealthCheck"

    _editconfigfile = None
    @property
    def editconfigfile(self):
        if not self._editconfigfile:
            f = "{}.edit{}".format(*os.path.splitext(self.configfile))
            if not os.path.exists(f):
                if os.path.exists(self.configfile):
                    shutil.copyfile(self.configfile,f)
                else:
                    with open(f,'w') as fw:
                        fw.write("[]")
            elif not os.path.isfile(f):
                raise Exception("The editing config file({}) is not a file".format(f))
            self._editconfigfile = f

        return self._editconfigfile

    _publishhistoriesfile = None
    @property
    def publishhistoriesfile(self):
        if not self._publishhistoriesfile:
            tmpfile = "{}.publishhistories{}".format(*os.path.splitext(self.configfile))
            if not os.path.exists(tmpfile):
                initialfile = "{}.initial{}".format(*os.path.splitext(self.configfile))
                shutil.copyfile(self.configfile,initialfile)
                with open(tmpfile,'w') as f:
                    f.write(json.dumps(["Initial",os.path.basename(initialfile),"","Initial"]))
            elif not os.path.isfile(tmpfile):
                raise Exception("The publish history file({}) is not a file".format(tmpfile))
            self._publishhistoriesfile = tmpfile

        return self._publishhistoriesfile

    _editing_healthcheck = None
    @property
    def editing_healthcheck(self):
        if not self._editing_healthcheck:
            self._editing_healthcheck = EditingHealthCheck(self,self.editconfigfile)

        return self._editing_healthcheck


    @property
    def publishhistories(self):
        histories = []
        with open(self.publishhistoriesfile,'r') as fr:
            while True:
                line = fr.readline()
                if not line:
                    break
                else:
                    try:
                        histories.append(json.loads(line.strip()))
                    except Exception as ex:
                        logger.error("{}: Failed to parse the published healthcheck configuration data ({})".format(self,line))

        return histories

    def rollback(self,configfile):
        configfile = os.path.join(os.path.dirname(self.configfile),configfile)
        if not os.path.exists(configfile):
            raise Exception("{}: The config file({}) doesn't exist".format(self,configfile))

        with open(configfile,'rb') as f:
            configtxt = f.read()

        config_hashcode = hashlib.sha256(configtxt).hexdigest()
        if config_hashcode == self.config_hashcode:
            logger.debug("{}: config file is not changed".format(self))
            return False

        shutil.copyfile(configfile,self.configfile)
        return True



healthcheck = ReleasedHealthCheck()

async def main():
    try:
        await healthcheck.continuous_check()
        await shutdown.wait()
    except exceptions.SystemShutdown as ex:
        pass
    except asyncio.CancelledError as ex:
        pass
    finally:
        await shutdown.shutdown()
        pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except asyncio.CancelledError as ex:
        pass

