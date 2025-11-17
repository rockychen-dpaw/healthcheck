import asyncio
import logging
import traceback
import json
import os
from signal import SIGINT, SIGTERM
from quart import  render_template,request,stream_with_context,redirect
from datetime import datetime,timedelta
import httpx

from status import app,application
from . import settings
from .healthcheckclient import healthstatuslistener,editinghealthstatuslistener
from .healthcheck import healthcheck,LastHealthCheck,SystemViewMeta
from .socket import commandclient
from . import shutdown
from . import serializers
from . import utils


logger = logging.getLogger("healthcheck.healthcheckclient")

_permissions = {}
async def can_admin(request):
    host = request.headers.get("host")
    if any(host.startswith(k) for k in  ("localhost:","127.0.0.1:")):
        return settings.DEBUG

    user = request.headers.get("X-email")
    if not user:
        return False
    try:
        perm = _permissions.get(user)
        now = utils.now()
        if not perm or (now - perm[1]).total_seconds() > settings.AUTH2_PERMCACHE_TIMEOUT:
            res = None
            async with httpx.AsyncClient(auth=(settings.AUTH2_USER,settings.AUTH2_PASSWORD),timeout=settings.AUTH2_TIMEOUT,verify=settings.AUTH2_SSLVERIFY) as client:
                res = await client.post("{}/sso/checkauthorization".format(settings.AUTH2_URL),data={"details":"false","flaturl":"true","flatuser":"true","url":"https://{}/healthcheck/config".format(host),"user":user})
            data = res.json()
            perm = (data[-1],now)
            _permissions[user] = perm
        return perm[0]
    except Exception as ex:
        logger.error("Failed to get the permission from auth2.{}: {}".format(ex.__class__.__name__,str(ex)))
        return False

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
    start = utils.now()
    nextcheck = start + timedelta(seconds = settings.HEARTBEAT) 
    try:
        res = await commandclient.exec("healthcheck",0) 
        msg = res[1]
        status = "green" if res[0] else "red"
    except Exception as ex:
        status = "red"
        msg = "Failed to ping healthcheck server. {}:{}".format(ex.__class__.__name__,str(ex))
    finally:
        end = utils.now()
    return "{}\n".format(json.dumps([["healthcheck","healthcheck"],[nextcheck,[start,end,status,msg,False ]]],cls=serializers.JSONFormater)).encode()

@app.route("/healthcheck/ping")
async def healthcheck_ping():
    try:
        res = await commandclient.exec("healthcheck",0) 
        msg = res[1]
        status = 200 if res[0] else 500
    except Exception as ex:
        status = 500
        msg = "{}:{}".format(ex.__class__.__name__,str(ex))
    return msg ,status

@app.route("/healthcheck")
@app.route("/healthcheck/")
async def healthcheckindex():
    user = request.headers.get("X-email")
    if user:
        defaultview = healthcheck.get_viewmeta(user)
    else:
        defaultview = {
            "id":"Default",
            "title": healthcheck.title,
            "description":"The dashboard for all systems"
        }

    adminable = await can_admin(request)

    return await render_template("healthcheck/index.html",systemviews=healthcheck.systemviews,can_admin=adminable,defaultview=defaultview)


@app.route("/healthcheck/config/systemview",methods=["GET","POST"],defaults={'system':None})
@app.route("/healthcheck/config/systemview/<system>",methods=["GET","POST"])
async def save_systemview(system):
    #permission check
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    if request.method == "GET":
        if system:
            viewmeta = healthcheck.get_viewmeta(system)
        else:
            viewmeta = SystemViewMeta(["","","",""])
        return await render_template("healthcheck/systemview.html",viewmeta=viewmeta,system=system)
    elif request.method == "POST":
        formdata = await request.form
        action = formdata.get("action","save")
        if action == "save":
            systemid = system or formdata.get("id")
            title = formdata.get("title")
            description = formdata.get("description")
            messages = []
            if not systemid :
                messages.append("System Identity can't be empty")
            if not title:
                messages.append("Title can't be empty.")
            if messages:
                viewmeta = SystemViewMeta([systemid,title,description])
                return await render_template("healthcheck/systemview.html",viewmeta=viewmeta,messages=messages,system=system)
            healthcheck.save_systemview(systemid,title,description)

            return redirect('/healthcheck')
        elif action == "cancel":
            return redirect("/healthcheck")
        else:
            raise Exception("Action({}) Not Support".format(action))

