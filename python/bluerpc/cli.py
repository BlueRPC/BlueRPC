import argparse
import asyncio
import logging
import signal
import socket
import sys

import grpc
from bluerpc.discovery import start_discovery
from bluerpc.log import AsyncLoggingInterceptor
from bluerpc.rpc import services_pb2_grpc
from bluerpc.service import BlueRPCService
from bluerpc.utils import find_adapter_by_address, list_adapters_mac
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)

_LOGGER = logging.getLogger("bluerpc")


async def serve(
    bind_addr="[::]:50052",
    name="unknown",
    keystore=None,
    adapter_mac="00:00:00:00:00:00",
    adapter_id=None,
) -> None:
    """
    Run the worker and the mDNS task

    Args:
        bind_addr: the gRPC server bind address
        name: the worker name
        keystore: path to a PKCS12 keystore (used for encryption)
        adapter: adapter mac address
    """
    server = grpc.aio.server(interceptors=[AsyncLoggingInterceptor()])
    services_pb2_grpc.add_BlueRPCServicer_to_server(
        BlueRPCService(name, adapter_mac, adapter_id), server
    )
    encrypted = False

    if keystore is not None:
        try:
            with open(keystore, "rb") as f:
                (
                    private_key,
                    certificate,
                    additional_certificates,
                ) = pkcs12.load_key_and_certificates(f.read(), b"")
            creds = grpc.ssl_server_credentials(
                [
                    (
                        private_key.private_bytes(
                            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
                        ),
                        certificate.public_bytes(Encoding.PEM),
                    )
                ],
                additional_certificates[0].public_bytes(Encoding.PEM),
            )
            server.add_secure_port(bind_addr, creds)
            encrypted = True
        except FileNotFoundError:
            _LOGGER.warn("keystore not found, starting with insecure mode")
            server.add_insecure_port(bind_addr)
    else:
        server.add_insecure_port(bind_addr)

    await server.start()
    _LOGGER.info(f"BlueRPC worker running on {bind_addr}")

    await start_discovery(bind_addr, name, encrypted, adapter_mac)

    await server.wait_for_termination()


def handler(a, b) -> None:
    """
    Callback for sigint/sigterm, terminates the worker
    """
    exit(0)


def run():
    """
    Parse the arguments and start the worker
    """
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    parser = argparse.ArgumentParser(description="BlueRPC Worker")
    parser.add_argument(
        "--bind_addr",
        type=str,
        help="bind address of the server",
        default="[::]:50052",
        nargs="?",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="name of this worker",
        default=socket.gethostname().split(".")[0].lower(),
        nargs="?",
    )
    parser.add_argument(
        "--keystore", type=str, help="path to the keystore", default=None, nargs="?"
    )
    parser.add_argument(
        "--debug", action="store_true", help="enable debug logs", default=False
    )
    parser.add_argument(
        "--adapter", type=str, help="adapter mac address", default=None, nargs="?"
    )
    parser.add_argument(
        "--list-adapters",
        action="store_true",
        help="list available adapters",
        default=False,
    )

    args = parser.parse_args()

    # setup logger
    level = logging.DEBUG if args.debug else logging.INFO
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setLevel(level)
    log_handler.setFormatter(
        logging.Formatter("%(asctime)s::%(levelname)s %(message)s")
    )
    _LOGGER.setLevel(level)
    _LOGGER.addHandler(log_handler)
    _LOGGER.propagate = False
    # other modules loggers
    logging.getLogger("bluetooth_adapters").setLevel(logging.ERROR)
    logging.getLogger("zeroconf").setLevel(logging.ERROR)

    if args.list_adapters:
        print(list_adapters_mac())
    else:
        adapter_id = None
        if args.adapter:
            adapter_id = find_adapter_by_address(args.adapter)
        asyncio.new_event_loop().run_until_complete(
            serve(args.bind_addr, args.name, args.keystore, args.adapter, adapter_id)
        )
