import asyncio
import logging
import traceback
import json
from signal import SIGINT, SIGTERM
from quart import  render_template,request,stream_with_context,redirect
from datetime import datetime,timedelta

from app import app
from . import settings
from .healthcheckclient import healthstatuslistener,editinghealthstatuslistener
from .healthcheck import healthcheck
from .socket import commandclient
from . import shutdown
from . import serializers


logger = logging.getLogger("healthcheck.healthcheckclient")

def exithandler():
    shutdown.shutdowning = True
    healthstatuslistener.request2close()
    editinghealthstatuslistener.request2close()

@app.before_serving
async def initialize():
    loop = asyncio.get_running_loop()
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, exithandler)
    healthstatuslistener.start()
    editinghealthstatuslistener.start()

@app.after_serving
async def post_shutdown():
    await shutdown.shutdown()

async def ping():
    start = datetime.now()
    nextcheck = start + timedelta(seconds = settings.HEARTBEAT_TIME) 
    try:
        res = await commandclient.exec("healthcheck",0) 
        msg = res[1]
        status = "green" if res[0] else "red"
    except Exception as ex:
        status = "red"
        msg = "{}:{}".format(ex.__class__.__name__,str(ex))
    finally:
        end = datetime.now()
    return "{}\n".format(json.dumps([["healthcheck","healthcheck"],[nextcheck,[start,end,status,msg,False ]]],cls=serializers.JSONFormater)).encode()

@app.route("/healthcheck/dashboard")
async def dashboard():
    healthservice_nextcheck = datetime.now() + timedelta(seconds=settings.HEARTBEAT_TIME + 1)
    healthservice_nextcheck = int(healthservice_nextcheck.timestamp()) * 1000
    return await render_template("healthcheck/dashboard.html",healthcheck=healthcheck,healthservice_nextcheck=healthservice_nextcheck,nextcheck_timeout=settings.NEXTCHECK_TIMEOUT,nextcheck_checkinterval=settings.NEXTCHECK_CHECKINTERVAL)

@app.route("/healthcheck/healthstatusstream")
async def healthstatusstream():
    @stream_with_context
    async def async_generator():
        for section in healthcheck.sectionlist:
            for service in section.servicelist:
                if service.healthstatus:
                    yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        print("&&&&&&&&&&&&&&&&&&&&&&&&")
        servicestatus = await ping()
        yield servicestatus
        reader = healthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            try:
                async with asyncio.timeout(settings.HEARTBEAT_TIME):
                    await healthstatuslistener.wait()
                    timeout = False
            except TimeoutError as ex:
                timeout = True
            for healthstatus in reader.items():
                yield "{}\n".format(json.dumps(healthstatus,cls=serializers.JSONFormater)).encode()
            if timeout:
                healthservicestatus = await ping()
                yield healthservicestatus
            else:
                now = datetime.now()
                yield "{}\n".format(json.dumps([["healthcheck","healthcheck"],[now + timedelta(seconds=settings.HEARTBEAT_TIME),[now,now,"green","Tested by other service check.",False ]]],cls=serializers.JSONFormater)).encode()


    return async_generator(), 200, None

@app.route("/healthcheck/config",methods=["GET","POST"])
async def edit_healthcheck():
    if request.method == "GET":
        with open(healthcheck.editconfigfile) as f:
            healthcheckconfig = f.read()
            return await render_template("healthcheck/edit.html",healthcheckconfig=healthcheckconfig,message=None)
    else:
        try:
            formdata = await request.form
            healthcheckconfig = ""
            action = formdata.get("action","save")
            if action == "save":
                healthcheckconfig = formdata.get("healthcheckconfig")
                changed = healthcheck.editing_healthcheck.save(healthcheckconfig)
            elif action == "reset":
                changed = healthcheck.editing_healthcheck.reset()
                with open(healthcheck.editing_healthcheck.configfile) as f:
                    healthcheckconfig = f.read()
            else:
                raise Exception("Action({}) Not Support".format(action))

            if changed:
                await commandclient.exec("reload_editing_healthcheck") 

            msg = None
        except Exception as ex:
            traceback.print_exc()
            msg = str(ex)

        return await render_template("healthcheck/edit.html",healthcheckconfig=healthcheckconfig,message=msg)

