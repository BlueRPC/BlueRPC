import asyncio
import logging
from importlib.metadata import version

import grpc
from bluerpc_client.rpc import common_pb2, services_pb2_grpc
from bluerpc_client.utils import BlueRPCConnectionError, ClientEvent
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 50
BACKOFF_BASE = 1.3


class BlueRPC:
    def __init__(
        self,
        host: str,
        port: int = 5052,
        key: bytes | None = None,
        cert: bytes | None = None,
        ca_cert: bytes | None = None,
        client_name: str = "bluerpc_client",
        reconnect: bool = True,
        device_name: str | None = None,
        zeroconf_instance: Zeroconf | None = None,
    ) -> None:
        """
        Client constructor

        Args:
            host: worker address
            port: worker port
            key: PEM encoded key file of the worker
            cert: PEM encoded cert file of the worker
            ca_cert: PEM encoded cert of the certificate authority
            client_name: name of this client
            reconnect: if we should try to reconnect automatically if the connection is lost
            device_name: name of the worker (can be auto filled if a connection is successful)
            zeroconf_instance: zeroconf instance to use (to reconnect immediately if the zeroconf entry of the worker is changed)
        """
        self._host = host
        self._port = port
        self._key = key
        self._cert = cert
        self._ca_cert = ca_cert
        self._client_name = client_name
        self._aiobrowser = None
        self._reconnect_enabled = reconnect
        self._reconnect_retries = 0
        self._reconnect_timer = None
        self._channel = None
        self._name = device_name
        self.settings = None
        self.connected = False
        self.conn = None
        self._loop = asyncio.get_event_loop()
        self._callbacks = []

        if zeroconf_instance:
            self._aiobrowser = AsyncServiceBrowser(
                zeroconf_instance,
                ["_bluerpc._tcp.local."],
                handlers=[self._on_service_state_change],
            )

    async def connect(self) -> bool:
        """
        Connect to the bluerpc server
        If the connection fails, automatically retry if possible

        Returns:
            bool: if success

        Raises:
            BlueRPCConnectionError if connection failed and retry is not possible
        """
        return await self._connect_impl()

    async def _connect_impl(self, reconnect=False) -> bool:
        """
        Internal connection implementation
        Will try to connect using secure or insecure channel and send a HelloRequest

        Args:
            reconnect: if this is a reconnect try or the first connection
        Returns:
            bool: if success
        Raises:
            BlueRPCConnectionError if failed to connect
        """
        try:
            if self._ca_cert and self._cert and self._key:
                creds = grpc.ssl_channel_credentials(
                    self._ca_cert,
                    self._key,
                    self._cert,
                )
                self._channel = grpc.aio.secure_channel(
                    f"{self._host}:{self._port}", creds
                )
            else:
                self._channel = grpc.aio.insecure_channel(f"{self._host}:{self._port}")

            self.conn = services_pb2_grpc.BlueRPCStub(self._channel)

            self.settings = await self.conn.Hello(
                common_pb2.HelloRequest(
                    name=self._client_name, version=version("bluerpc_client")
                )
            )
            _LOGGER.info(
                f"connected to {self.settings.name} v{self.settings.version} ({self.settings.operating_system}: {self.settings.operating_system_version})"
            )
        except grpc.aio._call.AioRpcError as error:
            _LOGGER.debug("bluerpc client can't connect: " + error.details())
            if reconnect:
                await self._call_callbacks(ClientEvent.RECONNECT_FAILURE)
            if self._reconnect_enabled:
                await self._schedule_reconnect()
                return False
            else:
                raise BlueRPCConnectionError(error)

        self.connected = True
        self._reconnect_retries = 0
        self._reconnect_timer = None
        if not self._name:
            self._name = self.settings.name
        if reconnect:
            await self._call_callbacks(ClientEvent.RECONNECT_SUCCESS)
        return True

    async def set_keystore(
        self, data: bytes, overwrite: bool = True, restart: bool = True
    ) -> bool:
        """
        Set the keystore for a worker
        Args:
            data: the keystore data
            overwrite: if a keystore already exists on the worker should be replaced
            restart: if the worker should be restarted to apply the new configuration
        Returns:
            bool: True if success
        """
        try:
            resp = await self.conn.SetKeystore(
                common_pb2.SetKeystoreRequest(
                    data=data, overwrite=overwrite, apply=restart
                )
            )
        except Exception as e:
            _LOGGER.warning("an error occured while setting the keystore: " + str(e))
            return False
        if resp.code == common_pb2.ERROR_CODE_KEYSTORE_ALREADY_EXISTS:
            _LOGGER.warning("keystore already exists")
        elif resp.code != common_pb2.ERROR_CODE_OK:
            _LOGGER.warning("error while setting keystore: " + resp.message)
        else:
            return True
        return False

    async def can_connect(self):
        """
        Check if we can connect to a device on this worker
        """
        try:
            resp = self.conn.BLEGetDevices(common_pb2.Void())
            assert resp.status.code == common_pb2.ERROR_CODE_OK
            assert (
                resp.max_connections == 0
                or resp.connected_devices < resp.max_connections
            )
            return True
        except grpc.aio._call.AioRpcError as err:
            await self.on_disconnect_err(err)
        except Exception as err:
            _LOGGER.error(str(err))
        return False

    async def disconnect(self):
        """
        Disconnect from bluerpc server
        """
        if self.connected:
            await self._channel.close()
            self.connected = False
        elif self._reconnect_timer:
            self._reconnect_timer.cancel()

    async def on_disconnect_err(self, error: grpc.aio._call.AioRpcError):
        """
        Function to call when the client is unexpectedly disconnected
        Will try to reconnect if possible
        """
        _LOGGER.debug(
            "bluerpc client unexpectedly disconnected with: " + error.details()
        )
        if self.connected and self._reconnect_enabled:
            self.connected = False
            await self._schedule_reconnect()
        else:
            self.connected = False

    async def _schedule_reconnect(self):
        """Schedule a reconnection attempt using exponential backoff (if max retries is not reached)"""
        self._reconnect_retries += 1
        if self._reconnect_retries > MAX_RETRIES:
            _LOGGER.error("connection failed, max number of retries reached")
            await self._call_callbacks(ClientEvent.RECONNECT_ABORT)
            return

        delay = BACKOFF_BASE**self._reconnect_retries
        _LOGGER.debug(
            f"retry #{self._reconnect_retries}, attempting to reconnect in {delay}"
        )
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
        self._reconnect_timer = self._loop.call_later(
            delay, self._connect_impl_sync, True
        )

    def _on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Callback for zeroconf service state change"""
        assert service_type == "_bluerpc._tcp.local."
        if (
            (
                state_change == ServiceStateChange.Added
                or state_change == ServiceStateChange.Updated
            )
            and name == f"{self._name}._bluerpc._tcp.local."
            and self._reconnect_timer
        ):
            # if this device has been discovered and that a connection retry is in scheduled, cancel it and run it immediately
            _LOGGER.debug(
                f"{name} zeroconf entry {'added' if state_change == ServiceStateChange else 'updated'}, retrying connection now"
            )
            self._reconnect_timer.cancel()
            asyncio.run_coroutine_threadsafe(self._connect_impl(True), self._loop)

    async def stop(self):
        """Disconnect and delete client"""
        await self.disconnect()
        if self._aiobrowser:
            await self._aiobrowser.async_cancel()

    async def register_callback(self, fun):
        """
        Register a callback for client events

        Args:
            fun: the callback function taking one argument of type ClientEvent
        """
        self._callbacks.append(fun)

    async def unregister_callback(self, fun):
        """
        Unregister a callback for client envents

        Args:
            fun: the callback function previously registered
        """
        del self._callbacks[fun]

    async def _call_callbacks(self, type: ClientEvent):
        """
        Call the registered callbacks with the client event
        """
        for i in self._callbacks:
            await i(type)

    def _connect_impl_sync(self, *args):
        asyncio.create_task(self._connect_impl(*args))
