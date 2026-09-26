package com.orbital.iptv.ui.search

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.view.inputmethod.EditorInfo
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.orbital.iptv.data.repository.XtreamRepository
import com.orbital.iptv.databinding.ActivitySearchBinding
import com.orbital.iptv.ui.home.HomeActivity
import com.orbital.iptv.ui.player.PlayerActivity
import com.orbital.iptv.ui.series.SeriesDetailActivity
import com.orbital.iptv.ui.vod.MovieDetailActivity
import com.orbital.iptv.utils.ContentCache
import com.orbital.iptv.utils.MainSidebarController
import com.orbital.iptv.utils.PrefsManager
import com.orbital.iptv.utils.SEKeyboardController
import com.orbital.iptv.utils.ThemeManager
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class SearchActivity : AppCompatActivity() {

    companion object {
        private const val KEY_QUERY = "search_query"
        private var clearRequested = false
        private var activeInstance: SearchActivity? = null

        fun clearForMainNavigation() {
            clearRequested = true
            activeInstance?.clearSearchUi()
        }
    }

    private lateinit var binding: ActivitySearchBinding
    private lateinit var movieAdapter: SearchAdapter
    private lateinit var seriesAdapter: SearchAdapter
    private lateinit var liveAdapter: SearchAdapter
    private lateinit var categoryAdapter: SearchAdapter
    private var currentQuery = ""
    private var searchJob: Job? = null
    private val repository = XtreamRepository()
    private var cachedLiveCategories: List<com.orbital.iptv.data.model.LiveCategory>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        ThemeManager.load(this)
        binding = ActivitySearchBinding.inflate(layoutInflater)
        setContentView(binding.root)

        MainSidebarController.setup(this, binding.root, MainSidebarController.Section.SEARCH)

        movieAdapter = SearchAdapter(::onSearchItem)
        seriesAdapter = SearchAdapter(::onSearchItem)
        liveAdapter = SearchAdapter(::onSearchItem)
        categoryAdapter = SearchAdapter(::onSearchItem)
        setupRows()
        setupSearchBar()

        val shouldClear = clearRequested
        clearRequested = false
        currentQuery = if (shouldClear) "" else savedInstanceState?.getString(KEY_QUERY).orEmpty()
        binding.etSearch.setText(currentQuery)
        binding.etSearch.setSelection(binding.etSearch.text.length)
        if (currentQuery.isNotBlank()) binding.etSearch.post { scheduleSearch(immediate = true) }
        activeInstance = this
    }

    override fun onResume() {
        super.onResume()
        if (clearRequested) {
            clearSearchUi()
            clearRequested = false
        }
        activeInstance = this
    }

    override fun onPause() {
        super.onPause()
        if (activeInstance === this) activeInstance = null
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString(KEY_QUERY, binding.etSearch.text?.toString().orEmpty())
        super.onSaveInstanceState(outState)
    }

    private fun setupRows() {
        val rows = listOf(binding.rvMovies, binding.rvSeries, binding.rvLive, binding.rvCategories)
        rows.forEach { rv ->
            rv.layoutManager = LinearLayoutManager(this, LinearLayoutManager.HORIZONTAL, false)
            rv.isNestedScrollingEnabled = false
            rv.itemAnimator = null
            rv.overScrollMode = View.OVER_SCROLL_NEVER
        }
        binding.rvMovies.adapter = movieAdapter
        binding.rvSeries.adapter = seriesAdapter
        binding.rvLive.adapter = liveAdapter
        binding.rvCategories.adapter = categoryAdapter
        binding.btnSearch.nextFocusDownId = binding.rvMovies.id
        binding.rvMovies.nextFocusUpId = binding.btnSearch.id
        binding.rvMovies.nextFocusDownId = binding.rvSeries.id
        binding.rvSeries.nextFocusUpId = binding.rvMovies.id
        binding.rvSeries.nextFocusDownId = binding.rvLive.id
        binding.rvLive.nextFocusUpId = binding.rvSeries.id
        binding.rvLive.nextFocusDownId = binding.rvCategories.id
        binding.rvCategories.nextFocusUpId = binding.rvLive.id
    }

    private fun setupSearchBar() {
        SEKeyboardController.install(this)
        SEKeyboardController.prepare(binding.etSearch)
        binding.etSearch.nextFocusRightId = binding.btnSearch.id
        binding.btnSearch.nextFocusLeftId = binding.etSearch.id

        // Live search: results start updating as the user types instead of waiting for SEARCH.
        // A short debounce keeps rapid remote-control presses from starting a separate search
        // pass for every intermediate character.
        binding.etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) {
                scheduleSearch(immediate = false)
            }
        })

        binding.btnSearch.setOnClickListener { scheduleSearch(immediate = true) }
        binding.btnSearch.setOnFocusChangeListener { view, hasFocus ->
            val p = ThemeManager.palette()
            val d = resources.displayMetrics.density
            view.background = if (hasFocus) ThemeManager.focusRowDrawable(d, p.bgMid, true, focusFillColor = p.focus)
            else ThemeManager.roundedBg(p.bgMid, d)
        }
        binding.etSearch.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_SEARCH) {
                scheduleSearch(immediate = true)
                true
            } else false
        }
    }

    private fun scheduleSearch(immediate: Boolean) {
        val query = binding.etSearch.text?.toString()?.trim().orEmpty()
        currentQuery = query
        searchJob?.cancel()

        if (query.isBlank()) {
            clearResultsOnly()
            return
        }

        searchJob = lifecycleScope.launch {
            if (!immediate) delay(220L)
            if (!isActive || query != binding.etSearch.text?.toString()?.trim()) return@launch
            performSearch(query)
        }
    }

    private suspend fun performSearch(query: String) {
        val profile = PrefsManager.getActiveProfile(this) ?: run {
            clearResultsOnly()
            binding.tvEmpty.text = "NO ACTIVE XTREAM USER"
            return
        }

        binding.progressBar.visibility = View.VISIBLE
        binding.tvEmpty.visibility = View.GONE

        try {
            val serverUrl = profile.serverUrl
            val username = profile.username
            val password = profile.password

            coroutineScope {
                val moviesJob = async {
                if (ContentCache.getMovies(this@SearchActivity, serverUrl) == null) {
                    ContentCache.downloadAndSaveMovies(this@SearchActivity, serverUrl, username, password)
                }
                ContentCache.searchMovies(this@SearchActivity, serverUrl, query)
            }
            val seriesJob = async {
                if (ContentCache.getSeries(this@SearchActivity, serverUrl) == null) {
                    ContentCache.downloadAndSaveSeries(this@SearchActivity, serverUrl, username, password)
                }
                ContentCache.searchSeries(this@SearchActivity, serverUrl, query)
            }
            val liveJob = async {
                if (ContentCache.getLiveStreams(this@SearchActivity, serverUrl) == null) {
                    ContentCache.downloadAndSaveLiveStreams(this@SearchActivity, serverUrl, username, password)
                }
                ContentCache.getLiveStreams(this@SearchActivity, serverUrl).orEmpty()
                    .filter { it.name.contains(query, ignoreCase = true) }
            }
            val categoriesJob = async {
                val categories = cachedLiveCategories ?: repository.getLiveCategories(
                    serverUrl, username, password
                ).getOrNull().orEmpty().also { cachedLiveCategories = it }
                categories.filter { it.categoryName.contains(query, ignoreCase = true) }
            }

            val movies = moviesJob.await()
            val series = seriesJob.await()
            val live = liveJob.await()
            val categories = categoriesJob.await()

            if (!currentCoroutineContext().isActive || query != binding.etSearch.text?.toString()?.trim()) return@coroutineScope

            movieAdapter.submitList(movies.map { SearchAdapter.Item.Movie(it) })
            seriesAdapter.submitList(series.map { SearchAdapter.Item.Series(it) })
            liveAdapter.submitList(live.map { SearchAdapter.Item.Live(it) })
            categoryAdapter.submitList(categories.map { SearchAdapter.Item.Category(it) })

            binding.headerMovies.visibility = if (movies.isNotEmpty()) View.VISIBLE else View.GONE
            binding.rvMovies.visibility = if (movies.isNotEmpty()) View.VISIBLE else View.GONE
            binding.headerSeries.visibility = if (series.isNotEmpty()) View.VISIBLE else View.GONE
            binding.rvSeries.visibility = if (series.isNotEmpty()) View.VISIBLE else View.GONE
            binding.headerLive.visibility = if (live.isNotEmpty()) View.VISIBLE else View.GONE
            binding.rvLive.visibility = if (live.isNotEmpty()) View.VISIBLE else View.GONE
            binding.headerCategories.visibility = if (categories.isNotEmpty()) View.VISIBLE else View.GONE
            binding.rvCategories.visibility = if (categories.isNotEmpty()) View.VISIBLE else View.GONE

            val total = movies.size + series.size + live.size + categories.size
            binding.resultsScroll.visibility = if (total > 0) View.VISIBLE else View.GONE
            binding.tvEmpty.visibility = if (total == 0) View.VISIBLE else View.GONE
            if (total == 0) binding.tvEmpty.text = "NO RESULTS FOUND"
            }
        } catch (e: Exception) {
            if (!currentCoroutineContext().isActive) return
            binding.resultsScroll.visibility = View.GONE
            binding.tvEmpty.visibility = View.VISIBLE
            binding.tvEmpty.text = "SEARCH FAILED: " + (e.message ?: "UNKNOWN ERROR")
        } finally {
            if (currentCoroutineContext().isActive) binding.progressBar.visibility = View.GONE
        }
    }

    private fun clearResultsOnly() {
        movieAdapter.submitList(emptyList())
        seriesAdapter.submitList(emptyList())
        liveAdapter.submitList(emptyList())
        categoryAdapter.submitList(emptyList())
        binding.headerMovies.visibility = View.GONE
        binding.headerSeries.visibility = View.GONE
        binding.headerLive.visibility = View.GONE
        binding.headerCategories.visibility = View.GONE
        binding.resultsScroll.visibility = View.GONE
        binding.tvEmpty.visibility = View.VISIBLE
        binding.tvEmpty.text = "ENTER A SEARCH TERM"
    }

    private fun clearSearchUi() {
        currentQuery = ""
        searchJob?.cancel()
        if (::binding.isInitialized) {
            binding.etSearch.setText("")
            binding.etSearch.clearFocus()
            clearResultsOnly()
        }
    }

    private fun onSearchItem(item: SearchAdapter.Item) {
        val profile = PrefsManager.getActiveProfile(this) ?: return
        when (item) {
            is SearchAdapter.Item.Movie -> startActivity(Intent(this, MovieDetailActivity::class.java).apply {
                putExtra(MovieDetailActivity.EXTRA_STREAM_ID, item.value.streamId)
                putExtra(MovieDetailActivity.EXTRA_STREAM_NAME, item.value.name)
                putExtra(MovieDetailActivity.EXTRA_STREAM_ICON, item.value.streamIcon ?: "")
                putExtra(MovieDetailActivity.EXTRA_CONTAINER_EXT, item.value.containerExtension ?: "mp4")
                putExtra(MovieDetailActivity.EXTRA_RATING, item.value.rating ?: "")
                putExtra(MovieDetailActivity.EXTRA_SERVER_URL, profile.serverUrl)
                putExtra(MovieDetailActivity.EXTRA_USERNAME, profile.username)
                putExtra(MovieDetailActivity.EXTRA_PASSWORD, profile.password)
            })
            is SearchAdapter.Item.Series -> startActivity(Intent(this, SeriesDetailActivity::class.java).apply {
                putExtra(SeriesDetailActivity.EXTRA_SERIES_ID, item.value.seriesId)
                putExtra(SeriesDetailActivity.EXTRA_SERIES_NAME, item.value.name)
                putExtra(SeriesDetailActivity.EXTRA_SERIES_COVER, item.value.cover ?: "")
                putExtra(SeriesDetailActivity.EXTRA_RATING, item.value.rating ?: "")
                putExtra(SeriesDetailActivity.EXTRA_SERVER_URL, profile.serverUrl)
                putExtra(SeriesDetailActivity.EXTRA_USERNAME, profile.username)
                putExtra(SeriesDetailActivity.EXTRA_PASSWORD, profile.password)
            })
            is SearchAdapter.Item.Live -> {
                val url = repository.buildStreamUrl(profile.serverUrl, profile.username, profile.password, item.value.streamId)
                startActivity(Intent(this, PlayerActivity::class.java).apply {
                    putExtra(PlayerActivity.EXTRA_STREAM_URL, url)
                    putExtra(PlayerActivity.EXTRA_CHANNEL_NAME, item.value.name)
                    putExtra(PlayerActivity.EXTRA_STREAM_ID, item.value.streamId)
                    putExtra(PlayerActivity.EXTRA_IS_LIVE, true)
                    item.value.num?.let { putExtra(PlayerActivity.EXTRA_CHANNEL_NUM, it) }
                })
            }
            is SearchAdapter.Item.Category -> startActivity(Intent(this, HomeActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
                putExtra(HomeActivity.EXTRA_SECTION, "LIVE")
                putExtra(HomeActivity.EXTRA_LIVE_CATEGORY_ID, item.value.categoryId)
            })
        }
    }

    override fun onDestroy() {
        if (activeInstance === this) activeInstance = null
        searchJob?.cancel()
        super.onDestroy()
    }
}
