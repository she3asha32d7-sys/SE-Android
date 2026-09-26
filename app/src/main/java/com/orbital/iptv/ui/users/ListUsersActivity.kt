package com.orbital.iptv.ui.users

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.orbital.iptv.R
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
        supportActionBar?.hide()
        ThemeManager.load(this)

        binding = ActivityListUsersBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val palette = ThemeManager.palette()
        binding.root.setBackgroundColor(palette.bgPrimary)
        MainSidebarController.setup(
            this,
            binding.root,
            MainSidebarController.Section.LIST_USERS
        )

        binding.btnAddUser.setOnClickListener {
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .putExtra("skip_auto", true)
                    .putExtra("add_user", true)
            )
        }

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

        if (profiles.isEmpty()) {
            binding.tvEmpty.visibility = View.VISIBLE
            binding.tvEmpty.text = "NO SAVED XTREAM USERS\nPRESS ADD USER TO ADD AN XTREAM ACCOUNT"
            return
        }

        binding.tvEmpty.visibility = View.GONE
        val activeId = PrefsManager.getActiveProfileId(this)
        profiles.forEach { profile ->
            addUserCard(profile, profile.id == activeId)
        }
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun addUserCard(profile: ServerProfile, active: Boolean) {
        val palette = ThemeManager.palette()
        val d = resources.displayMetrics.density

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(14), dp(18), dp(14))
            background = ThemeManager.roundedBg(
                if (active) palette.highlight else palette.bgMid,
                d
            )
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).also {
                it.setMargins(dp(4), dp(6), dp(4), dp(6))
            }
        }

        fun addField(label: String, value: String, important: Boolean = false) {
            card.addView(TextView(this).apply {
                text = "${label}: ${value}"
                textSize = if (important) 16f else 13f
                typeface = Typeface.create(
                    "sans-serif-condensed",
                    if (important) Typeface.BOLD else Typeface.NORMAL
                )
                setTextColor(if (active) Color.BLACK else Color.WHITE)
                setPadding(0, dp(if (important) 0 else 2), 0, dp(2))
            })
        }

        addField("HOST NAME", profile.name.ifBlank { "XTREAM USER" }, true)
        addField("USERNAME", profile.username)
        addField("PASSWORD", "********")
        addField("HOST", profile.serverUrl)

        card.addView(TextView(this).apply {
            text = if (active) "STATUS: ACTIVE" else "STATUS: NOT ACTIVE"
            textSize = 13f
            typeface = Typeface.create(
                "sans-serif-condensed",
                Typeface.BOLD
            )
            setTextColor(if (active) Color.BLACK else palette.accent)
            setPadding(0, dp(6), 0, dp(8))
        })

        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }

        fun actionButton(
            label: String,
            enabled: Boolean = true,
            onClick: () -> Unit
        ): TextView {
            return TextView(this).apply {
                text = label
                textSize = 11f
                gravity = Gravity.CENTER
                isFocusable = true
                isClickable = true
                isEnabled = enabled
                setTextColor(if (active) Color.BLACK else Color.WHITE)
                background = ThemeManager.roundedBg(palette.bgPrimary, d)
                alpha = if (enabled) 1f else 0.55f
                setOnFocusChangeListener { v, hasFocus ->
                    v.background = if (hasFocus) {
                        ThemeManager.focusRowDrawable(
                            d,
                            palette.bgPrimary,
                            true,
                            focusFillColor = palette.focus
                        )
                    } else {
                        ThemeManager.roundedBg(palette.bgPrimary, d)
                    }
                }
                setOnClickListener { if (enabled) onClick() }
            }
        }

        actions.addView(
            actionButton("ACTIVE", enabled = !active) {
                PrefsManager.setActiveProfile(this@ListUsersActivity, profile.id)
                Toast.makeText(
                    this@ListUsersActivity,
                    "XTREAM USER SET ACTIVE",
                    Toast.LENGTH_SHORT
                ).show()
                loadUsers()
            },
            LinearLayout.LayoutParams(0, dp(44), 1f).also {
                it.setMargins(0, 0, dp(4), 0)
            }
        )

        actions.addView(
            actionButton("EDIT") {
                startActivity(
                    Intent(this@ListUsersActivity, LoginActivity::class.java)
                        .putExtra("skip_auto", true)
                        .putExtra("edit_profile_id", profile.id)
                )
            },
            LinearLayout.LayoutParams(0, dp(44), 1f).also {
                it.setMargins(dp(4), 0, dp(4), 0)
            }
        )

        actions.addView(
            actionButton("DISCONNECT", enabled = active) {
                PrefsManager.disconnectProfile(
                    this@ListUsersActivity,
                    profile.id
                )
                Toast.makeText(
                    this@ListUsersActivity,
                    "XTREAM USER DISCONNECTED",
                    Toast.LENGTH_SHORT
                ).show()
                loadUsers()
            },
            LinearLayout.LayoutParams(0, dp(44), 1.2f).also {
                it.setMargins(dp(4), 0, dp(4), 0)
            }
        )

        actions.addView(
            actionButton("DELETE") {
                AlertDialog.Builder(
                    this@ListUsersActivity,
                    ThemeManager.dialogStyle()
                )
                    .setTitle("DELETE ${profile.name.uppercase()}?")
                    .setMessage("THIS WILL REMOVE THE XTREAM USER FROM LIST USERS.")
                    .setPositiveButton("DELETE") { _, _ ->
                        PrefsManager.deleteProfile(
                            this@ListUsersActivity,
                            profile.id
                        )
                        loadUsers()
                    }
                    .setNegativeButton("CANCEL", null)
                    .show()
            },
            LinearLayout.LayoutParams(0, dp(44), 1f).also {
                it.setMargins(dp(4), 0, 0, 0)
            }
        )

        card.addView(actions)
        binding.container.addView(card)
    }
}
