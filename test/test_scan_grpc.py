import time
from rpc import services_pb2_grpc, common_pb2, gatt_pb2


async def test_scan(client: services_pb2_grpc.BlueRPCStub):
    nb = 0
    await client.BLEScanStart(
        gatt_pb2.BLEScanRequest(interval=2000, active=True)
    )

    async for response in client.BLEReceiveScan(common_pb2.Void()):
        if response.status.code == common_pb2.ERROR_CODE_SCAN_STOPPED:
            return
        assert response.status.code == common_pb2.ERROR_CODE_OK
        for i in response.data:
            nb += 1
            assert i.time > 0
            assert i.device.mac != "" or i.device.uuid != ""
            print(
                f"mac: {i.device.mac} name: {i.name} rssi: {i.rssi} time: {i.time}"
            )
            print(f"\t service_data: {i.service_data}")
            print(f"\t manufacturer_data: {i.manufacturer_data}")

            if nb > 4:
                x = await client.BLEScanStop(common_pb2.Void())
                assert x.code == common_pb2.ERROR_CODE_OK
                return


async def test_scan_filter_service(client: services_pb2_grpc.BlueRPCStub):
    nb = 0
    f = [
        gatt_pb2.BLEScanFilter(
            type=gatt_pb2.BLE_SCAN_FILTER_TYPE_UUID,
            value="0000fe95-0000-1000-8000-00805f9b34fb",
        )
    ]
    await client.BLEScanStart(
        gatt_pb2.BLEScanRequest(interval=2000, active=True, filters=f)
    )

    async for response in client.BLEReceiveScan(common_pb2.Void()):
        if response.status.code == common_pb2.ERROR_CODE_SCAN_STOPPED:
            return
        assert response.status.code == common_pb2.ERROR_CODE_OK
        for i in response.data:
            nb += 1
            print(f"mac: {i.device.mac} rssi: {i.rssi} time: {i.time}")
            if nb == 2:
                x = await client.BLEScanStop(common_pb2.Void())
                assert x.code == common_pb2.ERROR_CODE_OK


async def test_scan_filter_mac(
    client: services_pb2_grpc.BlueRPCStub, ble_device: gatt_pb2.BLEDevice
):
    nb = 0
    f = [
        gatt_pb2.BLEScanFilter(
            type=gatt_pb2.BLE_SCAN_FILTER_TYPE_MAC, value=ble_device.mac
        )
    ]
    await client.BLEScanStart(
        gatt_pb2.BLEScanRequest(interval=2000, active=True, filters=f)
    )

    async for response in client.BLEReceiveScan(common_pb2.Void()):
        if response.status.code == common_pb2.ERROR_CODE_SCAN_STOPPED:
            return
        assert response.status.code == common_pb2.ERROR_CODE_OK
        for i in response.data:
            nb += 1
            print(f"mac: {i.device.mac} rssi: {i.rssi} time: {i.time}")
            if nb == 2:
                x = await client.BLEScanStop(common_pb2.Void())
                assert x.code == common_pb2.ERROR_CODE_OK
