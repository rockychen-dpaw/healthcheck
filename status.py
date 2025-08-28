import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ET
import httpx
import humanize
from quart import Quart, jsonify, make_response, render_template

dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()
TZ = ZoneInfo(os.environ.get("TZ", "Australia/Perth"))
DEBUG = os.getenv("DEBUG", False)
app = application = Quart(__name__, template_folder="templates", static_folder="static")
app.config.from_mapping(DEBUG=DEBUG, TZ=TZ)


# Configure logging.
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
formatter = logging.Formatter("{asctime} | {levelname} | {message}", style="{")
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

# Set Cache-Control headers or not.
CACHE_RESPONSE = os.getenv("CACHE_RESPONSE", True)


# Credentials for authenticated endpoints (required).
USER_SSO = os.getenv("USER_SSO")
PASS_SSO = os.getenv("PASS_SSO")
if not USER_SSO or not PASS_SSO:
    raise ValueError("Missing USER_SSO or PASS_SSO environment variables")

# Response endpoint URLS.
RT_URL = os.environ.get("RT_URL", "https://resourcetracking.dbca.wa.gov.au")
TRACKING_POINTS_MAX_DELAY = int(os.environ.get("TRACKING_POINTS_MAX_DELAY", 30))  # Minutes
RT_DEVICES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&format=json"
RT_IRIDIUM_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=iriditrak&format=json"
RT_IRIDIUM_METRICS_URL = RT_URL + "/api/devices/metrics/iriditrak/"
RT_TRACPLUS_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=tracplus&format=json"
RT_TRACPLUS_METRICS_URL = RT_URL + "/api/devices/metrics/tracplus/"
RT_DFES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=dfes&format=json"
RT_DFES_METRICS_URL = RT_URL + "/api/devices/metrics/dfes/"
RT_FLEETCARE_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=fleetcare&format=json"
RT_FLEETCARE_METRICS_URL = RT_URL + "/api/devices/metrics/fleetcare/"
RT_NETSTAR_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=netstar&format=json"
RT_NETSTAR_METRICS_URL = RT_URL + "/api/devices/metrics/netstar/"
CSW_API = os.environ.get("CSW_API", "https://csw.dbca.wa.gov.au/catalogue/api/records/?format=json&application__name=sss")
KMI_URL = os.environ.get("KMI_URL", "https://kmi.dbca.wa.gov.au/geoserver")
KMI_WFS_URL = f"{KMI_URL}/ows"
KMI_WMTS_URL = f"{KMI_URL}/gwc/service/wmts"
BFRS_URL = os.environ.get("BFRS_URL", "https://bfrs.dbca.wa.gov.au/api/v1/profile/?format=json")
AUTH2_STATUS_URL = os.environ.get("AUTH2_STATUS_URL", "https://auth2.dbca.wa.gov.au/status")

# Spatial data layer names.
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


