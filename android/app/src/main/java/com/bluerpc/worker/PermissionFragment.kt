package com.bluerpc.worker

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.ViewModelProvider

/**
 * Fragment used to request all required permissions and to enable bluetooth/location
 */
class PermissionFragment : Fragment() {
    private val model : MainViewModel by lazy{ ViewModelProvider(requireActivity())[MainViewModel::class.java] }

    // flow: requestPermissions() -> requestBluetooth() -> requestLocation()
    /**
     * Ask for bluetooth and location, if on android > 6, ask for permissions
     */
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            requestPermissions()
        } else {
            requestBluetooth()
        }
    }

    /**
     * Ask the user to enable location service if not enabled
     */
    private fun requestLocation() {
        val lm = ContextCompat.getSystemService(
            this.requireContext(),
            LocationManager::class.java
        )
        if (lm != null && !lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            AlertDialog.Builder(activity)
                .setMessage("Location is required for scanning")
                .setPositiveButton(
                    "Open Settings"
                ) { _, _ ->
                    activity?.startActivity(
                        Intent(
                            Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                    )
                }
                .setNegativeButton("Cancel", null)
                .show()
        }
    }

    /**
     * Ask the user to enable bluetooth service if not enabled
     * Will continue to start if success
     */
    private fun requestBluetooth() {
        val adp = ContextCompat.getSystemService(requireContext(), BluetoothManager::class.java)
        if (adp == null || adp.adapter == null) {
            Toast.makeText(this.context, "Bluetooth not available, cannot continue", Toast.LENGTH_SHORT).show()
            exit()
        } else {
            if (!adp.adapter.isEnabled) {
                bluetoothLauncher.launch(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE))
            } else {
                start()
            }
        }
    }

    /**
     * Callback for requestBluetooth()
     * will continue to start if success, or will exit on failure
     */
    private val bluetoothLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            start()
        } else {
            Toast.makeText(this.context, "Bluetooth not enabled, cannot continue", Toast.LENGTH_SHORT).show()
            exit()
        }
    }

    /**
     * Callback for requestPermissions()
     * will ask for background location if on android >= 11 and continue to requestBluetooth() or will exit if permissions are refused
     */
    private val requestBluetoothPermissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { permissions ->
        var permsOk = true
        permissions.entries.forEach {
            if(it.key != Manifest.permission.ACCESS_BACKGROUND_LOCATION && !it.value) {
                permsOk = false
            }
        }
        if(permsOk) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                AlertDialog.Builder(requireContext())
                    .setMessage("Background Location is required for scanning, please click Always Allow")
                    .setPositiveButton(
                        "Open Settings"
                    ) { _, _ ->
                        requestLocationPermission.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                    }
                    .setNegativeButton(
                        "Cancel"
                    ) { _, _ -> requestBluetooth() }
                    .show()
            } else {
                requestBluetooth()
            }
        } else {
            Toast.makeText(
                this.context,
                "Location/Ble permissions denied, cannot continue",
                Toast.LENGTH_SHORT
            ).show()
            exit()
        }
    }

    /**
     * Callback for request of ACCESS_BACKGROUND_LOCATION
     * Will continue to requestBluetooth regardless of the result as the refusal of this permission will only limit the application
     */
    private val requestLocationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
        if (!isGranted) {
            Toast.makeText(
                this.context,
                "Background location permission denied, scanning will be limited",
                Toast.LENGTH_SHORT
            ).show()
        }
        requestBluetooth()
    }

    /**
     * Request Location and Bluetooth permissions according to your android version
     */
    private fun requestPermissions() {
        val lst: MutableList<String> = ArrayList()
        // https://github.com/NordicSemiconductor/Android-Scanner-Compat-Library#permissions
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // from android 12, new permissions for bluetooth are required
            lst.add(Manifest.permission.BLUETOOTH_SCAN)
            lst.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // from android 10 FINE_LOCATION is required for bluetooth scanning
            lst.add(Manifest.permission.ACCESS_FINE_LOCATION)
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) {
                // from android 10 this permission is required
                // if we are below 11 we can request it directly (else we have to use requestLocationPermission)
                lst.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            // if we are below android 10, we can just request COARSE_LOCATION
            // permissions requests are only required if we are on android 6 or higher
            lst.add(Manifest.permission.ACCESS_COARSE_LOCATION)
        }
        var allOk = true
        for (perm in lst) {
            if (ContextCompat.checkSelfPermission(requireContext(), perm) == PackageManager.PERMISSION_DENIED) {
                allOk = false
                break
            }
        }
        if (allOk) {
            requestBluetooth()
        } else {
            requestBluetoothPermissions.launch(lst.toTypedArray())
        }
    }

    private fun exit() {
        model.ready.value = false
    }

    private fun start() {
        if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
            requestLocation()
        model.ready.value = true
    }
}

