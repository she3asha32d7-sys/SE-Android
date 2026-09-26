package com.orbital.iptv.ui.vod

import android.content.Intent
import com.orbital.iptv.ui.series.SeriesActivity
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
import com.orbital.iptv.data.model.VodCategory
import com.orbital.iptv.data.model.VodStream
import com.orbital.iptv.databinding.ActivityVodBinding
import com.orbital.iptv.R
import com.orbital.iptv.data.model.FavType
import com.orbital.iptv.data.repository.XtreamRepository
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
import com.orbital.iptv.utils.WatchHistoryManager
import com.orbital.iptv.ui.settings.SettingsActivity
import com.orbital.iptv.utils.MainSidebarController.Section

class VodActivity : AppCompatActivity() {

    companion object { const val EXTRA_OPEN_FAVOURITE_MOVIE = "open_favourite_MOVIE" }

    private lateinit var binding: ActivityVodBinding
    private lateinit var viewModel: VodViewModel
    private lateinit var adapter: VodAdapter
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private var allMovies: List<VodStream> = emptyList()
    private var showingContinue = false
    private var showingFavourites = false
    private var showingAll = true
    private var showingSearch = false
    private var showingLastAdded = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        binding = ActivityVodBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ThemeManager.load(this)
        val p = ThemeManager.palette()
        binding.root.setBackgroundColor(p.bgPrimary)
        binding.viewAccent?.setBackgroundColor(p.accent)

        viewModel = ViewModelProvider(this)[VodViewModel::class.java]
        MainSidebarController.setup(
            this, binding.root, Section.MOVIES,
            onSettings = { startActivity(Intent(this, SettingsActivity::class.java)) }
        )

        adapter = VodAdapter(this) { movie -> onMovieSelected(movie) }
        binding.rvMovies.apply {
            this.adapter = this@VodActivity.adapter
            layoutManager = GridLayoutManager(this@VodActivity, 4)
        }

        onBackPressedDispatcher.addCallback(this, object : androidx.activity.OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.rvMovies.hasFocus()) {
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

            if (!showingContinue && !showingFavourites && !showingSearch && !showingAll) {
                adapter.submitList(state.movies)
            }
            if (state.categories.isNotEmpty()) {
                buildCategoryMenu(state.categories, state.selectedCategory)
            }
        }

        val creds = PrefsManager.getCredentials(this) ?: run { finish(); return }
        viewModel.loadCategories(creds.serverUrl, creds.username, creds.password)

