import os
import shutil
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import settings

logger = logging.getLogger(__name__)

async def ainput(prompt: str = "") -> str:
    """Asynchronously get user input."""
    try:
        with ThreadPoolExecutor(1, "AsyncInput") as executor:
            return await asyncio.get_event_loop().run_in_executor(executor, input, prompt)
    except EOFError as ex:
        await shutdown.process_userinterruption()

def remove_file(f):
    try:
        os.remove(f)
    except Exception as ex:
        if os.path.exists(f):
            logger.error("Failed to remove the file '{}'. {} : {}".format(f,ex.__class__.__name__,str(ex)))

def makedir(folder):
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
        except FileExistsError as ex:
            pass
        except Exception as ex:
            raise ex
    elif not os.path.isdir(folder):
        raise Exception("The folder path({}) is not a directory".format(folder))

def deletedir(folder):
    try:
        shutil.rmtree(folder)
    except FileNotFoundError as ex:
        pass
    except Exception as ex:
        raise Exception("Failed to remove the folder({}).{}: {}".format(folder,ex.__class__.__name__,str(ex)))


def now():
    return datetime.now().astimezone(settings.TZ)

def parse_datetime(dt,pattern="%Y-%m-%dT%H:%M:%S.%f"):
    return datetime.strptime(dt,pattern).replace(tzinfo=settings.TZ)

def format_time(dt,pattern="%H:%M:%S"):
    return dt.strftime(pattern)

def parse_time(dt,pattern="%H:%M:%S"):
    if dt:
        return datetime.strptime(dt,pattern).time().replace(tzinfo=settings.TZ)
    else:
        return ""




