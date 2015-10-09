import os

#Environment variables
SSS_USERNAME = os.environ['SSS_USERNAME'] if os.environ.get('SSS_USERNAME', False) else None
SSS_PASSWORD = os.environ['SSS_PASSWORD'] if os.environ.get('SSS_PASSWORD', False) else None

#Login data
SSS_LOGIN_DATA = (SSS_USERNAME,SSS_PASSWORD)

#Delay times
TRACKING_POINTS_MAX_DELAY = 30  # Maximum allowable delay for tracking points (Minutes).
AWS_DATA_MAX_DELAY = 3600  # Maximum allowable delay for observation data (seconds).
