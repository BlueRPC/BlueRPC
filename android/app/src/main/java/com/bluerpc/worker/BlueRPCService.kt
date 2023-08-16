package com.bluerpc.worker

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.os.Build
import android.provider.Settings
import android.util.Log
import androidx.core.content.ContextCompat
import com.bluerpc.rpc.BLEConnectRequest
import com.bluerpc.rpc.BLEConnectResponse
import com.bluerpc.rpc.BLEConnectionPropertiesResponse
import com.bluerpc.rpc.BLEDevice
import com.bluerpc.rpc.BLEDevicesResponse
import com.bluerpc.rpc.BLEListServicesResponse
import com.bluerpc.rpc.BLENotificationRequest
import com.bluerpc.rpc.BLENotificationResponse
import com.bluerpc.rpc.BLEPairingCodeRequest
import com.bluerpc.rpc.BLEPairingRequest
import com.bluerpc.rpc.BLEReadCharacteristicRequest
import com.bluerpc.rpc.BLEReadDescriptorRequest
import com.bluerpc.rpc.BLEReadResponse
import com.bluerpc.rpc.BLEScanRequest
import com.bluerpc.rpc.BLEScanResponse
import com.bluerpc.rpc.BLEWriteCharacteristicRequest
import com.bluerpc.rpc.BLEWriteDescriptorRequest
import com.bluerpc.rpc.BlueRPCGrpc.BlueRPCImplBase
import com.bluerpc.rpc.ErrorCode
import com.bluerpc.rpc.HelloRequest
import com.bluerpc.rpc.HelloResponse
import com.bluerpc.rpc.SetKeystoreRequest
import com.bluerpc.rpc.StatusMessage
import com.bluerpc.rpc.Void
import com.bluerpc.rpc.WorkerMode
import com.bluerpc.rpc.WorkerType
import io.grpc.stub.StreamObserver
import java.io.File
import java.io.FileOutputStream
import java.net.NetworkInterface
import java.util.Collections


class BlueRPCService(private val ctx: Context): BlueRPCImplBase() {
    /**
     * first request after connection, returns general infos about the worker
     */
    private val startTime = System.currentTimeMillis()/1000
    private val sharedPref by lazy{ ctx.getSharedPreferences(Const.SHARED_PREF, Context.MODE_PRIVATE) }
    private val scanner = BLEScanner()
    private val conn = BLEConnection(ctx)

    @SuppressLint("HardwareIds")
    override fun hello(request: HelloRequest?, responseObserver: StreamObserver<HelloResponse>?) {
        var btMac = Const.DEFAULT_MAC
        var netMac = Const.DEFAULT_MAC
        var uid = ""

        // we can only get hardware mac addresses on android < 6
        if(Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            val adapter = (ctx.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
            btMac = adapter.address
            val manager = ctx.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager?
            netMac = manager!!.connectionInfo.macAddress
            uid = btMac
        } else {
            uid = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID)
        }

        val resp = HelloResponse.newBuilder()
            .addAllSupportedModes(
                listOf(
                    WorkerMode.WORKER_MODE_GATT_ACTIVE,
                    WorkerMode.WORKER_MODE_GATT_PASSIVE
                )
            )
            .setName(sharedPref.getString(Const.CFG_NAME, Build.MODEL))
            .setUptime(System.currentTimeMillis() / 1000 - startTime)
            .setOperatingSystem(
                if (ctx.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
                ) "Android TV" else "Android"
            )
            .setOperatingSystemVersion(Build.VERSION.SDK_INT.toString())
            .setVersion(BuildConfig.VERSION_NAME)
            .setWorkerType(WorkerType.WORKER_TYPE_ANDROID)
            .setBleFiltersRequired(Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && sharedPref.getInt(Const.CFG_SCANNING_MODE, Const.CFG_SCANNING_MODE_DEFAULT) == Const.CFG_SCANNING_MODE_FILTER)
            .setBtMac(btMac)
            .setNetMac(netMac)
            .setUid(uid)
            .build()
        if (responseObserver != null) {
            responseObserver.onNext(resp)
            responseObserver.onCompleted()
        }
    }

    /**
     * set the keystore
     */
    override fun setKeystore(
        request: SetKeystoreRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null) {
            var ksPath = sharedPref.getString(Const.CFG_TLS_KEYSTORE, Const.CFG_TLS_KEYSTORE_DEFAULT)
            if(ksPath != Const.CFG_TLS_KEYSTORE_DEFAULT) {
                // if path is external, we can't write to it
                if(!request.overwrite) {
                    // if overwrite not allowed return
                    responseObserver?.onNext(
                        StatusMessage.newBuilder()
                            .setCode(ErrorCode.ERROR_CODE_KEYSTORE_ALREADY_EXISTS).build()
                    )
                    responseObserver?.onCompleted()
                    return
                } else {
                    // else, reset keystore path to internal storage
                    with(sharedPref.edit()) {
                        putString(Const.CFG_TLS_KEYSTORE, Const.CFG_TLS_KEYSTORE_DEFAULT)
                    }
                }
            }
            val ksFile = File(ctx.filesDir.path + "/" + Const.KEYSTORE_DEFAULT_PATH)

            if(ksFile.exists()) {
                if (!request.overwrite) {
                    responseObserver?.onNext(
                        StatusMessage.newBuilder()
                            .setCode(ErrorCode.ERROR_CODE_KEYSTORE_ALREADY_EXISTS).build()
                    )
                    responseObserver?.onCompleted()
                    return
                }
            } else {
                ksFile.createNewFile()
            }
            val fos = FileOutputStream(ksFile)
            fos.write(request.data.toByteArray())
            fos.close()
            Log.d("BlueRPC", "new keystore installed at $ksFile")

            responseObserver?.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())
            responseObserver?.onCompleted()

