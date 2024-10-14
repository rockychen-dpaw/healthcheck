import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ET
import humanize
import requests
from bottle import Bottle, response, static_file

dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()
app = application = Bottle()


# Configure logging.
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

TZ = ZoneInfo(os.environ.get("TZ", "Australia/Perth"))
OUTPUT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DBCA Spatial Support System health checks</title>
<meta name="description" content="DBCA Spatial Support System health checks">
</head>
<body>
<h1>DBCA Spatial Support System health checks</h1>
{}
</body>
</html>"""
CACHE_RESPONSE = os.environ.get("CACHE_RESPONSE", True)
RT_URL = os.environ.get("RT_URL", "https://resourcetracking.dbca.wa.gov.au")
SSS_DEVICES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&format=json"
SSS_IRIDIUM_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=iriditrak&format=json"
SSS_TRACPLUS_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=tracplus&format=json"
SSS_DFES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=dfes&format=json"
SSS_FLEETCARE_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=fleetcare&format=json"
CSW_API = os.environ.get(
    "CSW_API", "https://csw.dbca.wa.gov.au/catalogue/api/records/?format=json&application__name=sss"
)
KMI_URL = os.environ.get("KMI_URL", "https://kmi.dbca.wa.gov.au/geoserver")
KMI_WFS_URL = f"{KMI_URL}/ows"
KMI_WMTS_URL = f"{KMI_URL}/gwc/service/wmts"
BFRS_URL = os.environ.get("BFRS_URL", "https://bfrs.dbca.wa.gov.au/api/v1/profile/?format=json")
AUTH2_URL = os.environ.get("AUTH2_URL", "https://auth2.dbca.wa.gov.au/healthcheck")
AUTH2_STATUS_URL = os.environ.get("AUTH2_URL", "https://auth2.dbca.wa.gov.au/status")
USER_SSO = os.environ.get("USER_SSO", "asi@dbca.wa.gov.au")
PASS_SSO = os.environ.get("PASS_SSO", "password")
TRACKING_POINTS_MAX_DELAY = int(os.environ.get("TRACKING_POINTS_MAX_DELAY", 30))  # Minutes
DBCA_GOING_BUSHFIRES_LAYER = os.environ.get("DBCA_GOING_BUSHFIRES_LAYER", None)
DBCA_CONTROL_LINES_LAYER = os.environ.get("DBCA_CONTROL_LINES_LAYER", None)
DFES_GOING_BUSHFIRES_LAYER = os.environ.get("DFES_GOING_BUSHFIRES_LAYER", None)
ALL_CURRENT_HOTSPOTS_LAYER = os.environ.get("ALL_CURRENT_HOTSPOTS_LAYER", None)
LIGHTNING_24H_LAYER = os.environ.get("LIGHTNING_24H_LAYER", None)
LIGHTNING_24_48H_LAYER = os.environ.get("LIGHTNING_24_48H_LAYER", None)
LIGHTNING_48_72H_LAYER = os.environ.get("LIGHTNING_48_72H_LAYER", None)
FUEL_AGE_1_6Y_LAYER = os.environ.get("FUEL_AGE_1_6Y_LAYER", None)
FUEL_AGE_NONFOREST_1_6Y_LAYER = os.environ.get("FUEL_AGE_NONFOREST_1_6Y_LAYER", None)
COG_BASEMAP_LAYER = os.environ.get("COG_BASEMAP_LAYER", None)
STATE_BASEMAP_LAYER = os.environ.get("STATE_BASEMAP_LAYER", None)
DBCA_BURN_PROGRAM_LAYER = os.environ.get("DBCA_BURN_PROGRAM_LAYER", None)
DAILY_ACTIVE_BURNS_LAYER = os.environ.get("DAILY_ACTIVE_BURNS_LAYER", None)
DBCA_LANDS_WATERS_LAYER = os.environ.get("DBCA_LANDS_WATERS_LAYER", None)
DBCA_LANDS_WATERS_INTEREST_LAYER = os.environ.get("DBCA_LANDS_WATERS_INTEREST_LAYER", None)


@app.route("/readiness")
def readiness():
    return "OK"


@app.route("/liveness")
def liveness():
    return "OK"


def get_session():
    session = requests.Session()
    session.auth = (USER_SSO, PASS_SSO)
    return session


def healthcheck():
    """Query HTTP sources and derive a dictionary of response successes."""
    d = {"server_time": datetime.now().astimezone(TZ).isoformat(timespec="seconds"), "success": True, "errors": []}

    session = get_session()

    try:
        trackingdata = session.get(SSS_DEVICES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["latest_point"] = t.isoformat()
        d["latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
    except Exception as e:
        LOGGER.warning(f"Error querying Resource Tracking: {SSS_DEVICES_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Resource Tracking: {SSS_DEVICES_URL}")
        d["latest_point"] = None
        d["latest_point_delay"] = None
        d["success"] = False

    try:
        trackingdata = session.get(SSS_IRIDIUM_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["iridium_latest_point"] = t.isoformat()
        d["iridium_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
    except Exception as e:
        LOGGER.warning(f"Error querying Resource Tracking: {SSS_IRIDIUM_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Resource Tracking: {SSS_IRIDIUM_URL}")
        d["iridium_latest_point"] = None
        d["iridium_latest_point_delay"] = None
        d["success"] = False

    try:
        trackingdata = session.get(SSS_TRACPLUS_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["tracplus_latest_point"] = t.isoformat()
        d["tracplus_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
    except Exception as e:
        LOGGER.warning(f"Error querying Resource Tracking: {SSS_TRACPLUS_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Resource Tracking: {SSS_TRACPLUS_URL}")
        d["tracplus_latest_point"] = None
        d["tracplus_latest_point_delay"] = None
        d["success"] = False

    try:
        trackingdata = session.get(SSS_DFES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["dfes_latest_point"] = t.isoformat()
        d["dfes_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
    except Exception as e:
        LOGGER.warning(f"Error querying Resource Tracking: {SSS_DFES_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Resource Tracking: {SSS_DFES_URL}")
        d["dfes_latest_point"] = None
        d["dfes_latest_point_delay"] = None
        d["success"] = False

    try:
        trackingdata = session.get(SSS_FLEETCARE_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["fleetcare_latest_point"] = t.isoformat()
        d["fleetcare_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
    except Exception as e:
        LOGGER.warning(f"Error querying Resource Tracking: {SSS_FLEETCARE_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Resource Tracking: {SSS_FLEETCARE_URL}")
        d["fleetcare_latest_point"] = None
        d["fleetcare_latest_point_delay"] = None
        d["success"] = False

    try:
        resp = session.get(CSW_API)
        resp.raise_for_status()
        j = resp.json()
        d["csw_catalogue_count"] = len(j)
    except Exception as e:
        LOGGER.warning(f"Error querying CSW API: {CSW_API}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying CSW API: {CSW_API}")
        d["csw_catalogue_count"] = None
        d["success"] = False

    try:
        # Public service, so we need to send an anonymous request.
        params = {
            "service": "wfs",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeNames": "public:todays_burns",
            "resultType": "hits",
        }
        resp = requests.get(KMI_WFS_URL, params=params)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        resp_d = {i[0]: i[1] for i in root.items()}
        d["todays_burns_count"] = int(resp_d["numberOfFeatures"])
    except Exception as e:
        LOGGER.warning("Error querying KMI WFS (public:todays_burns)")
        LOGGER.warning(e)
        d["errors"].append("Error querying KMI WFS (public:todays_burns)")
        d["todays_burns_count"] = None
        d["success"] = False

    try:
        resp = session.get(KMI_WMTS_URL, params={"request": "getcapabilities"})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
        layers = root.findall(".//wmts:Layer", ns)
        d["kmi_wmts_layer_count"] = len(layers)
    except Exception as e:
        LOGGER.warning("Error querying KMI WMTS layer count")
        LOGGER.warning(e)
        d["errors"].append("Error querying KMI WMTS layer count")
        d["kmi_wmts_layer_count"] = None
        d["success"] = False

    try:
        resp = session.get(BFRS_URL)
        resp.raise_for_status()
        j = resp.json()
        d["bfrs_profile_api_endpoint"] = True
    except Exception as e:
        LOGGER.warning(f"Error querying BFRS API endpoint: {BFRS_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying BFRS API endpoint: {BFRS_URL}")
        d["bfrs_profile_api_endpoint"] = None
        d["success"] = False

    # Common parameters to send with every GetMap request to KMI Geoserver.
    kmi_params = {
        "service": "WMS",
        "version": "1.1.0",
        "request": "GetMap",
        "bbox": "109.3,-40.4,132.6,-6.7",
        "width": "552",
        "height": "768",
        "srs": "EPSG:4326",
        "format": "image/jpeg",
        "layers": None,
    }

    for kmi_layer in [
        DBCA_GOING_BUSHFIRES_LAYER,
        DBCA_CONTROL_LINES_LAYER,
        DFES_GOING_BUSHFIRES_LAYER,
        ALL_CURRENT_HOTSPOTS_LAYER,
        LIGHTNING_24H_LAYER,
        LIGHTNING_24_48H_LAYER,
        LIGHTNING_48_72H_LAYER,
        FUEL_AGE_1_6Y_LAYER,
        FUEL_AGE_NONFOREST_1_6Y_LAYER,
        COG_BASEMAP_LAYER,
        STATE_BASEMAP_LAYER,
        DBCA_BURN_PROGRAM_LAYER,
        DAILY_ACTIVE_BURNS_LAYER,
        DBCA_LANDS_WATERS_LAYER,
        DBCA_LANDS_WATERS_INTEREST_LAYER,
    ]:
        if kmi_layer:
            kmi_params["layers"] = kmi_layer
            prefix = kmi_layer.split(":")[0]
            path = f"{prefix}/wms"
            try:
                url = f"{KMI_URL}/{path}"
                if prefix == "public":
                    resp = requests.get(url, params=kmi_params)
                else:
                    resp = session.get(url, params=kmi_params)
                resp.raise_for_status()
                if "ServiceExceptionReport" in str(resp.content):
                    d[kmi_layer] = False
                    d["success"] = False
                else:
                    d[kmi_layer] = True
            except Exception:
                d[kmi_layer] = False
                d["success"] = False

    try:
        resp = session.get(AUTH2_STATUS_URL)
        resp.raise_for_status()
        j = resp.json()
        d["auth2_status"] = j["healthy"]
    except Exception as e:
        LOGGER.warning(f"Error querying Auth2 status API endpoint: {AUTH2_STATUS_URL}")
        LOGGER.warning(e)
        d["errors"].append(f"Error querying Auth2 status API endpoint: {AUTH2_STATUS_URL}")
        d["auth2_status"] = None
        d["success"] = False

    return d


@app.route("/json")
def healthcheck_json():
    d = healthcheck()
    response.content_type = "application/json"
    if CACHE_RESPONSE:
        # Mark response as "cache for 60 seconds".
        response.set_header("Cache-Control", "max-age=60")

    try:
        return json.dumps(d)
    except Exception as e:
        LOGGER.warning("Error serialising healthcheck response as JSON")
        LOGGER.warning(e)
        return {
            "server_time": datetime.now().astimezone(TZ).isoformat(timespec="seconds"),
            "success": False,
        }


# Retain legacy health check route for PRTG.
@app.route("/legacy")
def index_legacy():
    d = healthcheck()
    output = f"<p>Server time: {d['server_time']}</p>\n"
    output += "<p>\n"

    output += f"Latest tracking point: {d['latest_point']}<br>\n"
    if d["latest_point_delay"] > TRACKING_POINTS_MAX_DELAY:
        output += "Resource Tracking Delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            d["latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Resource Tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            d["latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += f"Latest Iridium tracking point: {d['iridium_latest_point']}<br>\n"
    if d["iridium_latest_point_delay"] > TRACKING_POINTS_MAX_DELAY:
        output += "Iridium tracking delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            d["iridium_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Iridium tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            d["iridium_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += f"Latest Tracplus tracking point: {d['tracplus_latest_point']}<br>\n"
    output += "Tracplus tracking delay currently {0:.1f} min<br>\n".format(
        d["tracplus_latest_point_delay"],
    )

    output += f"Latest DFES tracking point: {d['dfes_latest_point']}<br>\n"
    output += "DFES tracking delay currently {0:.1f} min<br>\n".format(
        d["dfes_latest_point_delay"],
    )

    output += f"Latest Fleetcare tracking point: {d['fleetcare_latest_point']}<br>\n"
    if d["fleetcare_latest_point_delay"] > TRACKING_POINTS_MAX_DELAY:
        output += "Fleetcare tracking delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            d["fleetcare_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Fleetcare tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            d["fleetcare_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += "</p>\n<p>\n"

    if "csw_catalogue_count" in d and d["csw_catalogue_count"]:  # Should be >0
        output += f"CSW spatial catalogue for SSS: {d['csw_catalogue_count']} layers<br>\n"
    else:
        output += "CSW API endpoint: error<br>\n"

    if "todays_burns_count" in d:  # Burns count might be 0
        output += f"Today's burns count (KMI): {d['todays_burns_count']}<br>\n"
    else:
        output += "Today's burns count (KMI): error<br>\n"

    if d["kmi_wmts_layer_count"] and d["kmi_wmts_layer_count"]:  # Should be >0
        output += f"KMI WMTS layer count: {d['kmi_wmts_layer_count']}<br>\n"
    else:
        output += "KMI WMTS GetCapabilities: error<br>\n"

    if d["bfrs_profile_api_endpoint"]:
        output += "BFRS profile API endpoint: OK<br>\n"
    else:
        output += "BFRS profile API endpoint: error<br>\n"

    output += "</p>\n<p>\n"

    if d[DBCA_GOING_BUSHFIRES_LAYER]:
        output += f"DBCA Going Bushfires layer ({DBCA_GOING_BUSHFIRES_LAYER}): OK<br>\n"
    else:
        output += f"DBCA Going Bushfires layer ({DBCA_GOING_BUSHFIRES_LAYER}): error<br>\n"

    if d[DBCA_CONTROL_LINES_LAYER]:
        output += f"DBCA Control Lines layer ({DBCA_CONTROL_LINES_LAYER}): OK<br>\n"
    else:
        output += f"DBCA Control Lines ({DBCA_CONTROL_LINES_LAYER}): error<br>\n"

    if d[DFES_GOING_BUSHFIRES_LAYER]:
        output += f"DFES Going Bushfires layer ({DFES_GOING_BUSHFIRES_LAYER}): OK<br>\n"
    else:
        output += "DFES Going Bushfires layer (DFES_GOING_BUSHFIRES_LAYER): error<br>\n"

    if d[ALL_CURRENT_HOTSPOTS_LAYER]:
        output += f"All current hotspots layer ({ALL_CURRENT_HOTSPOTS_LAYER}): OK<br>\n"
    else:
        output += f"All current hotspots layer ({ALL_CURRENT_HOTSPOTS_LAYER}): error<br>\n"

    if d[LIGHTNING_24H_LAYER]:
        output += f"Lightning 24h layer ({LIGHTNING_24H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 24h layer ({LIGHTNING_24H_LAYER}): error<br>\n"

    if d[LIGHTNING_24_48H_LAYER]:
        output += f"Lightning 24-48h layer ({LIGHTNING_24_48H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 24-48h layer ({LIGHTNING_24_48H_LAYER}): error<br>\n"

    if d[LIGHTNING_48_72H_LAYER]:
        output += f"Lightning 48-72h layer ({LIGHTNING_48_72H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 48-72h layer ({LIGHTNING_48_72H_LAYER}): error<br>\n"

    if d[FUEL_AGE_1_6Y_LAYER]:
        output += f"Fuel age 1-6+ years layer ({FUEL_AGE_1_6Y_LAYER}): OK<br>\n"
    else:
        output += f"Fuel age 1-6+ years layer ({FUEL_AGE_1_6Y_LAYER}): error<br>\n"

    if d[FUEL_AGE_NONFOREST_1_6Y_LAYER]:
        output += f"Fuel age non forest 1-6+ years layer ({FUEL_AGE_NONFOREST_1_6Y_LAYER}): OK<br>\n"
    else:
        output += f"Fuel age non forest 1-6+ years layer ({FUEL_AGE_NONFOREST_1_6Y_LAYER}): error<br>\n"

    if d[COG_BASEMAP_LAYER]:
        output += f"COG basemap layer ({COG_BASEMAP_LAYER}): OK<br>\n"
    else:
        output += f"COG basemap layer ({COG_BASEMAP_LAYER}): error<br>\n"

    if d[STATE_BASEMAP_LAYER]:
        output += f"State basemap layer ({STATE_BASEMAP_LAYER}): OK<br>\n"
    else:
        output += f"State basemap layer ({STATE_BASEMAP_LAYER}): error<br>\n"

    if d[DBCA_BURN_PROGRAM_LAYER]:
        output += f"DBCA burn options program layer ({DBCA_BURN_PROGRAM_LAYER}): OK<br>\n"
    else:
        output += f"DBCA burn options program layer ({DBCA_BURN_PROGRAM_LAYER}): error<br>\n"

    if d[DAILY_ACTIVE_BURNS_LAYER]:
        output += f"Daily active and planned prescribed burns layer ({DAILY_ACTIVE_BURNS_LAYER}): OK<br>\n"
    else:
        output += f"Daily active and planned prescribed burns layer ({DAILY_ACTIVE_BURNS_LAYER}): error<br>\n"

    if d[DBCA_LANDS_WATERS_LAYER]:
        output += f"DBCA legislated lands and waters layer ({DBCA_LANDS_WATERS_LAYER}): OK<br>\n"
    else:
        output += f"DBCA legislated lands and waters layer ({DBCA_LANDS_WATERS_LAYER}): error<br>\n"

    if d[DBCA_LANDS_WATERS_INTEREST_LAYER]:
        output += f"DBCA lands and waters of interest layer ({DBCA_LANDS_WATERS_INTEREST_LAYER}): OK<br>\n"
    else:
        output += f"DBCA lands and waters of interest layer ({DBCA_LANDS_WATERS_INTEREST_LAYER}): error<br>\n"

    output += "</p>\n<p>\n"

    if d["auth2_status"]:
        output += "AUTH2 status: OK<br>\n"
    else:
        output += "AUTH2 status: error<br>\n"

    output += "</p>\n<p>\n"
    if d["success"]:
        output += "<strong>Finished checks, healthcheck succeeded!</strong>"
    else:
        output += "<strong>Finished checks, something is wrong =(</strong>"
    output += "</p>"

    if CACHE_RESPONSE:
        # Mark response as "cache for 60 seconds".
        response.set_header("Cache-Control", "max-age=60")
    return OUTPUT_TEMPLATE.format(output)


@app.route("/favicon.ico", method="GET")
def get_favicon():
    return static_file("favicon.ico", root="static/images/")


@app.route("/")
def index():
    return static_file("index.html", root="templates")


@app.route("/api/resource-tracking-latest")
def resource_tracking_latest():
    session = get_session()

    try:
        trackingdata = session.get(SSS_DEVICES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        seen = humanize.naturaltime(datetime.fromisoformat(trackingdata["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/resource-tracking-delay")
def resource_tracking_delay():
    session = get_session()

    try:
        trackingdata = session.get(SSS_DEVICES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            return f"<button class='pure-button button-error'>>{TRACKING_POINTS_MAX_DELAY} minutes</button>"
        else:
            return f"<button class='pure-button button-success'>≤{TRACKING_POINTS_MAX_DELAY} minutes</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/iridium-latest")
def iridium_latest():
    session = get_session()

    try:
        trackingdata = session.get(SSS_IRIDIUM_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        seen = humanize.naturaltime(datetime.fromisoformat(trackingdata["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/iridium-delay")
def iridium_delay():
    session = get_session()

    try:
        trackingdata = session.get(SSS_IRIDIUM_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            return f"<button class='pure-button button-error'>>{TRACKING_POINTS_MAX_DELAY} minutes</button>"
        else:
            return f"<button class='pure-button button-success'>≤{TRACKING_POINTS_MAX_DELAY} minutes</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/tracplus-latest")
def tracplus_latest():
    session = get_session()

    try:
        trackingdata = session.get(SSS_TRACPLUS_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        seen = humanize.naturaltime(datetime.fromisoformat(trackingdata["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dfes-latest")
def dfes_latest():
    session = get_session()

    try:
        trackingdata = session.get(SSS_DFES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        seen = humanize.naturaltime(datetime.fromisoformat(trackingdata["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/fleetcare-latest")
def fleetcare_latest():
    session = get_session()

    try:
        trackingdata = session.get(SSS_FLEETCARE_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        seen = humanize.naturaltime(datetime.fromisoformat(trackingdata["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/fleetcare-delay")
def fleetcare_delay():
    session = get_session()

    try:
        trackingdata = session.get(SSS_FLEETCARE_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            return f"<button class='pure-button button-error'>>{TRACKING_POINTS_MAX_DELAY} minutes</button>"
        else:
            return f"<button class='pure-button button-success'>≤{TRACKING_POINTS_MAX_DELAY} minutes</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/kmi-wmts-layers")
def kmi_wmts_layers():
    session = get_session()

    try:
        resp = session.get(KMI_WMTS_URL, params={"request": "getcapabilities"})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
        layers = root.findall(".//wmts:Layer", ns)
        layer_count = len(layers)
        return f"<button class='pure-button button-success'>{layer_count} layers</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/csw-layers")
def csw_layers():
    session = get_session()

    try:
        resp = session.get(CSW_API)
        resp.raise_for_status()
        j = resp.json()
        catalogue = len(j)
        return f"<button class='pure-button button-success'>{catalogue} layers</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/bfrs-status")
def bfrs_status():
    session = get_session()

    try:
        resp = session.get(BFRS_URL)
        resp.raise_for_status()
        return "<button class='pure-button button-success'>OK</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/auth2-status")
def auth2_status():
    session = get_session()

    try:
        resp = session.get(AUTH2_STATUS_URL)
        resp.raise_for_status()
        return "<button class='pure-button button-success'>OK</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/todays-burns")
def todays_burns():
    params = {
        "service": "wfs",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeNames": "public:todays_burns",
        "resultType": "hits",
    }

    # Public service, so we need to send an anonymous request.
    try:
        resp = requests.get(KMI_WFS_URL, params=params)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        resp_d = {i[0]: i[1] for i in root.items()}
        todays_burns = int(resp_d["numberOfFeatures"])
        return f"<button class='pure-button button-success'>{todays_burns}</button>"
    except:
        return "<button class='pure-button button-error'>ERROR</button>"


def get_kmi_layer(kmi_layer):
    # Common parameters to send with every GetTile request to KMI Geoserver.
    params = {
        "service": "WMTS",
        "version": "1.0.0",
        "request": "GetTile",
        # These matrix settings are most of the extent of Western Australia.
        "tilematrixset": "mercator",
        "tilematrix": "mercator:4",
        "tilecol": "13",
        "tilerow": "9",
        "format": "image/png",
        "layer": kmi_layer,
    }

    prefix = kmi_layer.split(":")[0]

    try:
        if prefix == "public":
            resp = requests.get(KMI_WMTS_URL, params=params)
        else:
            session = get_session()
            resp = session.get(KMI_WMTS_URL, params=params)
        resp.raise_for_status()
        if "ServiceExceptionReport" in str(resp.content):
            return False
        return True
    except:
        return False


@app.route("/api/dbca-going-bushfires")
def dbca_going_bushfires():
    if get_kmi_layer(DBCA_GOING_BUSHFIRES_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dbca-control-lines")
def dbca_control_lines():
    if get_kmi_layer(DBCA_CONTROL_LINES_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dfes-going-bushfires")
def dfes_going_bushfires():
    if get_kmi_layer(DFES_GOING_BUSHFIRES_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/current-hotspots")
def current_hotspots():
    if get_kmi_layer(ALL_CURRENT_HOTSPOTS_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/lightning-24h")
def lightning_24h():
    if get_kmi_layer(LIGHTNING_24H_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/lightning-24-48h")
def lightning_24_48h():
    if get_kmi_layer(LIGHTNING_24_48H_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/lightning-48-72h")
def lightning_48_72h():
    if get_kmi_layer(LIGHTNING_48_72H_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/fuel-age-1-6y")
def fuel_age_1_6y():
    if get_kmi_layer(FUEL_AGE_1_6Y_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/fuel-age-nonforest-1-6y")
def fuel_age_nonforest_1_6y():
    if get_kmi_layer(FUEL_AGE_NONFOREST_1_6Y_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/cog-basemap")
def cog_basemap():
    if get_kmi_layer(COG_BASEMAP_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/state-basemap")
def state_basemap():
    if get_kmi_layer(STATE_BASEMAP_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dbca-burn-program")
def dbca_burn_program():
    if get_kmi_layer(DBCA_BURN_PROGRAM_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/daily-active-burns")
def daily_active_burns():
    if get_kmi_layer(DAILY_ACTIVE_BURNS_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dbca-lands-waters")
def dbca_land_waters():
    if get_kmi_layer(DBCA_LANDS_WATERS_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/dbca-lands-waters-interest")
def dbca_land_waters_interest():
    if get_kmi_layer(DBCA_LANDS_WATERS_INTEREST_LAYER):
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return "<button class='pure-button button-error'>ERROR</button>"


if __name__ == "__main__":
    from bottle import run

    run(
        application,
        host="0.0.0.0",
        port=os.environ.get("PORT", 8080),
        reloader=True,
    )
