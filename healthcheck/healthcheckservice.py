import asyncio
import logging
import traceback
import json
from signal import SIGINT, SIGTERM
from quart import  render_template,request,stream_with_context,redirect

from app import app
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

@app.route("/healthcheck/status")
async def status():
    try:
        status = await commandclient.exec("healthcheck") 
        return {"status":status[0],"message":status[1]}
    except Exception as ex:
        return {"status":False, "message":"{}:{}".format(ex.__class__.__name__,str(ex))}

@app.route("/healthcheck/dashboard")
async def dashboard():
    return await render_template("healthcheck/dashboard.html",healthcheck=healthcheck)

@app.route("/healthcheck/healthstatusstream")
async def healthstatusstream():
    @stream_with_context
    async def async_generator():
        for section in healthcheck.sectionlist:
            for service in section.servicelist:
                yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        reader = healthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            await healthstatuslistener.wait()
            for healthstatus in reader.items():
                yield "{}\n".format(json.dumps(healthstatus,cls=serializers.JSONFormater)).encode()


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

    return await render_template("healthcheck/preview.html",healthcheck=healthcheck.editing_healthcheck,message=msg)

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

        reader = editinghealthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            await healthstatuslistener.wait()
            for healthstatus in reader.items():
                yield "{}\n".format(json.dumps(healthstatus,cls=serializers.JSONFormater)).encode()


    return async_generator(), 200, None

