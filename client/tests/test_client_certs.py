import os
import sys
sys.path.append(os.path.join(os.getcwd(), ".."))

from bluerpc_client import BlueRPC, create_certs, create_keystore, serialize_certs, load_certs
from bluerpc_client.bluerpc import _LOGGER
from datetime import timedelta
import asyncio
import base64
import json
import logging

level = logging.DEBUG
log_handler = logging.StreamHandler(sys.stdout)
log_handler.setLevel(level)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s::%(levelname)s %(message)s")
)
_LOGGER.setLevel(level)
_LOGGER.addHandler(log_handler)
_LOGGER.propagate = False

host = "192.168.1.99"
port = 5052
keystore_password = "secret1"

country = "FR"
cn = "hass.domain.tld"
CERT_DEFAULT_ORGANIZATION = "BlueRPC"
CERT_DEFAULT_VALIDITY = timedelta(weeks=5000)
CERT_DEFAULT_KEY_SIZE = 2048

def get_keys(keys_path):
    new = False
    keys_data = {}
    keys_data_s = {}
    try:
        with open(keys_path, "r") as f:
            keys_data_s = json.load(f)
    except FileNotFoundError:
        print("file not found")
        pass

    if "ca" not in keys_data_s:
        new = True
        ca_key, ca_cert = create_certs(
            country=country,
            common_name=cn,
            organization=CERT_DEFAULT_ORGANIZATION,
            validity=CERT_DEFAULT_VALIDITY,
            key_size=CERT_DEFAULT_KEY_SIZE,
            signing_key=None,
        )
        keys_data_s["ca"] = [
            base64.b64encode(serialize_certs(ca_key)).decode("utf-8"),
            base64.b64encode(serialize_certs(ca_cert)).decode("utf-8"),
        ]
        keys_data["ca"] = [ca_key, ca_cert]

        hass_key, hass_cert = create_certs(
            country=country,
            common_name=cn,
            organization=CERT_DEFAULT_ORGANIZATION,
            validity=CERT_DEFAULT_VALIDITY,
            key_size=CERT_DEFAULT_KEY_SIZE,
            signing_key=ca_key,
        )
        keys_data_s["hass"] = [
            base64.b64encode(serialize_certs(hass_key)).decode("utf-8"),
            base64.b64encode(serialize_certs(hass_cert)).decode("utf-8"),
        ]
        keys_data["hass"] = [hass_key, hass_cert]

        with open(keys_path, "w+") as f:
            json.dump(keys_data_s, f)
    else:
        keys_data["ca"] = load_certs(
            base64.b64decode(keys_data_s["ca"][0]),
            base64.b64decode(keys_data_s["ca"][1]),
        )
        keys_data["hass"] = load_certs(
            base64.b64decode(keys_data_s["hass"][0]),
            base64.b64decode(keys_data_s["hass"][1]),
        )
    return (new, keys_data)

async def main():
    new, keys = get_keys("keys.json")
    if new:
        print("creating and pushing new keystore")
        # create worker keystore
        worker_key, worker_cert = create_certs(
            country=country,
            common_name=host,
            organization=CERT_DEFAULT_ORGANIZATION,
            validity=CERT_DEFAULT_VALIDITY,
            key_size=CERT_DEFAULT_KEY_SIZE,
            signing_key=keys["ca"][0],
            issuer_cert=keys["ca"][1]
        )
        worker_keystore = create_keystore(worker_key, worker_cert, keys["ca"][1], keystore_password)
        client = BlueRPC(
            host,
            port,
            None,
            None,
            None,
            "homeassistant",
            False,
            None,
            None,
        )
        if await client.connect():
            ret = await client.set_keystore(worker_keystore, True, True)
            print(ret)
            await client.stop()
            await asyncio.sleep(5)
        else:
            print("connection error")
            return
            
    client2 = BlueRPC(
        host,
        port,
        key=serialize_certs(keys["hass"][0]),
        cert=serialize_certs(keys["hass"][1]),
        ca_cert=serialize_certs(keys["ca"][1]),
    )
    
    if await client2.connect():
        print(client2.settings)
        await client2.stop()
    else:
        print("connection error")

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
