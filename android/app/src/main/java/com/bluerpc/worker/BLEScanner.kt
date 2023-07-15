package com.bluerpc.worker

import android.annotation.SuppressLint
import android.os.ParcelUuid
import com.bluerpc.rpc.*
import com.google.protobuf.ByteString
import io.grpc.stub.StreamObserver
import no.nordicsemi.android.support.v18.scanner.*
import java.util.*
import java.util.concurrent.BlockingQueue
import java.util.concurrent.LinkedBlockingDeque

/**
 * Class handling BLE Scanning
 */
class BLEScanner {
    private var currentScanFilters = arrayListOf<ScanFilter>()
    private lateinit var scanner: BluetoothLeScannerCompat
    val observers: MutableList<StreamObserver<BLEScanResponse>> = mutableListOf()
    var isRunning = false

    /**
     * Convert gRPC BLEScanFilter to nordic ScanFilter
     * @param filters filters received in the gRPC request
     * @param mergeFilters if the new filters should be merged with the existing ones or replace them
     */
    fun setScanFilters(filters: List<BLEScanFilter>, mergeFilters: Boolean) {
        if(!mergeFilters)
            currentScanFilters = arrayListOf()

        for(f in filters) {
            when (f.type) {
                BLEScanFilterType.BLE_SCAN_FILTER_TYPE_MAC -> currentScanFilters.add(ScanFilter.Builder().setDeviceAddress(f.value).build())
                BLEScanFilterType.BLE_SCAN_FILTER_TYPE_NAME -> currentScanFilters.add(ScanFilter.Builder().setDeviceName(f.value).build())
                BLEScanFilterType.BLE_SCAN_FILTER_TYPE_UUID -> currentScanFilters.add(ScanFilter.Builder().setServiceUuid(ParcelUuid.fromString(f.value)).build())
                else -> {}
            }
        }
    }

    /**
     * Start BLE scan
     * @param active if the scan is in active or passive mode
     * @param interval scan interval
     */
    fun scan(active: Boolean, interval: Long) {
        scanner = BluetoothLeScannerCompat.getScanner()
        val scanSettings = ScanSettings.Builder()
            .setLegacy(false)
            .setScanMode(if (active) ScanSettings.SCAN_MODE_LOW_LATENCY else ScanSettings.SCAN_MODE_LOW_POWER)
            .setReportDelay(interval)
            .setUseHardwareBatchingIfSupported(true)
            .build()
        if(isRunning)
            stopScan()
        scanner.startScan(
            currentScanFilters, scanSettings, scanCallback
        )
        isRunning = true
    }

    fun stopScan() {
        scanner.stopScan(scanCallback)
        isRunning = false
    }

    /**
     * Scan Collback
     * used to process new scan results
     */
    private val scanCallback = object:ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            super.onScanResult(callbackType, result)
            addResult(result)
        }

        override fun onBatchScanResults(results: List<ScanResult?>) {
            for (r in results) {
                if(r != null)
                    addResult(r)
            }
        }

        @SuppressLint("MissingPermission")
        private fun addResult(r: ScanResult) {
            val builder = BLEScanResponse.newBuilder()
                .setName(r.device.name ?: "")
                .setTxpwr(r.txPower.toFloat())
                .setRssi(r.rssi.toFloat())
                .setDevice(BLEDevice.newBuilder().setMac(r.device.address).build())
                .setTime(System.currentTimeMillis()/1000)
                .setStatus(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())

            if(r.scanRecord != null) {
                if(r.scanRecord!!.serviceUuids != null)
                    builder.addAllServiceUuids(r.scanRecord!!.serviceUuids!!.map { it.toString() })

                val svData = arrayListOf<BLEAdvertisementData>()
                if(r.scanRecord!!.serviceData != null) {
                    r.scanRecord!!.serviceData!!.forEach {
                        svData.add(
                            BLEAdvertisementData
                                .newBuilder()
                                .setUuid(it.key.toString())
                                .setValue(ByteString.copyFrom(it.value))
                                .build()
                        )
                    }
                }
                builder.addAllServiceData(svData)

                val mfData = arrayListOf<BLEAdvertisementData>()
                if(r.scanRecord!!.manufacturerSpecificData != null) {
                    for (i in 0 until r.scanRecord!!.manufacturerSpecificData!!.size()) {
                        mfData.add(BLEAdvertisementData
                            .newBuilder()
                            .setUuid(r.scanRecord!!.manufacturerSpecificData!!.keyAt(i).toString())
                            .setValue(ByteString.copyFrom(r.scanRecord!!.manufacturerSpecificData!!.valueAt(i)))
                            .build()
                        )
                    }
                }
                builder.addAllManufacturerData(mfData)
            }
            val resp = builder.build()
            for (o in observers) {
                try {
                    o.onNext(resp)
                } catch (e: java.lang.Exception) {
                    // remove when disconnected
                    observers.remove(o)
                }
            }
        }
    }


}