import os
import logging.config
from zoneinfo import ZoneInfo

HOME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEALTHCHECK_DATA_DIR = os.environ.get("HEALTHCHECK_DATA_DIR",os.path.join(HOME_DIR,"data_dir"))
if not os.path.exists(HEALTHCHECK_DATA_DIR):
    os.makedirs(HEALTHCHECK_DATA_DIR)

DEBUG = os.environ.get("DEBUG","true").lower() == "true"

TZ = ZoneInfo(os.environ.get("TZ", "Australia/Perth"))  

try:
    HEARTBEAT_TIME = int(os.environ.get("HEARTBEAT_TIME"),10)
    if HEARTBEAT_TIME <=0 :
        HEARTBEAT_TIME = 10
except:
    HEARTBEAT_TIME = 10


NEXTCHECK_TIMEOUT = int(os.environ.get("NEXTCHECK_TIMEOUT",30)) * 1000 #configured in seconds, tranform it to milliseconds
NEXTCHECK_CHECKINTERVAL = int(os.environ.get("NEXTCHECK_CHECKINTERVAL",10)) * 1000 #configured in seconds, tranform it to milliseconds

BLOCK_TIMEOUT = int(os.environ.get("BLOCK_TIMEOUT",5)) # in seconds, 
SOCKET_ATTEMPTS = int(os.environ.get("SOCKET_ATTEMPTS",3))
HEALTHCHECKSERVER_LOCAL = os.environ.get("HEALTHCHECKSERVER_LOCAL","true").lower() == "true"
HEALTHCHECKSERVER_PORT = int(os.environ.get("HEALTHCHECKSERVER_PORT",9080))

HEALTHCHECK_CONFIG_FILE = os.environ.get("HALTHCHECK_CONFIG_FILE",os.path.join(HEALTHCHECK_DATA_DIR,"healthcheck.json"))

try:
    HEALTHSTATUS_PAGESIZE = int(os.environ.get("HEALTHSTATUS_PAGESIZE",100))
    if HEALTHSTATUS_PAGESIZE < 100:
        HEALTHSTATUS_PAGESIZE = 100
except :
    HEALTHSTATUS_PAGESIZE = 100
HEALTHSTATUS_BUFFER = int(os.environ.get("HEALTHSTATUS_BUFFER",1000))

HEALTHCHECK_PUBLISH_HISTORIES = int(os.environ.get("HEALTHCHECK_PUBLISH_HISTORIES",100))

ASYNCIO_EVENTS = int(os.environ.get("ASYNCIO_EVENTS",10))

try:
    HEALTHCHECK_WORKERS = os.environ.get("HEALTHCHECK_WORKERS",4)
except:
    HEALTHCHECK_WORKERS = 4

PORT = int(os.environ.get("PORT",9080))

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else "INFO",
            'formatter': 'console',
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False
        },
        'healthcheck': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else "INFO",
            'propagate': False
        }
    }
})

