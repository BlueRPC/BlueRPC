import asyncio
import collections
import platform
import time
from typing import Dict, List

from bleak import AdvertisementData, BleakScanner, BLEDevice
from bluerpc.rpc import gatt_pb2
from bluerpc.utils import get_kwargs, validate_mac


class BLEScanner:
    """
    This class is used to scan for Bluetooth Low-Energy devices and store the results as ready-to-send proto objects
    """

    scan_queues: Dict[str, asyncio.Queue] = {}
    scanned_devices = collections.deque(maxlen=10)

    def __init__(self, adapter) -> None:
        self.running = False
        self._scanFilters = {}
        self._scan_data = None
        self._adapter = adapter
        self.interval = 1

    def check_filters(self, device: BLEDevice) -> bool:
        """
        Check Filters

        Args:
            device: bleak device
        Returns:
            True if the device matches at least one of the filters (defined in the scan method) or that there is no filters
        """
        k = self._scanFilters.keys()
        if len(k) == 0:
            return True

        if (
            gatt_pb2.BLE_SCAN_FILTER_TYPE_MAC in k
            and device.address in self._scanFilters[gatt_pb2.BLE_SCAN_FILTER_TYPE_MAC]
        ):
            return True
        elif (
            gatt_pb2.BLE_SCAN_FILTER_TYPE_NAME in k
            and device.name in self._scanFilters[gatt_pb2.BLE_SCAN_FILTER_TYPE_NAME]
        ):
            return True

        return False

    async def detection_callback(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """
        Detection callback

        Called from the Bleak Scanner for each device discovered
        Applies the remaining filters, creates the proto objects and adds them to the queues

        Args:
            device: bleak device
            advertisement_data: bleak advertisement data
        """
        if not self.check_filters(device):
            return
        self.scanned_devices.append(device)

        mf_data = []
        adv_data = []
        svc = []
        for k, v in advertisement_data.manufacturer_data.items():
            mf_data.append(gatt_pb2.BLEAdvertisementData(uuid=str(k), value=v))
        for k, v in advertisement_data.service_data.items():
            svc.append(k)
            adv_data.append(gatt_pb2.BLEAdvertisementData(uuid=k, value=v))

        if validate_mac(device.address):
            d = gatt_pb2.BLEDevice(mac=device.address)
        else:
            d = gatt_pb2.BLEDevice(uuid=device.address)
        dev = gatt_pb2.BLEScanResponseData(
            device=d,
            rssi=advertisement_data.rssi,
            name=device.name,
            service_uuids=svc,
            service_data=adv_data,
            manufacturer_data=mf_data,
            time=round(time.time()),
        )
        for i in self.scan_queues.values():
            try:
                i.put_nowait(dev)
            except asyncio.QueueFull:
                i.get_nowait()
                i.put_nowait(dev)

    async def scan(self, active: bool, interval: int, filters: List[gatt_pb2.BLEScanFilter]) -> None:
        """
        Start scanner method

        Args:
            active: if the scanner should be in active or passive mode
            interval: interval to send messages
            filters: list of filters to apply for scanning, services uuid are processed directly by bleak, others are post-processed
        """
        self._scan_data = (active, filters)
        self.running = True
        self.interval = interval
        self._scanFilters = {}
        svc_filters = []
        for i in filters:
            if i.type == gatt_pb2.BLE_SCAN_FILTER_TYPE_UUID:
                svc_filters.append(i.value)
            else:
                if i.type not in self._scanFilters:
                    self._scanFilters[i.type] = []
                self._scanFilters[i.type].append(i.value)

        self._scanner = BleakScanner(
            detection_callback=self.detection_callback,
            scanning_mode=(
                "passive" if not active or platform.system() == "Darwin" else "active"
            ),
            service_uuids=svc_filters,
            **get_kwargs(self._adapter)
        )
        await self._scanner.start()

    async def stop_scan(self) -> None:
        """
        Stop scanner method

        Stops the scanner if not already stopped
        """
        if self.running:
            await self._scanner.stop()
            self.running = False

    async def restart_scan(self) -> None:
        """
        Restart the scanner

        Useful to restart the scanner after it was temporarily stopped to connect to a device
        """
        if self._scan_data and not self.running:
            await self.scan(self._scan_data[0], self._scan_data[1])
