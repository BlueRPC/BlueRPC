# Getting Started

To get started with BlueRPC, you need to install at least one worker and an integration.

## Worker

The workers are responsible for relaying the bluetooth commands to your bluetooth devices, they are currently two types of worker availables.

For a computer running Linux, MacOS or Windows, use the [python worker](workers/python.md).
You can install it with `pip install bluerpc` and run it directly with the command `bluerpc`.

For an android smartphone or a tv/box running android tv, use the [android worker](workers/android.md).
You can download the apk file on the [latest release](https://github.com/BlueRPC/BlueRPC/releases).

## Integration

Currently, the only integration is for Home-Assistant.

You can install it using [HACS](https://hacs.xyz/):

- In the HACS options > Custom Repositories, add the following [repository](https://github.com/BlueRPC/hass) and select "Integration" as category.
- Then,in HACS, install the BlueRPC integration
- Finally, in the "Devices & Services" page, add a new instance of the BlueRPC integration.

You need to repeat the third step for each worker.

You need to fill in the IP address of the worker, the port (by default 50052 for python and 5052 for android) and the name of the worker. 

If autodiscovery is enabled, the workers will be detected automatically and you will just need to click the "configure" button to add them.