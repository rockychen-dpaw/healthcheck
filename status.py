from dpaw_utils import requests
import bottle
from bottle import route, static_file, request
from datetime import datetime
from dateutil import parser
import json

from settings import RT_URL, TRACKING_POINTS_MAX_DELAY, AWS_DATA_MAX_DELAY


OUTPUT_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>DPaW OIM service health checks</title>
        <meta name="description" content="DPaW OIM service health checks">
    </head>
    <body>
        {0}
    </body>
</html>'''


SSS_DEVICES_URL = RT_URL + '/api/v1/device/?seen__isnull=false&format=json'
SSS_IRIDIUM_URL = RT_URL + '/api/v1/device/?seen__isnull=false&deviceid__startswith=3000340&format=json'
SSS_DPLUS_URL = RT_URL + '/api/v1/device/?seen__isnull=false&deviceid__startswith=500&format=json'
WEATHER_OBS_URL = RT_URL + '/api/v1/weatherobservation/?format=json&limit=1'
WEATHER_OBS_HEALTH_URL = RT_URL + '/weather/observations-health/'


@route('/')
def healthcheck():
    now = datetime.utcnow()
    output = "Server time (UTC): {0}<br><br>".format(now.isoformat())
    success = True

    # All resource point tracking
    try:
        trackingdata = json.loads(requests.get(request, SSS_DEVICES_URL).content)
        # Output latest point
        output += "Latest tracking point (AWST): {0}<br>".format(trackingdata["objects"][0]["seen"])
        # output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Resource Tracking Delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Resource Tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Resource Tracking load had an error: {}<br><br>'.format(e)

    # iridium tracking
    try:
        trackingdata = json.loads(requests.get(request, SSS_IRIDIUM_URL).content)
        # Output latest point
        output += "Latest Iridium tracking point (AWST): {0}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Iridium Tracking Delay too high! Currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Iridium Tracking delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Iridium Resource Tracking load had an error: {}<br><br>'.format(e)

    # Dplus Tracking
    try:
        trackingdata = json.loads(requests.get(request, SSS_DPLUS_URL).content)
        # Output latest point
        output += "Latest Dplus tracking point (AWST): {0}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        output += "Dplus Tracking delay currently <b>{0:.1f} min</b> <br><br>".format(trackingdata["objects"][0]["age_minutes"])
    except Exception as e:
        success = False
        output += 'Dplus Resource Tracking load had an error: {}<br><br>'.format(e)

    # Observations AWS data
    r = requests.get(request, WEATHER_OBS_URL)
    try:
        obsdata = json.loads(r.content)
        t = parser.parse(obsdata['objects'][0]['date'])  # Get the timestamp from the latest downloaded observation.
        output += "Latest weather data: {0}<br>".format(t.isoformat())
        now = datetime.now(tz=None)
        delay = now - t
        if delay.seconds > AWS_DATA_MAX_DELAY:  # Allow one hour delay in Observations weather data.
            success = False
            output += 'Observations AWS data delay too high! Currently: <b>{0:.1f} min</b> (max {1} min)<br><br>'.format(delay.seconds/60., AWS_DATA_MAX_DELAY/60)
        else:
            output += 'Observations AWS data delay currently <b>{0:.1f} min</b> (max {1} min)<br><br>'.format(delay.seconds/60., AWS_DATA_MAX_DELAY/60)
    except Exception as e:
        success = False
        output += 'Observations AWS load had an error: {}<br><br>'.format(e)

    # Individual weather station observation status.
    output += 'Weather station observation status (last hour):<br><ul>'
    r = requests.get(request, WEATHER_OBS_HEALTH_URL)
    try:
        stations = json.loads(r.content)
        for i in stations['objects']:
            output += '<li>{}: expected observations {}, actual observations {}, latest {} ({})</li>'.format(
                i['name'], i['observations_expected_hr'], i['observations_actual_hr'],
                i['last_reading'], i['observations_health'])
            if i['observations_health'] == 'error':
                success = False
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
    return output


@route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico', root='./static/images/')


application = bottle.default_app()
