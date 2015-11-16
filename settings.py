import os

SSS_DEVICES_URL = os.environ.get('SSS_DEVICES_URL','https://sss.dpaw.wa.gov.au/api/v1/device/?seen__isnull=false&format=json')

#Delay times
TRACKING_POINTS_MAX_DELAY = 30  # Maximum allowable delay for tracking points (Minutes).
AWS_DATA_MAX_DELAY = 3600  # Maximum allowable delay for observation data (seconds).
