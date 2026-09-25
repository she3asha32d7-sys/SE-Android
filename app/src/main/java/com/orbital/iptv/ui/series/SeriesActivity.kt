package com.orbital.iptv.ui.series

import android.content.Intent
import com.orbital.iptv.ui.vod.VodActivity
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import android.widget.EditText
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import androidx.recyclerview.widget.GridLayoutManager
import com.orbital.iptv.data.model.SeriesCategory
import com.orbital.iptv.data.model.SeriesStream
import com.orbital.iptv.databinding.ActivitySeriesBinding
import com.orbital.iptv.R
import com.orbital.iptv.data.model.FavType
import com.orbital.iptv.utils.ContentCache
import com.orbital.iptv.utils.FavouritesManager
import com.orbital.iptv.utils.PlayerLauncher
import com.orbital.iptv.utils.PrefsManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import com.orbital.iptv.utils.ThemeManager
import com.orbital.iptv.utils.MainSidebarController
import com.orbital.iptv.ui.settings.SettingsActivity
import com.orbital.iptv.utils.WatchHistoryManager
import com.orbital.iptv.utils.MainSidebarController.Section

class SeriesActivity : AppCompatActivity() {

    companion object { const val EXTRA_OPEN_FAVOURITE_SERIES = "open_favourite_SERIES" }

    private lateinit var binding: ActivitySeriesBinding
    private lateinit var viewModel: SeriesViewModel
    private lateinit var adapter: SeriesAdapter
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private var allShows: List<SeriesStream> = emptyList()
    private var showingContinue = false
    private var showingFavourites = false
    private var showingAll = true
    private var showingSearch = false
    private var showingLastAdded = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        binding = ActivitySeriesBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ThemeManager.load(this)
        val p = ThemeManager.palette()
        binding.root.setBackgroundColor(p.bgPrimary)
        binding.viewAccent?.setBackgroundColor(p.accent)

        viewModel = ViewModelProvider(this)[SeriesViewModel::class.java]
        MainSidebarController.setup(
            this, binding.root, Section.SERIES,
            onSettings = { startActivity(Intent(this, SettingsActivity::class.java)) }
        )

        adapter = SeriesAdapter(this) { show -> onShowSelected(show) }
        binding.rvShows.apply {
            this.adapter = this@SeriesActivity.adapter
            layoutManager = GridLayoutManager(this@SeriesActivity, 4)
        }

