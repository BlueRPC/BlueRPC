from __future__ import annotations

import asyncio
import json
import platform
from typing import Dict, List, Optional, Union

from bleak import BleakClient, BleakError, BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.exc import BleakDeviceNotFoundError
from bluerpc.ble_scan import BLEScanner
from bluerpc.rpc import common_pb2, gatt_pb2
from bluerpc.utils import get_appdata_dir, get_kwargs, validate_mac, validate_uuid

PAIRED_LIST_FILE = "paired.json"


class BLEConn:
    """
    Class used to manipulate connections with Bluetooth Low-Energy devices
    """

    devices: Dict[str, BLEConn] = {}
    paired_devices: List[gatt_pb2.BLEDevice] = []
    loaded_paired_devices = False
    disconnect_queue = asyncio.Queue()
    notif_queue = asyncio.Queue()
    macos = platform.system() == "Darwin"
    scanner = None

    @classmethod
    def set_scanner(self, sc: BLEScanner):
        """
        Set scanner, used to connect when a scan is also running

        Args:
            sc: the scanner instance
        """
        self.scanner = sc

    @classmethod
    def set_adapter(self, adapter: str):
        """
        Set adapter id

        Args:
            adapter: the adapter id
        """
        self.adapter = adapter

    @staticmethod
    def get_device(dev: gatt_pb2.BLEDevice) -> BLEConn:
        """
        Static method to get a BLEConn instance from a device (mac address or uuid)

        Args:
            dev: the device provided in the grpc requests

        Returns:
            a BLEConn instance
        """
        if dev.mac != "":
            if dev.mac not in BLEConn.devices:
                BLEConn.devices[dev.mac] = BLEConn(dev)
            return BLEConn.devices[dev.mac]
        else:
            if dev.uuid not in BLEConn.devices:
                BLEConn.devices[dev.uuid] = BLEConn(dev)
            return BLEConn.devices[dev.uuid]

    @staticmethod
    def get_devices() -> gatt_pb2.BLEDevicesResponse:
        """
        List devices infos

        The paired devices list is not reliable and is stored on a local file

        Returns:
            a BLEDevicesResponse
        """
        return gatt_pb2.BLEDevicesResponse(
            status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
            connected_devices=[i._device for i in BLEConn.devices.values()],
            reliable_paired_list=False,
            paired_devices=BLEConn.paired_devices,
        )

    @staticmethod
    def _load_paired_devices() -> None:
        """
        Load paired devices list from a file on the system (if it exists)
        """
        d = get_appdata_dir().joinpath(PAIRED_LIST_FILE)
        if d.exists():
            with open(d, "r") as f:
                data = json.load(f)
                for i in data["mac"]:
                    BLEConn.paired_devices.append(gatt_pb2.BLEDevice(mac=i))
                for i in data["uuid"]:
                    BLEConn.paired_devices.append(gatt_pb2.BLEDevice(uuid=i))

    @staticmethod
    def _save_paired_devices() -> None:
        """
        Save paired devices list to a json file on the system
        """
        d = get_appdata_dir().joinpath(PAIRED_LIST_FILE)
        data = {"mac": [], "uuid": []}
        for i in BLEConn.paired_devices:
            if i.mac != "":
                data["mac"].append(i.mac)
            else:
                data["uuid"].append(i.uuid)
        with open(d, "x") as f:
            json.dump(data, f)

    def __init__(self, dev: gatt_pb2.BLEDevice) -> None:
        """
        Constructor

        Args:
            dev: the device provided in the grpc requests, must contains a non null mac address or uuid
        """
        self._device = dev
        self._client = None
        if not BLEConn.loaded_paired_devices:
            BLEConn._load_paired_devices()
        self._listed = False
        self._chrs = {}
        self._notifs: List[BleakGATTCharacteristic] = []

    def _check(
        self, check_connect=True, uuids: List[str] = [], mac: Optional[str] = None
    ) -> Union[None, common_pb2.StatusMessage]:
        """
        General checks

        Args:
            check_connect: check if the device is currently connected
            uuids: check if UUIDs are valid
            mac: check if mac address is valid
        Returns:
            a StatusMessage with an error if something is invalid, else None
        """
        if check_connect and not self._client.is_connected:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_CONNECTION_REQUIRED,
                message="device not connected",
            )

        if mac is not None and not validate_mac(mac):
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_INVALID_CONNECTION_SETTINGS,
                message="invalid mac address",
            )

        for i in uuids:
            if not validate_uuid(i):
                return common_pb2.StatusMessage(
                    code=common_pb2.ERROR_CODE_INVALID_CONNECTION_SETTINGS,
                    message=f"invalid uuid: {i}",
                )
        return None

    def disconnect_callback(self, client: BleakClient) -> None:
        """
        Disconnect callback

        Called by bleak when a device is disconnected

        Args:
            client: the bleak client of the disconnected device
        """
        if client.address in BLEConn.devices:
            asyncio.get_running_loop().call_soon(
                BLEConn.disconnect_queue.put_nowait,
                BLEConn.devices[client.address]._device,
            )

    async def connect(self) -> gatt_pb2.BLEConnectResponse:
        """
        Connect

        Returns:
            a BLEConnectResponse (with the mtu if the connect operation succedeed)
        """

        if self._client is not None and self._client.is_connected:
            return gatt_pb2.BLEConnectResponse(
                status=common_pb2.StatusMessage(
                    code=common_pb2.ERROR_CODE_ALREADY_CONNECTED
                )
            )

        restart = False
        try:
            # validate and create client (mac or uuid)
            kwargs = get_kwargs(self.adapter)
            if self._device.mac != "":
                c = self._check(check_connect=False, mac=self._device.mac)
                if c is not None:
                    return c
                self._client = BleakClient(
                    self._device.mac,
                    disconnected_callback=self.disconnect_callback,
                    **kwargs,
                )
            else:
                c = self._check(check_connect=False, uuids=[self._device.uuid])
                if c is not None:
                    return c
                self._client = BleakClient(
                    self._device.uuid,
                    disconnected_callback=self.disconnect_callback,
                    **kwargs,
                )

            if self.scanner is not None and self.scanner.running:
                # check if a BLEDevice with this address was recently discovered
                found = False
                for i in self.scanner.scanned_devices:
                    if i.address == self._device.mac or i.address == self._device.uuid:
                        found = True
                        self._client = BleakClient(
                            i, disconnected_callback=self.disconnect_callback, **kwargs
                        )
                        break

                if not found:
                    # if not found, we need to stop the scanner to try to connect to the device
                    # otherwise there is an "Operation already in progress" error
                    await self.scanner.stop_scan()
                    restart = True

            await self._client.connect()

            if self._client.__class__.__name__ == "BleakClientBlueZDBus":
                await self._client._acquire_mtu()

            return gatt_pb2.BLEConnectResponse(
                status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
                mtu=self._client.mtu_size,
            )
        except BleakDeviceNotFoundError as e:
            return gatt_pb2.BLEConnectResponse(
                status=common_pb2.StatusMessage(
                    code=common_pb2.ERROR_CODE_UNAVAILABLE, message=str(e)
                )
            )
        except BleakError as e:
            return gatt_pb2.BLEConnectResponse(
                status=common_pb2.StatusMessage(
                    code=common_pb2.ERROR_CODE_ERROR, message=str(e)
                )
            )
        finally:
            if restart:
                await self.scanner.restart_scan()

    async def disconnect(self) -> common_pb2.StatusMessage:
        if self._client.is_connected:
            for i in self._notifs:
                await self._client.stop_notify(i)
            await self._client.disconnect()
            self._notifs = []
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)

    async def pair(self) -> common_pb2.StatusMessage:
        """
        Pairing

        Currently not supported, waiting for this pr to be merged:
        https://github.com/hbldh/bleak/pull/1100

        Returns:
            ERROR_CODE_UNSUPPORTED
        """
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_UNSUPPORTED)

    async def pair_code(self, code: str) -> common_pb2.StatusMessage:
        """
        Pairing (second step)

        Currently not supported, waiting for this pr to be merged:
        https://github.com/hbldh/bleak/pull/1100

        Returns:
            ERROR_CODE_UNSUPPORTED
        """
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_UNSUPPORTED)

    async def unpair(self) -> common_pb2.StatusMessage:
        """
        Unairing

        Supported only on Linux and Windows

        Returns:
            ERROR_CODE_OK or ERROR_CODE_UNSUPPORTED on macos
        """
        if not BLEConn.macos:
            self._client.unpair()
            del BLEConn.paired_devices[self._device]
            return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)
        else:
            common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_UNSUPPORTED)

    async def get_props(self) -> gatt_pb2.BLEConnectionPropertiesResponse:
        """
        Connection properties

        Currently, getting the rssi of connected devices is not supported by bleak

        Returns:
            BLEConnectionPropertiesResponse
        """
        return gatt_pb2.BLEConnectionPropertiesResponse(
            status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_UNSUPPORTED)
        )

    def _get_properties(self, props: List[str]) -> List[gatt_pb2.BLEChrProperty]:
        """
        Map bleak properties to proto enum types

        Args:
            props: list of str props from bleak
        Returns:
            a list of BLEChrProperty
        """
        m = {
            "read": gatt_pb2.BLE_CHR_PROPERTY_READ,
            "write": gatt_pb2.BLE_CHR_PROPERTY_WRITE,
            "notify": gatt_pb2.BLE_CHR_PROPERTY_NOTIFY,
            "broadcast": gatt_pb2.BLE_CHR_PROPERTY_BROADCAST,
            "extended-properties": gatt_pb2.BLE_CHR_PROPERTY_EXTENDED_PROPS,
            "indicate": gatt_pb2.BLE_CHR_PROPERTY_INDICATE,
            "authenticated-signed-writes": gatt_pb2.BLE_CHR_PROPERTY_SIGNED_WRITE,
            "write-without-response": gatt_pb2.BLE_CHR_PROPERTY_WRITE_NO_RESPONSE,
        }
        ret = []
        for i in props:
            if i in m:
                ret.append(m[i])
        return ret

    async def get_list(self) -> gatt_pb2.BLEListServicesResponse:
        """
        List Services/Characteristics/Descriptors of a ble device
        """
        c = self._check(check_connect=True)
        if c is not None:
            return gatt_pb2.BLEListServicesResponse(status=c)

        svcs = []

        for s in self._client.services:
            self._chrs[s.uuid] = {}
            chrs = []
            for c in s.characteristics:
                self._chrs[s.uuid][c.uuid] = c
                descs = []
                for d in c.descriptors:
                    descs.append(gatt_pb2.BLEDescriptor(uuid=d.uuid))
                chrs.append(
                    gatt_pb2.BLECharacteristic(
                        uuid=c.uuid,
                        properties=self._get_properties(c.properties),
                        descriptors=descs,
                    )
                )
            svcs.append(gatt_pb2.BLEService(uuid=s.uuid, characteristics=chrs))

        self._listed = True

        return gatt_pb2.BLEListServicesResponse(
            status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
            device=self._device,
            services=svcs,
        )

    async def _get_chr(
        self, service_uuid: str, uuid: str
    ) -> Union[common_pb2.StatusMessage, BleakGATTCharacteristic]:
        """
        Try to find a suitable BleakGATTCharacteristic

        Args:
            service_uuid: the uuid of the parent service of the characteristic
            uuid: the uuid of the characteristic
        Returns:
            a BleakGATTCharacteristic object if found, else an error message
        """
        c = self._check(
            check_connect=True,
            uuids=([service_uuid, uuid] if service_uuid != "" else [uuid]),
        )
        if c is not None:
            return c

        if not self._listed:
            await self.get_list()
        if service_uuid != "":
            if service_uuid in self._chrs and uuid in self._chrs[service_uuid]:
                return self._chrs[service_uuid][uuid]
        else:
            for i in self._chrs.values():
                if uuid in i:
                    return i[uuid]

        return common_pb2.StatusMessage(
            code=common_pb2.ERROR_CODE_UNKNOWN_CHARACTERISTIC
        )

    async def _get_desc(
        self, service_uuid, characteristic_uuid, uuid
    ) -> Union[BleakGATTDescriptor, common_pb2.StatusMessage]:
        """
        Try to find a suitable BleakGATTDescriptor from the provided UUIDs

        Args:
            service_uuid: the uuid of the parent service of the characteristic
            characteristic_uuid: the uuid of the parent characteristic of the descriptor
            uuid: the uuid of the descriptor
        Returns:
            a BleakGATTDescriptor object, or an error message if not found
        """
        c = self._check(
            check_connect=True, uuids=[service_uuid, characteristic_uuid, uuid]
        )
        if c is not None:
            return c

        chr = await self._get_chr(service_uuid, characteristic_uuid)
        if isinstance(chr, BleakGATTCharacteristic):
            for i in chr.descriptors:
                if i.uuid == uuid:
                    return i

        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_UNKNOWN_DESCRIPTOR)

    async def read_characteristic(self, service_uuid, uuid) -> gatt_pb2.BLEReadResponse:
        try:
            c = await self._get_chr(service_uuid, uuid)
            if isinstance(c, BleakGATTCharacteristic):
                return gatt_pb2.BLEReadResponse(
                    status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
                    data=bytes(await self._client.read_gatt_char(c)),
                )
            else:
                return c
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )

    async def read_descriptor(
        self, service_uuid, characteristic_uuid, uuid
    ) -> gatt_pb2.BLEReadResponse:
        try:
            c = await self._get_desc(service_uuid, characteristic_uuid, uuid)
            if isinstance(c, BleakGATTDescriptor):
                return gatt_pb2.BLEReadResponse(
                    status=common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK),
                    data=bytes(await self._client.read_gatt_descriptor(c)),
                )
            else:
                return c
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )

    async def write_characteristic(
        self, service_uuid, uuid, data, with_response
    ) -> common_pb2.StatusMessage:
        try:
            c = await self._get_chr(service_uuid, uuid)
            if isinstance(c, BleakGATTCharacteristic):
                await self._client.write_gatt_char(c, data, with_response)
                return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)
            else:
                return c
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )

    async def write_descriptor(
        self, service_uuid, characteristic_uuid, uuid, data
    ) -> common_pb2.StatusMessage:
        try:
            c = await self._get_desc(service_uuid, characteristic_uuid, uuid)
            if isinstance(c, BleakGATTDescriptor):
                await self._client.write_gatt_descriptor(c.handle, data)
                return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)
            else:
                return c
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )

    def notif_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
        """
        Notification callback called by bleak (registered by start_notif)

        Adds a BLENotificationResponse with the provided data in the notifs queue

        Args:
            sender: the BleakGATTCharacteristic used to register the notification
            data: the notification data
        """
        asyncio.get_running_loop().call_soon(
            BLEConn.notif_queue.put_nowait,
            gatt_pb2.BLENotificationResponse(
                device=self._device,
                service_uuid=sender.service_uuid,
                uuid=sender.uuid,
                data=bytes(data),
            ),
        )

    async def subscribe(self, service_uuid, uuid) -> common_pb2.StatusMessage:
        c = await self._get_chr(service_uuid, uuid)
        if not isinstance(c, BleakGATTCharacteristic):
            return c
        try:
            if c not in self._notifs:
                await self._client.start_notify(c, self.notif_callback)
                self._notifs.append(c)
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)

    async def unsubscribe(self, service_uuid, uuid) -> common_pb2.StatusMessage:
        c = await self._get_chr(service_uuid, uuid)
        if not isinstance(c, BleakGATTCharacteristic):
            return c
        try:
            if c in self._notifs:
                await self._client.stop_notify(c)
                del self._notifs[c]
        except BleakError as e:
            return common_pb2.StatusMessage(
                code=common_pb2.ERROR_CODE_ERROR, message=str(e)
            )
        return common_pb2.StatusMessage(code=common_pb2.ERROR_CODE_OK)
