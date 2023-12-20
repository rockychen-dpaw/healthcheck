from bottle import Bottle, static_file, response
from datetime import datetime
import json
import os
import requests
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv
    load_dotenv()
app = application = Bottle()


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
RT_URL = os.environ.get("RT_URL", "https://resourcetracking.dbca.wa.gov.au")
SSS_DEVICES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&format=json"
SSS_IRIDIUM_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=iriditrak&format=json"
SSS_TRACPLUS_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=tracplus&format=json"
SSS_DFES_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=dfes&format=json"
SSS_FLEETCARE_URL = RT_URL + "/api/v1/device/?seen__isnull=false&source_device_type=fleetcare&format=json"
CSW_API = os.environ.get("CSW_API", "https://csw.dbca.wa.gov.au/catalogue/api/records/?format=json&application__name=sss")
KMI_URL = os.environ.get("KMI_URL", "https://kmi.dbca.wa.gov.au/geoserver")
KMI_WFS_URL = f"{KMI_URL}/wfs"
KMI_WMTS_URL = f"{KMI_URL}/public/gwc/service/wmts"
BFRS_URL = os.environ.get("BFRS_URL", "https://bfrs.dbca.wa.gov.au/api/v1/profile/?format=json")
AUTH2_URL = os.environ.get("AUTH2_URL", "https://auth2.dbca.wa.gov.au/healthcheck")
AUTH2_STATUS_URL = os.environ.get("AUTH2_URL", "https://auth2.dbca.wa.gov.au/status")
USER_SSO = os.environ.get("USER_SSO", "asi@dbca.wa.gov.au")
PASS_SSO = os.environ.get("PASS_SSO", "password")
TRACKING_POINTS_MAX_DELAY = int(os.environ.get("TRACKING_POINTS_MAX_DELAY", 30))  # Minutes
DBCA_GOING_BUSHFIRES_URL = os.environ.get("DBCA_GOING_BUSHFIRES_URL", None)
DBCA_CONTROL_LINES_URL = os.environ.get("DBCA_CONTROL_LINES_URL", None)
DFES_GOING_BUSHFIRES_URL = os.environ.get("DFES_GOING_BUSHFIRES_URL", None)
ALL_CURRENT_HOTSPOTS = os.environ.get("ALL_CURRENT_HOTSPOTS", None)
LIGHTNING_24H = os.environ.get("LIGHTNING_24H", None)
LIGHTNING_24_48H = os.environ.get("LIGHTNING_24_48H", None)
LIGHTNING_48_72H = os.environ.get("LIGHTNING_48_72H", None)
FUEL_AGE_1_6Y = os.environ.get("FUEL_AGE_1_6Y", None)
FUEL_AGE_NONFOREST_1_6Y = os.environ.get("FUEL_AGE_NONFOREST_1_6Y", None)
COG_BASEMAP = os.environ.get("COG_BASEMAP", None)
STATE_BASEMAP = os.environ.get("STATE_BASEMAP", None)
DBCA_BURN_PROGRAM = os.environ.get("DBCA_BURN_PROGRAM", None)
DAILY_ACTIVE_BURNS = os.environ.get("DAILY_ACTIVE_BURNS", None)
DBCA_LANDS_WATERS = os.environ.get("DBCA_LANDS_WATERS", None)
DBCA_LANDS_WATERS_INTEREST = os.environ.get("DBCA_LANDS_WATERS_INTEREST", None)


@app.route("/readiness")
def readiness():
    return "OK"


@app.route("/liveness")
def liveness():
    return "OK"


