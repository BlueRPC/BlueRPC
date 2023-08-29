import os
import sys
sys.path.append(os.path.join(os.getcwd(), ".."))

import asyncio
import logging
from bluerpc_client import BlueRPC, ClientEvent
from bluerpc_client.bluerpc import _LOGGER
import zeroconf

level = logging.DEBUG
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setLevel(level)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s::%(levelname)s %(message)s")
)
_LOGGER.setLevel(level)
_LOGGER.addHandler(log_handler)
_LOGGER.propagate = False

async def main():
    client = BlueRPC(
        "127.0.0.1",
        5052,
        None,
        None,
        None,
        "homeassistant",
        True,
        "scheta",
        zeroconf.Zeroconf(),
    )
    await client.register_callback(mycallback)

    if await client.connect():
        print(client.settings)
        await client.stop()
        return
    else:
        print("connection error")
        await asyncio.sleep(60*60)

async def mycallback(ev: ClientEvent):
    print(ev)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