@app.route("/healthcheck/config/systemview/<system>/delete",methods=["GET"])
async def delete_systemview(system):
    healthcheck.delete_systemview(system)
    return redirect('/healthcheck')

@app.route("/healthcheck/dashboard",defaults={'system': None})
@app.route("/healthcheck/dashboard/<system>")
async def dashboard(system):
    healthservice_nextcheck = utils.now() + timedelta(seconds=settings.HEARTBEAT + 1)
    healthservice_nextcheck = int(healthservice_nextcheck.timestamp()) * 1000
    user = request.headers.get("X-email")
    adminable = await can_admin(request)
    if system:
        viewkey = system
        statusstreamurl = "/healthcheck/healthstatusstream/{}".format(system)
    else:
        viewkey = user
        statusstreamurl = "/healthcheck/healthstatusstream"

    if viewkey:
        healthcheckview = healthcheck.get_view(viewkey)
    else:
        healthcheckview = healthcheck


    return await render_template("healthcheck/dashboard.html",healthcheck=healthcheckview,healthservice_nextcheck=healthservice_nextcheck,nextcheck_timeout=settings.NEXTCHECK_TIMEOUT,nextcheck_checkinterval=settings.NEXTCHECK_CHECKINTERVAL,baseurl="/healthcheck",statusstreamurl=statusstreamurl,adminable=adminable,heartbeat=settings.HEARTBEAT,user=user,system=system)

@app.route("/healthcheck/reload")
async def reload_dashboard():
    try:
        res = await commandclient.exec("reload_dashboard") 
        return "OK", 200
    except Exception as ex:
        return "Failed to reload the dashboard.{}".format(str(ex)), 500


@app.route("/healthcheck/healthstatusstream",defaults={'system': None})
@app.route("/healthcheck/healthstatusstream/<system>")
async def healthstatusstream(system):
    viewkey = system or request.headers.get("X-email")
    viewsettings = healthcheck.get_viewsettings(viewkey)

    @stream_with_context
    async def async_generator():
        for section in healthcheck.healthchecksections:
            for service in section.healthcheckservices:
                if service.healthstatus:
                    yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        servicestatus = await ping()
        yield servicestatus
        reader = healthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            try:
                async with asyncio.timeout(settings.HEARTBEAT):
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
                now = utils.now()
                yield "{}\n".format(json.dumps([["healthcheck","healthcheck"],[now + timedelta(seconds=settings.HEARTBEAT),[now,now,"green","Tested by other service check.",False ]]],cls=serializers.JSONFormater)).encode()

    @stream_with_context
    async def async_generator_view():
        for section in healthcheck.healthchecksections:
            serviceset = viewsettings.get(section.sectionid,set())
            for service in section.healthcheckservices:
                if service.healthstatus and service.serviceid in serviceset:
                    yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        servicestatus = await ping()
        yield servicestatus
        reader = healthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            try:
                async with asyncio.timeout(settings.HEARTBEAT):
                    await healthstatuslistener.wait()
                    timeout = False
            except TimeoutError as ex:
                timeout = True
            for healthstatus in reader.items():
                if healthstatus[0][1] in viewsettings.get(healthstatus[0][0],set()):
                    yield "{}\n".format(json.dumps(healthstatus,cls=serializers.JSONFormater)).encode()
            if timeout:
                healthservicestatus = await ping()
                yield healthservicestatus
            else:
                now = utils.now()
                yield "{}\n".format(json.dumps([["healthcheck","healthcheck"],[now + timedelta(seconds=settings.HEARTBEAT),[now,now,"green","Tested by other service check.",False ]]],cls=serializers.JSONFormater)).encode()


    return async_generator_view() if viewsettings else async_generator(), 200, None

