package com.bluerpc.worker

import android.R
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.PowerManager.WakeLock
import androidx.core.app.NotificationCompat
import io.grpc.Server
import io.grpc.netty.NettyServerBuilder
/*
import io.grpc.netty.GrpcSslContexts
import io.netty.handler.ssl.SslContextBuilder
import java.io.File
import java.io.InputStream
import java.security.KeyStore
*/


class
ForegroundService: Service() {
    private var wakeLock: WakeLock? = null
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


        /*
        val ksPass = "".toCharArray()
        val ks: KeyStore = KeyStore.getInstance("BKS")
        val ksFile: InputStream = resources.openRawResource(R.raw.client)
        ks.load(ksFile, ksPass)
        ksFile.close()

        val sslContext = GrpcSslContexts
            .forServer(File(ks.getCertificate("a").publicKey.encoded.toString()), File(ks.getKey("a", ksPass).encoded.toString()))
            .trustManager(File(ks.getCertificate("a").publicKey.encoded.toString()))
            .build()
         */

        println("starting ...")
        server = NettyServerBuilder
            .forPort(sharedPref.getInt(Const.CFG_PORT, Const.CFG_PORT_DEFAULT))
            .addService(BlueRPCService(applicationContext))
            //.sslContext(sslContext)
            .build()
        server.start()
        println("started")
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
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

}