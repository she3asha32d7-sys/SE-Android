from pathlib import Path

def replace_once(path: str, old: str, new: str):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    p.write_text(s.replace(old, new, 1))

# Persist Auto Rotate. Default: ON.
p = Path("app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt")
s = p.read_text()
needle = """    // ── PiP ───────────────────────────────────────────────────────────────────

    fun isPipEnabled(context: Context): Boolean =
"""
insert = """    // ── Auto Rotate ───────────────────────────────────────────────────────────

    // ON keeps the existing SE landscape sensor-rotation policy.
    // OFF locks every Activity to whatever rotation is currently active.
    fun isAutoRotateEnabled(context: Context): Boolean =
        prefs(context).getBoolean("auto_rotate_enabled", true)

    fun setAutoRotateEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean("auto_rotate_enabled", enabled).apply()
    }

    // ── PiP ───────────────────────────────────────────────────────────────────

    fun isPipEnabled(context: Context): Boolean =
"""
replace_once("app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt", needle, insert)

# Make the app-wide orientation policy honor the preference.
p = Path("app/src/main/java/com/orbital/iptv/OrbitalApp.kt")
s = p.read_text()
s = s.replace(
"""import android.app.Application
import android.app.NotificationChannel
""",
"""import android.app.Application
import android.app.NotificationChannel
import android.content.pm.ActivityInfo
""",
1)
s = s.replace(
"""class OrbitalApp : Application() {
    override fun onCreate() {
""",
"""class OrbitalApp : Application() {
    private fun applyOrientationPolicy(a: Activity) {
        a.requestedOrientation = if (com.orbital.iptv.utils.PrefsManager.isAutoRotateEnabled(a)) {
            // Preserve the app's existing landscape-only sensor behavior when ON.
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        } else {
            // Lock the display to the exact rotation that is active right now.
            ActivityInfo.SCREEN_ORIENTATION_LOCKED
        }
    }

    override fun onCreate() {
""",
1)
s = s.replace(
"""                // Genç IPTV-style auto-rotation: follow the sensor between the two
                // landscape directions only. Portrait is never requested by SE.
                a.requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
""",
"""                applyOrientationPolicy(a)
""",
1)
s = s.replace(
"""                // Re-apply the landscape sensor policy whenever an existing Activity
                // is brought back to the foreground (for example via REORDER_TO_FRONT).
                // This prevents navigation from reverting a manually rotated landscape side.
                a.requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
""",
"""                // Re-apply the selected policy when an Activity returns to the foreground.
                applyOrientationPolicy(a)
""",
1)
p.write_text(s)

# Add Auto Rotate above PiP and move both switches left.
p = Path("app/src/main/res/layout/activity_settings.xml")
s = p.read_text()
old = """                <androidx.appcompat.widget.SwitchCompat android:id="@+id/switch_pip" android:text="PICTURE IN PICTURE" android:textColor="@color/sky_white" android:textSize="14sp" android:layout_width="match_parent" android:layout_height="50dp" android:layout_marginTop="6dp"/>
"""
new = """                <androidx.appcompat.widget.SwitchCompat android:id="@+id/switch_auto_rotate" android:text="AUTO ROTATE" android:textColor="@color/sky_white" android:textSize="14sp" android:layout_width="match_parent" android:layout_height="50dp" android:layout_marginTop="6dp" android:layout_marginEnd="28dp"/>
                <androidx.appcompat.widget.SwitchCompat android:id="@+id/switch_pip" android:text="PICTURE IN PICTURE" android:textColor="@color/sky_white" android:textSize="14sp" android:layout_width="match_parent" android:layout_height="50dp" android:layout_marginTop="6dp" android:layout_marginEnd="28dp"/>
"""
replace_once("app/src/main/res/layout/activity_settings.xml", old, new)

# Wire setting and apply orientation immediately on toggle.
p = Path("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt")
s = p.read_text()
old = """        b.tvBuiltinPlayerValue.text = "SE PLAYER"
        b.btnDefaultQuality.text = "DEFAULT QUALITY: \${qualityLabel(PrefsManager.getDefaultQuality(this))}"
"""
new = """        b.tvBuiltinPlayerValue.text = "SE PLAYER"
        b.switchAutoRotate.isChecked = PrefsManager.isAutoRotateEnabled(this)
        b.switchAutoRotate.setOnCheckedChangeListener { _, checked ->
            PrefsManager.setAutoRotateEnabled(this, checked)
            requestedOrientation = if (checked) {
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            } else {
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LOCKED
            }
        }
        b.btnDefaultQuality.text = "DEFAULT QUALITY: \${qualityLabel(PrefsManager.getDefaultQuality(this))}"
"""
replace_once("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt", old, new)
old = """        b.switchPip.setTextColor(if (ThemeManager.currentMode() == PrefsManager.ThemeMode.LIGHT) 0xFF20232B.toInt() else 0xFFFFFFFF.toInt())
"""
new = """        val switchTextColor = if (ThemeManager.currentMode() == PrefsManager.ThemeMode.LIGHT) 0xFF20232B.toInt() else 0xFFFFFFFF.toInt()
        b.switchAutoRotate.setTextColor(switchTextColor)
        b.switchPip.setTextColor(switchTextColor)
"""
replace_once("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt", old, new)

print("Auto Rotate patch applied successfully")