async def get_session(timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(auth=(USER_SSO, PASS_SSO), timeout=timeout)


async def fetch_data(session, url, error_list, source_desc) -> Optional[Dict[str, Any]]:
    """Convenience function to query an authenticated endpoint, parse and return JSON."""
    try:
        resp = await session.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data
    except:
        LOGGER.exception(f"Error while querying {source_desc}: {url}")
        error_list.append(f"Error while querying {source_desc}: {url}")
        return None


async def get_healthcheck() -> Dict[str, Any]:
    """Query HTTP sources and return a dictionary of response successes."""
    session = await get_session()
    d = {"server_time": datetime.now().astimezone(TZ).isoformat(timespec="seconds"), "success": True, "errors": []}

    # All tracking device types delay.
    source_desc = "All Resource Tracking devices"
    data = await fetch_data(session, RT_DEVICES_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["latest_point"] = t.isoformat()
        d["latest_point_age_min"] = data["objects"][0]["age_minutes"]
        # The age of the first logged point returned from this endpoint exceeding the maximum delay triggers failure.
        if data["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
            d["errors"].append(f"{source_desc} exceeds max delay {TRACKING_POINTS_MAX_DELAY}")
    else:
        # No return data from this endpoint triggers failure.
        d["latest_point"] = None
        d["latest_point_age_min"] = None
        d["success"] = False

    # Iridium device delay.
    source_desc = "Iridium devices"
    data = await fetch_data(session, RT_IRIDIUM_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["iridium_latest_point"] = t.isoformat()
        d["iridium_latest_point_age_min"] = data["objects"][0]["age_minutes"]
        # The age of the first logged point returned from this endpoint exceeding the maximum delay triggers failure.
        if data["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
            d["errors"].append(f"{source_desc} exceeds max delay {TRACKING_POINTS_MAX_DELAY}")
    else:
        d["iridium_latest_point"] = None
        d["iridium_latest_point_age_min"] = None

    # Iridium device metrics.
    source_desc = "Iridium device metrics"
    data = await fetch_data(session, RT_IRIDIUM_METRICS_URL, d["errors"], source_desc)
    if data:
        d["iridium_loggedpoint_rate_min"] = int(data["logged_point_count"] / data["minutes"])
    else:
        d["iridium_loggedpoint_rate_min"] = None

    # TracPlus device delay (no max age).
    source_desc = "TracPlus devices"
    data = await fetch_data(session, RT_TRACPLUS_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["tracplus_latest_point"] = t.isoformat()
        d["tracplus_latest_point_delay"] = data["objects"][0]["age_minutes"]
    else:
        d["tracplus_latest_point"] = None
        d["tracplus_latest_point_delay"] = None

    # TracPlus device metrics.
    source_desc = "TracPlus device metrics"
    data = await fetch_data(session, RT_TRACPLUS_METRICS_URL, d["errors"], source_desc)
    if data:
        d["tracplus_loggedpoint_rate_min"] = int(data["logged_point_count"] / data["minutes"])
    else:
        d["tracplus_loggedpoint_rate_min"] = None

    # DFES device delay (no max age).
    source_desc = "DFES devices"
    data = await fetch_data(session, RT_DFES_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["dfes_latest_point"] = t.isoformat()
        d["dfes_latest_point_delay"] = data["objects"][0]["age_minutes"]
    else:
        d["dfes_latest_point"] = None
        d["dfes_latest_point_delay"] = None

    # DFES device metrics.
    source_desc = "DFES device metrics"
    data = await fetch_data(session, RT_DFES_METRICS_URL, d["errors"], source_desc)
    if data:
        d["dfes_loggedpoint_rate_min"] = int(data["logged_point_count"] / data["minutes"])
    else:
        d["dfes_loggedpoint_rate_min"] = None

    # Fleetcare device delay.
    source_desc = "Fleetcare devices"
    data = await fetch_data(session, RT_FLEETCARE_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["fleetcare_latest_point"] = t.isoformat()
        d["fleetcare_latest_point_delay"] = data["objects"][0]["age_minutes"]
        # The age of the first logged point returned from this endpoint exceeding the maximum delay triggers failure.
        if data["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            d["success"] = False
            d["errors"].append(f"{source_desc} exceeds max delay {TRACKING_POINTS_MAX_DELAY}")
    else:
        d["fleetcare_latest_point"] = None
        d["fleetcare_latest_point_delay"] = None

    # Fleetcare device metrics.
    source_desc = "Fleetcare device metrics"
    data = await fetch_data(session, RT_FLEETCARE_METRICS_URL, d["errors"], source_desc)
    if data:
        d["fleetcare_loggedpoint_rate_min"] = int(data["logged_point_count"] / data["minutes"])
    else:
        d["fleetcare_loggedpoint_rate_min"] = None

    # Netstar device delay (no max age).
    source_desc = "Netstar devices"
    data = await fetch_data(session, RT_NETSTAR_URL, d["errors"], source_desc)
    if data:
        t = datetime.fromisoformat(data["objects"][0]["seen"]).astimezone(TZ)
        d["netstar_latest_point"] = t.isoformat()
        d["netstar_latest_point_delay"] = data["objects"][0]["age_minutes"]
    else:
        d["netstar_latest_point"] = None
        d["netstar_latest_point_delay"] = None

    # Netstar device metrics.
    source_desc = "Netstar device metrics"
    data = await fetch_data(session, RT_NETSTAR_METRICS_URL, d["errors"], source_desc)
    if data:
        d["netstar_loggedpoint_rate_min"] = int(data["logged_point_count"] / data["minutes"])
    else:
        d["netstar_loggedpoint_rate_min"] = None

    # CSW API response.
    source_desc = "CSW API endpoint"
    data = await fetch_data(session, CSW_API, d["errors"], source_desc)
    if data:
        d["csw_catalogue_count"] = len(data)
    else:
        # No response from this endpoint triggers failure.
        d["csw_catalogue_count"] = None
        d["success"] = False

    # KMI WFS: Today's Burns layer (anonymous request).
    try:
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": "public:todays_burns",
            "maxFeatures": 1,
            "outputFormat": "application/json",
        }
        resp = httpx.get(KMI_WFS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        d["todays_burns_count"] = data["totalFeatures"]
    except:
        LOGGER.exception("Error querying KMI WFS (public:todays_burns)")
        d["errors"].append("Error querying KMI WFS (public:todays_burns)")
        d["todays_burns_count"] = None
        d["success"] = False

    # KMI WMTS GetCapabilities endpoint.
    try:
        resp = await session.get(KMI_WMTS_URL, params={"request": "getcapabilities"})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
        # Parse the XML response.
        layers = root.findall(".//wmts:Layer", ns)
        d["kmi_wmts_layer_count"] = len(layers)
    except Exception as e:
        LOGGER.warning("Error querying KMI WMTS layer count")
        LOGGER.warning(e)
        d["errors"].append("Error querying KMI WMTS layer count")
        d["kmi_wmts_layer_count"] = None
        d["success"] = False

    # BFRS API response.
    source_desc = "BFRS API endpoint"
    data = await fetch_data(session, BFRS_URL, d["errors"], source_desc)
    if data:
        d["bfrs_profile_api_endpoint"] = True
    else:
        # No response from this endpoint triggers failure.
        d["bfrs_profile_api_endpoint"] = None
        d["success"] = False

    # Common parameters to send with every GetMap request to KMI Geoserver.
    kmi_params = {
        "service": "WMS",
        "version": "1.1.0",
        "request": "GetMap",
        # Bounding box covers WA:
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
                    resp = httpx.get(url, params=kmi_params)
                else:
                    resp = await session.get(url, params=kmi_params)
                resp.raise_for_status()
                if "ServiceExceptionReport" in str(resp.content):
                    d[kmi_layer] = False
                    d["success"] = False
                    d["errors"].append(f"Error querying KMI layer {kmi_layer}")
                else:
                    d[kmi_layer] = True
            except Exception:
                d[kmi_layer] = False
                d["success"] = False

    # Auth2 status response.
    source_desc = "Auth2 status API endpoint"
    data = await fetch_data(session, AUTH2_STATUS_URL, d["errors"], source_desc)
    if data:
        d["auth2_status"] = data["healthy"]
    else:
        # No response from this endpoint triggers failure.
        d["auth2_status"] = None
        d["success"] = False

    return d


@app.route("/readyz")
async def readiness():
    return "OK"


@app.route("/livez")
async def liveness():
    return "OK"


@app.route("/json")
async def healthcheck_json():
    try:
        data = await get_healthcheck()
        response = jsonify(data)
        if CACHE_RESPONSE:
            # Mark response as "cache for 60 seconds".
            response.headers["Cache-Control"] = "max-age=60"
        return response
    except:
        LOGGER.exception("Error serialising healthcheck response as JSON")
        return jsonify(
            {
                "server_time": datetime.now().astimezone(TZ).isoformat(timespec="seconds"),
                "success": False,
            }
        )


# Retain legacy health check route for PRTG.
@app.route("/legacy")
async def index_legacy():
    data = await get_healthcheck()
    output = f"<p>Server time: {data['server_time']}</p>\n"
    output += "<p>\n"

    output += f"Latest tracking point: {data['latest_point']}<br>\n"
    if data["latest_point_age_min"] > TRACKING_POINTS_MAX_DELAY:
        output += "Resource Tracking Delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            data["latest_point_age_min"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Resource Tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            data["latest_point_age_min"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += f"Latest Iridium tracking point: {data['iridium_latest_point']}<br>\n"
    if data["iridium_latest_point_age_min"] > TRACKING_POINTS_MAX_DELAY:
        output += "Iridium tracking delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            data["iridium_latest_point_age_min"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Iridium tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            data["iridium_latest_point_age_min"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += f"Latest Tracplus tracking point: {data['tracplus_latest_point']}<br>\n"
    output += "Tracplus tracking delay currently {0:.1f} min<br>\n".format(
        data["tracplus_latest_point_delay"],
    )

    output += f"Latest DFES tracking point: {data['dfes_latest_point']}<br>\n"
    output += "DFES tracking delay currently {0:.1f} min<br>\n".format(
        data["dfes_latest_point_delay"],
    )

    output += f"Latest Fleetcare tracking point: {data['fleetcare_latest_point']}<br>\n"
    if data["fleetcare_latest_point_delay"] > TRACKING_POINTS_MAX_DELAY:
        output += "Fleetcare tracking delay too high! Currently {0:.1f} min (max {1} min)<br>\n".format(
            data["fleetcare_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )
    else:
        output += "Fleetcare tracking delay currently {0:.1f} min (max {1} min)<br>\n".format(
            data["fleetcare_latest_point_delay"],
            TRACKING_POINTS_MAX_DELAY,
        )

    output += "</p>\n<p>\n"

    if "csw_catalogue_count" in data and data["csw_catalogue_count"]:  # Should be >0
        output += f"CSW spatial catalogue for SSS: {data['csw_catalogue_count']} layers<br>\n"
    else:
        output += "CSW API endpoint: error<br>\n"

    if "todays_burns_count" in data:  # Burns count might be 0
        output += f"Today's burns count (KMI): {data['todays_burns_count']}<br>\n"
    else:
        output += "Today's burns count (KMI): error<br>\n"

    if data["kmi_wmts_layer_count"] and data["kmi_wmts_layer_count"]:  # Should be >0
        output += f"KMI WMTS layer count: {data['kmi_wmts_layer_count']}<br>\n"
    else:
        output += "KMI WMTS GetCapabilities: error<br>\n"

    if data["bfrs_profile_api_endpoint"]:
        output += "BFRS profile API endpoint: OK<br>\n"
    else:
        output += "BFRS profile API endpoint: error<br>\n"

    output += "</p>\n<p>\n"

    if data[DBCA_GOING_BUSHFIRES_LAYER]:
        output += f"DBCA Going Bushfires layer ({DBCA_GOING_BUSHFIRES_LAYER}): OK<br>\n"
    else:
        output += f"DBCA Going Bushfires layer ({DBCA_GOING_BUSHFIRES_LAYER}): error<br>\n"

    if data[DBCA_CONTROL_LINES_LAYER]:
        output += f"DBCA Control Lines layer ({DBCA_CONTROL_LINES_LAYER}): OK<br>\n"
    else:
        output += f"DBCA Control Lines ({DBCA_CONTROL_LINES_LAYER}): error<br>\n"

    if data[DFES_GOING_BUSHFIRES_LAYER]:
        output += f"DFES Going Bushfires layer ({DFES_GOING_BUSHFIRES_LAYER}): OK<br>\n"
    else:
        output += "DFES Going Bushfires layer (DFES_GOING_BUSHFIRES_LAYER): error<br>\n"

    if data[ALL_CURRENT_HOTSPOTS_LAYER]:
        output += f"All current hotspots layer ({ALL_CURRENT_HOTSPOTS_LAYER}): OK<br>\n"
    else:
        output += f"All current hotspots layer ({ALL_CURRENT_HOTSPOTS_LAYER}): error<br>\n"

    if data[LIGHTNING_24H_LAYER]:
        output += f"Lightning 24h layer ({LIGHTNING_24H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 24h layer ({LIGHTNING_24H_LAYER}): error<br>\n"

    if data[LIGHTNING_24_48H_LAYER]:
        output += f"Lightning 24-48h layer ({LIGHTNING_24_48H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 24-48h layer ({LIGHTNING_24_48H_LAYER}): error<br>\n"

    if data[LIGHTNING_48_72H_LAYER]:
        output += f"Lightning 48-72h layer ({LIGHTNING_48_72H_LAYER}): OK<br>\n"
    else:
        output += f"Lightning 48-72h layer ({LIGHTNING_48_72H_LAYER}): error<br>\n"

    if data[FUEL_AGE_1_6Y_LAYER]:
        output += f"Fuel age 1-6+ years layer ({FUEL_AGE_1_6Y_LAYER}): OK<br>\n"
    else:
        output += f"Fuel age 1-6+ years layer ({FUEL_AGE_1_6Y_LAYER}): error<br>\n"

    if data[FUEL_AGE_NONFOREST_1_6Y_LAYER]:
        output += f"Fuel age non forest 1-6+ years layer ({FUEL_AGE_NONFOREST_1_6Y_LAYER}): OK<br>\n"
    else:
        output += f"Fuel age non forest 1-6+ years layer ({FUEL_AGE_NONFOREST_1_6Y_LAYER}): error<br>\n"

    if data[COG_BASEMAP_LAYER]:
        output += f"COG basemap layer ({COG_BASEMAP_LAYER}): OK<br>\n"
    else:
        output += f"COG basemap layer ({COG_BASEMAP_LAYER}): error<br>\n"

    if data[STATE_BASEMAP_LAYER]:
        output += f"State basemap layer ({STATE_BASEMAP_LAYER}): OK<br>\n"
    else:
        output += f"State basemap layer ({STATE_BASEMAP_LAYER}): error<br>\n"

    if data[DBCA_BURN_PROGRAM_LAYER]:
        output += f"DBCA burn options program layer ({DBCA_BURN_PROGRAM_LAYER}): OK<br>\n"
    else:
        output += f"DBCA burn options program layer ({DBCA_BURN_PROGRAM_LAYER}): error<br>\n"

    if data[DAILY_ACTIVE_BURNS_LAYER]:
        output += f"Daily active and planned prescribed burns layer ({DAILY_ACTIVE_BURNS_LAYER}): OK<br>\n"
    else:
        output += f"Daily active and planned prescribed burns layer ({DAILY_ACTIVE_BURNS_LAYER}): error<br>\n"

    if data[DBCA_LANDS_WATERS_LAYER]:
        output += f"DBCA legislated lands and waters layer ({DBCA_LANDS_WATERS_LAYER}): OK<br>\n"
    else:
        output += f"DBCA legislated lands and waters layer ({DBCA_LANDS_WATERS_LAYER}): error<br>\n"

    if data[DBCA_LANDS_WATERS_INTEREST_LAYER]:
        output += f"DBCA lands and waters of interest layer ({DBCA_LANDS_WATERS_INTEREST_LAYER}): OK<br>\n"
    else:
        output += f"DBCA lands and waters of interest layer ({DBCA_LANDS_WATERS_INTEREST_LAYER}): error<br>\n"

    output += "</p>\n<p>\n"

    if data["auth2_status"]:
        output += "AUTH2 status: OK<br>\n"
    else:
        output += "AUTH2 status: error<br>\n"

    output += "</p>\n<p>\n"
    if data["success"]:
        output += "<strong>Finished checks, healthcheck succeeded!</strong>"
    else:
        output += "<strong>Finished checks, something is wrong =(</strong>"
    output += "</p>"

    output_html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <title>DBCA Spatial Support System health checks</title>
    <meta name="description" content="DBCA Spatial Support System health checks">
    </head>
    <body>
    <h1>DBCA Spatial Support System health checks</h1>
    {output}
    </body>
    </html>"""
    response = await make_response(output_html)

    if CACHE_RESPONSE:
        # Mark response as "cache for 60 seconds".
        response.headers["Cache-Control"] = "max-age=60"

    return response


@app.route("/")
async def index():
    """The root view returns a static page which queries API endpoints asynchronously and renders the result."""
    return await render_template("index.html")


ERROR_BUTTON_HTML = "<button class='pure-button button-error'>ERROR</button>"


@app.route("/api/<source>/latest")
async def api_source_latest(source):
    session = await get_session()

    endpoint_map = {
        "all-sources": RT_DEVICES_URL,
        "iridium": RT_IRIDIUM_URL,
        "tracplus": RT_TRACPLUS_URL,
        "dfes": RT_DFES_URL,
        "fleetcare": RT_FLEETCARE_URL,
        "netstar": RT_NETSTAR_URL,
    }

    try:
        resp = await session.get(endpoint_map[source])
        resp.raise_for_status()
        data = resp.json()
        seen = humanize.naturaltime(datetime.fromisoformat(data["objects"][0]["seen"]))
        return f"<button class='pure-button button-success'>{seen}</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/<source>/loggedpoint-rate")
async def api_source_loggedpoint_rate(source):
    session = await get_session()

    endpoint_map = {
        "iridium": RT_IRIDIUM_METRICS_URL,
        "tracplus": RT_TRACPLUS_METRICS_URL,
        "dfes": RT_DFES_METRICS_URL,
        "fleetcare": RT_FLEETCARE_METRICS_URL,
        "netstar": RT_NETSTAR_METRICS_URL,
    }

    try:
        resp = await session.get(endpoint_map[source])
        resp.raise_for_status()
        data = resp.json()
        loggedpoint_rate = int(data["logged_point_count"] / data["minutes"])
        if loggedpoint_rate < 1:
            loggedpoint_rate = "<1"
        return f"<button class='pure-button button-success'>{loggedpoint_rate} points/min</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/<source>/delay")
async def api_source_delay(source):
    session = await get_session()

    endpoint_map = {
        "all-sources": RT_DEVICES_URL,
        "iridium": RT_IRIDIUM_URL,
        "fleetcare": RT_FLEETCARE_URL,
    }

    try:
        trackingdata = await session.get(endpoint_map[source])
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            return f"<button class='pure-button button-error'>>{TRACKING_POINTS_MAX_DELAY} min</button>"
        else:
            return f"<button class='pure-button button-success'>≤{TRACKING_POINTS_MAX_DELAY} min</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/kmi-wmts-layers")
async def api_kmi_wmts_layers():
    session = await get_session()

    try:
        resp = await session.get(KMI_WMTS_URL, params={"request": "getcapabilities"})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
        layers = root.findall(".//wmts:Layer", ns)
        layer_count = len(layers)
        return f"<button class='pure-button button-success'>{layer_count} layers</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/csw-layers")
async def api_csw_layers():
    session = await get_session()

    try:
        resp = await session.get(CSW_API)
        resp.raise_for_status()
        j = resp.json()
        catalogue = len(j)
        return f"<button class='pure-button button-success'>{catalogue} layers</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/bfrs-status")
async def api_bfrs_status():
    session = await get_session()

    try:
        resp = await session.get(BFRS_URL)
        resp.raise_for_status()
        return "<button class='pure-button button-success'>OK</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/auth2-status")
async def api_auth2_status():
    session = await get_session()

    try:
        resp = await session.get(AUTH2_STATUS_URL)
        resp.raise_for_status()
        return "<button class='pure-button button-success'>OK</button>"
    except:
        return ERROR_BUTTON_HTML


@app.route("/api/todays-burns")
async def api_todays_burns():
    params = {
        "service": "wfs",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeNames": "public:todays_burns",
        "resultType": "hits",
    }

    # Public service, so we need to send an anonymous request.
    try:
        resp = httpx.get(KMI_WFS_URL, params=params)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        resp_d = {i[0]: i[1] for i in root.items()}
        todays_burns = int(resp_d["numberOfFeatures"])
        return f"<button class='pure-button button-success'>{todays_burns}</button>"
    except:
        return ERROR_BUTTON_HTML


async def get_kmi_layer(kmi_layer) -> bool:
    """Query KMI WMTS and return boolean if the service responds or not."""
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
            resp = httpx.get(KMI_WMTS_URL, params=params)
        else:
            session = await get_session()
            resp = await session.get(KMI_WMTS_URL, params=params)
        resp.raise_for_status()
        if "ServiceExceptionReport" in str(resp.content):
            return False
        return True
    except:
        return False


@app.route("/api/kmi/<kmi_layer>")
async def api_kmi_layer_responds(kmi_layer):
    layer_map = {
        "dbca-going-bushfires": DBCA_GOING_BUSHFIRES_LAYER,
        "dbca-control-lines": DBCA_CONTROL_LINES_LAYER,
        "dfes-going-bushfires": DFES_GOING_BUSHFIRES_LAYER,
        "current-hotspots": ALL_CURRENT_HOTSPOTS_LAYER,
        "lightning-24h": LIGHTNING_24H_LAYER,
        "lightning-24-48h": LIGHTNING_24_48H_LAYER,
        "lightning-48-72h": LIGHTNING_48_72H_LAYER,
        "fuel-age-1-6y": FUEL_AGE_1_6Y_LAYER,
        "fuel-age-nonforest-1-6y": FUEL_AGE_NONFOREST_1_6Y_LAYER,
        "cog-basemap": COG_BASEMAP_LAYER,
        "state-basemap": STATE_BASEMAP_LAYER,
        "dbca-burn-program": DBCA_BURN_PROGRAM_LAYER,
        "daily-active-burns": DAILY_ACTIVE_BURNS_LAYER,
        "dbca-lands-waters": DBCA_LANDS_WATERS_LAYER,
        "dbca-lands-waters-interest": DBCA_LANDS_WATERS_INTEREST_LAYER,
    }
    kmi_resp = await get_kmi_layer(layer_map[kmi_layer])
    if kmi_resp:
        return "<button class='pure-button button-success'>OK</button>"
    else:
        return ERROR_BUTTON_HTML


if __name__ == "__main__":
    application.run(host="0.0.0.0", port=os.environ.get("PORT", 8080), use_reloader=True)
