from rpc import services_pb2_grpc, common_pb2, gatt_pb2

# https://github.com/ChrisScheffler/miflora/wiki/The-Basics#services--characteristics
SERVICE_UUID = "00001204-0000-1000-8000-00805f9b34fb"
W_CHR_UUID = "00001a00-0000-1000-8000-00805f9b34fb"
R_CHR_UUID = "00001a01-0000-1000-8000-00805f9b34fb"

# py.test.exe .\test_miflora_grpc.py --mac="AA:BB:CC:DD:EE:FF" --url="127.0.0.1:50052" -v -s


async def disconnect(
    client: services_pb2_grpc.BlueRPCStub, ble_device: gatt_pb2.BLEDevice
):
    x = await client.BLEDisconnect(ble_device)
    assert x.code == common_pb2.ERROR_CODE_OK


async def test_hello(client: services_pb2_grpc.BlueRPCStub):
    x = await client.Hello(common_pb2.HelloRequest(name="test", version="1.0"))
    assert x.uptime > 0
    assert common_pb2.WORKER_MODE_GATT_PASSIVE in x.supported_modes
    assert common_pb2.WORKER_MODE_GATT_ACTIVE in x.supported_modes


async def test_list(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    x = await client.BLEListServices(ble_connect)
    assert x.status.code == common_pb2.ERROR_CODE_OK
    assert x.device.mac == ble_connect.mac
    assert len(x.services) > 0
    print(x.services)
    await disconnect(client, ble_connect)


async def test_rw(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    x = await client.BLEWriteCharacteristic(
        gatt_pb2.BLEWriteCharacteristicRequest(
            device=ble_connect,
            service_uuid=SERVICE_UUID,
            uuid=W_CHR_UUID,
            data=b"\xa0\x1f",
        )
    )
    assert x.code == common_pb2.ERROR_CODE_OK
    y = await client.BLEReadCharacteristic(
        gatt_pb2.BLEReadCharacteristicRequest(
            device=ble_connect, service_uuid=SERVICE_UUID, uuid=R_CHR_UUID
        )
    )
    assert y.status.code == common_pb2.ERROR_CODE_OK
    temp = int.from_bytes(bytearray(y.data)[0:2], byteorder="little") / 10
    assert temp > -20
    assert temp < 40
    print(temp)
    await disconnect(client, ble_connect)


async def test_rw_no_svc(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    x = await client.BLEWriteCharacteristic(
        gatt_pb2.BLEWriteCharacteristicRequest(
            device=ble_connect, uuid=W_CHR_UUID, data=b"\xa0\x1f"
        )
    )
    assert x.code == common_pb2.ERROR_CODE_OK
    y = await client.BLEReadCharacteristic(
        gatt_pb2.BLEReadCharacteristicRequest(device=ble_connect, uuid=R_CHR_UUID)
    )
    assert y.status.code == common_pb2.ERROR_CODE_OK
    temp = int.from_bytes(bytearray(y.data)[0:2], byteorder="little") / 10
    assert temp > -20
    assert temp < 40
    print(temp)
    await disconnect(client, ble_connect)


async def test_conn_props(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    x = await client.BLEGetConnectionProperties(ble_connect)
    assert x.status.code == common_pb2.ERROR_CODE_OK
    print(x.rssi)
    await disconnect(client, ble_connect)


async def test_devs(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    x = await client.BLEGetDevices(common_pb2.Void())
    assert x.status.code == common_pb2.ERROR_CODE_OK
    assert len(x.connected_devices) >= 1
    print(x)
    await disconnect(client, ble_connect)
