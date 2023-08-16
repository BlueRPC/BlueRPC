from enum import Enum

from grpc.aio._call import AioRpcError


class ClientEvent(Enum):
    RECONNECT_SUCCESS = 1
    RECONNECT_FAILURE = 2
    RECONNECT_ABORT = 3


class BlueRPCException(Exception):
    pass


class BlueRPCInvalidReturnCode(BlueRPCException):
    pass


class BlueRPCConnectionError(BlueRPCException):
    def __init__(self, exc: AioRpcError) -> None:
        super().__init__(exc.details())
