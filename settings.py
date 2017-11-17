import confy
import os

confy.read_environment_file()

RT_URL = os.environ.get('RT_URL', 'https://resourcetracking.dpaw.wa.gov.au')
if RT_URL[-1:] == '/':
    RT_URL = RT_URL[:-1]

RT_URL_UAT = os.environ.get('RT_URL_UAT', 'https://resourcetracking-uat.dpaw.wa.gov.au')
if RT_URL_UAT[-1:] == '/':
    RT_URL_UAT = RT_URL_UAT[:-1]

# Delay times
TRACKING_POINTS_MAX_DELAY = 30  # Maximum allowable delay for tracking points (Minutes).
AWS_DATA_MAX_DELAY = 3600  # Maximum allowable delay for observation data (seconds).
