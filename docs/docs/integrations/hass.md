# Home Assistant

This integration provides a Bluetooth proxy implementation using BlueRPC.

## Installation

To install this integration, you will need to edit a few this about your installation:

(This is caused by limitations on the way integrations are installed: to enable this one, we need to add it to a file of the bluetooth_adapters integrations, and we also need to manually install the `bluerpc-client` package because the `grpcio` package in home-assistant is pinned to an incompatible version).

### For docker

You will need to use [this dockerfile](https://github.com/BlueRPC/hass-integration/blob/main/Dockerfile) to build your home-assistant image.

You can then install this integration using [HACS](https://hacs.xyz/):

- In the HACS options > Custom Repositories, add the following [repository](https://github.com/BlueRPC/hass) and select "Integration" as category.
- Then, in HACS, install the BlueRPC integration
- Finally, in the "Devices & Services" page, add a new instance of the BlueRPC integration.

## Configuration

When you add a new instance of the BlueRPC integration, you will need to fill in the IP address of the worker, the port (by default 5052) and the name of the worker. 

If autodiscovery is enabled, the workers will be detected automatically and you will just need to click the "configure" button to add them.

The last field is for the keystore password (to enable encryption), you need to set the same password on the worker (either in the app settings for android or using the `--keystore-password` option for python). It is recommanded to use a strong password and to not reuse it between multiple workers.