@app.route("/healthcheck/config/publish",methods=["GET","POST"])
async def publish_healthcheck():
    if request.method == "GET":
        with open(healthcheck.editconfigfile) as f:
            healthcheckconfig = f.read()
            return await render_template("healthcheck/publish.html",healthcheckconfig=healthcheckconfig,message=None)
    else:
        try:
            formdata = await request.form
            action = formdata.get("action","publish")
            if action == "publish":
                comments = formdata.get("comments")
                if not comments:
                    comments = "No comments"
                user = request.headers.get("x-email")
                if not user:
                    user = "guest"
                changed = healthcheck.editing_healthcheck.publish(user,comments)
            else:
                raise Exception("Action({}) Not Support".format(action))

            if changed:
                await commandclient.exec("reload_healthcheck") 

            return redirect("/healthcheck/publishhistories")

        except Exception as ex:
            traceback.print_exc()
            msg = str(ex)
            return await render_template("healthcheck/edit.html",healthcheckconfig=healthcheckconfig,message=msg)

@app.route("/healthcheck/publishhistories",methods=["GET"])
async def publishhistories():
    return await render_template("healthcheck/publishhistories.html",publishhistories=healthcheck.publishhistories,message=None)

@app.route("/healthcheck/rollback",methods=["POST"])
async def rollback():
    try:
        formdata = await request.form
        configfile = formdata.get("configfile")
        if not configfile:
            raise Exception( "Missing configfile.")
        else:
            changed = healthcheck.rollback(configfile)

        if changed:
            await commandclient.exec("reload_healthcheck") 

        return redirect("/healthcheck/dashboard")
    except Exception as ex:
        traceback.print_exc()
        msg = str(ex)
        return await render_template("healthcheck/publishhistories.html",publishhistories=healthcheck.publishhistories,message=msg)



@app.route("/healthcheck/config/preview",methods=["GET"])
async def preview_editing_healthcheck():
    try:
        result = await commandclient.exec("start_preview_healthcheck")
        if result[0]:
            msg = None
        else:
            msg = result[1]
    except Exception as ex:
        traceback.print_exc()
        msg = str(ex)

    healthservice_nextcheck = datetime.now() + timedelta(seconds=settings.HEARTBEAT_TIME + 1)
    healthservice_nextcheck = int(healthservice_nextcheck.timestamp()) * 1000
    return await render_template("healthcheck/preview.html",healthcheck=healthcheck.editing_healthcheck,message=msg,healthservice_nextcheck=healthservice_nextcheck,nextcheck_timeout=settings.NEXTCHECK_TIMEOUT,nextcheck_checkinterval=settings.NEXTCHECK_CHECKINTERVAL)

@app.route("/healthcheck/config/preview/start",methods=["GET"])
async def start_preview_editing_healthcheck():
    try:
        result = await commandclient.exec("start_preview_healthcheck")
        if result[0]:
            msg = "OK"
        else:
            msg = result[1]
        return msg
    except Exception as ex:
        msg = str(ex)
        return Response(msg,status="400")

@app.route("/healthcheck/config/preview/stop",methods=["GET"])
async def stop_preview_editing_healthcheck():
    try:
        result = await commandclient.exec("stop_preview_healthcheck")
        if result[0]:
            msg = "OK"
        else:
            msg = result[1]
        return msg
    except Exception as ex:
        msg = str(ex)
        return Response(msg,status="400")


@app.route("/healthcheck/editinghealthstatusstream")
async def editinghealthstatusstream():
    @stream_with_context
    async def async_generator():
        for section in healthcheck.editing_healthcheck.sectionlist:
            for service in section.servicelist:
                yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        servicestatus = await ping()
        yield servicestatus
        reader = editinghealthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            try:
                async with asyncio.timeout(settings.HEARTBEAT_TIME):
                    await editinghealthstatuslistener.wait()
                    timeout = False
            except TimeoutError as ex:
                timeout = True

            for healthstatus in reader.items():
                yield "{}\n".format(json.dumps(healthstatus,cls=serializers.JSONFormater)).encode()
            if timeout:
                healthservicestatus = await ping()
                yield healthservicestatus
            else:
                now = datetime.now()
                yield "{}\n".format(json.dumps([["healthcheck","healthcheck"],[now + timedelta(seconds=settings.HEARTBEAT_TIME),[now,now,"green","Tested by other service check.",False ]]],cls=serializers.JSONFormater)).encode()


    return async_generator(), 200, None

