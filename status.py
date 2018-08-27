from bottle import Bottle, static_file
import confy
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzoffset
from dateutil.utils import default_tzinfo
import os
from pytz import timezone
import requests


dot_env = os.path.join(os.getcwd(), '.env')
if os.path.exists(dot_env):
    confy.read_environment_file()
app = application = Bottle()


OUTPUT_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>DBCA OIM service health checks</title>
        <meta name="description" content="DBCA OIM service health checks">
    </head>
    <body>
        {}
    </body>
</html>'''
RT_URL = confy.env('RT_URL', 'https://resourcetracking.dpaw.wa.gov.au')
RT_URL_UAT = confy.env('RT_URL_UAT', 'https://resourcetracking-uat.dpaw.wa.gov.au')
SSS_DEVICES_URL = RT_URL + '/api/v1/device/?seen__isnull=false&format=json'
SSS_IRIDIUM_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=iriditrak&format=json'
SSS_DPLUS_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=dplus&format=json'
SSS_TRACPLUS_URL = RT_URL + '/api/v1/device/?seen__isnull=false&source_device_type=tracplus&format=json'
SSS_DFES_URL = RT_URL_UAT + '/api/v1/device/?seen__isnull=false&source_device_type=dfes&format=json'
WEATHER_OBS_URL = RT_URL + '/api/v1/weatherobservation/?format=json&limit=1'
WEATHER_OBS_HEALTH_URL = RT_URL + '/weather/observations-health/'
USER_SSO = confy.env('USER_SSO')
PASS_SSO = confy.env('PASS_SSO')
# Maximum allowable delay for tracking points (minutes).
TRACKING_POINTS_MAX_DELAY = confy.env('TRACKING_POINTS_MAX_DELAY', 30)
# Maximum allowable delay for observation data (seconds).
AWS_DATA_MAX_DELAY = confy.env('AWS_DATA_MAX_DELAY', 3600)
AWST_TZ = tzoffset('AWST', 28800)  # AWST timezone offset.


@app.route('/')
def healthcheck():
    now = datetime.now().astimezone(AWST_TZ)
    output = "Server time (AWST): {}<br><br>".format(now.isoformat())
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
            output += "Iridium Tracking Delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Iridium Tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(
                trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Iridium Resource Tracking load had an error: {}<br><br>'.format(e)

    # Dplus Tracking
    try:
        trackingdata = requests.get(SSS_DPLUS_URL).json()
        # Output latest point
        output += "Latest Dplus tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "Dplus Tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
            trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        success = False
        output += 'Dplus Resource Tracking load had an error: {}<br><br>'.format(e)

    # Tracplus Tracking
    try:
        trackingdata = requests.get(SSS_TRACPLUS_URL).json()
        # Output latest point
        output += "Latest Tracplus tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "Tracplus Tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
            trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        pass

    # DFES Tracking
    try:
        trackingdata = requests.get(SSS_DFES_URL, auth=(USER_SSO, PASS_SSO)).json()
        # Output latest point
        output += "(UAT) Latest DFES tracking point (AWST): {}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "(UAT) DFES Tracking delay currently <b>{0:.1f} min</b> <br><br>".format(
            trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        pass  # Currently this does not cause the healthcheck to fail.

    # Observations AWS data
    try:
        obsdata = requests.get(WEATHER_OBS_URL).json()
        # Get the timestamp from the latest downloaded observation.
        t = default_tzinfo(parse(obsdata['objects'][0]['date']), AWST_TZ)
        output += "Latest weather data (AWST): {0}<br>".format(t.isoformat())
        now = datetime.now().astimezone(AWST_TZ)
        delay = now - t
        if delay.seconds > AWS_DATA_MAX_DELAY:  # Allow one hour delay in Observations weather data.
            success = False
            output += 'Observations AWS data delay too high! Currently: <b>{0:.1f} min</b> (max {1} min)<br><br>'.format(
                delay.seconds / 60., AWS_DATA_MAX_DELAY / 60)
        else:
            output += 'Observations AWS data delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>'.format(
                delay.seconds / 60., AWS_DATA_MAX_DELAY / 60)
    except Exception as e:
        success = False
        output += 'Observations AWS load had an error: {}<br><br>'.format(e)

    # Individual weather station observation status.
    output += 'Weather station observation status (last hour):<br><ul>'
    try:
        stations = requests.get(WEATHER_OBS_HEALTH_URL).json()
        for i in stations['objects']:
            output += '<li>{}: expected observations {}, actual observations {}, latest {} ({})</li>'.format(
                i['name'], i['observations_expected_hr'], i['observations_actual_hr'],
                i['last_reading'], i['observations_health'])
        output += '</ul><br>'
    except:
        success = False
        output += '<li>Error loading weather station status data</li></ul><br>'

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
    run(application, host='0.0.0.0', port=confy.env('PORT', 8080))
