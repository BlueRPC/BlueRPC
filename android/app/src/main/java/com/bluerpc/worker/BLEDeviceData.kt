package com.bluerpc.worker

import android.bluetooth.BluetoothGatt
import com.bluerpc.rpc.*

import io.grpc.stub.StreamObserver

class BLEDeviceData(val gattDevice: BluetoothGatt, val device: BLEDevice) {
    var statusResponseObserver: StreamObserver<StatusMessage>? = null
    var readResponseObserver: StreamObserver<BLEReadResponse>? = null
    var lockOperation = false
        private set
    var service = ""
        private set
    var characteristic = ""
        private set
    var descriptor = ""
        private set
    var discoveryFinished = false
        private set

    fun finishDiscovery() {
        discoveryFinished = true
    }

    fun done() {
        lockOperation = false
        readResponseObserver = null
        statusResponseObserver = null
    }

    fun setGATT(svc: String, chr: String, desc: String = "") {
        service = svc
        characteristic = chr
        descriptor = desc
        lockOperation = true
    }

    fun cancel() {
        val status = StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_CONNECTION_FAILED)
            .setMessage("connection closed before response was received").build()
        try {
            statusResponseObserver?.onNext(status)
            statusResponseObserver?.onCompleted()
            readResponseObserver?.onNext(BLEReadResponse.newBuilder().setStatus(status).build())
            readResponseObserver?.onCompleted()
        } catch (e: java.lang.Exception) {
        }
    }


    private var connPropsResponseObserver: StreamObserver<BLEConnectionPropertiesResponse>? = null
    private val initConnStates = mutableMapOf<String, Boolean>("rssi" to false)
    private var connStates = initConnStates
    private var connData = BLEConnectionPropertiesResponse.newBuilder()

    fun setConnPropsResponseObserver(obs: StreamObserver<BLEConnectionPropertiesResponse>) {
        connPropsResponseObserver = obs
        connData = BLEConnectionPropertiesResponse.newBuilder()
    }

    fun setConnRssi(value: Float?) {
        connStates["rssi"] = true
        if(value != null)
            connData.rssi = value
        sendConnData()
    }

    private fun sendConnData() {
        if(!connStates.values.contains(false)) {
            // send
            connPropsResponseObserver?.onNext(connData.setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build()).build())
            connPropsResponseObserver?.onCompleted()

            // reset
            connStates = initConnStates
            connData = BLEConnectionPropertiesResponse.newBuilder()
            connPropsResponseObserver = null
        }
    }
}