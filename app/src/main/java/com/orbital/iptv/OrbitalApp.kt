package com.orbital.iptv

import android.app.Activity
import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import com.orbital.iptv.utils.SEKeyboardController

class OrbitalApp : Application() {
    override fun onCreate() {
        super.onCreate()
        com.orbital.iptv.utils.TickerManager.pruneStale(this)
        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            override fun onActivityCreated(a: Activity, b: Bundle?) {
                a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                // Genç IPTV-style auto-rotation: follow the sensor between the two
                // landscape directions only. Portrait is never requested by SE.
                a.requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                SEKeyboardController.install(a)
            }
            override fun onActivityStarted(a: Activity) {}
            override fun onActivityResumed(a: Activity) {
                // Re-apply the landscape sensor policy whenever an existing Activity
                // is brought back to the foreground (for example via REORDER_TO_FRONT).
                // This prevents navigation from reverting a manually rotated landscape side.
                a.requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                SEKeyboardController.install(a)
            }
            override fun onActivityPaused(a: Activity) {}
            override fun onActivityStopped(a: Activity) {}
            override fun onActivitySaveInstanceState(a: Activity, b: Bundle) {}
            override fun onActivityDestroyed(a: Activity) {}
        })
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(
                    REMINDER_CHANNEL_ID,
                    "Programme Reminders",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Alerts when your programmes are about to start"
                }
            )
        }
    }


    companion object {
        const val REMINDER_CHANNEL_ID = "se_iptv_reminders"
    }
}