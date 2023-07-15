package com.bluerpc.worker

import android.annotation.SuppressLint
import android.bluetooth.*
import android.content.Context
import android.os.Build
import com.bluerpc.rpc.*
import com.google.protobuf.ByteString
import io.grpc.stub.StreamObserver
import java.util.*


@SuppressLint("MissingPermission")
class BLEConnection(private val ctx: Context) {
    private val adapter = (ctx.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private var devices: MutableMap<String, BLEDeviceData> = mutableMapOf()
    var disconnectObservers: MutableList<StreamObserver<BLEDevice>> = mutableListOf()
    var notificationObservers: MutableList<StreamObserver<BLENotificationResponse>> = mutableListOf()
    private val statusOK = StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build()
    private val statusLocked = StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_DEVICE_BUSY).setMessage("an operation is already in progress").build()
    private val notificationDescriptor = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    /**
     * Callback object for all gatt operations
     */
    private val gattCallback = object: BluetoothGattCallback() {

        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            super.onConnectionStateChange(gatt, status, newState)
            if (newState == BluetoothGatt.STATE_DISCONNECTED) {
                // if still waiting for callback, send an error
                devices[gatt.device.address]?.cancel()

                // send disconnect message
                val disconnectMsg = BLEDevice.newBuilder().setMac(gatt.device.address).build()
                for (d in disconnectObservers) {
                    try {
                        d.onNext(disconnectMsg)
                    } catch (e: java.lang.Exception) {
                        disconnectObservers.remove(d)
                    }
                }
                // remove device from connected list
                devices.remove(gatt.device.address)
            } else if (newState == BluetoothGatt.STATE_CONNECTED) {
                // start discovery of services (needed for every operation)
                gatt.discoverServices()
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            devices[gatt.device.address]?.finishDiscovery()
        }

        override fun onCharacteristicRead(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
            status: Int
        ) {
            val dev = devices[gatt.device.address]
            if (status == BluetoothGatt.GATT_SUCCESS)
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(statusOK).setData(
                        ByteString.copyFrom(value)
                    ).build()
                )
            else
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(
                        StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                            .setMessage("gatt chr read error, (callback) code: $status")
                    ).build()
                )
            dev?.readResponseObserver?.onCompleted()
            dev?.done()
        }

        @Deprecated("Used natively in Android 12 and lower", level = DeprecationLevel.HIDDEN)
        override fun onCharacteristicRead(
            gatt: BluetoothGatt?,
            characteristic: BluetoothGattCharacteristic?,
            status: Int
        ) {
            if (gatt != null && characteristic != null)
                onCharacteristicRead(gatt, characteristic, characteristic.value, status)
            else if (gatt != null) {
                val dev = devices[gatt.device.address]
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(
                        StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                            .setMessage("characteristic unavailable (callback)")
                    ).build()
                )
                dev?.readResponseObserver?.onCompleted()
                dev?.done()
            }
        }

        override fun onCharacteristicWrite(
            gatt: BluetoothGatt?,
            characteristic: BluetoothGattCharacteristic?,
            status: Int
        ) {
            if(gatt != null) {
                val dev = devices[gatt.device.address]
                if (status == BluetoothGatt.GATT_SUCCESS)
                    dev?.statusResponseObserver?.onNext(statusOK)
                else
                    dev?.statusResponseObserver?.onNext(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage(
                        "error writing characteristic, (callback) code:$status"
                    ).build()
                )
                dev?.statusResponseObserver?.onCompleted()
                dev?.done()
            }
        }

        override fun onDescriptorRead(
            gatt: BluetoothGatt,
            descriptor: BluetoothGattDescriptor,
            status: Int,
            value: ByteArray
        ) {
            val dev = devices[gatt.device.address]
            if (status == BluetoothGatt.GATT_SUCCESS)
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(statusOK).setData(
                        ByteString.copyFrom(value)
                    ).build()
                )
            else
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(
                        StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                            .setMessage("gatt desc read error, (callback) code: $status")
                    ).build()
                )
            dev?.readResponseObserver?.onCompleted()
            dev?.done()
        }

        @Deprecated("Used natively in Android 12 and lower", level = DeprecationLevel.HIDDEN)
        override fun onDescriptorRead(
            gatt: BluetoothGatt?,
            descriptor: BluetoothGattDescriptor?,
            status: Int
        ) {
            if (gatt != null && descriptor != null)
                onDescriptorRead(gatt, descriptor, status, descriptor.value)
            else if (gatt != null) {
                val dev = devices[gatt.device.address]
                dev?.readResponseObserver?.onNext(
                    BLEReadResponse.newBuilder().setStatus(
                        StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                            .setMessage("descriptor unavailable (callback)")
                    ).build()
                )
                dev?.readResponseObserver?.onCompleted()
                dev?.done()
            }
        }

        override fun onDescriptorWrite(
            gatt: BluetoothGatt?,
            descriptor: BluetoothGattDescriptor?,
            status: Int
        ) {
            if(gatt != null) {
                val dev = devices[gatt.device.address]

                if(descriptor?.uuid == notificationDescriptor) {
                    // if notification descriptor, subscribe to notification
                    if(dev != null) {
                        val chr = getCharacteristic(dev.gattDevice, dev.service, dev.characteristic)
                        if(chr != null) {
                            chr.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                            if (dev.gattDevice.setCharacteristicNotification(chr, true))
                                dev.statusResponseObserver?.onNext(statusOK)
                            else
                                dev.statusResponseObserver?.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("failed to subscribe to notification (callback)").build())
                            dev.statusResponseObserver?.onCompleted()
                        } else {
                            dev.statusResponseObserver?.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_CHARACTERISTIC).setMessage("failed to subscribe to notification (callback)").build())
                        }
                    }
                } else {
                    // else, just send descriptor write status
                    if (status == BluetoothGatt.GATT_SUCCESS)
                        dev?.statusResponseObserver?.onNext(statusOK)
                    else
                        dev?.statusResponseObserver?.onNext(
                            StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage(
                                "error writing descriptor, (callback) code:$status"
                            ).build()
                        )
                    dev?.statusResponseObserver?.onCompleted()
                }
                dev?.done()
            }
        }

        @Deprecated("Used natively in Android 12 and lower", level = DeprecationLevel.HIDDEN)
        override fun onCharacteristicChanged(
            gatt: BluetoothGatt?,
            characteristic: BluetoothGattCharacteristic?
        ) {
            if(gatt != null && characteristic != null)
                onCharacteristicChanged(gatt, characteristic, characteristic.value)
        }

        // when a notification is received
        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray
        ) {
            val dev = devices[gatt.device.address]
            for(n in notificationObservers) {
                try {
                    n.onNext(
                        BLENotificationResponse.newBuilder().setDevice(dev?.device).setData(
                            ByteString.copyFrom(value)
                        ).setUuid(characteristic.uuid.toString()).build()
                    )
                } catch (e: java.lang.Exception) {
                    notificationObservers.remove(n)
                }
            }
        }

        override fun onReadRemoteRssi(gatt: BluetoothGatt?, rssi: Int, status: Int) {
            if(gatt != null) {
                devices[gatt.device.address]?.setConnRssi(rssi.toFloat())
            }
        }
    }

    fun connect(request: BLEConnectRequest, responseObserver: StreamObserver<BLEConnectResponse>
    ) {
        val dev: BluetoothDevice = adapter.getRemoteDevice(request.device.mac)
        try {
            val gatt = dev.connectGatt(ctx, false, gattCallback)
            devices[request.device.mac] = BLEDeviceData(gatt, request.device)
            responseObserver.onNext(
                BLEConnectResponse.newBuilder()
                    .setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())
                    .build()
            )
            responseObserver.onCompleted()
        } catch (e: Exception) {
            responseObserver.onNext(
                BLEConnectResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_FAILED)
                        .setMessage(e.toString()).build()
                ).build()
            )
            responseObserver.onCompleted()
        }
    }

    fun disconnect(request: BLEDevice, responseObserver: StreamObserver<StatusMessage>) {
        devices[request.mac]?.gattDevice?.disconnect()
        responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())
        responseObserver.onCompleted()
    }

    /**
     * Block until device is ready to be queried
     * @param mac the mac address of the device
     * @return true if the device is still connected
     */
    private fun checkDiscovery(mac: String): Boolean {
        try {
            while (devices[mac]?.discoveryFinished != true) {
                Thread.sleep(50)
            }
        } catch (_: InterruptedException) {}
        return devices.containsKey(mac)
    }

    /**
     * Map android BluetoothGattCharacteristic to gRPC BLEChrProperty
     * @param chr The android ble characteristics properties
     * @return a list of BLEChrProperty
     */
    private fun getCharacteristicProperties(chr: BluetoothGattCharacteristic): List<BLEChrProperty>? {
        val props: MutableList<BLEChrProperty> = mutableListOf()
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_READ != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_READ)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_WRITE)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_NOTIFY)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_BROADCAST != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_BROADCAST)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_EXTENDED_PROPS != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_EXTENDED_PROPS)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_INDICATE != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_INDICATE)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_SIGNED_WRITE != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_SIGNED_WRITE)
        if (chr.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_WRITE_NO_RESPONSE)
        if (props.size == 0) props.add(BLEChrProperty.BLE_CHR_PROPERTY_UNK)
        return props
    }

    fun listServices(request: BLEDevice, responseObserver: StreamObserver<BLEListServicesResponse>) {
        if(!checkDiscovery(request.mac)) {
            responseObserver.onNext(BLEListServicesResponse.newBuilder().setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build()).build())
            responseObserver.onCompleted()
            return
        }

        val lst: MutableList<BLEService> = mutableListOf()
        val svcs = devices[request.mac]?.gattDevice?.services
        if(svcs == null) {
            responseObserver.onNext(
                BLEListServicesResponse.newBuilder().setDevice(request)
                    .setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).build()).build()
            )
            responseObserver.onCompleted()
            return
        }
        for (sv in svcs) {
            val chrs: MutableList<BLECharacteristic> = mutableListOf()
            for (chr in sv.characteristics) {
                val descs: MutableList<BLEDescriptor> = mutableListOf()
                for (desc in chr.descriptors) {
                    descs.add(BLEDescriptor.newBuilder().setUuid(desc.uuid.toString()).build())
                }
                chrs.add(
                    BLECharacteristic.newBuilder()
                        .setUuid(chr.uuid.toString())
                        .addAllProperties(getCharacteristicProperties(chr))
                        .addAllDescriptors(descs)
                        .build()
                )
            }
            lst.add(
                BLEService.newBuilder()
                    .setUuid(sv.uuid.toString())
                    .addAllCharacteristics(chrs)
                    .build()
            )
        }
        responseObserver.onNext(
            BLEListServicesResponse.newBuilder().addAllServices(lst).setDevice(request)
                .setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build()).build()
        )
        responseObserver.onCompleted()
    }

    /**
     * Find a characteristic
     * @param gatt gatt device
     * @param svc service uuid (can be empty, the first characteristic found will be returned)
     * @param chr characteristic uuid (required)
     * @return null if not found
     */
    private fun getCharacteristic(gatt: BluetoothGatt, svc: String, chr: String): BluetoothGattCharacteristic? {
        if(svc == "") {
            for (sv in gatt.services) {
                for (c in sv.characteristics) {
                    if (c.uuid.toString() == chr) {
                        return c
                    }
                }
            }
        } else {
            return gatt.getService(UUID.fromString(svc))?.getCharacteristic(UUID.fromString(chr))
        }
        return null
    }

    fun readCharacteristic(request: BLEReadCharacteristicRequest, responseObserver: StreamObserver<BLEReadResponse>) {
        if(!checkDiscovery(request.device.mac)) {
            responseObserver.onNext(BLEReadResponse.newBuilder().setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build()).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.device.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(BLEReadResponse.newBuilder().setStatus(statusLocked).build())
            responseObserver.onCompleted()
            return
        }

        dev.readResponseObserver = responseObserver
        dev.setGATT(request.serviceUuid, request.uuid)
        val chr = getCharacteristic(dev.gattDevice, request.serviceUuid, request.uuid)
        // if not found
        if (chr == null) {
            responseObserver.onNext(
                BLEReadResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_CHARACTERISTIC)
                        .setMessage("unable to find characteristic").build()
                ).build()
            )
            responseObserver.onCompleted()
            dev.done()
        }
        // check for error returned when reading
        else if (!dev.gattDevice.readCharacteristic(chr)) {
            responseObserver.onNext(
                BLEReadResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                        .setMessage("unable to read characteristic").build()
                ).build()
            )
            responseObserver.onCompleted()
            dev.done()
        }
    }

    /**
     * Convert gRPC gatt write mode to android gatt write mode
     * @param m the BLEWriteMode
     * @return a BluetoothGattCharacteristic write type integer
     */
    private fun getWriteMode(m: BLEWriteMode): Int {
        return when (m) {
            BLEWriteMode.BLE_WRITE_MODE_NO_RESPONSE -> BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            BLEWriteMode.BLE_WRITE_MODE_SIGNED -> BluetoothGattCharacteristic.WRITE_TYPE_SIGNED
            else -> BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        }
    }

    fun writeCharacteristic(request: BLEWriteCharacteristicRequest, responseObserver: StreamObserver<StatusMessage>) {
        if(!checkDiscovery(request.device.mac)) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.device.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(statusLocked)
            responseObserver.onCompleted()
            return
        }

        dev.statusResponseObserver = responseObserver
        dev.setGATT(request.serviceUuid, request.uuid)
        val chr = getCharacteristic(dev.gattDevice, request.serviceUuid, request.uuid)
        // if not found
        if (chr == null) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_CHARACTERISTIC).setMessage("unable to find characteristic").build())
            responseObserver.onCompleted()
            dev.done()
        }
        else {
            var status = BluetoothGatt.GATT_FAILURE
            // write characteristic (different method if android > 33)
            if(Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                chr.writeType = getWriteMode(request.mode)
                chr.value = request.data.toByteArray()
                if(dev.gattDevice.writeCharacteristic(chr))
                    status = BluetoothGatt.GATT_SUCCESS
            } else {
                status = dev.gattDevice.writeCharacteristic(chr, request.data.toByteArray(), getWriteMode(request.mode))
            }
            // check for error returned when writing
            if (status != BluetoothGatt.GATT_SUCCESS) {
                responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("unable to write characteristic, error code: $status").build())
                responseObserver.onCompleted()
                dev.done()
            }
        }
    }

    fun readDescriptor(request: BLEReadDescriptorRequest, responseObserver: StreamObserver<BLEReadResponse>) {
        if(!checkDiscovery(request.device.mac)) {
            responseObserver.onNext(BLEReadResponse.newBuilder().setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build()).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.device.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(BLEReadResponse.newBuilder().setStatus(statusLocked).build())
            responseObserver.onCompleted()
            return
        }

        dev.readResponseObserver = responseObserver
        dev.setGATT(request.serviceUuid, request.characteristicUuid, request.uuid)
        val desc = getCharacteristic(dev.gattDevice, request.serviceUuid, request.characteristicUuid)?.getDescriptor(UUID.fromString(request.uuid))
        // if not found
        if (desc == null) {
            responseObserver.onNext(
                BLEReadResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_DESCRIPTOR)
                        .setMessage("unable to find descriptor").build()
                ).build()
            )
            responseObserver.onCompleted()
            dev.done()
        }
        // check for error returned when reading
        else if (!dev.gattDevice.readDescriptor(desc)) {
            responseObserver.onNext(
                BLEReadResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR)
                        .setMessage("unable to read descriptor").build()
                ).build()
            )
            responseObserver.onCompleted()
            dev.done()
        }
    }

    fun writeDescriptor(request: BLEWriteDescriptorRequest, responseObserver: StreamObserver<StatusMessage>) {
        if(!checkDiscovery(request.device.mac)) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.device.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(statusLocked)
            responseObserver.onCompleted()
            return
        }

        dev.statusResponseObserver = responseObserver
        dev.setGATT(request.serviceUuid, request.characteristicUuid, request.uuid)
        val desc = getCharacteristic(dev.gattDevice, request.serviceUuid, request.characteristicUuid)?.getDescriptor(UUID.fromString(request.uuid))
        // if not found
        if (desc == null) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_DESCRIPTOR).setMessage("unable to find descriptor").build())
            responseObserver.onCompleted()
        }
        else {
            var status = BluetoothGatt.GATT_FAILURE
            // write descriptor (different method if android > 33)
            if(Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                desc.value = request.data.toByteArray()
                if(dev.gattDevice.writeDescriptor(desc))
                    status = BluetoothGatt.GATT_SUCCESS
            } else {
                status = dev.gattDevice.writeDescriptor(desc, request.data.toByteArray())
            }
            // check for error returned when writing
            if (status != BluetoothGatt.GATT_SUCCESS) {
                responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("unable to write descriptor, error code: $status").build())
                responseObserver.onCompleted()
                dev.done()
            }
        }
    }

    fun notification(request: BLENotificationRequest, responseObserver: StreamObserver<StatusMessage>) {
        if(!checkDiscovery(request.device.mac)) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.device.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(statusLocked)
            responseObserver.onCompleted()
            return
        }


        val chr = getCharacteristic(dev.gattDevice, request.serviceUuid, request.uuid)
        // if not found
        if (chr == null) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_UNKNOWN_CHARACTERISTIC)
                .setMessage("unable to find characteristic").build())
            responseObserver.onCompleted()
            return
        }

        if(request.subscribe) {
            // enable notification by writing a special descriptor
            // the notification subscription will be enabled in the descriptor write callback
            dev.setGATT(request.serviceUuid, request.uuid)
            dev.statusResponseObserver = responseObserver

            var status = BluetoothGatt.GATT_FAILURE
            val desc: BluetoothGattDescriptor = chr.getDescriptor(notificationDescriptor)
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                desc.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                if(dev.gattDevice.writeDescriptor(desc))
                    status = BluetoothGatt.GATT_SUCCESS
            } else {
                status = dev.gattDevice.writeDescriptor(desc, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            }

            // check for error returned when writing
            if (status != BluetoothGatt.GATT_SUCCESS) {
                responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("unable to write descriptor for notification, error code: $status").build())
                responseObserver.onCompleted()
                dev.done()
            }
        } else {
            // unsubscribe from notification
            if(dev.gattDevice.setCharacteristicNotification(chr, false))
                responseObserver.onNext(statusOK)
            else
                responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("failed to unsubscribe from notification").build())
            responseObserver.onCompleted()
        }
    }

    fun getDevices(responseObserver: StreamObserver<BLEDevicesResponse>) {
        responseObserver.onNext(
            BLEDevicesResponse.newBuilder()
                .setStatus(statusOK)
                .addAllConnectedDevices(devices.map { x -> x.value.device })
                .addAllPairedDevices(adapter.bondedDevices
                    .filter { x -> x.type == BluetoothDevice.DEVICE_TYPE_LE }
                    .map { x -> BLEDevice.newBuilder().setMac(x.address).build() }
                )
                .setMaxConnections(7)
                .setReliablePairedList(true)
                .build()
        )
        responseObserver.onCompleted()
    }

    fun getConnectionProperties(request: BLEDevice, responseObserver: StreamObserver<BLEConnectionPropertiesResponse>) {
        if(!checkDiscovery(request.mac)) {
            responseObserver.onNext(
                BLEConnectionPropertiesResponse.newBuilder().setStatus(
                    StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_REQUIRED).build()
                ).build())
            responseObserver.onCompleted()
            return
        }

        val dev: BLEDeviceData = devices[request.mac]!!
        if(dev.lockOperation) {
            responseObserver.onNext(BLEConnectionPropertiesResponse.newBuilder().setStatus(statusLocked).build())
            responseObserver.onCompleted()
            return
        }

        if(!dev.gattDevice.readRemoteRssi()) {
            responseObserver.onNext(BLEConnectionPropertiesResponse.newBuilder().setStatus(
                StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_ERROR).setMessage("unable to read device rssi").build()
            ).build())
            responseObserver.onCompleted()
        } else {
            dev.setConnPropsResponseObserver(responseObserver)
        }
    }
}