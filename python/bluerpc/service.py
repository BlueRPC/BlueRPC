import asyncio
import logging
import os
import platform
import sys
import time

import grpc
from bluerpc.ble_conn import BLEConn
from bluerpc.ble_scan import BLEScanner
from bluerpc.rpc import common_pb2, gatt_pb2, services_pb2_grpc
from bluerpc.utils import get_net_mac, get_version

START_TIME = time.time()
_LOGGER = logging.getLogger("bluerpc")


class BlueRPCService(services_pb2_grpc.BlueRPCServicer):
    """
    Implementation of the BlueRPCService
    """

    def __init__(
        self, name, adapter_mac="00:00:00:00:00:00", adapter_id=None, keystore_path=""
    ) -> None:
        super().__init__()
        self._name = name
        self._adapter_mac = adapter_mac
        self._ble_scanner = BLEScanner(adapter_id)
        self._keystore_path = keystore_path
        BLEConn.set_scanner(self._ble_scanner)
        BLEConn.set_adapter(adapter_id)

    async def Hello(
        self, request: common_pb2.HelloRequest, context: grpc.aio.ServicerContext
    ) -> common_pb2.HelloResponse:
        net_mac = get_net_mac()
        return common_pb2.HelloResponse(
            name=self._name,
            version=get_version(),
            uptime=round(time.time() - START_TIME),
            supported_modes=[
                common_pb2.WORKER_MODE_GATT_ACTIVE,
                common_pb2.WORKER_MODE_GATT_PASSIVE,
            ],
            worker_type=common_pb2.WORKER_TYPE_PYTHON,
            operating_system=platform.system(),
            operating_system_version=platform.release(),
            bt_mac=self._adapter_mac,
            net_mac=net_mac,
            uid=(self._adapter_mac == "00:00:00:00:00:00" or net_mac).replace(":", ""),
        )

    async def SetKeystore(
        self, request: common_pb2.SetKeystoreRequest, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        if os.path.exists(self._keystore_path) and not request.overwrite:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_KEYSTORE_ALREADY_EXISTS
            )
        try:
            _LOGGER.debug("saving new keystore in %s", self._keystore_path)
            with open(self._keystore_path, "wb") as f:
                f.write(request.data)
        except Exception as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )
        if request.apply:
            asyncio.get_event_loop().call_later(2, self.restart)
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)

    def restart(self):
        args = []
        for i in sys.argv:
            if i != "--insecure":
                args.append(i)
        os.execv(sys.executable, ["python"] + args)

    async def BLEScanStart(
        self, request: gatt_pb2.BLEScanRequest, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        if not self._ble_scanner.running:
            await self._ble_scanner.scan(
                request.active, request.interval, request.filters
            )
            return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)
        else:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_SCAN_ALREADY_RUNNING
            )

    async def BLEScanStop(
        self, request: common_pb2.Void, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        await self._ble_scanner.stop_scan()
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)

    async def BLEConnect(
        self, request: gatt_pb2.BLEConnectRequest, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEConnectResponse:
        return await BLEConn.get_device(request.device).connect()

    async def BLEDisconnect(
        self, request: gatt_pb2.BLEDevice, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request).disconnect()

    async def BLEReceiveDisconnect(
        self, request: common_pb2.Void, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEDevice:
        while True:
            yield await BLEConn.disconnect_queue.get()

    async def BLEPair(
        self, request: gatt_pb2.BLEPairingRequest, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request.device).pair()

    async def BLEPairCode(
        self, request: gatt_pb2.BLEPairingCodeRequest, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request.device).pair_code(request.code)

    async def BLEUnpair(
        self, request: gatt_pb2.BLEDevice, context: grpc.aio.ServicerContext
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request).unpair()

    async def BLEGetConnectionProperties(
        self, request: gatt_pb2.BLEDevice, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEConnectionPropertiesResponse:
        return await BLEConn.get_device(request).get_props()

    async def BLEGetDevices(
        self, request: common_pb2.Void, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEDevicesResponse:
        return BLEConn.get_devices()

    async def BLEListServices(
        self, request: gatt_pb2.BLEDevice, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEListServicesResponse:
        return await BLEConn.get_device(request).get_list()

    async def BLEReadCharacteristic(
        self,
        request: gatt_pb2.BLEReadCharacteristicRequest,
        context: grpc.aio.ServicerContext,
    ) -> gatt_pb2.BLEReadResponse:
        return await BLEConn.get_device(request.device).read_characteristic(
            request.service_uuid, request.uuid
        )

    async def BLEReadDescriptor(
        self,
        request: gatt_pb2.BLEReadDescriptorRequest,
        context: grpc.aio.ServicerContext,
    ) -> gatt_pb2.BLEReadResponse:
        return await BLEConn.get_device(request.device).read_descriptor(
            request.service_uuid, request.characteristic_uuid, request.uuid
        )

    async def BLEWriteCharacteristic(
        self,
        request: gatt_pb2.BLEWriteCharacteristicRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request.device).write_characteristic(
            request.service_uuid,
            request.uuid,
            request.data,
            request.mode != gatt_pb2.BLE_WRITE_MODE_NO_RESPONSE,
        )

    async def BLEWriteDescriptor(
        self,
        request: gatt_pb2.BLEWriteDescriptorRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.StatusMessage:
        return await BLEConn.get_device(request.device).write_descriptor(
            request.service_uuid,
            request.characteristic_uuid,
            request.uuid,
            request.data,
        )

    async def BLENotification(
        self,
        request: gatt_pb2.BLENotificationRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.StatusMessage:
        if request.subscribe:
            return await BLEConn.get_device(request.device).subscribe(
                request.service_uuid, request.uuid
            )
        else:
            return await BLEConn.get_device(request.device).unsubscribe(
                request.service_uuid, request.uuid
            )

    async def BLEReceiveNotifications(
        self, request: common_pb2.Void, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLENotificationResponse:
        while True:
            yield await BLEConn.notif_queue.get()

    async def BLEReceiveScan(
        self, request: common_pb2.Void, context: grpc.aio.ServicerContext
    ) -> gatt_pb2.BLEScanResponse:
        BLEScanner.scan_queues[context.peer()] = asyncio.Queue(20)
        context.add_done_callback(self.rpc_scan_disconnect)
        while self._ble_scanner.running:
            data = []
            try:
                while True:
                    data.append(BLEScanner.scan_queues[context.peer()].get_nowait())
            except asyncio.QueueEmpty:
                pass
            yield gatt_pb2.BLEScanResponse(
                status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
                data=data,
            )
            await asyncio.sleep(self._ble_scanner.interval / 1000)
        yield gatt_pb2.BLEScanResponse(
            status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_SCAN_STOPPED)
        )

    def rpc_scan_disconnect(self, context: grpc.aio.ServicerContext):
        del BLEScanner.scan_queues[context.peer()]
