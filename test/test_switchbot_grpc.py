from rpc import services_pb2_grpc, common_pb2, gatt_pb2
import asyncio

READ_CHAR = "cba20003-224d-11e6-9fb8-0002a5d5c51b"
WRITE_CHAR = "cba20002-224d-11e6-9fb8-0002a5d5c51b"


async def test_switchbot(
    client: services_pb2_grpc.BlueRPCStub, ble_connect: gatt_pb2.BLEDevice
):
    n = await client.BLENotification(
        gatt_pb2.BLENotificationRequest(
            device=ble_connect, uuid=READ_CHAR, subscribe=True
        )
    )
    assert n.code == common_pb2.ERROR_CODE_OK

    w = await client.BLEWriteCharacteristic(
        gatt_pb2.BLEWriteCharacteristicRequest(
            device=ble_connect, uuid=WRITE_CHAR, data=b"W\x115\xc2F\xd5\x01"
        )
    )
    assert w.code == common_pb2.ERROR_CODE_OK

    async for resp in client.BLEReceiveNotifications(common_pb2.Void()):
        assert resp.device.mac == ble_connect.mac
        assert resp.uuid == READ_CHAR
        break
