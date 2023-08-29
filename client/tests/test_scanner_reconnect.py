import os
import sys
sys.path.append(os.path.join(os.getcwd(), ".."))

import asyncio
import logging
from bluerpc_client import BlueRPC, ClientEvent, BlueRPCBLEScanner
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

scanning = False
client = None

async def main():
    global client
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
    await client.register_callback(cb)
    if await client.connect():
        await start_scan()
    else:
        print("connection error")
    await asyncio.sleep(60*60)

async def cb(e):
    if e == ClientEvent.RECONNECT_SUCCESS:
        global scanning
        if not scanning:
            print("retying scan")
            await asyncio.sleep(10)
            if not await start_scan():
                print("scan conn err")

async def start_scan():
    global scanning
    global client
    scanning = True
    scanner = BlueRPCBLEScanner(client, adv, disc, [], True)
    if not await scanner.start(interval=2):
        print("scanner start error")
    else:
        await asyncio.sleep(60*60)

def adv(a):
    print(a)

async def disc():
    print("======= DISCONNECTED ========")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