        scope.launch {
            val cached = ContentCache.getMovies(this@VodActivity, creds.serverUrl)
            if (cached != null) {
                allMovies = cached
                when {
                    showingAll -> adapter.submitList(allMovies)
                    showingFavourites -> showFavouritesMovies()
                    showingContinue -> showContinueWatching()
                    showingLastAdded -> adapter.submitList(allMovies.sortedByDescending { recentSortKey(it.added) }.take(30))
                }
            } else {
                ContentCache.downloadAndSaveMovies(
                    this@VodActivity, creds.serverUrl, creds.username, creds.password
                )
                ContentCache.getMovies(this@VodActivity, creds.serverUrl)?.let {
                    allMovies = it
                    when {
                        showingAll -> adapter.submitList(allMovies)
                        showingFavourites -> showFavouritesMovies()
                        showingContinue -> showContinueWatching()
                        showingLastAdded -> adapter.submitList(allMovies.sortedByDescending { recentSortKey(it.added) }.take(30))
                    }
                }
            }
        }
    }

    private fun buildCategoryMenu(categories: List<VodCategory>, selected: VodCategory?) {
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
                setOnFocusChangeListener { _, hasFocus ->
                    if (!selectedRow) background = ThemeManager.focusRowDrawable(density, p.bgMid, hasFocus)
                }
                setOnClickListener { action() }
            })
        }

        addRow("SEARCH", showingSearch) { showMovieSearchDialog() }
        addRow("ALL", showingAll) {
            showingSearch = false; showingFavourites = false; showingContinue = false; showingAll = true
            showAllMovies()
            buildCategoryMenu(categories, selected)
        }

        addRow("★  FAVOURITE", showingFavourites) {
            showingSearch = false; showingFavourites = true; showingContinue = false; showingAll = false
            showFavouritesMovies()
            buildCategoryMenu(categories, selected)
        }

        addRow("▶  CONTINUE WATCHING", showingContinue) {
            showingSearch = false; showingFavourites = false; showingContinue = true; showingLastAdded = false; showingAll = false
            showContinueWatching()
            buildCategoryMenu(categories, selected)
        }

        addRow("LAST ADDED", showingLastAdded) {
            showingSearch = false; showingFavourites = false; showingContinue = false; showingLastAdded = true; showingAll = false
            scope.launch {
                val list = ensureAllMovies()
                    .sortedByDescending { recentSortKey(it.added) }
                    .take(30)
                adapter.submitList(list)
            }
            buildCategoryMenu(categories, selected)
        }

        var offset = 5
        val visibleCategories = categories.filter { !it.categoryName.equals("MOVIES", true) }
        visibleCategories.forEachIndexed { i, cat ->
            val isSelected = !showingContinue && !showingFavourites && !showingSearch && !showingLastAdded && !showingAll && cat.categoryId == selected?.categoryId
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
                nextFocusRightId = R.id.rv_movies
            }
            nameView.nextFocusRightId = heartView.id
            val profile = PrefsManager.getActiveProfile(this@VodActivity)
            fun syncHeart() {
                val fav = profile?.let { FavouritesManager.containsCategory(this@VodActivity, "MOVIES", it.serverUrl, cat.categoryId) } == true
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
                showingContinue = false; showingFavourites = false; showingSearch = false; showingLastAdded = false; showingAll = false
                viewModel.selectCategory(cat)
            }
            heartView.setOnClickListener {
                if (profile != null) {
                    FavouritesManager.toggleCategory(this@VodActivity, "MOVIES", cat.categoryId, cat.categoryName, profile.serverUrl, profile.id)
                    syncHeart()
                }
            }
            row.addView(nameView)
            row.addView(heartView)
            syncBackground()
            container.addView(row)
        }
    }

    private fun showMovieSearchDialog() {
        val input = com.orbital.iptv.utils.SEKeyboardController.prepare(EditText(this).apply {
            hint = "SEARCH MOVIES"
            setSingleLine(true)
            setText("")
            requestFocus()
        })
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("SEARCH MOVIES")
            .setView(input)
            .setPositiveButton("SEARCH") { _, _ ->
                val query = input.text.toString().trim()
                if (query.isBlank()) return@setPositiveButton
                showingSearch = true; showingAll = false; showingFavourites = false; showingContinue = false; showingLastAdded = false
                scope.launch {
                    val list = ensureAllMovies()
                    adapter.submitList(list.filter { it.name.contains(query, ignoreCase = true) })
                    viewModel.uiState.value?.categories?.let { buildCategoryMenu(it, viewModel.uiState.value?.selectedCategory) }
                }
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }

    private suspend fun ensureAllMovies(): List<VodStream> {
        if (allMovies.isNotEmpty()) return allMovies
        val creds = PrefsManager.getCredentials(this) ?: return emptyList()
        ContentCache.getMovies(this, creds.serverUrl)?.let {
            allMovies = it
            return it
        }
        ContentCache.downloadAndSaveMovies(this, creds.serverUrl, creds.username, creds.password)
        ContentCache.getMovies(this, creds.serverUrl)?.let {
            allMovies = it
            return it
        }
        return emptyList()
    }

    private fun showAllMovies() {
        scope.launch { adapter.submitList(ensureAllMovies()) }
    }

    private fun recentSortKey(raw: String?): Long {
        val v = raw?.trim().orEmpty()
        v.toLongOrNull()?.let { return it }
        return Regex("\\d{4}[-/]\\d{2}[-/]\\d{2}").find(v)?.value?.replace('/','-')?.replace("-","")?.toLongOrNull() ?: 0L
    }

    private fun showFavouritesMovies() {
        val favIds = FavouritesManager.getAll(this)
            .filter { it.type == FavType.MOVIE && !it.hasResume }
            .map { it.streamId }.toSet()
        val favMovies = allMovies.filter { it.streamId in favIds }
        adapter.submitList(favMovies)
    }

    private fun showContinueWatching() {
        val continueItems = FavouritesManager.getAll(this).filter { it.hasResume && it.type == FavType.MOVIE }
        val resumeLabels = continueItems.associate { fav ->
            fav.streamId to "▶ FROM ${FavouritesManager.formatDuration(fav.resumePositionMs)} / ${FavouritesManager.formatDuration(fav.durationMs)}"
        }
        val resumeMovies = allMovies.filter { it.streamId in resumeLabels }
        adapter.submitList(resumeMovies, resumeLabels)
    }

    private fun onMovieSelected(movie: VodStream) {
        val creds = viewModel.getCredentials() ?: return
        if (showingContinue) {
            val favId  = "movie_${movie.streamId}"
            val fav    = FavouritesManager.getById(this, favId)
            val vodUrl = XtreamRepository().buildVodUrl(
                creds.first, creds.second, creds.third,
                movie.streamId, movie.containerExtension ?: "mp4"
            )
            PlayerLauncher.launch(
                activity  = this,
                streamUrl = vodUrl,
                title     = movie.name,
                streamId  = movie.streamId,
                isLive    = false,
                favId     = favId,
                artUrl    = movie.streamIcon ?: "",
                resumeMs  = fav?.resumePositionMs ?: 0L
            )
            return
        }
        startActivity(Intent(this, MovieDetailActivity::class.java).apply {
            putExtra(MovieDetailActivity.EXTRA_STREAM_ID, movie.streamId)
            putExtra(MovieDetailActivity.EXTRA_STREAM_NAME, movie.name)
            putExtra(MovieDetailActivity.EXTRA_STREAM_ICON, movie.streamIcon ?: "")
            putExtra(MovieDetailActivity.EXTRA_CONTAINER_EXT, movie.containerExtension ?: "mp4")
            putExtra(MovieDetailActivity.EXTRA_RATING, movie.rating ?: "")
            putExtra(MovieDetailActivity.EXTRA_SERVER_URL, creds.first)
            putExtra(MovieDetailActivity.EXTRA_USERNAME, creds.second)
            putExtra(MovieDetailActivity.EXTRA_PASSWORD, creds.third)
        })
    }

}