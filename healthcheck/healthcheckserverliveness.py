import asyncio

from .socket import CommandClient

async def main():
    #listener = HealthStatusListenerClient()
    commandclient = CommandClient()
    result = await commandclient.exec("healthcheck",0)
    if not result[0]:
        raise Exception(result[1])

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as ex:
        print("Failed to check healthcheckserver status.{}: {}".format(ex.__class__.__name__,str(ex)))
        exit(1)


