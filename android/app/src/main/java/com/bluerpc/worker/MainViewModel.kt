package com.bluerpc.worker

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.MutableLiveData

class MainViewModel(application: Application) : AndroidViewModel( application ) {
    val ready = MutableLiveData<Boolean>()
}