def healthcheck():
    """Query HTTP sources and derive a dictionary of response successes.
    """
    d = {
        "server_time": datetime.now().astimezone(TZ).isoformat(timespec="seconds"),
        "success": True,
    }

    session = requests.Session()
    session.auth = (USER_SSO, PASS_SSO)

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
        d["success"] = False

    try:
        trackingdata = session.get(SSS_TRACPLUS_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["tracplus_latest_point"] = t.isoformat()
        d["tracplus_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
    except Exception as e:
        d["success"] = False

    try:
        trackingdata = session.get(SSS_DFES_URL)
        trackingdata.raise_for_status()
        trackingdata = trackingdata.json()
        t = datetime.fromisoformat(trackingdata["objects"][0]["seen"]).astimezone(TZ)
        d["dfes_latest_point"] = t.isoformat()
        d["dfes_latest_point_delay"] = trackingdata["objects"][0]["age_minutes"]
    except Exception as e:
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
        d["success"] = False

    try:
        resp = session.get(CSW_API)
        resp.raise_for_status()
        j = resp.json()
        d["csw_catalogue_count"] = len(j)
    except Exception as e:
        d["success"] = False

    try:
        params = {"service": "wfs", "version": "1.1.0", "request": "GetFeature", "typeNames": "public:todays_burns", "resultType": "hits"}
        # Send an anonymous request.
        resp = requests.get(KMI_WFS_URL, params=params)
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        resp_d = {i[0]: i[1] for i in root.items()}
        d["todays_burns_count"] = int(resp_d["numberOfFeatures"])
    except Exception as e:
        d["success"] = False

    try:
        # Send an anonymous request.
        resp = requests.get(KMI_WMTS_URL, params={"request": "getcapabilities"})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
        layers = root.findall(".//wmts:Layer", ns)
        d["kmi_wmts_layer_count"] = len(layers)
    except Exception as e:
        d["success"] = False

    try:
        resp = session.get(BFRS_URL)
        resp.raise_for_status()
        j = resp.json()
        d["bfrs_profile_api_endpoint"] = True
    except Exception as e:
        d["success"] = False

    if DBCA_GOING_BUSHFIRES_URL:
        try:
            url = f"{KMI_URL}/{DBCA_GOING_BUSHFIRES_URL}"
            resp = session.get(url)
            resp.raise_for_status()
            d["dbca_going_bushfires_layer"] = True
        except Exception as e:
            d["dbca_going_bushfires_layer"] = False
            d["success"] = False

    if DBCA_CONTROL_LINES_URL:
        try:
            url = f"{KMI_URL}/{DBCA_CONTROL_LINES_URL}"
            resp = session.get(url)
            resp.raise_for_status()
            d["dbca_control_lines_layer"] = True
        except Exception as e:
            d["dbca_control_lines_layer"] = False
            d["success"] = False

    if DFES_GOING_BUSHFIRES_URL:
        try:
            url = f"{KMI_URL}/{DFES_GOING_BUSHFIRES_URL}"
            resp = session.get(url)
            resp.raise_for_status()
            d["dfes_going_bushfires_layer"] = True
        except Exception as e:
            d["dfes_going_bushfires_layer"] = False
            d["success"] = False

    if ALL_CURRENT_HOTSPOTS:
        try:
            url = f"{KMI_URL}/{ALL_CURRENT_HOTSPOTS}"
            resp = session.get(url)
            resp.raise_for_status()
            d["all_current_hotspots_layer"] = True
        except Exception as e:
            d["all_current_hotspots_layer"] = False
            d["success"] = False

    if LIGHTNING_24H:
        try:
            url = f"{KMI_URL}/{LIGHTNING_24H}"
            resp = session.get(url)
            resp.raise_for_status()
            d["lightning_24h_layer"] = True
        except Exception as e:
            d["lightning_24h_layer"] = False
            d["success"] = False

    if LIGHTNING_24_48H:
        try:
            url = f"{KMI_URL}/{LIGHTNING_24_48H}"
            resp = session.get(url)
            resp.raise_for_status()
            d["lightning_24_48h_layer"] = True
        except Exception as e:
            d["lightning_24_48h_layer"] = False
            d["success"] = False

    if LIGHTNING_48_72H:
        try:
            url = f"{KMI_URL}/{LIGHTNING_48_72H}"
            resp = session.get(url)
            resp.raise_for_status()
            d["lightning_48_72h_layer"] = True
        except Exception as e:
            d["lightning_48_72h_layer"] = False
            d["success"] = False

    if FUEL_AGE_1_6Y:
        try:
            url = f"{KMI_URL}/{FUEL_AGE_1_6Y}"
            resp = session.get(url)
            resp.raise_for_status()
            d["fuel_age_1_6y_layer"] = True
        except Exception as e:
            d["fuel_age_1_6y_layer"] = False
            d["success"] = False

    if FUEL_AGE_NONFOREST_1_6Y:
        try:
            url = f"{KMI_URL}/{FUEL_AGE_NONFOREST_1_6Y}"
            resp = session.get(url)
            resp.raise_for_status()
            d["fuel_age_nonforest_1_6y_layer"] = True
        except Exception as e:
            d["fuel_age_nonforest_1_6y_layer"] = False
            d["success"] = False

    if COG_BASEMAP:
        try:
            url = f"{KMI_URL}/{COG_BASEMAP}"
            resp = session.get(url)
            resp.raise_for_status()
            d["cog_basemap_layer"] = True
        except Exception as e:
            d["cog_basemap_layer"] = False
            d["success"] = False

    if STATE_BASEMAP:
        try:
            url = f"{KMI_URL}/{STATE_BASEMAP}"
            resp = session.get(url)
            resp.raise_for_status()
            d["state_basemap_layer"] = True
        except Exception as e:
            d["state_basemap_layer"] = False
            d["success"] = False

    if DBCA_BURN_PROGRAM:
        try:
            url = f"{KMI_URL}/{DBCA_BURN_PROGRAM}"
            resp = session.get(url)
            resp.raise_for_status()
            d["dbca_burn_program_layer"] = True
        except Exception as e:
            d["dbca_burn_program_layer"] = False
            d["success"] = False

    if DAILY_ACTIVE_BURNS:
        try:
            url = f"{KMI_URL}/{DAILY_ACTIVE_BURNS}"
            # Don't use an authenticated session to download public layers.
            resp = requests.get(url)
            resp.raise_for_status()
            d["daily_active_burns_layer"] = True
        except Exception as e:
            d["daily_active_burns_layer"] = False
            d["success"] = False

    if DBCA_LANDS_WATERS:
        try:
            url = f"{KMI_URL}/{DBCA_LANDS_WATERS}"
            # Don't use an authenticated session to download public layers.
            resp = requests.get(url)
            resp.raise_for_status()
            d["dbca_lands_waters_layer"] = True
        except Exception as e:
            d["dbca_lands_waters_layer"] = False
            d["success"] = False

    if DBCA_LANDS_WATERS_INTEREST:
        try:
            url = f"{KMI_URL}/{DBCA_LANDS_WATERS_INTEREST}"
            resp = session.get(url)
            resp.raise_for_status()
            d["dbca_lands_waters_interest_layer"] = True
        except Exception as e:
            d["dbca_lands_waters_interest_layer"] = False
            d["success"] = False

    try:
        resp = session.get(AUTH2_STATUS_URL)
        resp.raise_for_status()
        j = resp.json()
        d["auth2_status"] = j["healthy"]
    except Exception as e:
        d["success"] = False

    return d


@app.route("/json")
def healthcheck_json():
    d = healthcheck()
    response.content_type = "application/json"
    # Mark response as 'never cache'.
    response.set_header("Cache-Control", "private, max-age=0")
    return json.dumps(d)


@app.route("/")
def healthcheck_http():
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
        d['dfes_latest_point_delay'],
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

    if d["csw_catalogue_count"]:
        output += f"CSW spatial catalogue for SSS: {d['csw_catalogue_count']} layers<br>\n"
    else:
        output += f"CSW API endpoint error<br>\n"

    if d["todays_burns_count"]:
        output += f"Today's burns count (KMI): {d['todays_burns_count']}<br>\n"
    else:
        output += f"Today's burns count (KMI): error<br>\n"

    if d["kmi_wmts_layer_count"]:
        output += f"KMI WMTS layer count (public workspace): {d['kmi_wmts_layer_count']}<br>\n"
    else:
        output += f"KMI WMTS GetCapabilities error<br>\n"

    if d["bfrs_profile_api_endpoint"]:
        output += "BFRS profile API endpoint: OK<br>\n"
    else:
        output += f"BFRS profile API endpoint error<br>\n"

    output += "</p>\n<p>\n"

    if d["dbca_going_bushfires_layer"]:
        output += "DBCA Going Bushfires layer (KMI): OK<br>\n"
    else:
        output += f"DBCA Going Bushfires layer (KMI) error<br>\n"

    if d["dbca_control_lines_layer"]:
        output += "DBCA Control Lines layer (KMI): OK<br>\n"
    else:
        output += f"DBCA Control Lines (KMI) error<br>\n"

    if d["dfes_going_bushfires_layer"]:
        output += "DFES Going Bushfires layer (KMI): OK<br>\n"
    else:
        output += f"DFES Going Bushfires layer (KMI) error<br>\n"

    if d["all_current_hotspots_layer"]:
        output += "All current hotspots layer (KMI): OK<br>\n"
    else:
        output += f"All current hotspots layer (KMI) error<br>\n"

    if d["lightning_24h_layer"]:
        output += "Lightning 24h layer (KMI): OK<br>\n"
    else:
        output += f"Lightning 24h layer (KMI) error<br>\n"

    if d["lightning_24_48h_layer"]:
        output += "Lightning 24-48h layer (KMI): OK<br>\n"
    else:
        output += f"Lightning 24-48h layer (KMI) error<br>\n"

    if d["lightning_48_72h_layer"]:
        output += "Lightning 48-72h layer (KMI): OK<br>\n"
    else:
        output += f"Lightning 48-72h layer (KMI) error<br>\n"

    if d["fuel_age_1_6y_layer"]:
        output += "Fuel age 1-6+ years layer (KMI): OK<br>\n"
    else:
        output += f"Fuel age 1-6+ years layer (KMI) error<br>\n"

    if d["fuel_age_nonforest_1_6y_layer"]:
        output += "Fuel age non forest 1-6+ years layer (KMI): OK<br>\n"
    else:
        output += f"Fuel age non forest 1-6+ years layer (KMI) error<br>\n"

    if d["cog_basemap_layer"]:
        output += "COG basemap layer (KMI): OK<br>\n"
    else:
        output += f"COG basemap layer (KMI) error<br>\n"

    if d["state_basemap_layer"]:
        output += "State basemap layer (KMI): OK<br>\n"
    else:
        output += f"State basemap layer (KMI) error<br>\n"

    if d["dbca_burn_program_layer"]:
        output += "DBCA burn options program layer (KMI): OK<br>\n"
    else:
        output += f"DBCA burn options program layer (KMI) error<br>\n"

    if d["daily_active_burns_layer"]:
        output += "Daily active and planned prescribed burns layer (KMI): OK<br>\n"
    else:
        output += f"Daily active and planned prescribed burns layer (KMI) error<br>\n"

    if d["dbca_lands_waters_layer"]:
        output += "DBCA legislated lands and waters layer (KMI): OK<br>\n"
    else:
        output += f"DBCA legislated lands and waters layer (KMI) error<br>\n"

    if d["dbca_lands_waters_interest_layer"]:
        output += "DBCA lands and waters of interest layer (KMI): OK<br>\n"
    else:
        output += f"DBCA lands and waters of interest layer (KMI) error<br>\n"

    output += "</p>\n<p>\n"

    if d["auth2_status"]:
        output += "AUTH2 status: OK<br>\n"
    else:
        output += f"AUTH2 error<br>\n"

    output += "</p>\n<p>\n"
    if d["success"]:
        output += "<strong>Finished checks, healthcheck succeeded!</strong>"
    else:
        output += "<strong>Finished checks, something is wrong =(</strong>"
    output += "</p>"

    response.set_header("Cache-Control", "private, max-age=0")
    return OUTPUT_TEMPLATE.format(output)


@app.route("/favicon.ico", method="GET")
def get_favicon():
    return static_file("favicon.ico", root="./static/images/")


if __name__ == "__main__":
    from bottle import run
    run(application, host="0.0.0.0", port=os.environ.get("PORT", 8080))
