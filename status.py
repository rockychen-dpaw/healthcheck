import os
import sys
import subprocess
import json
from pexpect import pxssh



# NOTE TO SELF: DON'T MOVE THESE IMPORTS ABOVE THE activate_this LINE!!!!1!
from dpaw_utils import requests
import bottle
from bottle import route, run, static_file,request
from datetime import datetime, timedelta
from dateutil import parser
import pytz
from settings import *


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

 
SSS_DEVICES_URL = SSS_URL + '/api/v1/device/?seen__isnull=false&format=json'
SSS_IRIDIUM_URL = SSS_URL + '/api/v1/device/?seen__isnull=false&deviceid__contains=3000340&format=json'
WEATHER_OBS_URL = SSS_URL + '/api/v1/weatherobservation/?format=json&limit=1'

@route('/')
def healthcheck():
    now = datetime.utcnow()
    output = "Server time (UTC): {0}<br>".format(now.isoformat())
    success = True
    # Resource Tracking points
    r = requests.get(request, SSS_DEVICES_URL)

    
    try:
        trackingdata = json.loads(r.content)
        # Output latest point
        output += "Latest tracking point (AWST): {0}<br>".format(trackingdata["objects"][0]["seen"])
        # output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Resource Tracking Delay too high! Currently {0:.1f} min (max {1} min)<br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Resource Tracking delay currently {0:.1f} min (max {1} min)<br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Resource Tracking load had an error: {}<br>'.format(e)

    try:
        trackingdata = json.loads(requests.get(request, SSS_IRIDIUM_URL).content)
        # Output latest point
        output += "Latest Iridium tracking point (AWST): {0}<br>".format(trackingdata["objects"][0]["seen"])
        # Output the delay
        if trackingdata["objects"][0]["age_minutes"] > TRACKING_POINTS_MAX_DELAY:
            success = False
            output += "Iridium Tracking Delay too high! Currently {0:.1f} min (max {1} min)<br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
        else:
            output += "Iridium Tracking delay currently {0:.1f} min (max {1} min)<br>".format(trackingdata["objects"][0]["age_minutes"], TRACKING_POINTS_MAX_DELAY)
    except Exception as e:
        success = False
        output += 'Iridium Resource Tracking load had an error: {}<br>'.format(e)

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
            output += 'Observations AWS data delay too high! Currently: {0:.1f} min (max {1} min)<br>'.format(delay.seconds/60., AWS_DATA_MAX_DELAY/60)
        else:
            output += 'Observations AWS data delay currently {0:.1f} min (max {1} min)<br>'.format(delay.seconds/60., AWS_DATA_MAX_DELAY/60)
    except Exception as e:
        success = False
        output += 'Observations AWS load had an error: {}<br>'.format(e)
    if success:
        output += "Finished checks, healthcheck succeeded!"
    else:
        output += "Finished checks, something is wrong =("
    return OUTPUT_TEMPLATE.format(output)
    return output

@route('/favicon.ico', method='GET')
def get_favicon():
    return static_file('favicon.ico',root='./static/images/')

application = bottle.default_app()
