# Python

The python worker is available for Windows, Linux and MacOS.

## Installation

You can install the python worker using pip with `pip install bluerpc`. You can then run it with the command `bluerpc`.

You can also run it using docker with this image `ghcr.io/bluerpc/worker`, an example docker-compose file is provided [here](https://github.com/BlueRPC/BlueRPC/blob/master/src/python/docker-compose.yml).

## Configuration

|Command|Default|Description|
|--|--|--|
|debug|False|enable debug logging, default level is info|
|bind_addr|[::]:50052|the bind address of the worker|
|name|hostname of the pc|the name of the worker|
|adapter|autoselect|the mac address of the bluetooth adapter to use (linux only)|
|list-adapters|False|list available bluetooth adapters (linux only)|
|keystore|no encryption|path to a keystore for encryption support|