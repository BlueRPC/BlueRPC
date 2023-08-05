from enum import Enum


class ClientEvent(Enum):
    RECONNECT_SUCCESS = 1
    RECONNECT_FAILURE = 2
    RECONNECT_ABORT = 3
