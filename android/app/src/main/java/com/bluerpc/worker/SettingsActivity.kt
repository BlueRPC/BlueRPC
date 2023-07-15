package com.bluerpc.worker

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.RequiresApi
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.bluerpc.worker.databinding.ActivitySettingsBinding

/**
 * Settings Activity
 * Allows to configure name and port for the worker
 */
class SettingsActivity : AppCompatActivity() {

    private val binding by lazy { ActivitySettingsBinding.inflate(layoutInflater) }
    private val sharedPref by lazy{ applicationContext.getSharedPreferences(Const.SHARED_PREF, Context.MODE_PRIVATE) }

    /**
     * Initialize listeners and default values for settings
     */
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(binding.root)

        binding.name.setText(sharedPref.getString(Const.CFG_NAME, Build.MODEL))
        binding.port.setText(sharedPref.getInt(Const.CFG_PORT, Const.CFG_PORT_DEFAULT).toString())
        binding.mdns.isChecked = sharedPref.getBoolean(Const.CFG_ENABLE_MDNS, Const.CFG_ENABLE_MDS_DEFAULT)

        if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            binding.disableBattery.visibility = View.VISIBLE
            binding.disableBattery.setOnClickListener {
                disableBattery()
            }
        }

        // background scanning limitations were introduced in android 8
        if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            binding.bgScan.visibility = View.VISIBLE
            when (sharedPref.getInt(Const.CFG_SCANNING_MODE, Const.CFG_SCANNING_MODE_DEFAULT)) {
                Const.CFG_SCANNING_MODE_SCREEN_ON -> binding.forceScreenOn.isChecked = true
                Const.CFG_SCANNING_MODE_IGNORE -> binding.ignoreBgLimits.isChecked = true
                else -> binding.doNothing.isChecked = true
            }
        }

        if(sharedPref.getString(Const.CFG_TLS_KEYSTORE, Const.CFG_TLS_KEYSTORE_DEFAULT) != Const.CFG_TLS_KEYSTORE_DEFAULT) {
            binding.tls.isEnabled = true
            binding.tls.isChecked = sharedPref.getBoolean(Const.CFG_TLS_ENABLE, Const.CFG_TLS_ENABLE_DEFAULT)
        }

        binding.add.setOnClickListener {
            save()
        }

        binding.cancel.setOnClickListener {
            startActivity(Intent(this, MainActivity::class.java))
        }

        binding.pickKeystore.setOnClickListener {
            openKSLauncher.launch(arrayOf(
                "application/x-java-jce-keystore",
                "application/x-java-keystore",
                "application/keychain_access",
                "application/x-pkcs12"
            ))
        }

    }

    /**
     * Open an alert to ask the user to disable battery optimizations
     * Will then redirect to the system settings page
     */
    @RequiresApi(Build.VERSION_CODES.M)
    private fun disableBattery() {
        AlertDialog.Builder(this)
            .setMessage("To ensure that this service stays enabled, it might be needed to disable battery optimizations. This is especially the cas for Oneplus, Xiaomi or Huawei phones.")
            .setPositiveButton("OK") { _, _ -> run {
                val intent = Intent()
                intent.action = Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS
                startActivity(intent)
            } }
            .setNegativeButton("Cancel") { d, _ -> d.cancel() }
            .show()
    }

    /**
     * Open a file picker to select a keystore and save its path to the shared preferences
     */
    private val openKSLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { result ->
        with(sharedPref.edit()) {
            putString(Const.CFG_TLS_KEYSTORE, result.toString())
            if(!binding.tls.isEnabled) {
                binding.tls.isEnabled = true
                binding.tls.isChecked = sharedPref.getBoolean(Const.CFG_TLS_ENABLE, Const.CFG_TLS_ENABLE_DEFAULT)
            }
        }
    }

    /**
     * Save settings to shared preferences
     */
    private fun save() {
        with(sharedPref.edit()) {
            putString(Const.CFG_NAME, binding.name.text.toString())
            putInt(Const.CFG_PORT, binding.port.text.toString().toInt())
            putBoolean(Const.CFG_ENABLE_MDNS, binding.mdns.isChecked)
            var x = Const.CFG_SCANNING_MODE_FILTER;
            if(binding.ignoreBgLimits.isChecked)
                x = Const.CFG_SCANNING_MODE_IGNORE
            else if(binding.forceScreenOn.isChecked)
                x = Const.CFG_SCANNING_MODE_SCREEN_ON
            putInt(Const.CFG_SCANNING_MODE, x)
            apply()
        }
        startActivity(Intent(this, MainActivity::class.java))
    }

}