            if(request.apply) {
                ctx.stopService(Intent(ctx, ForegroundService::class.java))
                ContextCompat.startForegroundService(ctx, Intent(ctx, ForegroundService::class.java))
            }
        }
    }

    /**
     * start a scanner
     */
    override fun bLEScanStart(
        request: BLEScanRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null) {
            scanner.setScanFilters(request.filtersList, request.mergeFilters)
            scanner.scan(request.active, request.interval)
        }
        if(responseObserver != null) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())
            responseObserver.onCompleted()
        }
    }

    /**
     * stop the scanner
     */
    override fun bLEScanStop(request: Void?, responseObserver: StreamObserver<StatusMessage>?) {
        if(request != null) {
            scanner.stopScan()
        }
        if(responseObserver != null) {
            responseObserver.onNext(StatusMessage.newBuilder().setCode(ErrorCode.ERROR_CODE_OK).build())
            responseObserver.onCompleted()
        }
    }

    /**
     * connect
     */
    override fun bLEConnect(
        request: BLEConnectRequest?,
        responseObserver: StreamObserver<BLEConnectResponse>?
    ) {
        if(request != null && responseObserver != null)
            conn.connect(request, responseObserver)
    }

    /**
     * disconnect
     */
    override fun bLEDisconnect(
        request: BLEDevice?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null && responseObserver != null)
            conn.disconnect(request, responseObserver)
    }

    /**
     * pair
     */
    override fun bLEPair(
        request: BLEPairingRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        super.bLEPair(request, responseObserver)
    }

    /**
     * pairing code (should be called after BLEPair when
     * ERROR_CODE_PAIRING_CODE_REQUIRED is returned)
     */
    override fun bLEPairCode(
        request: BLEPairingCodeRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        super.bLEPairCode(request, responseObserver)
    }

    /**
     * unpair
     */
    override fun bLEUnpair(request: BLEDevice?, responseObserver: StreamObserver<StatusMessage>?) {
        super.bLEUnpair(request, responseObserver)
    }

    /**
     * get a list of connected and paired devices
     */
    override fun bLEGetDevices(
        request: Void?,
        responseObserver: StreamObserver<BLEDevicesResponse>?
    ) {
        if(responseObserver != null)
            conn.getDevices(responseObserver)
    }

    /**
     * get connection properties
     */
    override fun bLEGetConnectionProperties(
        request: BLEDevice?,
        responseObserver: StreamObserver<BLEConnectionPropertiesResponse>?
    ) {
        if(request != null && responseObserver != null) {
            conn.getConnectionProperties(request, responseObserver)
        }
    }

    /**
     * list services, characteristics and descriptors for a device
     */
    override fun bLEListServices(
        request: BLEDevice?,
        responseObserver: StreamObserver<BLEListServicesResponse>?
    ) {
        if(request != null && responseObserver != null)
            conn.listServices(request, responseObserver)
    }

    /**
     * read characteristic
     */
    override fun bLEReadCharacteristic(
        request: BLEReadCharacteristicRequest?,
        responseObserver: StreamObserver<BLEReadResponse>?
    ) {
        if(request != null && responseObserver != null)
            conn.readCharacteristic(request, responseObserver)
    }

    /**
     * read descriptor
     */
    override fun bLEReadDescriptor(
        request: BLEReadDescriptorRequest?,
        responseObserver: StreamObserver<BLEReadResponse>?
    ) {
        if(request != null && responseObserver != null)
            conn.readDescriptor(request, responseObserver)
    }

    /**
     * write characteristic
     */
    override fun bLEWriteCharacteristic(
        request: BLEWriteCharacteristicRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null && responseObserver != null)
            conn.writeCharacteristic(request, responseObserver)
    }

    /**
     * write descriptor
     */
    override fun bLEWriteDescriptor(
        request: BLEWriteDescriptorRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null && responseObserver != null)
            conn.writeDescriptor(request, responseObserver)
    }

    /**
     * subscribe or unsubscribe to a characteristic notification
     */
    override fun bLENotification(
        request: BLENotificationRequest?,
        responseObserver: StreamObserver<StatusMessage>?
    ) {
        if(request != null && responseObserver != null)
            conn.notification(request, responseObserver)
    }

    /**
     * global method to receive all the subscribed notifications
     */
    override fun bLEReceiveNotifications(
        request: Void?,
        responseObserver: StreamObserver<BLENotificationResponse>?
    ) {
        if(responseObserver != null)
            conn.notificationObservers.add(responseObserver)
    }

    /**
     * global method to receive disconnect notifications
     */
    override fun bLEReceiveDisconnect(
        request: Void?,
        responseObserver: StreamObserver<BLEDevice>?
    ) {
        if(responseObserver != null)
            conn.disconnectObservers.add(responseObserver)
    }

    /**
     * global method to receive scan results
     */
    override fun bLEReceiveScan(
        request: Void?,
        responseObserver: StreamObserver<BLEScanResponse>?
    ) {
        if(responseObserver != null)
            scanner.observers.add(responseObserver)
    }

    /**
     * Get mac address of the network interface
     */
    private fun getMacAddr(): String? {
        try {
            val all: List<NetworkInterface> =
                Collections.list(NetworkInterface.getNetworkInterfaces())
            for (nif in all) {
                if (!nif.name.equals("wlan0", ignoreCase = true)) continue
                val macBytes = nif.hardwareAddress ?: return ""
                val res = StringBuilder()
                for (b in macBytes) {
                    res.append(String.format("%02X:", b))
                }
                if (res.isNotEmpty()) {
                    res.deleteCharAt(res.length - 1)
                }
                return res.toString()
            }
        } catch (ex: Exception) { }
        return "00:00:00:00:00:00"
    }

}