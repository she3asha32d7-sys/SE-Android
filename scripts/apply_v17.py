from pathlib import Path

def replace(path, old, new):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"Pattern not found in {path}: {old[:80]!r}")
    p.write_text(s.replace(old, new, 1))

replace("app/build.gradle", "versionCode 1000015", "versionCode 1000017")
replace("app/build.gradle", 'versionName "100.0.15"', 'versionName "100.0.17"')
replace("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.15"', 'rootProject.name = "SEAndroid_v100.0.17"')
replace("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt", 'b.tvBuiltinPlayerValue.text = "SE"', 'b.tvBuiltinPlayerValue.text = "SE PLAYER"')

p=Path("app/src/main/res/layout/activity_settings.xml")
s=p.read_text()
start=s.index('<TextView android:id="@+id/about_text"')
end=s.index('/>', start)+2
new='<TextView android:id="@+id/about_text" android:text="Name: SE IPTV PLAYER&#10;Version: V100.0.17&#10;Application id: com.se.iptv.player&#10;Platform: Android&#10;License: Open Source" android:textColor="@color/sky_white" android:textSize="14sp" android:lineSpacingExtra="5dp" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="10dp"/>'
p.write_text(s[:start]+new+s[end:])

p=Path("app/src/main/res/layout/activity_login.xml")
s=p.read_text()
s=s.replace('android:layout_width="128dp"\n            android:layout_height="128dp"\n            android:src="@drawable/se_logo_full"',
            'android:layout_width="192dp"\n            android:layout_height="192dp"\n            android:src="@drawable/se_logo_full"',1)
p.write_text(s)

Path("app/src/main/res/drawable/se_launcher_scaled.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<inset xmlns:android="http://schemas.android.com/apk/res/android" android:inset="0dp">
    <bitmap android:src="@drawable/se_launcher" android:gravity="fill"/>
</inset>
''')

Path("app/src/main/java/com/orbital/iptv/ui/users/ListUsersActivity.kt").write_text('''package com.orbital.iptv.ui.users

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.orbital.iptv.data.model.ServerProfile
import com.orbital.iptv.databinding.ActivityListUsersBinding
import com.orbital.iptv.ui.login.LoginActivity
import com.orbital.iptv.utils.MainSidebarController
import com.orbital.iptv.utils.PrefsManager
import com.orbital.iptv.utils.ThemeManager

class ListUsersActivity : AppCompatActivity() {
    private lateinit var binding: ActivityListUsersBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ThemeManager.load(this)
        binding = ActivityListUsersBinding.inflate(layoutInflater)
        setContentView(binding.root)
        MainSidebarController.setup(this, binding.root, MainSidebarController.Section.LIST_USERS)
        binding.btnAddUser.setOnClickListener {
            startActivity(Intent(this, LoginActivity::class.java)
                .putExtra("skip_auto", true)
                .putExtra("add_user", true))
        }
        binding.btnRefresh.setOnClickListener { loadUsers() }
        loadUsers()
    }

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) loadUsers()
    }

    private fun loadUsers() {
        val profiles = PrefsManager.getProfiles(this)
        binding.container.removeAllViews()
        binding.progressBar.visibility = View.GONE
        binding.tvEmpty.visibility = if (profiles.isEmpty()) View.VISIBLE else View.GONE
        binding.tvEmpty.text = if (profiles.isEmpty()) "NO SAVED USERS" else ""
        profiles.forEach { addUserRow(it, it.id == PrefsManager.getActiveProfileId(this)) }
    }

    private fun addUserRow(profile: ServerProfile, active: Boolean) {
        val palette = ThemeManager.palette()
        val d = resources.displayMetrics.density

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((16*d).toInt(), (14*d).toInt(), (16*d).toInt(), (14*d).toInt())
            background = ThemeManager.roundedBg(if (active) palette.highlight else palette.bgMid, d)
            isFocusable = true
            isClickable = true
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).also { it.setMargins((6*d).toInt(), (5*d).toInt(), (6*d).toInt(), (5*d).toInt()) }
            setOnFocusChangeListener { v, hasFocus ->
                v.background = if (hasFocus)
                    ThemeManager.focusRowDrawable(d, palette.bgMid, true, focusFillColor = palette.focus)
                else
                    ThemeManager.roundedBg(if (active) palette.highlight else palette.bgMid, d)
            }
        }

        fun field(label: String, value: String) = TextView(this).apply {
            text = label + ": " + value
            textSize = 12f
            setTextColor(if (active) Color.BLACK else Color.WHITE)
            setPadding(0, (2*d).toInt(), 0, (2*d).toInt())
        }

        val name = TextView(this).apply {
            text = "Name: " + profile.name
            textSize = 16f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            setTextColor(if (active) Color.BLACK else Color.WHITE)
        }

        card.addView(name)
        card.addView(field("Host", profile.serverUrl))
        card.addView(field("User name", profile.username))
        card.addView(field("Password", "×××××"))

        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }

        val edit = TextView(this).apply {
            text = "EDIT"
            textSize = 12f
            gravity = Gravity.CENTER
            isFocusable = true
            isClickable = true
            setTextColor(if (active) Color.BLACK else palette.accent)
            background = ThemeManager.roundedBg(palette.bgPrimary, d)
            setOnClickListener {
                startActivity(Intent(this@ListUsersActivity, LoginActivity::class.java)
                    .putExtra("skip_auto", true)
                    .putExtra("edit_profile_id", profile.id))
            }
        }

        val delete = TextView(this).apply {
            text = "DELETE"
            textSize = 12f
            gravity = Gravity.CENTER
            isFocusable = true
            isClickable = true
            setTextColor(if (active) Color.BLACK else Color.WHITE)
            background = ThemeManager.roundedBg(palette.bgPrimary, d)
            setOnClickListener {
                PrefsManager.deleteProfile(this@ListUsersActivity, profile.id)
                val remaining = PrefsManager.getProfiles(this@ListUsersActivity)
                if (profile.id == PrefsManager.getActiveProfileId(this@ListUsersActivity)) {
                    remaining.firstOrNull()?.let { PrefsManager.setActiveProfile(this@ListUsersActivity, it.id) }
                }
                Toast.makeText(this@ListUsersActivity, "USER DELETED", Toast.LENGTH_SHORT).show()
                loadUsers()
            }
        }

        actions.addView(edit, LinearLayout.LayoutParams(0, (42*d).toInt(), 1f).also {
            it.setMargins(0, (8*d).toInt(), (4*d).toInt(), 0)
        })
        actions.addView(delete, LinearLayout.LayoutParams(0, (42*d).toInt(), 1f).also {
            it.setMargins((4*d).toInt(), (8*d).toInt(), 0, 0)
        })
        card.addView(actions)
        binding.container.addView(card)
    }
}
''')

print("v100.0.17 source modifications applied")
