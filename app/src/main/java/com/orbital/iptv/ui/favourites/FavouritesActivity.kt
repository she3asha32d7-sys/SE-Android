package com.orbital.iptv.ui.favourites

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.orbital.iptv.data.model.*
import com.orbital.iptv.databinding.ActivityFavouritesBinding
import com.orbital.iptv.ui.home.HomeActivity
import com.orbital.iptv.ui.series.SeriesActivity
import com.orbital.iptv.ui.vod.VodActivity
import com.orbital.iptv.utils.*
import kotlinx.coroutines.*

class FavouritesActivity: AppCompatActivity() {
    private lateinit var b: ActivityFavouritesBinding
    private lateinit var ma: FavouritesAdapter
    private lateinit var sa: FavouritesAdapter
    private lateinit var la: FavouritesAdapter
    private lateinit var ca: FavouritesAdapter
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreate(x: Bundle?) {
        super.onCreate(x)
        supportActionBar?.hide()
        b = ActivityFavouritesBinding.inflate(layoutInflater)
        setContentView(b.root)
        ThemeManager.load(this)
        val p = ThemeManager.palette()
        b.root.setBackgroundColor(p.bgPrimary)
        b.viewAccent?.setBackgroundColor(p.accent)
        MainSidebarController.setup(this, b.root, MainSidebarController.Section.FAVOURITES)

        ma = FavouritesAdapter(::click, ::longClick)
        sa = FavouritesAdapter(::click, ::longClick)
        la = FavouritesAdapter(::click, ::longClick)
        ca = FavouritesAdapter(::click, ::longClick)

        setupRow(b.rvMovies, ma, 320)
        setupRow(b.rvSeries, sa, 320)
        setupRow(b.rvLive, la, 184)
        setupRow(b.rvCategories, ca, 184)
    }

    private fun setupRow(r: androidx.recyclerview.widget.RecyclerView, a: FavouritesAdapter, heightDp: Int) {
        r.adapter = a
        r.layoutManager = LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false)
        r.isNestedScrollingEnabled = false
        r.itemAnimator = null
        r.layoutParams = r.layoutParams.apply {
            height = (heightDp * resources.displayMetrics.density).toInt()
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val x = FavouritesManager.getAll(this)
        val m = x.filter { it.type == FavType.MOVIE && !it.hasResume }
        val s = x.filter { it.type == FavType.SERIES && !it.hasResume && !it.isUpNext }
        val l = x.filter { it.type == FavType.LIVE }
        val c = x.filter { it.type == FavType.CATEGORY }

        sec(b.headerMovies, b.rvMovies, ma, m)
        sec(b.headerSeries, b.rvSeries, sa, s)
        sec(b.headerLive, b.rvLive, la, l)
        sec(b.headerCategories, b.rvCategories, ca, c)

        b.tvEmpty.visibility =
            if (m.isEmpty() && s.isEmpty() && l.isEmpty() && c.isEmpty()) View.VISIBLE else View.GONE
        b.tvCount.text = "${m.size + s.size + l.size + c.size} ITEMS"
    }

    private fun sec(
        h: View,
        r: androidx.recyclerview.widget.RecyclerView,
        a: FavouritesAdapter,
        x: List<FavouriteItem>
    ) {
        h.visibility = if (x.isEmpty()) View.GONE else View.VISIBLE
        r.visibility = h.visibility
        if (x.isNotEmpty()) a.submitList(x) else a.submitList(emptyList())
    }

    private fun click(i: FavouriteItem) {
        when (i.type) {
            FavType.MOVIE -> openMovie(i)
            FavType.SERIES, FavType.EPISODE -> openSeries(i)
            FavType.LIVE -> startActivity(
                Intent(this, HomeActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
                    putExtra(HomeActivity.EXTRA_SECTION, "LIVE")
                }
            )
            FavType.CATEGORY -> cat(i)
        }
    }

    private fun profileFor(i: FavouriteItem) =
        PrefsManager.getProfiles(this).firstOrNull { it.id == i.profileId }
            ?: PrefsManager.getActiveProfile(this)

    private fun openMovie(i: FavouriteItem) {
        val p = profileFor(i) ?: return
        startActivity(Intent(this, com.orbital.iptv.ui.vod.MovieDetailActivity::class.java).apply {
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_ID, i.streamId)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_NAME, i.title)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_ICON, i.artUrl)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_CONTAINER_EXT, "mp4")
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_SERVER_URL, p.serverUrl)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_USERNAME, p.username)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_PASSWORD, p.password)
            putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_URL_OVERRIDE, i.streamUrl)
        })
    }

    private fun openSeries(i: FavouriteItem) {
        val p = profileFor(i) ?: return
        startActivity(Intent(this, com.orbital.iptv.ui.series.SeriesDetailActivity::class.java).apply {
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_ID, i.seriesId.takeIf { it > 0 } ?: i.streamId)
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_NAME, i.title.substringBefore(" — ").ifBlank { i.title })
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_COVER, i.artUrl)
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERVER_URL, p.serverUrl)
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_USERNAME, p.username)
            putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_PASSWORD, p.password)
        })
    }

    private fun cat(i: FavouriteItem) {
        val p = PrefsManager.getProfiles(this).firstOrNull { it.id == i.profileId }
            ?: PrefsManager.getActiveProfile(this) ?: return
        PrefsManager.setActiveProfile(this, p.id)
        when (i.categoryType) {
            "MOVIES" -> startActivity(Intent(this, VodActivity::class.java))
            "SERIES" -> startActivity(Intent(this, SeriesActivity::class.java))
            "LIVE" -> startActivity(
                Intent(this, HomeActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
                    putExtra(HomeActivity.EXTRA_SECTION, "LIVE")
                }
            )
        }
    }

    private fun longClick(i: FavouriteItem) {
        androidx.appcompat.app.AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle(i.title.uppercase())
            .setItems(arrayOf("REMOVE FROM FAVOURITES", "CANCEL")) { _, w ->
                if (w == 0) {
                    FavouritesManager.remove(this, i.id)
                    refresh()
                }
            }
            .show()
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }
}