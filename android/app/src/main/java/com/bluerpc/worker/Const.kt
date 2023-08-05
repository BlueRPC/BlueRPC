package com.bluerpc.worker

/**
 * Constants
 * Mostly used for key and defaults for shared preferences
 */
object Const {
    const val SHARED_PREF = "bluerpcSharedPreferences"

    const val CFG_NAME = "name"

    const val CFG_PORT = "port"
    const val CFG_PORT_DEFAULT = 5052

    const val DEFAULT_MAC = "00:00:00:00:00:00"

    /**
     * Enable mDNS broadcasting to allow auto-discovery by the clients
     */
    const val CFG_ENABLE_MDNS = "mdns"
    const val CFG_ENABLE_MDS_DEFAULT = true


    /**
     * Background Scanning Modes
     * FILTER: default mode, the worker will report scanning limitations to the client so that it will provide filters
     * SCREEN_ON: The worker will darken the screen but force it to stay on to allow background scanning without filter limitations
     * IGNORE: The worker will report no limitations to the client (can be useful if you already have an app keeping the screen on)
     */
    const val CFG_SCANNING_MODE = "bgScanMode"
    const val CFG_SCANNING_MODE_DEFAULT = 0
    const val CFG_SCANNING_MODE_FILTER = 0
    const val CFG_SCANNING_MODE_SCREEN_ON = 1
    const val CFG_SCANNING_MODE_IGNORE = 2

    /**
     * Enable secure mode
     * needs a keystore
     */
    const val CFG_TLS_ENABLE = "tls"
    const val CFG_TLS_ENABLE_DEFAULT = false

    /**
     * Path to the keystore
     */
    const val CFG_TLS_KEYSTORE = "keystore"
    const val CFG_TLS_KEYSTORE_DEFAULT = "INTERNAL_STORAGE"

    /**
     * Keystore Password
     */
    const val CFG_TLS_KEYSTORE_PASSWORD = "keystorePassword"
}