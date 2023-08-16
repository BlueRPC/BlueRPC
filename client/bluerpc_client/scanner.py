"""Bluetooth scanner for BlueRPC."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List

import grpc
from bluerpc_client.rpc import common_pb2, gatt_pb2
from bluerpc_client.utils import (
    BlueRPCConnectionError,
    BlueRPCInvalidReturnCode,
    ClientEvent,
)

_LOGGER = logging.getLogger(__name__)


class BlueRPCBLEScanner:
    """Scanner for BlueRPC BLE devices."""

    def __init__(
        self,
        client,
        on_advertisement,
        on_disconnect=None,
        services: List[str] = [],
        reconnect=True,
    ) -> None:
        """
        Create the scanner

        Args:
            client: a BlueRPC client instance (must be already connected to start the scanner)
            on_advertisement: a callback function taking one argument of type BlueRPCBLEAdvertisement, will be called on each new advertisement
            on_disconnect: a callback function called when the scanner is disconnected
            services: a list of service uuid to filter on
            reconnect: if the scanner should try to reconnect if the connection is lost (must also be enabled for the client)
        """
        self._client = client
        self._filters = []
        self._on_advertisement = on_advertisement
        self._on_disconnect = on_disconnect
        for i in services:
            self._filters.append(
                gatt_pb2.BLEScanFilter(type=gatt_pb2.BLE_SCAN_FILTER_TYPE_UUID, value=i)
            )
        self._reconnect = reconnect
        self._connect_lock = asyncio.Lock()
        self._reconnect_aborted = False

    async def start(self) -> bool:
        """Start the scanner"""
        await self._client.register_callback(self._on_client_event)
        await self._connect_lock.acquire()
        return await self._start_impl()

    async def _start_impl(self) -> bool:
        """Start the scanner"""
        try:
            resp = await self._client.conn.BLEScanStart(
                gatt_pb2.BLEScanRequest(
                    interval=2000,
                    active=True,
                    filters=self._filters,
                    merge_filters=self._client.settings.ble_filters_required,
                )
            )
            if (
                resp.code == common_pb2.ERROR_CODE_OK
                or resp.code == common_pb2.ERROR_CODE_SCAN_ALREADY_RUNNING
            ):
                asyncio.create_task(self._scan_handler())
                return True
            else:
                raise BlueRPCInvalidReturnCode(
                    f"scanner connect error: {resp.message} (code {resp.code})"
                )
        except grpc.aio._call.AioRpcError as e:
            if self._reconnect:
                # if connection failed, create scan handler, the conn will fail
                # and go in the except block to ask for reconnect and wait until connected
                asyncio.create_task(self._scan_handler())
            else:
                raise BlueRPCConnectionError(e)

        return False

    async def stop(self):
        """Stop the scanner"""
        try:
            if self._client.connected:
                await self._client.conn.BLEScanStop(common_pb2.Void())
        except grpc.aio._call.AioRpcError as e:
            _LOGGER.error(str(e))
        finally:
            await self._connect_lock.release()
            if self._on_disconnect is not None:
                self._on_disconnect()

    async def _scan_handler(self):
        """Background task to receive the bluetooth advertisements"""
        try:
            async for response in self._client.conn.BLEReceiveScan(common_pb2.Void()):
                if response.status.code == common_pb2.ERROR_CODE_SCAN_STOPPED:
                    # auto restart ?
                    await self.stop()
                    break
                elif response.status.code == common_pb2.ERROR_CODE_OK:
                    for i in response.data:
                        self._on_advertisement(BlueRPCBLEAdvertisement(i))
                else:
                    _LOGGER.warning(
                        f"scanner adv error: {response.status.message} (code {response.status.code})"
                    )
        except grpc.aio._call.AioRpcError as e:
            if self._reconnect:
                await self._client.on_disconnect_err(e)
                await self._connect_lock.acquire()
                if self._reconnect_aborted:
                    raise e
                else:
                    await self._start_impl()
            else:
                await self._client.on_disconnect_err(e)
                if self._on_disconnect is not None:
                    self._on_disconnect()

    async def _on_client_event(self, event):
        if self._reconnect and (
            event == ClientEvent.RECONNECT_SUCCESS
            or event == ClientEvent.RECONNECT_ABORT
        ):
            self._reconnect_aborted = event == ClientEvent.RECONNECT_ABORT
            self._connect_lock.release()


@dataclass(frozen=True)
class BlueRPCBLEAdvertisement:
    mac_address: str
    name: str
    rssi: float
    txpwr: float
    service_uuids: List[str]
    service_data: Dict[str, bytes]
    manufacturer_data: Dict[int, bytes]

    def __init__(self, resp: gatt_pb2.BLEScanResponseData):
        self.name = resp.name
        self.mac_address = resp.device.mac
        self.rssi = resp.rssi
        self.txpwr = resp.txpwr
        self.service_uuids = list(resp.service_uuids)
        self.service_data = {}
        for i in resp.service_data:
            self.service_data[i.uuid] = bytes(i.value)
        self.manufacturer_data = {}
        for i in resp.manufacturer_data:
            self.manufacturer_data[i.uuid] = bytes(i.value)
