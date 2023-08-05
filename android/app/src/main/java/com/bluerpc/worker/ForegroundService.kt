package com.bluerpc.worker

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.PowerManager.WakeLock
import android.provider.Settings
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import io.grpc.Server
import io.grpc.netty.NettyServerBuilder
import io.grpc.netty.GrpcSslContexts
import java.io.File
import java.io.InputStream
import java.security.KeyStore


class ForegroundService: Service() {
    private var wakeLock: WakeLock? = null
    private var nsdManager: NsdManager? = null
    private lateinit var server: Server
    private val sharedPref by lazy{ applicationContext.getSharedPreferences(Const.SHARED_PREF, Context.MODE_PRIVATE) }

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "bluerpc:WAKE_LOCK_TAG")
            wakeLock!!.acquire()
        }
        createNotificationChannel()
        val notification: Notification =
            NotificationCompat.Builder(this, "NOTIFICATION_CHANNEL").setContentTitle("BlueRPC")
                .setContentText("BlueRPC Worker is running").build()
        startForeground(1001, notification)

        Log.d("BlueRPC", "Starting server ...")
        val builder = NettyServerBuilder
            .forPort(sharedPref.getInt(Const.CFG_PORT, Const.CFG_PORT_DEFAULT))
            .addService(BlueRPCService(applicationContext))

        if(sharedPref.getBoolean(Const.CFG_TLS_ENABLE, Const.CFG_TLS_ENABLE_DEFAULT)) {
            var ksPath = sharedPref.getString(Const.CFG_TLS_KEYSTORE, Const.CFG_TLS_KEYSTORE_DEFAULT)
            if(ksPath == Const.CFG_TLS_KEYSTORE_DEFAULT)
                ksPath = filesDir.path + "/bluerpc.p12"
            var ksPass = sharedPref.getString(Const.CFG_TLS_KEYSTORE_PASSWORD, "")

            val ks: KeyStore = KeyStore.getInstance("PKCS12")
            val ksFile: InputStream = openFileInput(ksPath)
            ks.load(ksFile, ksPass?.toCharArray())
            ksFile.close()

            val sslContext = GrpcSslContexts
                .forServer(File(ks.getCertificate("bluerpc").publicKey.encoded.toString()), File(ks.getKey("bluerpc", ksPass?.toCharArray()).encoded.toString()))
                .trustManager(File(ks.getCertificateChain("bluerpc")[0].publicKey.encoded.toString()))
                .build()
            builder.sslContext(sslContext)
        }

        server = builder.build()
        server.start()

        if(sharedPref.getBoolean(Const.CFG_ENABLE_MDNS, Const.CFG_ENABLE_MDS_DEFAULT)) {
            registerService()
        }
        Log.d("BlueRPC", "Server started")
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name: CharSequence = "BlueRPC Foreground Service"
            val description = "BlueRPC Worker persistent notification"
            val importance = NotificationManager.IMPORTANCE_DEFAULT
            val channel = NotificationChannel("NOTIFICATION_CHANNEL", name, importance)
            channel.description = description
            val notificationManager: NotificationManager = applicationContext.getSystemService(
                NotificationManager::class.java
            )
            notificationManager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        server.shutdownNow()
        if (wakeLock != null && wakeLock!!.isHeld) {
            wakeLock!!.release()
        }
        unregisterService()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    @SuppressLint("HardwareIds")
    private fun registerService() {
        val serviceInfo = NsdServiceInfo().apply {
            serviceName = sharedPref.getString(Const.CFG_NAME, Build.MODEL)
            serviceType = "_bluerpc._tcp"
            port = sharedPref.getInt(Const.CFG_PORT, Const.CFG_PORT_DEFAULT)
            if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                val uid = if(Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
                    val adapter = (applicationContext.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
                    adapter.address
                } else {
                    Settings.Secure.getString(applicationContext.contentResolver, Settings.Secure.ANDROID_ID)
                }
                setAttribute("name", serviceName)
                setAttribute("version", BuildConfig.VERSION_NAME)
                setAttribute("uid", uid)
            }
        }

        nsdManager = (ContextCompat.getSystemService(applicationContext, NsdManager::class.java))?.apply {
            registerService(serviceInfo, NsdManager.PROTOCOL_DNS_SD, serviceRegistrationListener)
        }
    }

    private val serviceRegistrationListener = object : NsdManager.RegistrationListener {
        override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
            Log.d("BlueRPC", "mDns service registered")
        }

        override fun onServiceUnregistered(serviceInfo: NsdServiceInfo?) {
            Log.d("BlueRPC", "mDns service unregistered")
        }

        override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
            Log.w("BlueRPC", "failed to register mDns service: $errorCode")
        }

        override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo?, errorCode: Int) {
            Log.w("BlueRPC", "failed to register mDns service: $errorCode")
        }
    }

    private fun unregisterService() {
        nsdManager?.apply {
            unregisterService(serviceRegistrationListener)
        }
        nsdManager = null
    }

}