from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()

def fail(msg):
    raise SystemExit(msg)

# Persist a concrete orientation lock captured when the user turns Auto Rotate OFF.
prefs = ROOT / "app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt"
s = prefs.read_text()
old = '''    // ── Auto Rotate ───────────────────────────────────────────────────────────

    // ON keeps the existing SE landscape sensor-rotation policy.
    // OFF locks every Activity to whatever rotation is currently active.
    fun isAutoRotateEnabled(context: Context): Boolean =
        prefs(context).getBoolean("auto_rotate_enabled", true)

    fun setAutoRotateEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean("auto_rotate_enabled", enabled).apply()
    }
'''
new = '''    // ── Auto Rotate ───────────────────────────────────────────────────────────

    // ON follows the normal SE landscape sensor rotation.
    // OFF uses one concrete orientation captured at the moment the user switches it OFF.
    fun isAutoRotateEnabled(context: Context): Boolean =
        prefs(context).getBoolean("auto_rotate_enabled", true)

    fun setAutoRotateEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean("auto_rotate_enabled", enabled).apply()
    }

    fun hasAutoRotateLockOrientation(context: Context): Boolean =
        prefs(context).contains("auto_rotate_lock_orientation")

    fun getAutoRotateLockOrientation(context: Context): Int =
        prefs(context).getInt(
            "auto_rotate_lock_orientation",
            android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        )

    fun setAutoRotateLockOrientation(context: Context, orientation: Int) {
        prefs(context).edit().putInt("auto_rotate_lock_orientation", orientation).apply()
    }
'''
if old not in s:
    fail("PrefsManager Auto Rotate block not found")
prefs.write_text(s.replace(old, new, 1))

# Application-wide policy: ON = sensor landscape, OFF = the same concrete orientation
# captured by the setting, applied before/after each Activity becomes visible.
app = ROOT / "app/src/main/java/com/orbital/iptv/OrbitalApp.kt"
s = app.read_text()

old_class = '''class OrbitalApp : Application() {
    private fun applyOrientationPolicy(a: Activity) {
        if (com.orbital.iptv.utils.PrefsManager.isAutoRotateEnabled(a)) {
            // Preserve the app's existing landscape-only sensor behavior when ON.
            a.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        } else {
            // Android's LOCKED mode freezes the exact rotation that is active now.
            // Do not replace this with PORTRAIT/LANDSCAPE: those would change the
            // current display orientation instead of preserving it.
            a.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LOCKED
        }
    }
'''
new_class = '''class OrbitalApp : Application() {
    private fun applyOrientationPolicy(a: Activity) {
        val prefs = com.orbital.iptv.utils.PrefsManager
        a.requestedOrientation = if (prefs.isAutoRotateEnabled(a)) {
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        } else {
            // Never use SCREEN_ORIENTATION_LOCKED on each new Activity: it can lock
            // after the system has already reconsidered the sensor orientation.
            // Reuse the concrete orientation captured when OFF was selected.
            prefs.getAutoRotateLockOrientation(a)
        }
    }
}
'''
if old_class not in s:
    fail("OrbitalApp class policy block not found")
s = s.replace(old_class, new_class, 1)

old_lifecycle = '''        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            override fun onActivityCreated(a: Activity, b: Bundle?) {
                a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                applyOrientationPolicy(a)
                
            }
            override fun onActivityStarted(a: Activity) {}
            override fun onActivityResumed(a: Activity) {
                // Re-apply sensor rotation when ON. When OFF, keep the current
                // rotation locked instead of continuously re-requesting it.
                if (com.orbital.iptv.utils.PrefsManager.isAutoRotateEnabled(a)) {
                    applyOrientationPolicy(a)
                }
            }
'''
new_lifecycle = '''        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            override fun onActivityPreCreated(a: Activity, b: Bundle?) {
                // API 29+: apply the stored concrete lock before Activity.onCreate.
                // This prevents a newly opened page from getting a sensor orientation
                // request during navigation while Auto Rotate is OFF.
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    applyOrientationPolicy(a)
                }
            }

            override fun onActivityCreated(a: Activity, b: Bundle?) {
                a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                applyOrientationPolicy(a)
            }

            override fun onActivityStarted(a: Activity) {}

            override fun onActivityResumed(a: Activity) {
                // Re-apply the same global policy on every resume. OFF always uses the
                // persisted concrete orientation; it never re-reads the sensor.
                applyOrientationPolicy(a)
            }
'''
if old_lifecycle not in s:
    fail("OrbitalApp lifecycle block not found")
s = s.replace(old_lifecycle, new_lifecycle, 1)
app.write_text(s)

# Settings: capture the exact currently displayed orientation before turning the sensor OFF.
settings = ROOT / "app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt"
s = settings.read_text()
old = '''        b.switchAutoRotate.setOnCheckedChangeListener { _, checked ->
            PrefsManager.setAutoRotateEnabled(this, checked)
            // Apply the new policy immediately. When turning OFF, LOCKED freezes
            // the exact rotation visible at the moment the switch is changed.
            requestedOrientation = if (checked) {
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            } else {
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LOCKED
            }
        }
'''
new = '''        b.switchAutoRotate.setOnCheckedChangeListener { _, checked ->
            if (checked) {
                PrefsManager.setAutoRotateEnabled(this, true)
                // Restore normal two-way landscape sensor rotation.
                requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            } else {
                // Capture the display rotation BEFORE changing requestedOrientation.
                val rotation = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
                    display.rotation
                } else {
                    @Suppress("DEPRECATION")
                    windowManager.defaultDisplay.rotation
                }

                // SE is a landscape app. Capture the currently visible landscape side
                // and lock to that concrete side for every Activity while OFF.
                val lockOrientation = when (rotation) {
                    android.view.Surface.ROTATION_180,
                    android.view.Surface.ROTATION_270 ->
                        android.content.pm.ActivityInfo.SCREEN_ORIENTATION_REVERSE_LANDSCAPE
                    else ->
                        android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                }

                PrefsManager.setAutoRotateLockOrientation(this, lockOrientation)
                PrefsManager.setAutoRotateEnabled(this, false)

                // Apply the concrete orientation immediately. Every later Activity
                // receives this same value while Auto Rotate remains OFF.
                requestedOrientation = lockOrientation
            }
        }
'''
if old not in s:
    fail("Settings Auto Rotate listener not found")
s = s.replace(old, new, 1)
settings.write_text(s)

# Version 100.0.100.
build = ROOT / "app/build.gradle"
s = build.read_text()
s = re.sub(r"versionCode\s+\d+", "versionCode 1000100", s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.100"', s, count=1)
build.write_text(s)

root_settings = ROOT / "settings.gradle"
s = root_settings.read_text()
s = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.100"', s, count=1)
root_settings.write_text(s)

# Hard checks.
assert 'SCREEN_ORIENTATION_LOCKED' not in app.read_text()
assert 'getAutoRotateLockOrientation' in app.read_text()
assert 'onActivityPreCreated' in app.read_text()
assert 'setAutoRotateLockOrientation' in settings.read_text()
assert 'SCREEN_ORIENTATION_REVERSE_LANDSCAPE' in settings.read_text()
assert 'versionName "100.0.100"' in build.read_text()
print("V100.0.100 Auto Rotate hard-lock fix applied")