@app.route("/healthcheck/customize",defaults={'system': None},methods=["GET","POST"])
@app.route("/healthcheck/config/view/<system>",methods=["GET","POST"])
async def customize_dashboard(system):
    #permission check
    if system:
        editable = await can_admin(request)
        if not editable:
            return "Not Authorized", 403


    user = request.headers.get("X-email")
    viewkey = system or user
    if request.method == "GET":
        healthcheckview = healthcheck.get_view(viewkey)

        return await render_template("healthcheck/customize.html",healthcheck=healthcheckview,viewkey=viewkey,system=system,user=user)
    else:
        try:
            formdata = await request.form
            action = formdata.get("action","save")
            if action == "save":
                all_selected = True
                viewsettings = {}

                for section in healthcheck.healthchecksections:
                    for service in section.healthcheckservices:
                        if "{}:{}".format(section.sectionid,service.serviceid) in formdata:
                            if section.sectionid not in viewsettings:
                                viewsettings[section.sectionid] = set()
                            viewsettings[section.sectionid].add(service.serviceid)
                        else:
                            all_selected = False

                if all_selected or not viewsettings:
                    healthcheck.save_viewsettings(viewkey)
                else:
                    healthcheck.save_viewsettings(viewkey,viewsettings)
            elif action == "reset":
                healthcheck.save_viewsettings(viewkey)
            else:
                raise Exception("Action({}) Not Support".format(action))

            msg = None
        except Exception as ex:
            traceback.print_exc()
            msg = str(ex)
        if user:
            return redirect("/healthcheck/dashboard/{}".format(system))
        else:
            return redirect("/healthcheck/dashboard")


@app.route("/healthcheck/history/<sectionid>/<serviceid>",defaults={'pageid': ""})
@app.route("/healthcheck/history/<sectionid>/<serviceid>/<pageid>")
async def healthcheckhistory(sectionid,serviceid,pageid):
    service = healthcheck.get_service(sectionid,serviceid)
    if not service:
        return "The service({}.{}) doesn't exist".format(sectionid,serviceid) ,404

    pages = service.healthcheckpages.get_pages()

    if pageid:
        try:
            pageid = int(pageid)
        except:
            return redirect("/healthcheck/history/{}/{}".format(sectionid,serviceid))

        page = next((p for p in pages if pageid == p.pageid),None)
        if not page:
            return redirect("/healthcheck/history/{}/{}".format(sectionid,serviceid))
    elif pages:
        page = pages[-1]
    else:
        page = None

    return await render_template("healthcheck/healthcheckhistory.html",service=service,pages=reversed(pages),page=page,baseurl="/healthcheck")