        onBackPressedDispatcher.addCallback(this, object : androidx.activity.OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.rvShows.hasFocus()) {
                    binding.catContainer.getChildAt(0)?.requestFocus()
                    return
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
                isEnabled = true
            }
        })

        viewModel.uiState.observe(this) { state ->
            binding.progressBar.visibility = if (state.isLoading) View.VISIBLE else View.GONE
            state.error?.let {
                binding.tvError.text = it.uppercase()
                binding.tvError.visibility = View.VISIBLE
            } ?: run { binding.tvError.visibility = View.GONE }

            if (!showingContinue && !showingFavourites && !showingSearch && !showingAll && !showingLastAdded) {
                adapter.submitList(state.shows)
            }
            if (state.categories.isNotEmpty()) {
                buildCategoryMenu(state.categories, state.selectedCategory)
            }
        }

        val creds = PrefsManager.getCredentials(this) ?: run { finish(); return }
        viewModel.loadCategories(creds.serverUrl, creds.username, creds.password)

        scope.launch {
            val cached = ContentCache.getSeries(this@SeriesActivity, creds.serverUrl)
            if (cached != null) {
                allShows = cached
                when {
                    showingAll -> adapter.submitList(allShows)
                    showingFavourites -> showFavouritesSeries()
                    showingContinue -> showContinueWatching()
                    showingLastAdded -> adapter.submitList(allShows.sortedByDescending { recentSortKey(it.added ?: it.lastModified) }.take(30))
                }
            } else {
                ContentCache.downloadAndSaveSeries(
                    this@SeriesActivity, creds.serverUrl, creds.username, creds.password
                )
                ContentCache.getSeries(this@SeriesActivity, creds.serverUrl)?.let {
                    allShows = it
                    when {
                        showingAll -> adapter.submitList(allShows)
                        showingFavourites -> showFavouritesSeries()
                        showingContinue -> showContinueWatching()
                        showingLastAdded -> adapter.submitList(allShows.sortedByDescending { recentSortKey(it.added ?: it.lastModified) }.take(30))
                    }
                }
            }
        }
    }

    private fun buildCategoryMenu(categories: List<SeriesCategory>, selected: SeriesCategory?) {
        val container = binding.catContainer
        container.removeAllViews()

        val p = ThemeManager.palette()
        val density = resources.displayMetrics.density
        val rowH = (46 * density).toInt()
        val pad = (16 * density).toInt()
        val marginPx = (p.itemMarginDp * density).toInt()

        fun addRow(label: String, selectedRow: Boolean = false, action: () -> Unit) {
            container.addView(TextView(this).apply {
                val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, rowH)
                if (marginPx > 0) lp.setMargins(marginPx, marginPx / 2, marginPx, marginPx / 2)
                layoutParams = lp
                gravity = Gravity.CENTER_VERTICAL
                setPadding(pad, 0, 0, 0)
                text = label
                textSize = 13f
                typeface = Typeface.create("sans-serif-condensed", Typeface.NORMAL)
                isClickable = true; isFocusable = true
                background = ThemeManager.roundedBg(if (selectedRow) p.highlight else p.bgMid, density)
                setTextColor(if (selectedRow) 0xFF000000.toInt() else 0xFFFFFFFF.toInt())
                setOnFocusChangeListener { _, hasFocus -> if (!selectedRow) background = ThemeManager.focusRowDrawable(density, p.bgMid, hasFocus) }
                setOnClickListener { action() }
            })
        }

        addRow("SEARCH", showingSearch) { showSeriesSearchDialog() }
        addRow("ALL", showingAll) {
            showingSearch = false; showingFavourites = false; showingContinue = false; showingLastAdded = false; showingAll = true
            showAllSeries(); buildCategoryMenu(categories, selected)
        }
        addRow("★  FAVOURITE", showingFavourites) {
            showingSearch = false; showingFavourites = true; showingContinue = false; showingLastAdded = false; showingAll = false
            showFavouritesSeries(); buildCategoryMenu(categories, selected)
        }
        addRow("▶  CONTINUE WATCHING", showingContinue) {
            showingSearch = false; showingFavourites = false; showingContinue = true; showingLastAdded = false; showingAll = false
            showContinueWatching(); buildCategoryMenu(categories, selected)
        }
        addRow("LAST ADDED", showingLastAdded) {
            showingSearch = false; showingFavourites = false; showingContinue = false; showingLastAdded = true; showingAll = false
            scope.launch {
                val list = ensureAllSeries().sortedByDescending { recentSortKey(it.added ?: it.lastModified) }.take(30)
                adapter.submitList(list)
                buildCategoryMenu(categories, selected)
            }
        }

        val offset = 5
        val visibleCategories = categories.filter { !it.categoryName.equals("SERIES", true) }
        visibleCategories.forEachIndexed { i, cat ->
            val isSelected = !showingContinue && !showingFavourites && !showingSearch && !showingAll && !showingLastAdded && cat.categoryId == selected?.categoryId
            val idx = i + offset
            val normalBg = if (idx % 2 == 0) p.bgMid else p.bgPrimary
            val row = LinearLayout(this).apply {
                val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, rowH)
                if (marginPx > 0) lp.setMargins(marginPx, marginPx / 2, marginPx, marginPx / 2)
                layoutParams = lp
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                layoutDirection = View.LAYOUT_DIRECTION_LTR
                isFocusable = false
            }
            val nameView = TextView(this).apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f)
                gravity = Gravity.LEFT or Gravity.CENTER_VERTICAL
                setPadding(pad, 0, 0, 0)
                layoutDirection = View.LAYOUT_DIRECTION_LTR
                textDirection = View.TEXT_DIRECTION_ANY_RTL
                text = cat.categoryName
                textSize = 13f
                typeface = Typeface.create("sans-serif-condensed", Typeface.NORMAL)
                isClickable = true; isFocusable = true
            }
            val heartView = TextView(this).apply {
                id = View.generateViewId()
                layoutParams = LinearLayout.LayoutParams((56 * density).toInt(), LinearLayout.LayoutParams.MATCH_PARENT)
                gravity = Gravity.CENTER
                setPadding(0, 0, pad / 2, 0)
                textSize = 24f
                typeface = Typeface.DEFAULT
                isClickable = true; isFocusable = true
                nextFocusRightId = R.id.rv_shows
            }
            nameView.nextFocusRightId = heartView.id
            val profile = PrefsManager.getActiveProfile(this@SeriesActivity)
            fun syncHeart() {
                val fav = profile?.let { FavouritesManager.containsCategory(this@SeriesActivity, "SERIES", it.serverUrl, cat.categoryId) } == true
                heartView.text = if (fav) "♥" else "♡"
                heartView.setTextColor(if (fav) 0xFFFF2222.toInt() else 0xFFFFFFFF.toInt())
            }
            syncHeart()
            fun syncBackground(hasFocus: Boolean = nameView.hasFocus() || heartView.hasFocus()) {
                row.background = if (isSelected) ThemeManager.roundedBg(p.highlight, density)
                else ThemeManager.focusRowDrawable(density, normalBg, hasFocus)
                nameView.setTextColor(if (isSelected) 0xFF000000.toInt() else 0xFFFFFFFF.toInt())
            }
            nameView.setOnFocusChangeListener { _, hasFocus -> syncBackground(hasFocus) }
            heartView.setOnFocusChangeListener { _, hasFocus -> syncBackground(hasFocus) }
            nameView.setOnClickListener {
                showingContinue = false; showingFavourites = false; showingSearch = false; showingAll = false; showingLastAdded = false
                viewModel.selectCategory(cat)
            }
            heartView.setOnClickListener {
                if (profile != null) {
                    FavouritesManager.toggleCategory(this@SeriesActivity, "SERIES", cat.categoryId, cat.categoryName, profile.serverUrl, profile.id)
                    syncHeart()
                }
            }
            row.addView(nameView)
            row.addView(heartView)
            syncBackground()
            container.addView(row)
        }
    }

    private fun showSeriesSearchDialog() {
        val input = com.orbital.iptv.utils.SEKeyboardController.prepare(EditText(this).apply { hint = "SEARCH SERIES"; setSingleLine(true); requestFocus() })
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("SEARCH SERIES")
            .setView(input)
            .setPositiveButton("SEARCH") { _, _ ->
                val query = input.text.toString().trim()
                if (query.isBlank()) return@setPositiveButton
                showingSearch = true; showingAll = false; showingFavourites = false; showingContinue = false; showingLastAdded = false
                scope.launch {
                    val list = ensureAllSeries().filter { it.name.contains(query, ignoreCase = true) }
                    adapter.submitList(list)
                    viewModel.uiState.value?.categories?.let { buildCategoryMenu(it, viewModel.uiState.value?.selectedCategory) }
                }
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }

    private suspend fun ensureAllSeries(): List<SeriesStream> {
        if (allShows.isNotEmpty()) return allShows
        val creds = PrefsManager.getCredentials(this) ?: return emptyList()
        ContentCache.getSeries(this, creds.serverUrl)?.let { allShows = it; return it }
        ContentCache.downloadAndSaveSeries(this, creds.serverUrl, creds.username, creds.password)
        ContentCache.getSeries(this, creds.serverUrl)?.let { allShows = it; return it }
        return emptyList()
    }

    private fun showAllSeries() {
        scope.launch { adapter.submitList(ensureAllSeries()) }
    }

    private fun recentSortKey(raw: String?): Long {
        val v = raw?.trim().orEmpty()
        v.toLongOrNull()?.let { return it }
        return Regex("\\d{4}[-/]\\d{2}[-/]\\d{2}").find(v)?.value?.replace('/','-')?.replace("-","")?.toLongOrNull() ?: 0L
    }

    private fun showFavouritesSeries() {
        val favSeriesIds = FavouritesManager.getAll(this).filter { it.type == FavType.SERIES || (it.type == FavType.EPISODE && !it.hasResume && !it.isUpNext && it.seriesId >= 0) }.map { it.seriesId }.toSet()
        val favShows = allShows.filter { it.seriesId in favSeriesIds }
        adapter.submitList(favShows)
    }

    private fun showContinueWatching() {
        val continueItems = FavouritesManager.getAll(this)
            .filter { it.type == FavType.EPISODE && (it.hasResume || it.isUpNext) }
        // Per series, take the most recently touched episode
        val latestBySeriesId = continueItems
            .groupBy { it.seriesId }
            .mapValues { (_, eps) -> eps.maxByOrNull { it.addedAt }!! }
        val resumeLabels = latestBySeriesId.mapValues { (_, fav) ->
            val ep = if (fav.season.isNotBlank() && fav.episodeNum > 0)
                "S${fav.season}E${"%-2d".format(fav.episodeNum).trim()}  " else ""
            if (fav.isUpNext) "▶ ${ep}UP NEXT"
            else "▶ ${ep}FROM ${FavouritesManager.formatDuration(fav.resumePositionMs)} / ${FavouritesManager.formatDuration(fav.durationMs)}"
        }
        val resumeShows = allShows.filter { it.seriesId in resumeLabels }
        adapter.submitList(resumeShows, resumeLabels)
    }

    private fun onShowSelected(show: SeriesStream) {
        val creds = viewModel.getCredentials() ?: return
        if (showingContinue) {
            val fav = FavouritesManager.getAll(this)
                .filter { it.type == FavType.EPISODE && it.seriesId == show.seriesId && (it.hasResume || it.isUpNext) }
                .maxByOrNull { it.addedAt }
            if (fav != null) {
                PlayerLauncher.launch(
                    activity     = this,
                    streamUrl    = fav.streamUrl,
                    title        = fav.title,
                    streamId     = fav.streamId,
                    isLive       = false,
                    favId        = fav.id,
                    artUrl       = fav.artUrl,
                    resumeMs     = fav.resumePositionMs,
                    seriesId     = fav.seriesId,
                    season       = fav.season,
                    episodeNum   = fav.episodeNum,
                    episodeId    = fav.episodeId,
                    nextEpUrl    = fav.nextEpisodeUrl,
                    nextEpTitle  = fav.nextEpisodeTitle,
                    nextEpNum    = fav.nextEpisodeNum,
                    nextEpSeason = fav.nextEpisodeSeason,
                    nextEpId     = fav.nextEpisodeId
                )
                return
            }
        }
        startActivity(Intent(this, SeriesDetailActivity::class.java).apply {
            putExtra(SeriesDetailActivity.EXTRA_SERIES_ID, show.seriesId)
            putExtra(SeriesDetailActivity.EXTRA_SERIES_NAME, show.name)
            putExtra(SeriesDetailActivity.EXTRA_SERIES_COVER, show.cover ?: "")
            putExtra(SeriesDetailActivity.EXTRA_RATING, show.rating ?: "")
            putExtra(SeriesDetailActivity.EXTRA_SERVER_URL, creds.first)
            putExtra(SeriesDetailActivity.EXTRA_USERNAME, creds.second)
            putExtra(SeriesDetailActivity.EXTRA_PASSWORD, creds.third)
        })
    }

}