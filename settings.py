import os

SSS_URL = os.environ.get('SSS_URL','https://sss.dpaw.wa.gov.au')
if SSS_URL[-1:] == "/" : SSS_URL = SSS_URL[:-1]

#Delay times
TRACKING_POINTS_MAX_DELAY = 30  # Maximum allowable delay for tracking points (Minutes).
DPLUS_POINTS_MAX_DELAY = 60  # Maximum allowable delay for Dplus tracking points (Minutes).
AWS_DATA_MAX_DELAY = 3600  # Maximum allowable delay for observation data (seconds).

DPLUS_IGNORE_START = "1830"
DPLUS_IGNORE_END = "0630"
