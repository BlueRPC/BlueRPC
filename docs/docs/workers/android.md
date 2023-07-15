# Android

The android worker is available for Android >= 4.3 and Android TV.

## Installation

You can install the android worker, download the apk from the latest release [here](https://github.com/BlueRPC/BlueRPC/releases).

On your smartphone, you can just click on the apk file to install it.

On android tv, you can put the apk file on a usb drive and use a file explorer on the tv to install it.
You can also install it using adb by enabling developer mode and debugging on the tv, and by typing on your pc `adb connect <tvip>` and `adb install <path_to_apk>`.

## Permissions

The application will ask for a number of permissions on the first start, here is an explanation for these permissions.

- Bluetooth connect: starting from android 12, this is required to connect to a bluetooth device
- Nearby devices/Bluetooth find: starting from android 10, this is required to scan for bluetooth devices
- Position: starting from android 6, the location permission is required to scan for bluetooth devices, on the newest devices, you need both this permission and the previous one as the previous one is too restrictive for scanning. It is required to click "Always Allow" as the worker will be running in background.

On start, the application will also ask you to enable (if not already enabled) bluetooth and location


## Configuration

To configure the application, click on the settings button.

|Command|Default|Description|
|--|--|--|
|Device Name|name of your device|the name of the worker|
|GRPC Port|5052|the port of the worker|
|Background Scanning|use filters|background scanning mode (only shown if your version of android is > 8)|
|Enable mDNS|True|enable autodiscovery|
|Enable TLS|False|enable encryption, to enable this, you will first need to select a keystore by clicking on the button below the checkbox|

Background Scanning (ADVANCED):

On android > 8, new limitations were introduced for bluetooth background scanning.

- Force screen to stay ON: if you stay on the app, the screen will stay on forever, preventing to app to go to background
- Ignore background limtations: the worker will report that there is no scanning limitations on this device, use this option for example if you already have an app keeping the screen on
- Use filters: this is the default option, the worker will report that there is a scanning limitation and the client will need to provide scanning filters to allow scanning