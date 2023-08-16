import pytest
import grpc
import asyncio
from rpc import gatt_pb2, services_pb2_grpc, common_pb2
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption

@pytest.fixture(scope="session")
def event_loop():
    return asyncio.get_event_loop()


def pytest_addoption(parser):
    parser.addoption("--mac", action="store", default=None)
    parser.addoption("--url", action="store", default=None)
    parser.addoption("--keystore", action="store", default=None)
    parser.addoption("--keystore-password", action="store", default=None)


@pytest.fixture(scope="session")
async def client(pytestconfig):
    url = pytestconfig.getoption("url")
    keystore = pytestconfig.getoption("keystore")
    ks_pass = pytestconfig.getoption("keystore_password")
    assert url != None, "please provide the worker url with the --url option"

    if keystore is not None:
        assert ks_pass != None, "please provide the keystore password with the --keystore-password option, default is: password"
        with open(keystore, "rb") as f:
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(f.read(), ks_pass.encode("utf-8"))
        creds = grpc.ssl_channel_credentials(
            additional_certificates[0].public_bytes(Encoding.PEM),
            private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
            certificate.public_bytes(Encoding.PEM)
        )
        return services_pb2_grpc.BlueRPCStub(grpc.aio.secure_channel(url, creds))
    else:
        return services_pb2_grpc.BlueRPCStub(grpc.aio.insecure_channel(url))


@pytest.fixture(scope="session")
def ble_device(pytestconfig) -> gatt_pb2.BLEDevice:
    mac = pytestconfig.getoption("mac")
    assert mac != None, "please provide the device mac address with the --mac option"
    return gatt_pb2.BLEDevice(mac=mac)


@pytest.fixture()
async def ble_connect(
    client: services_pb2_grpc.BlueRPCStub, ble_device: gatt_pb2.BLEDevice
):
    x = await client.BLEConnect(gatt_pb2.BLEConnectRequest(device=ble_device))
    assert x.status.code == common_pb2.ERROR_CODE_OK
    return ble_device
