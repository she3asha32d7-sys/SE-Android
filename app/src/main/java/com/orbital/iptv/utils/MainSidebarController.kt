package com.orbital.iptv.utils

import android.app.Activity
import android.content.Intent
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.orbital.iptv.R
import com.orbital.iptv.ui.favourites.FavouritesActivity
import com.orbital.iptv.ui.home.HomeActivity
import com.orbital.iptv.ui.series.SeriesActivity
import com.orbital.iptv.ui.vod.VodActivity
import com.orbital.iptv.recording.RecordingsActivity
import com.orbital.iptv.ui.downloads.DownloadsActivity
import com.orbital.iptv.ui.settings.SettingsActivity

object MainSidebarController {
    enum class Section { HOME, LIVE_TV, MOVIES, SERIES, FAVOURITES, DOWNLOADS, RECORDS, SETTINGS, LIST_USERS }

    fun setup(
        activity: AppCompatActivity,
        root: View,
        selected: Section,
        onSettings: (() -> Unit)? = null,
        onHome: (() -> Unit)? = null,
        onLiveTv: (() -> Unit)? = null
    ) {
        val items = listOf(
            Section.HOME to R.id.nav_home,
            Section.LIVE_TV to R.id.nav_live_tv,
            Section.MOVIES to R.id.nav_movies,
            Section.SERIES to R.id.nav_series,
            Section.FAVOURITES to R.id.nav_favourites,
            Section.DOWNLOADS to R.id.nav_downloads,
            Section.RECORDS to R.id.nav_records,
            Section.SETTINGS to R.id.nav_settings,
            Section.LIST_USERS to R.id.nav_list_users
        )
        val density = activity.resources.displayMetrics.density
        val palette = ThemeManager.palette()
        root.findViewById<TextView>(R.id.tv_global_datetime)?.setTextColor(palette.accent)
        items.forEach { (section, id) ->
            val view = root.findViewById<TextView>(id) ?: return@forEach
            val isSelected = section == selected
            view.background = ThemeManager.navTabDrawable(density, selected = isSelected)
            view.setTextColor(if (isSelected) palette.tabTextOnSelected else 0xFFFFFFFF.toInt())
            view.setOnFocusChangeListener { v, hasFocus ->
                v.background = ThemeManager.focusRowDrawable(
                    density, palette.bgHeader, hasFocus,
                    focusFillColor = if (isSelected) palette.tabSelected else palette.focus
                )
                (v as? TextView)?.setTextColor(
                    if (hasFocus || isSelected) palette.accent else 0xFFFFFFFF.toInt()
                )
            }
            view.setOnClickListener {
                if (section == selected) return@setOnClickListener
                when (section) {
                    Section.HOME -> if (onHome != null) onHome() else goHome(activity, "HOME")
                    Section.LIVE_TV -> if (onLiveTv != null) onLiveTv() else goHome(activity, "LIVE")
                    Section.MOVIES -> go(activity, VodActivity::class.java)
                    Section.SERIES -> go(activity, SeriesActivity::class.java)
                    Section.FAVOURITES -> go(activity, FavouritesActivity::class.java)
                    Section.DOWNLOADS -> go(activity, DownloadsActivity::class.java)
                    Section.RECORDS -> go(activity, RecordingsActivity::class.java)
                    Section.SETTINGS -> if (onSettings != null) onSettings() else {
                        activity.startActivity(Intent(activity, SettingsActivity::class.java))
                        noAnimation(activity)
                    }
                    Section.LIST_USERS -> go(activity, com.orbital.iptv.ui.users.ListUsersActivity::class.java)
                }
            }
        }
        root.findViewById<android.widget.HorizontalScrollView>(R.id.main_sidebar_container)?.post {
            val scroll = root.findViewById<android.widget.HorizontalScrollView>(R.id.main_sidebar_container)
            val selectedView = items.firstOrNull { it.first == selected }?.second
                ?.let { root.findViewById<TextView>(it) }
            if (selectedView != null) {
                val target = (selectedView.left - (scroll.width - selectedView.width) / 2).coerceAtLeast(0)
                scroll.scrollTo(target, 0)
                if (root.findFocus() == null) selectedView.requestFocus()
            }
        }
        root.findViewById<TextView>(R.id.nav_exit)?.let { view ->
            view.background = ThemeManager.navTabDrawable(density, selected = false)
            view.setTextColor(0xFFFFFFFF.toInt())
            view.setOnFocusChangeListener { v, hasFocus ->
                v.background = ThemeManager.focusRowDrawable(
                    density, palette.bgHeader, hasFocus, focusFillColor = palette.focus
                )
                (v as? TextView)?.setTextColor(if (hasFocus) palette.accent else 0xFFFFFFFF.toInt())
            }
            view.setOnClickListener { confirmExit(activity) }
        }
    }

    private fun <T : Activity> go(activity: AppCompatActivity, target: Class<T>) {
        if (activity::class.java == target) return
        activity.startActivity(Intent(activity, target).apply {
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        })
        noAnimation(activity)
    }

    private fun goHome(activity: AppCompatActivity, mode: String) {
        if (activity is HomeActivity) {
            activity.showSection(mode)
            return
        }
        activity.startActivity(Intent(activity, HomeActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            putExtra(HomeActivity.EXTRA_SECTION, mode)
        })
        noAnimation(activity)
    }

    private fun noAnimation(activity: Activity) {
        @Suppress("DEPRECATION") activity.overridePendingTransition(0, 0)
    }

    private fun confirmExit(activity: Activity) {
        AlertDialog.Builder(activity, ThemeManager.dialogStyle())
            .setTitle("Do You Want To Exit The App")
            .setMessage("")
            .setPositiveButton("Yes") { _, _ -> activity.finishAffinity() }
            .setNegativeButton("No", null)
            .show()
    }
}