from bottle import Bottle, static_file, response
from datetime import datetime
from dateutil.tz import tzoffset
import json
import os
import requests
import xml.etree.ElementTree as ET


dot_env = os.path.join(os.getcwd(), '.env')
if os.path.exists(dot_env):
    from dotenv import load_dotenv
    load_dotenv()
app = application = Bottle()


OUTPUT_TEMPLATE = '''<!DOCTYPE html>
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
</html>'''
RT_URL = os.environ.get('RT_URL', 'https://resourcetracking.dbca.wa.gov.au')
SSS_DEVICES_URL = RT_URL + '/api/v1/device/?seen__isnull=false&format=json'
SSS_IRIDIUM_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=iriditrak&format=json'
SSS_DPLUS_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=dplus&format=json'
SSS_TRACPLUS_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=tracplus&format=json'
SSS_DFES_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=dfes&format=json'
SSS_FLEETCARE_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=fleetcare&format=json'
CSW_API = os.environ.get('CSW_API', 'https://csw.dbca.wa.gov.au/catalogue/api/records/?format=json&application__name=sss')
KMI_URL = os.environ.get('KMI_URL', 'https://kmi.dbca.wa.gov.au/geoserver')
BFRS_URL = os.environ.get('BFRS_URL', 'https://bfrs.dbca.wa.gov.au/api/v1/profile/?format=json')
USER_SSO = os.environ.get('USER_SSO', 'asi@dbca.wa.gov.au')
PASS_SSO = os.environ.get('PASS_SSO', 'password')
# Maximum allowable delay for tracking points (minutes).
TRACKING_POINTS_MAX_DELAY = int(os.environ.get('TRACKING_POINTS_MAX_DELAY', 30))
# Maximum allowable delay for aircraft tracking (minutes, optional).
AIRCRAFT_TRACKING_MAX_DELAY = int(os.environ.get('AIRCRAFT_TRACKING_MAX_DELAY', 0))
# Maximum allowable delay for observation data (seconds).
AWS_DATA_MAX_DELAY = int(os.environ.get('AWS_DATA_MAX_DELAY', 3600))
AWST_TZ = tzoffset('AWST', 28800)  # AWST timezone offset.


