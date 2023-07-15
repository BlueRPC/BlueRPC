package com.bluerpc.worker

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.fragment.app.commit
import androidx.lifecycle.ViewModelProvider
import com.bluerpc.worker.databinding.ActivityMainBinding


class MainActivity : AppCompatActivity() {
    private val binding by lazy { ActivityMainBinding.inflate(layoutInflater) }
    private val model by lazy{ ViewModelProvider(this)[MainViewModel::class.java] }
    private val keepScreenON by lazy{ applicationContext.getSharedPreferences(Const.SHARED_PREF, Context.MODE_PRIVATE).getInt(Const.CFG_SCANNING_MODE, Const.CFG_SCANNING_MODE_DEFAULT) == Const.CFG_SCANNING_MODE_SCREEN_ON }
    private val START = "Start"
    private val STOP = "Stop"

    private fun serviceRunning(serviceClass: Class<*>): Boolean {
        val manager = applicationContext.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        for (service in manager.getRunningServices(Int.MAX_VALUE)) {
            if (serviceClass.name == service.service.className) {
                return true
            }
        }
        return false
    }

    private fun service(start: Boolean = true) {
        if(start && !serviceRunning(ForegroundService::class.java)) {
            ContextCompat.startForegroundService(this, Intent(this, ForegroundService::class.java))
            binding.start.text = STOP
            if(keepScreenON)
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else if(!start && serviceRunning(ForegroundService::class.java)) {
            stopService(Intent(this, ForegroundService::class.java))
            binding.start.text = START
            if(keepScreenON)
                window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(binding.root)

        if(serviceRunning(ForegroundService::class.java)) {
            binding.start.text = STOP
            if(keepScreenON)
                window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }

        binding.settings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        binding.start.setOnClickListener {
            if(binding.start.text == STOP) {
                service(false)
            } else {
                service(true)
            }
        }

        supportFragmentManager.commit {
            add(binding.fragmentContainerView.id, PermissionFragment())
            disallowAddToBackStack()
        }

        model.ready.observe(this) {
            if(it) {
                service(true)
            } else {
                finish()
            }
        }
    }
}