@app.route("/healthcheck/details/<sectionid>/<serviceid>/<pageid>/<starttime>")
async def healthcheckdetails(sectionid,serviceid,pageid,starttime):
    service = healthcheck.get_service(sectionid,serviceid)
    if not service:
        return "The service({}.{}) doesn't exist".format(sectionid,serviceid) ,404

    starttime = datetime.strptime(starttime,'%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=settings.TZ)

    try:
        pageid = int(pageid)
    except:
        return "Details Not Found",404

    page = None
    pages = service.healthcheckpages.get_pages()
    if pageid == 0:
        for p in reversed(pages):
            if p.starttime <= starttime:
                page = p
                break
    else:
        page = next((p for p in pages if pageid == p.pageid),None)

    if not page:
        return "Details Not Found",404

    try:
        detailfile = page.detailfile(starttime)
        with open(detailfile) as f:
            data = f.read()
        return data,200,{"Content-Type":"application/json"}
    except Exception as ex:
        return await render_template("healthcheck/healthcheckhistory.html",service=service,pages=reversed(pages),page=page,baseurl="/healthcheck/config",message=str(ex))

@app.route("/healthcheck/config/edit",methods=["GET","POST"])
async def edit_healthcheck():
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

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
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

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

            return redirect("/healthcheck/config/publishhistories")

        except Exception as ex:
            traceback.print_exc()
            msg = str(ex)
            return await render_template("healthcheck/edit.html",healthcheckconfig=healthcheckconfig,message=msg)

@app.route("/healthcheck/config/publishhistories",methods=["GET"])
async def publishhistories():
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    return await render_template("healthcheck/publishhistories.html",publishhistories=healthcheck.publishhistories,message=None)

@app.route("/healthcheck/config/rollback",methods=["POST"])
async def rollback():
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

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
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    try:
        result = await commandclient.exec("start_preview_healthcheck")
        if result[0]:
            msg = None
        else:
            msg = result[1]
    except Exception as ex:
        traceback.print_exc()
        msg = str(ex)

    healthservice_nextcheck = utils.now() + timedelta(seconds=settings.HEARTBEAT + 1)
    healthservice_nextcheck = int(healthservice_nextcheck.timestamp()) * 1000
    return await render_template("healthcheck/preview.html",healthcheck=healthcheck.editing_healthcheck,message=msg,healthservice_nextcheck=healthservice_nextcheck,nextcheck_timeout=settings.NEXTCHECK_TIMEOUT,nextcheck_checkinterval=settings.NEXTCHECK_CHECKINTERVAL,baseurl="/healthcheck/config",statusstreamurl="/healthcheck/config/healthstatusstream",heartbeat=settings.HEARTBEAT)

@app.route("/healthcheck/config/history/<sectionid>/<serviceid>",defaults={'pageid': ""})
@app.route("/healthcheck/config/history/<sectionid>/<serviceid>/<pageid>")
async def editinghealthcheckhistory(sectionid,serviceid,pageid):
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    service = healthcheck.editing_healthcheck.get_service(sectionid,serviceid)
    if not service:
        return "The service({}.{}) doesn't exist".format(sectionid,serviceid) ,404

    pages = service.healthcheckpages.get_pages()
    if pageid:
        try:
            pageid = int(pageid)
        except:
            return redirect("/healthcheck/config/history/{}/{}".format(sectionid,serviceid))
        page = next((p for p in pages if pageid == p.pageid),None)
        if not page:
            return redirect("/healthcheck/config/history/{}/{}".format(sectionid,serviceid))
    elif pages:
        page = pages[-1]
    else:
        page = None

    return await render_template("healthcheck/healthcheckhistory.html",service=service,pages=reversed(pages),page=page,baseurl="/healthcheck/config")

@app.route("/healthcheck/config/details/<sectionid>/<serviceid>/<pageid>/<starttime>")
async def editinghealthcheckdetails(sectionid,serviceid,pageid,starttime):
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    service = healthcheck.editing_healthcheck.get_service(sectionid,serviceid)
    if not service:
        return "The service({}.{}) doesn't exist".format(sectionid,serviceid) ,404

    starttime = datetime.strptime(starttime,'%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=settings.TZ)

    try:
        pageid = int(pageid)
    except:
        return "Details Not Found",404

    page = None
    pages = service.healthcheckpages.get_pages()
    if pageid == 0:
        for p in reversed(pages):
            if isinstance(p,LastHealthCheck) or p.starttime <= starttime:
                page = p
                break
    else:
        page = next((p for p in pages if pageid == p.pageid),None)

    if not page:
        return "Details Not Found",404


    try:
        detailfile = page.detailfile(starttime)
        with open(detailfile) as f:
            data = f.read()
        return data,200,{"Content-Type":"application/json"}
    except Exception as ex:
        return await render_template("healthcheck/healthcheckhistory.html",service=service,pages=reversed(pages),page=page,baseurl="/healthcheck/config",message=str(ex))


@app.route("/healthcheck/config/preview/start",methods=["GET"])
async def start_preview_editing_healthcheck():
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

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
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

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


@app.route("/healthcheck/json",defaults={'system': None})
@app.route("/healthcheck/json/<system>")
def jsonstatus(system):
    viewkey = system or request.headers.get("X-email")
    details = request.args.get("details") or ""
    return healthcheck.get_view(viewkey).get_jsonstatus(details.lower() == "true"),200,{"Content-Type":"application/json"}

@app.route("/healthcheck/config/healthstatusstream")
async def editinghealthstatusstream():
    editable = await can_admin(request)
    if not editable:
        return "Not Authorized", 403

    @stream_with_context
    async def async_generator():
        for section in healthcheck.editing_healthcheck.healthchecksections:
            for service in section.healthcheckservices:
                yield "{}\n".format(json.dumps([[section.sectionid,service.serviceid],service.healthstatus],cls=serializers.JSONFormater)).encode()

        if editinghealthstatuslistener.continuouscheck_started:
            yield "{}\n".format(json.dumps("continuouscheck_started")).encode()
        else:
            yield "{}\n".format(json.dumps("continuouscheck_stopped")).encode()

        servicestatus = await ping()
        yield servicestatus
        reader = editinghealthstatuslistener.get_healthstatusreader()
        while not shutdown.shutdowning:
            try:
                async with asyncio.timeout(settings.HEARTBEAT):
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
                now = utils.now()
                yield "{}\n".format(json.dumps([["healthcheck","healthcheck"],[now + timedelta(seconds=settings.HEARTBEAT),[now,now,"green","Tested by other service check.",False ]]],cls=serializers.JSONFormater)).encode()


    return async_generator(), 200, None

if __name__ == "__main__":
    loop = shutdown.patch_asyncio()

    application.run(host="0.0.0.0", port=os.environ.get("PORT", 8080), use_reloader=True,loop=loop)
    print("**={}".format(application))
