# Home Assistant

This integration provides a Bluetooth proxy implementation using BlueRPC.

## Installation

You can install this integration using [HACS](https://hacs.xyz/):

- In the HACS options > Custom Repositories, add the following [repository](https://github.com/BlueRPC/hass) and select "Integration" as category.
- Then, in HACS, install the BlueRPC integration
- Finally, in the "Devices & Services" page, add a new instance of the BlueRPC integration.

## Configuration

When you add a new instance of the BlueRPC integration, you will need to fill in the IP address of the worker, the port (by default 50052 for python and 5052 for android) and the name of the worker. 

If autodiscovery is enabled, the workers will be detected automatically and you will just need to click the "configure" button to add them.

Encryption is currently not supported.