@app.route('/json')
def healthcheck_json():
    d = {
        'server_time': datetime.now().astimezone(AWST_TZ).isoformat(),
        'success': True,
        'latest_point': None,
        'latest_point_delay': None,
        'iridium_latest_point': None,
        'iridium_latest_point_delay': None,
        'dplus_latest_point': None,
        'dplus_latest_point_delay': None,
        'tracplus_latest_point': None,
        'tracplus_latest_point_delay': None,
        'dfes_latest_point': None,
        'dfes_latest_point_delay': None,
        'fleetcare_latest_point': None,
        'fleetcare_latest_point_delay': None,
        'csw_catalogue_count': None,
        'todays_burns_count': None,
        'kmi_wmts_layer_count': None,
        'bfrs_profile_api_endpoint': None,
    }

    trackingdata = requests.get(SSS_DEVICES_URL).json()
    d['latest_point'] = trackingdata["objects"][0]["seen"]
    d['latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]
    if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
        d['success'] = False

    trackingdata = requests.get(SSS_IRIDIUM_URL).json()
    d['iridium_latest_point'] = trackingdata["objects"][0]["seen"]
    d['iridium_latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]
    if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
        d['success'] = False

    trackingdata = requests.get(SSS_DPLUS_URL).json()
    d['dplus_latest_point'] = trackingdata["objects"][0]["seen"]
    d['dplus_latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]
    if trackingdata["objects"][0]["age_minutes"] > AIRCRAFT_TRACKING_MAX_DELAY:
        d['success'] = False

    trackingdata = requests.get(SSS_TRACPLUS_URL).json()
    d['tracplus_latest_point'] = trackingdata["objects"][0]["seen"]
    d['tracplus_latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]

    trackingdata = requests.get(SSS_DFES_URL, auth=(USER_SSO, PASS_SSO)).json()
    d['dfes_latest_point'] = trackingdata["objects"][0]["seen"]
    d['dfes_latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]

    trackingdata = requests.get(SSS_FLEETCARE_URL).json()
    d['fleetcare_latest_point'] = trackingdata["objects"][0]["seen"]
    d['fleetcare_latest_point_delay'] = trackingdata["objects"][0]["age_minutes"]
    if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
        d['success'] = False

    try:
        resp = requests.get(CSW_API, auth=(USER_SSO, PASS_SSO)).json()
        d['csw_catalogue_count'] = len(resp)
    except Exception as e:
        d['success'] = False

    try:
        url = KMI_URL + '/wfs'
        params = {'service': 'wfs', 'version': '1.1.0', 'request': 'GetFeature', 'typeNames': 'public:todays_burns', 'resultType': 'hits'}
        resp = requests.get(url, params=params)
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        resp_d = {i[0]: i[1] for i in root.items()}
        d['todays_burns_count'] = resp_d['numberOfFeatures']
    except Exception as e:
        d['success'] = False

    try:
        url = KMI_URL + '/public/gwc/service/wmts'
        resp = requests.get(url, params={'request': 'getcapabilities'})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'wmts': 'http://www.opengis.net/wmts/1.0', 'ows': 'http://www.opengis.net/ows/1.1'}
        layers = root.findall('.//wmts:Layer', ns)
        d['kmi_wmts_layer_count'] = len(layers)
    except Exception as e:
        d['success'] = False

    try:
        url = 'https://bfrs.dpaw.wa.gov.au/api/v1/profile/?format=json'
        resp = requests.get(url, auth=(USER_SSO, PASS_SSO)).json()
        d['bfrs_profile_api_endpoint'] = True
    except Exception as e:
        d['success'] = False

    response.content_type = 'application/json'
    return json.dumps(d)


@app.route('/')
def healthcheck():
    now = datetime.now().astimezone(AWST_TZ)
    output = "Server time: {}<br><br>".format(now.isoformat())
    success = True

    # All resource point tracking
    try:
        trackingdata = requests.get(SSS_DEVICES_URL).json()
        # Output latest point
        output += "Latest tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Resource Tracking Delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Resource Tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Resource Tracking load had an error: {}<br><br>'.format(e)

    # Iridium tracking
    try:
        trackingdata = requests.get(SSS_IRIDIUM_URL).json()
        # Output latest point
        output += "Latest Iridium tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Iridium tracking delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Iridium tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Iridium resource tracking load had an error: {}<br><br>'.format(e)

    # Dplus Tracking
    try:
        trackingdata = requests.get(SSS_DPLUS_URL).json()
        # Output latest point
        output += "Latest Dplus tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if AIRCRAFT_TRACKING_MAX_DELAY and trackingdata["objects"][0]["age_minutes"] > AIRCRAFT_TRACKING_MAX_DELAY:
            success = False
            output += "Dplus tracking delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], AIRCRAFT_TRACKING_MAX_DELAY)
        else:
            if AIRCRAFT_TRACKING_MAX_DELAY:
                output += "Dplus tracking delay currently <b>{0:.1f} min</b> (max {1} min) <br><br>".format(
                    trackingdata["objects"][0]["age_minutes"], AIRCRAFT_TRACKING_MAX_DELAY)
            else:
                output += "Dplus tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
                    trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        success = False
        output += 'Dplus resource tracking load had an error: {}<br><br>'.format(e)

    # Tracplus Tracking
    try:
        trackingdata = requests.get(SSS_TRACPLUS_URL).json()
        # Output latest point
        output += "Latest Tracplus tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "Tracplus tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
            trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        pass  # Currently this does not cause the healthcheck to fail.

    # DFES Tracking
    try:
        trackingdata = requests.get(SSS_DFES_URL, auth=(USER_SSO, PASS_SSO)).json()
        # Output latest point
        output += "Latest DFES tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "DFES tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
            trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        pass  # Currently this does not cause the healthcheck to fail.

    # Fleetcare Tracking
    try:
        trackingdata = requests.get(SSS_FLEETCARE_URL, auth=(USER_SSO, PASS_SSO)).json()
        # Output latest point
        output += "Latest Fleetcare tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Fleetcare tracking delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Fleetcare tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Fleetcare resource tracking had an error: {}<br><br>'.format(e)

    # CSW catalogue API endpoint
    try:
        resp = requests.get(CSW_API, auth=(USER_SSO, PASS_SSO)).json()
        output += 'CSW spatial catalogue for SSS: {} layers<br><br>'.format(len(resp))
    except Exception as e:
        success = False
        output += 'CSW API endpoint returned an error: {}<br><br>'.format(e)

    # Today's Burns WFS endpoint
    try:
        url = KMI_URL + '/wfs'
        params = {'service': 'wfs', 'version': '1.1.0', 'request': 'GetFeature', 'typeNames': 'public:todays_burns', 'resultType': 'hits'}
        resp = requests.get(url, params=params)
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        d = {i[0]: i[1] for i in root.items()}
        output += "Today's burns count: {}<br><br>".format(d['numberOfFeatures'])
    except Exception as e:
        success = False
        output += "Today's Burns WFS endpoint returned an error: {}<br><br>".format(e)

    # KMI WMTS endpoint
    try:
        url = KMI_URL + '/public/gwc/service/wmts'
        resp = requests.get(url, params={'request': 'getcapabilities'})
        if not resp.status_code == 200:
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'wmts': 'http://www.opengis.net/wmts/1.0', 'ows': 'http://www.opengis.net/ows/1.1'}
        layers = root.findall('.//wmts:Layer', ns)
        output += 'KMI WMTS layer count (public workspace): {}<br><br>'.format(len(layers))
    except Exception as e:
        success = False
        output += "KMI WMTS GetCapabilities request returned an error: {}<br><br>".format(e)

    # BFRS profile API endpoint
    try:
        resp = requests.get(BFRS_URL, auth=(USER_SSO, PASS_SSO)).json()
        output += 'BFRS profile API endpoint: OK<br><br>'
    except Exception as e:
        success = False
        output += "BFRS profile API endpoint returned an error: {}<br><br>".format(e)

    # Success or failure.
    if success:
        output += "Finished checks, healthcheck succeeded!"
    else:
        output += "<b>Finished checks, something is wrong =(</b>"

    return OUTPUT_TEMPLATE.format(output)


@app.route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico', root='./static/images/')


if __name__ == '__main__':
    from bottle import run
    run(application, host='0.0.0.0', port=os.environ.get('PORT', 8080))
