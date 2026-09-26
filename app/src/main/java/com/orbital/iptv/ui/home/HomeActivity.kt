package com.orbital.iptv.ui.home

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.Gravity
import android.view.ViewGroup
import android.view.LayoutInflater
import android.graphics.Color
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.work.*
import com.bumptech.glide.Glide
import com.orbital.iptv.R
import com.orbital.iptv.data.api.ApiClient
import com.orbital.iptv.data.model.EpgListing
import com.orbital.iptv.data.model.LiveCategory
import com.orbital.iptv.data.model.LiveStream
import com.orbital.iptv.data.model.ServerProfile
import com.orbital.iptv.data.model.getDecodedDescription
import com.orbital.iptv.data.model.getDecodedTitle
import com.orbital.iptv.data.repository.XtreamRepository
import com.orbital.iptv.databinding.ActivityHomeBinding
import com.orbital.iptv.recording.*
import com.orbital.iptv.ui.games.BubbleShooterActivity
import com.orbital.iptv.ui.games.GamesActivity
import com.orbital.iptv.ui.games.TeletextActivity
import com.orbital.iptv.utils.MainSidebarController
import com.orbital.iptv.utils.MainSidebarController.Section
import com.orbital.iptv.ui.sports.SportsActivity
import com.orbital.iptv.ui.login.LoginActivity
import com.orbital.iptv.ui.player.PlayerActivity
import com.orbital.iptv.ui.series.SeriesActivity
import com.orbital.iptv.ui.favourites.FavouritesActivity
import com.orbital.iptv.ui.vod.VodActivity
import com.orbital.iptv.ui.emby.EmbyBrowserActivity
import com.orbital.iptv.ui.emby.EmbyLoginActivity
import com.orbital.iptv.ui.plex.PlexBrowserActivity
import com.orbital.iptv.ui.plex.PlexLoginActivity
import com.orbital.iptv.ui.tv.TvModeActivity
import com.orbital.iptv.ui.tv.TvModeHolder
import com.orbital.iptv.utils.*
import com.orbital.iptv.ui.settings.SettingsActivity
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.common.MediaItem
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit

class HomeActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_SECTION = "section"
    }


    private lateinit var binding: ActivityHomeBinding
    private lateinit var viewModel: HomeViewModel
    private val repository = XtreamRepository()
    private var currentChannels: List<LiveStream> = emptyList()
    private lateinit var liveAdapter: LiveChannelAdapter
    private var epgLoadingJob: Job? = null
    private var miniPlayer: ExoPlayer? = null
    private var liveSearchActive = false
    private var currentSection: Section = Section.HOME




    override fun onResume() {
        super.onResume()
        if (miniPlayer != null && binding.miniPlayer.player == null) binding.miniPlayer.player = miniPlayer
        ReminderBus.register { r -> showReminderDialog(r) }
    }

    override fun onPause() {
        super.onPause()
        ReminderBus.unregister()
    }

    private fun showReminderDialog(r: ReminderBus.Reminder) {
        val msg = buildString {
            append(r.title)
            if (r.channelName.isNotBlank()) append("\n${r.channelName}")
            append("\n\nThis programme is starting now.")
        }
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("📺  PROGRAMME STARTING")
            .setMessage(msg)
            .setPositiveButton("WATCH NOW") { _, _ ->
                if (r.streamUrl.isNotBlank()) {
                    PlayerLauncher.launch(
                        activity  = this,
                        streamUrl = r.streamUrl,
                        title     = r.channelName,
                        streamId  = r.streamId,
                        isLive    = true
                    )
                }
            }
            .setNegativeButton("DISMISS", null)
            .show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        // Load the theme before inflating — EpgView reads ThemeManager.palette() once in its
        // constructor, so if this ran after inflate() a cold start (fresh process, no prior
        // activity to have already called load()) would bake in the default SE palette
        // regardless of the user's saved theme.
        ThemeManager.load(this)
        binding = ActivityHomeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        miniPlayer = ExoPlayer.Builder(this).build().also { binding.miniPlayer.player = it }
        ApiClient.liveFormat = PrefsManager.getLiveFormat(this)
        viewModel = ViewModelProvider(this)[HomeViewModel::class.java]
        setupLiveChannels()
        showSection(intent.getStringExtra(EXTRA_SECTION) ?: "HOME")
        applyTheme()
        observeViewModel()
        loadData()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility == View.GONE) { showSection("HOME"); return }
                // Back from the category list used to fall straight through to the app-exit
                // path below with no stop in between — send it up to the top nav bar first, same
                // as a Live TV screen would on any other platform.
                if (binding.originalCatContainer?.hasFocus() == true) {
                    binding.root.findViewById<View>(R.id.nav_live_tv)?.requestFocus()
                    return
                }
                if (binding.root.findViewById<View>(R.id.rv_live_channels)?.hasFocus() == true) {
                    val selectedId = viewModel.uiState.value?.selectedXtreamCategory?.categoryId
                    val container = binding.originalCatContainer
                    for (i in 0 until container.childCount) {
                        val child = container.getChildAt(i)
                        if (child.isFocusable && child.tag == selectedId) { child.requestFocus(); return }
                    }
                }
                if (binding.root.findViewById<View>(R.id.main_sidebar_container)?.hasFocus() == true) {
                    confirmExitApp()
                    return
                }
                if (PrefsManager.isTvModeEnabled(this@HomeActivity)) {
                    val url = PrefsManager.getLastTvChannelUrl(this@HomeActivity)
                    if (url != null) {
                        startActivity(Intent(this@HomeActivity, TvModeActivity::class.java).apply {
                            putExtra(TvModeActivity.EXTRA_STREAM_URL,   url)
                            putExtra(TvModeActivity.EXTRA_CHANNEL_NAME, PrefsManager.getLastTvChannelName(this@HomeActivity) ?: "")
                            putExtra(TvModeActivity.EXTRA_STREAM_ID,    PrefsManager.getLastTvStreamId(this@HomeActivity))
                            putExtra(TvModeActivity.EXTRA_CATEGORY_ID,  PrefsManager.getLastTvCategoryId(this@HomeActivity))
                        })
                        return
                    }
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
                isEnabled = true
            }
        })
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        when (intent.getStringExtra(EXTRA_SECTION)?.uppercase(Locale.ROOT)) {
            "LIVE" -> showSection("LIVE")
            "HOME" -> showSection("HOME")
            else -> showSection("HOME")
        }
    }

    private fun confirmExitApp() {
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("Do You Want To Exit The App")
            .setPositiveButton("Yes") { _, _ -> finishAffinity() }
            .setNegativeButton("No", null)
            .show()
    }

    fun showSection(mode:String) {
        currentSection = if (mode.equals("HOME", true)) Section.HOME else Section.LIVE_TV
        val home = currentSection == Section.HOME
        binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility = View.VISIBLE
        binding.root.findViewById<View>(R.id.dashboard_container)?.visibility = if (home) View.VISIBLE else View.GONE
        binding.root.findViewById<View>(R.id.layout_live_categories)?.visibility = if (home) View.GONE else View.VISIBLE
        binding.root.findViewById<View>(R.id.layout_live_content)?.visibility = if (home) View.GONE else View.VISIBLE
        MainSidebarController.setup(
            this,
            binding.root,
            currentSection,
            onSettings = { startActivity(Intent(this, SettingsActivity::class.java)) },
            onHome = { showSection("HOME") },
            onLiveTv = { showSection("LIVE") }
        )
        if (home) buildHomeDashboard()
    }

    private var homeMetadataJob: Job? = null

    /**
     * Home dashboard is intentionally a real vertical ScrollView so the whole mobile screen
     * can be swiped.  Continue Watching cards reuse the same visual card resources used by the
     * Movies / Series screens, while Live TV gets a matching icon + programme card.
     */
    private fun buildHomeDashboard() {
        val dash = binding.root.findViewById<LinearLayout>(R.id.dashboard_container) ?: return
        homeMetadataJob?.cancel()
        dash.removeAllViews()
        dash.visibility = View.VISIBLE

        val p = ThemeManager.palette()
        val d = resources.displayMetrics.density
        val scroll = android.widget.ScrollView(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            isFillViewport = true
            isVerticalScrollBarEnabled = true
            overScrollMode = View.OVER_SCROLL_IF_CONTENT_SCROLLS
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
            setPadding((8*d).toInt(), (6*d).toInt(), (8*d).toInt(), (24*d).toInt())
        }
        scroll.addView(content)
        dash.addView(scroll)

        // Home shortcuts.
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
        listOf("LIVE TV" to "LIVE", "MOVIES" to "MOVIES", "SERIES" to "SERIES").forEach { (label, mode) ->
            buttons.addView(TextView(this).apply {
                text = label
                textSize = 15f
                setTextColor(Color.WHITE)
                gravity = Gravity.CENTER
                background = ThemeManager.roundedBg(p.bgMid, d)
                isFocusable = true
                isClickable = true
                setPadding((10*d).toInt(), 0, (10*d).toInt(), 0)
                setOnClickListener {
                    when (mode) {
                        "LIVE" -> showSection("LIVE")
                        "MOVIES" -> startActivity(Intent(this@HomeActivity, VodActivity::class.java).apply { addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT) })
                        "SERIES" -> startActivity(Intent(this@HomeActivity, SeriesActivity::class.java).apply { addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT) })
                    }
                }
                layoutParams = LinearLayout.LayoutParams(0, (58*d).toInt(), 1f).also {
                    it.setMargins((8*d).toInt(), (8*d).toInt(), (8*d).toInt(), (8*d).toInt())
                }
            })
        }
        content.addView(buttons)

        val metadataTextViews = mutableMapOf<String, TextView>()
        val metadataSeriesTextViews = mutableMapOf<String, TextView>()

        fun addSectionTitle(title: String) {
            content.addView(TextView(this).apply {
                text = title
                setTextColor(p.accent)
                textSize = 14f
                setTypeface(typeface, Typeface.BOLD)
                setPadding((14*d).toInt(), (18*d).toInt(), (14*d).toInt(), (6*d).toInt())
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
            })
        }

        fun addHorizontalRow(row: LinearLayout, cardHeight: Int) {
            content.addView(android.widget.HorizontalScrollView(this).apply {
                layoutParams = LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    (cardHeight*d).toInt()
                )
                isHorizontalScrollBarEnabled = false
                isFillViewport = false
                clipChildren = false
                clipToPadding = false
                addView(row, ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT)
            })
        }

        // LIVE TV: keep the actual watched channel data, but present it as a media card with icon,
        // channel name, current programme when available, resume time, favourite and remove.
        val liveHistory = WatchHistoryManager.get(this, "LIVE").take(15)
        if (liveHistory.isNotEmpty()) {
            addSectionTitle("CONTINUE WATCHING LIVE TV")
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            liveHistory.forEach { h ->
                val channel = currentChannels.firstOrNull { it.streamId == h.streamId }
                row.addView(makeHomeLiveContinueCard(h, channel?.epgNow, channel?.streamIcon ?: h.artUrl, d))
            }
            addHorizontalRow(row, 186)
        }

        // MOVIES: same card resource as the Movies page, sourced from its real Continue Watching
        // entries so poster + title + favourite state stay consistent with that screen.
        val movieHistory = FavouritesManager.getAll(this)
            .filter { it.type == com.orbital.iptv.data.model.FavType.MOVIE && it.hasResume }
            .sortedByDescending { it.addedAt }
            .take(15)
        if (movieHistory.isNotEmpty()) {
            addSectionTitle("CONTINUE WATCHING MOVIES")
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            movieHistory.forEach { fav ->
                row.addView(makeHomeMovieContinueCard(fav, d, metadataTextViews))
            }
            addHorizontalRow(row, 320)
        }

        // SERIES: exactly one latest Continue item per series, matching SeriesActivity's own logic.
        val seriesHistory = FavouritesManager.getAll(this)
            .filter { it.type == com.orbital.iptv.data.model.FavType.EPISODE && (it.hasResume || it.isUpNext) }
            .groupBy { it.seriesId }
            .mapNotNull { (_, eps) -> eps.maxByOrNull { it.addedAt } }
            .sortedByDescending { it.addedAt }
            .take(15)
        if (seriesHistory.isNotEmpty()) {
            addSectionTitle("CONTINUE WATCHING SERIES")
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            seriesHistory.forEach { fav ->
                row.addView(makeHomeSeriesContinueCard(fav, d, metadataSeriesTextViews))
            }
            addHorizontalRow(row, 320)
        }

        // Pull fresh movie/series metadata only when available so the card can show the same
        // rating/year information as the library pages without blocking Home rendering.
        val profile = PrefsManager.getActiveProfile(this)
        if (profile != null && (metadataTextViews.isNotEmpty() || metadataSeriesTextViews.isNotEmpty())) {
            homeMetadataJob = lifecycleScope.launch {
                val gate = Semaphore(4)
                val movieJobs = movieHistory.map { fav ->
                    async(Dispatchers.IO) {
                        gate.withPermit {
                            val info = repository.getVodInfo(profile.serverUrl, profile.username, profile.password, fav.streamId).getOrNull()?.info
                            fav.id to info
                        }
                    }
                }
                val seriesJobs = seriesHistory.map { fav ->
                    async(Dispatchers.IO) {
                        gate.withPermit {
                            val info = repository.getSeriesInfo(profile.serverUrl, profile.username, profile.password, fav.seriesId).getOrNull()?.info
                            fav.id to info
                        }
                    }
                }
                val movieInfo = movieJobs.awaitAll()
                val seriesInfo = seriesJobs.awaitAll()
                withContext(Dispatchers.Main) {
                    movieInfo.forEach { (id, info) ->
                        val tv = metadataTextViews[id] ?: return@forEach
                        val fav = movieHistory.firstOrNull { it.id == id } ?: return@forEach
                        tv.text = buildString {
                            info?.rating?.trim()?.takeIf { it.isNotBlank() && it != "0" && it != "0.0" }?.let { append("★ ").append(it) }
                            info?.releaseDate?.let { Regex("\\d{4}").find(it)?.value }?.let { y -> if (isNotEmpty()) append("  •  "); append(y) }
                            if (isNotEmpty()) append("  •  ")
                            append("▶ ").append(FavouritesManager.formatDuration(fav.resumePositionMs))
                            if (fav.durationMs > 0) append(" / ").append(FavouritesManager.formatDuration(fav.durationMs))
                        }
                    }
                    seriesInfo.forEach { (id, info) ->
                        val tv = metadataSeriesTextViews[id] ?: return@forEach
                        val fav = seriesHistory.firstOrNull { it.id == id } ?: return@forEach
                        val episodeTag = if (fav.season.isNotBlank() && fav.episodeNum > 0)
                            "S${fav.season}E${"%02d".format(fav.episodeNum)}" else ""
                        tv.text = buildString {
                            info?.rating?.trim()?.takeIf { it.isNotBlank() && it != "0" && it != "0.0" }?.let { append("★ ").append(it) }
                            info?.releaseDate?.let { Regex("\\d{4}").find(it)?.value }?.let { y -> if (isNotEmpty()) append("  •  "); append(y) }
                            if (episodeTag.isNotBlank()) { if (isNotEmpty()) append("  •  "); append(episodeTag) }
                            if (isNotEmpty()) append("  •  ")
                            if (fav.isUpNext) append("▶ UP NEXT")
                            else {
                                append("▶ ").append(FavouritesManager.formatDuration(fav.resumePositionMs))
                                if (fav.durationMs > 0) append(" / ").append(FavouritesManager.formatDuration(fav.durationMs))
                            }
                        }
                    }
                }
            }
        }
    }

    private fun makeHomeMovieContinueCard(
        fav: com.orbital.iptv.data.model.FavouriteItem,
        d: Float,
        metadataTextViews: MutableMap<String, TextView>
    ): View {
        val root = LayoutInflater.from(this).inflate(R.layout.item_vod_movie, null, false)
        root.layoutParams = LinearLayout.LayoutParams((170*d).toInt(), ViewGroup.LayoutParams.WRAP_CONTENT).also {
            it.setMargins((5*d).toInt(), (4*d).toInt(), (5*d).toInt(), (8*d).toInt())
        }
        val poster = root.findViewById<ImageView>(R.id.iv_poster)
        val title = root.findViewById<TextView>(R.id.tv_title)
        val rating = root.findViewById<TextView>(R.id.tv_rating)
        val favBtn = root.findViewById<TextView>(R.id.btn_fav)
        title.text = fav.title
        rating.text = "▶ ${FavouritesManager.formatDuration(fav.resumePositionMs)}" + if (fav.durationMs > 0) " / ${FavouritesManager.formatDuration(fav.durationMs)}" else ""
        rating.setTextColor(0xFF00CCFF.toInt())
        poster.setBackgroundColor(ThemeManager.palette().bgMid)
        if (fav.artUrl.isNotBlank()) Glide.with(this).load(fav.artUrl).centerCrop().into(poster)
        fun syncFavorite() {
            val checked = FavouritesManager.contains(this, fav.id)
            favBtn.text = if (checked) "♥" else "♡"
            favBtn.setTextColor(if (checked) 0xFFFF2222.toInt() else Color.WHITE)
        }
        syncFavorite()
        favBtn.setOnClickListener {
            if (FavouritesManager.contains(this, fav.id)) FavouritesManager.remove(this, fav.id)
            else FavouritesManager.addOrUpdate(this, fav)
            syncFavorite()
        }
        root.setOnClickListener {
            PlayerLauncher.launch(this, fav.streamUrl, fav.title, fav.streamId, false, fav.id, fav.artUrl, fav.resumePositionMs)
        }
        applyHomeCardFocus(root, title, d)
        metadataTextViews[fav.id] = rating
        return root
    }

    private fun makeHomeSeriesContinueCard(
        fav: com.orbital.iptv.data.model.FavouriteItem,
        d: Float,
        metadataTextViews: MutableMap<String, TextView>
    ): View {
        val root = LayoutInflater.from(this).inflate(R.layout.item_series_show, null, false)
        root.layoutParams = LinearLayout.LayoutParams((170*d).toInt(), ViewGroup.LayoutParams.WRAP_CONTENT).also {
            it.setMargins((5*d).toInt(), (4*d).toInt(), (5*d).toInt(), (8*d).toInt())
        }
        val poster = root.findViewById<ImageView>(R.id.iv_poster)
        val title = root.findViewById<TextView>(R.id.tv_title)
        val rating = root.findViewById<TextView>(R.id.tv_rating)
        val favBtn = root.findViewById<TextView>(R.id.btn_fav)
        title.text = fav.title.substringBefore(" — ").ifBlank { fav.title }
        val ep = if (fav.season.isNotBlank() && fav.episodeNum > 0) "S${fav.season}E${"%02d".format(fav.episodeNum)}" else ""
        rating.text = buildString {
            if (ep.isNotBlank()) append(ep).append("  •  ")
            if (fav.isUpNext) append("▶ UP NEXT") else {
                append("▶ ").append(FavouritesManager.formatDuration(fav.resumePositionMs))
                if (fav.durationMs > 0) append(" / ").append(FavouritesManager.formatDuration(fav.durationMs))
            }
        }
        rating.setTextColor(0xFF00CCFF.toInt())
        poster.setBackgroundColor(ThemeManager.palette().bgMid)
        if (fav.artUrl.isNotBlank()) Glide.with(this).load(fav.artUrl).centerCrop().into(poster)
        fun syncFavorite() {
            val checked = FavouritesManager.contains(this, fav.id)
            favBtn.text = if (checked) "♥" else "♡"
            favBtn.setTextColor(if (checked) 0xFFFF2222.toInt() else Color.WHITE)
        }
        syncFavorite()
        favBtn.setOnClickListener {
            if (FavouritesManager.contains(this, fav.id)) FavouritesManager.remove(this, fav.id)
            else FavouritesManager.addOrUpdate(this, fav)
            syncFavorite()
        }
        root.setOnClickListener {
            PlayerLauncher.launch(
                activity = this,
                streamUrl = fav.streamUrl,
                title = fav.title,
                streamId = fav.streamId,
                isLive = false,
                favId = fav.id,
                artUrl = fav.artUrl,
                resumeMs = fav.resumePositionMs,
                seriesId = fav.seriesId,
                season = fav.season,
                episodeNum = fav.episodeNum,
                episodeId = fav.episodeId,
                nextEpUrl = fav.nextEpisodeUrl,
                nextEpTitle = fav.nextEpisodeTitle,
                nextEpNum = fav.nextEpisodeNum,
                nextEpSeason = fav.nextEpisodeSeason,
                nextEpId = fav.nextEpisodeId
            )
        }
        applyHomeCardFocus(root, title, d)
        metadataTextViews[fav.id] = rating
        return root
    }

    private fun makeHomeLiveContinueCard(
        h: WatchHistoryItem,
        currentProgramme: String?,
        iconUrl: String,
        d: Float
    ): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = ThemeManager.roundedBg(ThemeManager.palette().bgMid, d)
            isFocusable = true
            isClickable = true
            layoutParams = LinearLayout.LayoutParams((182*d).toInt(), (168*d).toInt()).also {
                it.setMargins((5*d).toInt(), (4*d).toInt(), (5*d).toInt(), (8*d).toInt())
            }
            setPadding((8*d).toInt(), (8*d).toInt(), (8*d).toInt(), (8*d).toInt())
        }
        val top = FrameLayout(this).apply { layoutParams = LinearLayout.LayoutParams(-1, (100*d).toInt()) }
        val icon = ImageView(this).apply {
            layoutParams = FrameLayout.LayoutParams(-1, -1)
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(ThemeManager.palette().bgPrimary)
        }
        top.addView(icon)
        val liveTag = TextView(this).apply {
            text = "LIVE TV"
            textSize = 9f
            setTextColor(Color.WHITE)
            setBackgroundColor(0xAA000000.toInt())
            setPadding((6*d).toInt(), (3*d).toInt(), (6*d).toInt(), (3*d).toInt())
            layoutParams = FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START)
        }
        top.addView(liveTag)
        root.addView(top)
        root.addView(TextView(this).apply {
            text = h.title
            textSize = 13f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.WHITE)
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(-1, (26*d).toInt())
        })
        root.addView(TextView(this).apply {
            text = currentProgramme?.takeIf { it.isNotBlank() } ?: "CONTINUE WATCHING"
            textSize = 10f
            setTextColor(0xFF9AA8C8.toInt())
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = LinearLayout.LayoutParams(-1, (20*d).toInt())
        })
        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(-1, (24*d).toInt())
        }
        bottom.addView(TextView(this).apply {
            text = "▶ RESUME"
            textSize = 9f
            setTextColor(ThemeManager.palette().accent)
            layoutParams = LinearLayout.LayoutParams(0, -1, 1f)
            gravity = Gravity.CENTER_VERTICAL
        })
        bottom.addView(TextView(this).apply {
            text = "🗑"
            textSize = 15f
            setTextColor(0xFFFF6666.toInt())
            gravity = Gravity.CENTER
            isFocusable = true
            isClickable = true
            layoutParams = LinearLayout.LayoutParams((34*d).toInt(), -1)
            setOnClickListener {
                WatchHistoryManager.remove(this@HomeActivity, h.id)
                buildHomeDashboard()
            }
        })
        root.addView(bottom)
        if (iconUrl.isNotBlank()) Glide.with(this).load(iconUrl).centerCrop().into(icon)
        root.setOnClickListener {
            PlayerLauncher.launch(this, h.streamUrl, h.title, h.streamId, true, artUrl = h.artUrl, resumeMs = h.positionMs)
        }
        applyHomeCardFocus(root, root.getChildAt(1) as TextView, d)
        return root
    }

    private fun applyHomeCardFocus(root: View, title: TextView, d: Float) {
        root.setOnFocusChangeListener { _, hasFocus ->
            val pp = ThemeManager.palette()
            if (hasFocus) {
                root.scaleX = 1.045f
                root.scaleY = 1.045f
                root.elevation = (8*d)
                title.setTextColor(pp.accent)
                val bg = android.graphics.drawable.GradientDrawable()
                bg.setColor(pp.bgMid)
                bg.setStroke((3*d).toInt().coerceAtLeast(2), pp.accent)
                root.background = bg
            } else {
                root.scaleX = 1f
                root.scaleY = 1f
                root.elevation = 0f
                title.setTextColor(Color.WHITE)
                root.background = ThemeManager.roundedBg(pp.bgMid, d)
            }
        }
    }

    private fun setupLiveChannels() {
        liveAdapter = LiveChannelAdapter { channel -> onChannelSelected(channel) }
        binding.root.findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.rv_live_channels)?.apply {
            adapter = liveAdapter
            layoutManager = androidx.recyclerview.widget.GridLayoutManager(this@HomeActivity, 2)
            itemAnimator = null
            isFocusable = true
        }
    }

    private fun showBoxOfficeMenu() {
        data class MenuItem(val label: String, val action: () -> Unit)
        val items = mutableListOf(
            MenuItem("MOVIES")     { startActivity(Intent(this, VodActivity::class.java)) },
            MenuItem("SERIES")     { startActivity(Intent(this, SeriesActivity::class.java)) },
            MenuItem("CATCHUP")    { startActivity(Intent(this, com.orbital.iptv.ui.catchup.CatchupActivity::class.java)) },
            MenuItem("CONTINUE WATCHING / FAVOURITES") { startActivity(Intent(this, FavouritesActivity::class.java)) }
        )
        if (EmbyPrefsManager.getSession(this) != null)
            items.add(MenuItem("EMBY") { startActivity(Intent(this, EmbyBrowserActivity::class.java)) })
        if (PlexPrefsManager.getSession(this) != null)
            items.add(MenuItem("PLEX") { startActivity(Intent(this, PlexBrowserActivity::class.java)) })
        items.add(MenuItem("⏺ RECORDINGS") { startActivity(Intent(this, com.orbital.iptv.recording.RecordingsActivity::class.java)) })
        if (com.orbital.iptv.utils.TorboxPrefsManager.getApiKey(this) != null)
            items.add(MenuItem("TORBOX") { startActivity(Intent(this, com.orbital.iptv.ui.torbox.TorboxBrowserActivity::class.java)) })

        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("CONTENT")
            .setItems(items.map { it.label }.toTypedArray()) { _, i -> items[i].action() }
            .show()
    }

    private fun showRadioMenu() {
        val stations = com.orbital.iptv.ui.radio.RadioStations.load(this)
        if (stations.isEmpty()) {
            Toast.makeText(this, "NO RADIO STATIONS FOUND", Toast.LENGTH_SHORT).show()
            return
        }
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("RADIO")
            .setItems(stations.map { it.name.uppercase() }.toTypedArray()) { _, which ->
                val station = stations[which]
                startActivity(Intent(this, PlayerActivity::class.java).apply {
                    putExtra(PlayerActivity.EXTRA_STREAM_URL, station.url)
                    putExtra(PlayerActivity.EXTRA_CHANNEL_NAME, station.name)
                    putExtra(PlayerActivity.EXTRA_IS_LIVE, true)
                })
            }
            .show()
    }

    private fun showInteractiveMenu() {
        data class MenuItem(val label: String, val action: () -> Unit)
        val items = mutableListOf(
            MenuItem("SPORTS BAR")     { startActivity(Intent(this, SportsActivity::class.java)) },
            MenuItem("TELETEXT")       { startActivity(Intent(this, TeletextActivity::class.java)) },
            MenuItem("BUBBLE SHOOTER") { startActivity(Intent(this, BubbleShooterActivity::class.java)) },
        )
        val tickerOn = TickerManager.newsTickerEnabled
        items.add(MenuItem("NEWS TICKER: ${if (tickerOn) "ON" else "OFF"}") {
            TickerManager.newsTickerEnabled = !tickerOn
            TickerManager.sportHeadlines.clear()
            showInteractiveMenu()
        })
        items.add(MenuItem("TICKER SPORTS...") { showTickerSportPicker() })
        items.add(MenuItem("EMBY") {
            val dest = if (EmbyPrefsManager.getSession(this) != null) EmbyBrowserActivity::class.java else EmbyLoginActivity::class.java
            startActivity(Intent(this, dest))
        })
        items.add(MenuItem("PLEX") {
            val dest = if (PlexPrefsManager.getSession(this) != null) PlexBrowserActivity::class.java else PlexLoginActivity::class.java
            startActivity(Intent(this, dest))
        })
        items.add(MenuItem("TORBOX") { showTorboxKeyDialog() })

        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("INTERACTIVE")
            .setItems(items.map { it.label }.toTypedArray()) { _, i -> items[i].action() }
            .show()
    }

    private fun showTorboxKeyDialog() {
        val current = com.orbital.iptv.utils.TorboxPrefsManager.getApiKey(this) ?: ""
        val et = com.orbital.iptv.utils.SEKeyboardController.prepare(android.widget.EditText(this).apply {
            setText(current)
            hint = "PASTE TORBOX API KEY HERE"
            setPadding(48, 24, 48, 24)
        })
        val builder = androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("TORBOX API KEY")
            .setMessage("Get your key at torbox.app → Settings → API")
            .setView(et)
            .setPositiveButton("SAVE") { _, _ ->
                val key = et.text.toString().trim()
                if (key.isNotBlank()) {
                    com.orbital.iptv.utils.TorboxPrefsManager.saveApiKey(this, key)
                    Toast.makeText(this, "TORBOX KEY SAVED", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("CANCEL", null)
        if (current.isNotBlank()) {
            builder.setNeutralButton("REMOVE KEY") { _, _ ->
                com.orbital.iptv.utils.TorboxPrefsManager.clear(this)
                Toast.makeText(this, "TORBOX KEY REMOVED", Toast.LENGTH_SHORT).show()
            }
        }
        val dlg = builder.show()
        dlg.window?.decorView?.post { com.orbital.iptv.utils.SEKeyboardController.showFocused(dlg.window!!.decorView) }
    }

    private fun showTickerSportPicker() {
        val feeds = TickerManager.SPORT_FEEDS
        val selectedIds = TickerManager.getSelectedSportIds(this).toMutableSet()
        val checked = feeds.map { it.id in selectedIds }.toBooleanArray()
        val labels = feeds.map { "${it.emoji} ${it.name}" }.toTypedArray()

        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("SELECT SPORTS FOR NEWS TICKER")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked ->
                if (isChecked) selectedIds.add(feeds[which].id)
                else selectedIds.remove(feeds[which].id)
            }
            .setPositiveButton("DONE") { _, _ ->
                TickerManager.setSelectedSportIds(this, selectedIds)
                if (selectedIds.isNotEmpty()) TickerManager.newsTickerEnabled = true
                TickerManager.sportHeadlines.clear()
            }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun showManageServerCategoriesDialog() {
        val categories = viewModel.uiState.value?.xtreamCategories ?: emptyList()
        if (categories.isEmpty()) {
            android.widget.Toast.makeText(this, "NO SERVER CATEGORIES LOADED", android.widget.Toast.LENGTH_SHORT).show()
            return
        }
        val hiddenIds = CategoryPrefs.getHiddenServerCatIds(this).toMutableSet()
        val labels  = categories.map { it.categoryName.uppercase() }.toTypedArray()
        val checked = categories.map { it.categoryId !in hiddenIds }.toBooleanArray()

        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("SHOW / HIDE CATEGORIES")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked ->
                if (isChecked) hiddenIds.remove(categories[which].categoryId)
                else           hiddenIds.add(categories[which].categoryId)
            }
            .setPositiveButton("SAVE") { _, _ ->
                CategoryPrefs.setHiddenServerCatIds(this, hiddenIds)
                loadData()
            }
            .setNegativeButton("CANCEL", null)
            .show()
    }


    private fun showOpenSubsKeyDialog() {
        val current = PrefsManager.getOpenSubsApiKey(this) ?: ""
        val et = com.orbital.iptv.utils.SEKeyboardController.prepare(android.widget.EditText(this).apply {
            setText(current)
            hint = "PASTE API KEY HERE"
            setPadding(48, 24, 48, 24)
        })
        val builder = androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("OPENSUBTITLES API KEY")
            .setMessage("Get a free key at opensubtitles.com → Consumers")
            .setView(et)
            .setPositiveButton("SAVE") { _, _ ->
                val key = et.text.toString().trim()
                if (key.isNotBlank()) PrefsManager.setOpenSubsApiKey(this, key)
            }
            .setNegativeButton("CANCEL", null)
        if (current.isNotBlank()) {
            builder.setNeutralButton("REMOVE KEY") { _, _ ->
                PrefsManager.setOpenSubsApiKey(this, "")
            }
        }
        val dlg = builder.show()
        dlg.window?.decorView?.post { com.orbital.iptv.utils.SEKeyboardController.showFocused(dlg.window!!.decorView) }
    }

    private fun showTmdbKeyDialog() {
        val current = PrefsManager.getTmdbApiKey(this) ?: ""
        val et = com.orbital.iptv.utils.SEKeyboardController.prepare(android.widget.EditText(this).apply {
            setText(current)
            hint = "PASTE API KEY HERE"
            setPadding(48, 24, 48, 24)
        })
        val builder = androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("TMDB API KEY")
            .setMessage("Get a free key at themoviedb.org → Settings → API. Used for EPG posters/synopsis.")
            .setView(et)
            .setPositiveButton("SAVE") { _, _ ->
                val key = et.text.toString().trim()
                if (key.isNotBlank()) PrefsManager.setTmdbApiKey(this, key)
            }
            .setNegativeButton("CANCEL", null)
        if (current.isNotBlank()) {
            builder.setNeutralButton("REMOVE KEY") { _, _ ->
                PrefsManager.setTmdbApiKey(this, "")
            }
        }
        val dlg = builder.show()
        dlg.window?.decorView?.post { com.orbital.iptv.utils.SEKeyboardController.showFocused(dlg.window!!.decorView) }
    }

    private fun showServerManager() {
        val profiles = PrefsManager.getProfiles(this)
        val activeId = PrefsManager.getActiveProfileId(this)

        val labels = profiles.map { p ->
            "${if (p.id == activeId) "●" else "○"}  ${p.name.uppercase()}  —  ${p.serverUrl}"
        }.toMutableList<String>()
        labels.add("＋  ADD NEW SERVER")
        labels.add("✕  REMOVE A SERVER")

        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("SERVERS")
            .setItems(labels.toTypedArray()) { _, which ->
                when (which) {
                    profiles.size -> {
                        val intent = Intent(this, LoginActivity::class.java)
                        intent.putExtra("skip_auto", true)
                        startActivity(intent)
                        finish()
                    }
                    profiles.size + 1 -> showDeleteServerPicker(profiles, activeId)
                    else -> {
                        val selected = profiles[which]
                        if (selected.id != activeId) {
                            PrefsManager.setActiveProfile(this, selected.id)
                            PrefsManager.setUseOriginalCategories(this, false)
                            lifecycleScope.launch {
                                EpgCache.clearAll(this@HomeActivity)
                                ContentCache.clearAll(this@HomeActivity)
                                loadData()
                            }
                        }
                    }
                }
            }
            .show()
    }

    private fun showDeleteServerPicker(profiles: List<ServerProfile>, activeId: String?) {
        if (profiles.isEmpty()) return
        val labels = profiles.map { "✕  ${it.name.uppercase()}" }.toTypedArray()
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("REMOVE SERVER")
            .setItems(labels) { _, which ->
                val toDelete = profiles[which]
                androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
                    .setTitle("REMOVE ${toDelete.name.uppercase()}?")
                    .setMessage("THIS CANNOT BE UNDONE.")
                    .setPositiveButton("REMOVE") { _, _ ->
                        PrefsManager.deleteProfile(this, toDelete.id)
                        val remaining = PrefsManager.getProfiles(this)
                        if (remaining.isEmpty()) {
                            PrefsManager.clearCredentials(this)
                            finish()
                        } else if (toDelete.id == activeId) {
                            PrefsManager.setActiveProfile(this, remaining.first().id)
                            lifecycleScope.launch {
                                EpgCache.clearAll(this@HomeActivity)
                                ContentCache.clearAll(this@HomeActivity)
                                loadData()
                            }
                        }
                    }
                    .setNegativeButton("CANCEL", null)
                    .show()
            }
            .show()
    }

    private fun refreshServer() {
        val name = PrefsManager.getActiveProfile(this)?.name?.uppercase() ?: "SERVER"
        android.widget.Toast.makeText(this, "REFRESHING $name...", android.widget.Toast.LENGTH_SHORT).show()
        TvModeHolder.allChannels = emptyList()
        TvModeHolder.categories  = emptyList()
        viewModel.refreshServer()
    }

    private fun confirmClearAllData() {
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("CLEAR ALL SAVED DATA")
            .setMessage("This will remove all server profiles, favourites, and cached data. You will need to log in again. Are you sure?")
            .setPositiveButton("CLEAR ALL") { _, _ ->
                PrefsManager.clearCredentials(this)
                finish()
            }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun showLiveChannels(channels: List<LiveStream>) {
        currentChannels = channels
        liveAdapter.submitList(channels)
        val rv = binding.root.findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.rv_live_channels)
        if (!rv.hasFocus() && channels.isNotEmpty()) rv.requestFocus()
    }

    private fun applyTheme() {
        val p = ThemeManager.palette()
        // Status/nav bar colour is drawn by the system, not any View in this layout — it's set
        // via the static Theme.SE style (themes.xml) and never responds to the in-app
        // palette otherwise, which is why it kept showing the old blue behind the logo/status bar.
        window.statusBarColor = p.bgPrimary
        window.navigationBarColor = p.bgPrimary

        binding.root.setBackgroundColor(p.bgPrimary)
        binding.root.findViewById<View>(R.id.main_sidebar_container)?.setBackgroundColor(p.bgHeader)
        binding.root.findViewById<View>(R.id.view_vertical_divider)?.setBackgroundColor(p.accent)
        binding.root.findViewById<View>(R.id.view_live_accent)?.setBackgroundColor(p.accent)
        MainSidebarController.setup(
            this,
            binding.root,
            currentSection,
            onSettings = { startActivity(Intent(this, SettingsActivity::class.java)) },
            onHome = { showSection("HOME") },
            onLiveTv = { showSection("LIVE") }
        )
        binding.bottomStatusBar?.setBackgroundColor(p.bgPrimary)
        binding.tvStatusHint?.setTextColor(0xFF888888.toInt())
    }

    private fun observeViewModel() {
        viewModel.uiState.observe(this) { state ->
            binding.progressBar?.visibility = if (state.isLoading) View.VISIBLE else View.GONE

            state.error?.let { error ->
                binding.tvError?.text = error.uppercase()
                binding.tvError?.visibility = View.VISIBLE
            } ?: run {
                binding.tvError?.visibility = View.GONE
            }

            showLiveChannels(state.channels)
            binding.tvChannelCount?.text = "${state.channels.size} CHANNELS"

            setupCategoryMenu(state.xtreamCategories, state.selectedXtreamCategory)
        }
        viewModel.epgUpdate.observe(this) { streamId -> liveAdapter.notifyStreamChanged(streamId) }
    }

    private fun setupCategoryMenu(categories: List<LiveCategory>, selected: LiveCategory?) {
        val hiddenIds = CategoryPrefs.getHiddenServerCatIds(this)
        val visibleCategories = categories.filter { it.categoryId !in hiddenIds }
        val container = binding.originalCatContainer ?: return
        container.visibility = View.VISIBLE
        container.removeAllViews()

        val rowHeightPx = android.util.TypedValue.applyDimension(
            android.util.TypedValue.COMPLEX_UNIT_DIP, 38f, resources.displayMetrics
        ).toInt()
        val paddingPx = android.util.TypedValue.applyDimension(
            android.util.TypedValue.COMPLEX_UNIT_DIP, 12f, resources.displayMetrics
        ).toInt()
        val p = ThemeManager.palette()
        val density = resources.displayMetrics.density
        val marginPx = (p.itemMarginDp * density).toInt()

        fun addRow(label: String, selectedRow: Boolean = false, action: () -> Unit) {
            container.addView(TextView(this).apply {
                val lp = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT, rowHeightPx
                )
                if (marginPx > 0) lp.setMargins(marginPx, marginPx / 2, marginPx, marginPx / 2)
                layoutParams = lp
                gravity = Gravity.CENTER_VERTICAL
                setPadding(paddingPx, 0, 0, 0)
                text = label
                textSize = 12f
                typeface = Typeface.create("sans-serif-condensed", Typeface.NORMAL)
                isClickable = true; isFocusable = true
                nextFocusRightId = R.id.rv_live_channels
                background = ThemeManager.roundedBg(if (selectedRow) p.highlight else p.bgMid, density)
                setTextColor(if (selectedRow) 0xFF000000.toInt() else 0xFFFFFFFF.toInt())
                setOnFocusChangeListener { _, hasFocus -> if (!selectedRow) background = ThemeManager.focusRowDrawable(density, p.bgMid, hasFocus) }
                setOnClickListener { action() }
            })
        }

        addRow("SEARCH", liveSearchActive) { showLiveSearchDialog() }
        addRow("ALL", !liveSearchActive && selected == null) {
            liveSearchActive = false
            viewModel.selectAllChannels()
        }
        addRow("★  FAVOURITE", !liveSearchActive && selected?.categoryId == HomeViewModel.FAV_CATEGORY_ID) {
            liveSearchActive = false
            val ids = FavouritesManager.getLiveChannels(this@HomeActivity).map { it.streamId }.toSet()
            viewModel.selectFavouriteChannels(ids)
        }
        addRow("▶  CONTINUE WATCHING", !liveSearchActive && selected?.categoryId == HomeViewModel.CONTINUE_CATEGORY_ID) {
            liveSearchActive = false
            val ids = WatchHistoryManager.get(this@HomeActivity, "LIVE").map { it.streamId }
            viewModel.selectContinueChannels(ids)
        }

        val categoryRows = if (liveSearchActive) {
            visibleCategories.filter { it.categoryName.contains(liveSearchQuery, ignoreCase = true) }
        } else visibleCategories

        categoryRows.forEachIndexed { index, category ->
            val normalBg = if (index % 2 == 0) p.rowEven else p.rowOdd
            val isSelected = !liveSearchActive && category.categoryId == selected?.categoryId
            val row = LinearLayout(this).apply {
                val lp = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT, rowHeightPx
                )
                if (marginPx > 0) lp.setMargins(marginPx, marginPx / 2, marginPx, marginPx / 2)
                layoutParams = lp
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                layoutDirection = View.LAYOUT_DIRECTION_LTR
                tag = category.categoryId
                if (p.cardElevation > 0f) elevation = p.cardElevation * density
                isFocusable = false
            }
            val nameView = TextView(this).apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.MATCH_PARENT, 1f)
                gravity = Gravity.LEFT or Gravity.CENTER_VERTICAL
                setPadding(paddingPx, 0, 0, 0)
                layoutDirection = View.LAYOUT_DIRECTION_LTR
                textDirection = View.TEXT_DIRECTION_ANY_RTL
                text = category.categoryName
                textSize = 12f
                typeface = Typeface.create("sans-serif-condensed", Typeface.NORMAL)
                isClickable = true; isFocusable = true
            }
            val heartView = TextView(this).apply {
                id = View.generateViewId()
                layoutParams = LinearLayout.LayoutParams((56 * density).toInt(), LinearLayout.LayoutParams.MATCH_PARENT)
                gravity = Gravity.CENTER
                setPadding(0, 0, paddingPx / 2, 0)
                textSize = 23f
                typeface = Typeface.DEFAULT
                isClickable = true; isFocusable = true
                nextFocusRightId = R.id.rv_live_channels
            }
            nameView.nextFocusRightId = heartView.id
            val profile = PrefsManager.getActiveProfile(this@HomeActivity)
            fun syncHeart() {
                val fav = profile?.let { FavouritesManager.containsCategory(this@HomeActivity, "LIVE", it.serverUrl, category.categoryId) } == true
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
                liveSearchActive = false
                if (PinManager.isCategoryLocked(this@HomeActivity, category.categoryId)) {
                    promptPin("ENTER PIN TO VIEW CATEGORY") { viewModel.selectXtreamCategory(category) }
                } else viewModel.selectXtreamCategory(category)
            }
            heartView.setOnClickListener {
                if (profile != null) {
                    FavouritesManager.toggleCategory(this@HomeActivity, "LIVE", category.categoryId, category.categoryName, profile.serverUrl, profile.id)
                    syncHeart()
                }
            }
            row.addView(nameView)
            row.addView(heartView)
            syncBackground()
            container.addView(row)
        }
    }

    private var liveSearchQuery: String = ""

    private fun showLiveSearchDialog() {
        val input = com.orbital.iptv.utils.SEKeyboardController.prepare(android.widget.EditText(this).apply {
            hint = "SEARCH CHANNEL OR CATEGORY"
            setSingleLine(true)
            requestFocus()
        })
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("SEARCH LIVE TV")
            .setView(input)
            .setPositiveButton("SEARCH") { _, _ ->
                val q = input.text.toString().trim()
                if (q.isBlank()) return@setPositiveButton
                liveSearchQuery = q
                liveSearchActive = true
                viewModel.searchChannelsAndCategories(q)
                val state = viewModel.uiState.value
                setupCategoryMenu(state?.xtreamCategories ?: emptyList(), state?.selectedXtreamCategory)
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }

    private fun toggleLiveFormat() {
        val current = PrefsManager.getLiveFormat(this)
        val next = if (current == "ts") "m3u8" else "ts"
        PrefsManager.setLiveFormat(this, next)
        ApiClient.liveFormat = next
        val label = if (next == "m3u8") "HLS (.m3u8) — try this if TS shows black screen" else "MPEG-TS (.ts) — standard format"
        android.widget.Toast.makeText(this, "LIVE FORMAT SET TO: $label", android.widget.Toast.LENGTH_LONG).show()
    }

    private fun toggleTvMode() {
        val enabled = !PrefsManager.isTvModeEnabled(this)
        PrefsManager.setTvModeEnabled(this, enabled)
        if (enabled) {
            startActivity(Intent(this, TvModeActivity::class.java))
        } else {
            android.widget.Toast.makeText(this, "TV MODE OFF", android.widget.Toast.LENGTH_SHORT).show()
        }
    }

    private fun loadData() {
        val credentials = PrefsManager.getCredentials(this) ?: run {
            finish()
            return
        }
        viewModel.loadData(credentials.serverUrl, credentials.username, credentials.password)
    }

    // ── EPG recording / reminder (mirrors EpgActivity) ────────────────────────

    private fun handleProgrammeTap(streamId: Int, channelName: String, url: String, listing: EpgListing) {
        val title   = listing.getDecodedTitle().ifBlank { "Recording" }
        val startMs = (listing.startTimestamp?.toLongOrNull() ?: 0L) * 1000L
        val endMs   = (listing.stopTimestamp?.toLongOrNull()  ?: 0L) * 1000L
        val nowMs   = System.currentTimeMillis()

        if (endMs > 0L && endMs <= nowMs) {
            AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
                .setTitle("CANNOT RECORD")
                .setMessage("'$title' has already finished.")
                .setPositiveButton("OK", null)
                .show()
            return
        }

        val timeFmt = SimpleDateFormat("HH:mm", Locale.UK)
        val dateFmt = SimpleDateFormat("EEE dd MMM", Locale.UK)
        val availGb = RecordingRepository.availableGb(this)
        val timeStr = if (startMs > 0L) {
            val dateStr = dateFmt.format(Date(startMs))
            val endStr  = if (endMs > 0L) timeFmt.format(Date(endMs)) else "?"
            "$dateStr  ${timeFmt.format(Date(startMs))} — $endStr"
        } else "Time unknown"
        val label = if (startMs > nowMs) "SCHEDULE RECORDING" else "RECORD NOW (ongoing)"

        // The EPG listing's own description is the authoritative synopsis for THIS airing —
        // available synchronously, no catalog guesswork needed. The VOD/series lookup below is
        // now only used to fill in a poster + a short genre/year/rating line, and as a plot
        // fallback for the (rare) case where the broadcaster's EPG feed sends no description.
        val epgSynopsis = listing.getDecodedDescription().trim()

        fun infoBody(catalogHeader: String?, catalogPlotFallback: String?) = listOfNotNull(
            title, "$channelName\n$timeStr",
            catalogHeader?.takeIf { it.isNotBlank() },
            epgSynopsis.ifBlank { catalogPlotFallback ?: "" }.takeIf { it.isNotBlank() },
            "Available storage: ${"%.1f".format(availGb)} GB"
        ).joinToString("\n\n")

        val (posterView, posterImg, infoTv) = buildProgrammeInfoView()
        infoTv.text = infoBody(null, null)

        val builder = AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle(label)
            .setView(posterView)
            .setPositiveButton("RECORD") { _, _ ->
                if (endMs > 0L) {
                    scheduleRecording(streamId, channelName, url, title, startMs.coerceAtLeast(nowMs), endMs)
                } else {
                    askForDuration { durationMs ->
                        scheduleRecording(streamId, channelName, url, title, startMs.coerceAtLeast(nowMs), startMs.coerceAtLeast(nowMs) + durationMs)
                    }
                }
            }
            .setNegativeButton("CANCEL", null)
        if (startMs > nowMs) {
            builder.setNeutralButton("SET REMINDER") { _, _ ->
                scheduleReminder(channelName, title, startMs, url, streamId)
            }
        }
        builder.show()

        // Best-effort VOD/series catalog lookup for a poster (+ genre/year/rating line) — never
        // blocks the dialog, since it depends on the movies/series cache already being warm on disk.
        val durationMinutes = if (startMs > 0L && endMs > startMs) (endMs - startMs) / 60_000L else -1L
        lifecycleScope.launch {
            val creds = PrefsManager.getCredentials(this@HomeActivity) ?: return@launch
            val match = lookupShowPoster(creds.serverUrl, creds.username, creds.password, title, epgSynopsis, durationMinutes)
                ?: return@launch
            match.posterUrl?.takeIf { it.isNotBlank() }?.let { Glide.with(this@HomeActivity).load(it).into(posterImg) }
            infoTv.text = infoBody(match.header, match.plot)
        }
    }

    private enum class ShowKind { MOVIE, SERIES, UNKNOWN }

    /**
     * Xtream's EPG data has no explicit movie/series flag, so infer it from the listing text and
     * runtime: season/episode markers ("S3 E12", "Series 3", "Ep 4/6") are the strongest, least
     * ambiguous signal and always mean SERIES; failing that, a "(YYYY)" year suffix or a runtime
     * over ~75 minutes leans MOVIE, and a short runtime leans SERIES. Used to search the more
     * likely catalog first (and skip a wasted VOD-info lookup when we're confident it's a series).
     */
    private fun classifyShowKind(title: String, description: String, durationMinutes: Long): ShowKind {
        val combined = "$title $description"
        val seriesPattern = Regex(
            """\bS\d{1,2}\s?[:\-]?\s?E\d{1,3}\b|\bSeries\s?\d+\b|\bSeason\s?\d+\b|\bEp(?:isode)?\.?\s?\d+(\s?/\s?\d+)?\b""",
            RegexOption.IGNORE_CASE
        )
        val moviePattern = Regex("""\(\d{4}\)""")

        return when {
            seriesPattern.containsMatchIn(combined) -> ShowKind.SERIES
            moviePattern.containsMatchIn(title) -> ShowKind.MOVIE
            durationMinutes >= 75 -> ShowKind.MOVIE
            durationMinutes in 1 until 70 -> ShowKind.SERIES
            else -> ShowKind.UNKNOWN
        }
    }

    private data class ShowPosterMatch(val posterUrl: String?, val header: String, val plot: String?)

    /** Builds the poster (left) + info text (right) row used inside the programme-tap dialog. */
    private fun buildProgrammeInfoView(): Triple<View, ImageView, TextView> {
        val d = resources.displayMetrics.density
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding((4 * d).toInt(), (4 * d).toInt(), (4 * d).toInt(), (4 * d).toInt())
        }
        val poster = ImageView(this).apply {
            layoutParams = LinearLayout.LayoutParams((90 * d).toInt(), (128 * d).toInt())
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(0xFF0A1628.toInt())
        }
        val infoTv = TextView(this).apply {
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
                marginStart = (12 * d).toInt()
            }
            setTextColor(0xFFCCDDEE.toInt())
            textSize = 12f
            typeface = Typeface.create("sans-serif-condensed", Typeface.NORMAL)
        }
        root.addView(poster)
        root.addView(infoTv)
        return Triple(root, poster, infoTv)
    }

    /**
     * Matches a live-TV programme title against TMDB (if an API key is set) or, failing that,
     * the cached VOD/series catalogs, to find a poster + synopsis.
     */
    private suspend fun lookupShowPoster(
        serverUrl: String, username: String, password: String,
        title: String, description: String, durationMinutes: Long
    ): ShowPosterMatch? = withContext(Dispatchers.IO) {
        val query = title.trim()
        if (query.isBlank()) return@withContext null
        val kind = classifyShowKind(title, description, durationMinutes)

        val tmdbKey = PrefsManager.getTmdbApiKey(this@HomeActivity)
        if (tmdbKey != null) {
            val preferType = when (kind) {
                ShowKind.MOVIE  -> "movie"
                ShowKind.SERIES -> "tv"
                ShowKind.UNKNOWN -> null
            }
            val candidates = com.orbital.iptv.data.tmdb.TmdbRepository.search(tmdbKey, query, preferType)
            val tmdb = candidates.firstOrNull { isGoodTitleMatch(query, it.title) }
            if (tmdb != null) {
                val header = listOfNotNull(
                    tmdb.year,
                    tmdb.voteAverage?.let { "★ %.1f".format(it) }
                ).joinToString("  •  ")
                return@withContext ShowPosterMatch(tmdb.posterUrl, header, tmdb.overview)
            }
        }

        fun header(genre: String?, releaseDate: String?, rating: String?): String = listOfNotNull(
            genre?.takeIf { it.isNotBlank() },
            releaseDate?.takeIf { it.isNotBlank() },
            rating?.takeIf { it.isNotBlank() && it != "0" }?.let { "★ $it" }
        ).joinToString("  •  ")

        suspend fun trySeries(): ShowPosterMatch? {
            val matches = ContentCache.searchSeries(this@HomeActivity, serverUrl, query)
            val series = matches.firstOrNull { isGoodTitleMatch(query, it.name) } ?: return null
            return ShowPosterMatch(series.cover, header(series.genre, series.releaseDate, series.rating), series.plot)
        }

        suspend fun tryMovie(): ShowPosterMatch? {
            val matches = ContentCache.searchMovies(this@HomeActivity, serverUrl, query)
            val movie = matches.firstOrNull { isGoodTitleMatch(query, it.name) } ?: return null
            val info = repository.getVodInfo(serverUrl, username, password, movie.streamId).getOrNull()?.info
            val poster = info?.coverBig?.takeIf { it.isNotBlank() }
                ?: info?.movieImage?.takeIf { it.isNotBlank() }
                ?: movie.streamIcon
            val plot = info?.plot?.takeIf { it.isNotBlank() } ?: info?.description
            return ShowPosterMatch(poster, header(info?.genre, info?.releaseDate, info?.rating ?: movie.rating), plot)
        }

        when (kind) {
            ShowKind.MOVIE  -> tryMovie() ?: trySeries()
            ShowKind.SERIES -> trySeries() ?: tryMovie()
            ShowKind.UNKNOWN -> trySeries() ?: tryMovie()
        }
    }

    private fun normalizeTitle(s: String): String = s.lowercase()
        .replace(Regex("\\(\\d{4}\\)"), "")                              // "(2023)"
        .replace(Regex("s\\d{1,2}\\s?e\\d{1,3}", RegexOption.IGNORE_CASE), "")  // "S01E02"
        .replace(Regex("[^a-z0-9 ]"), " ")
        .replace(Regex("\\s+"), " ")
        .trim()

    /**
     * Requires an exact match after normalising noise (years, S01E02, punctuation) — no partial
     * or prefix matching. A word-boundary prefix rule was tried first but is unsafe for TV
     * titles: "Hacks" ⊂ "Hacksaw Ridge" (no boundary — already excluded) is one failure mode, but
     * "Prisoner" ⊂ "Prisoner: Cell Block H" (a genuinely different, unrelated show) DOES land on
     * a word boundary and was a real false-positive match. Titles are short enough, and wrong
     * posters bad enough, that only an exact match is worth showing.
     */
    private fun isGoodTitleMatch(epgTitle: String, candidateName: String): Boolean {
        val a = normalizeTitle(epgTitle)
        val b = normalizeTitle(candidateName)
        return a.isNotBlank() && a == b
    }

    private fun scheduleReminder(channelName: String, title: String, startMs: Long, streamUrl: String, streamId: Int) {
        val delayMs = (startMs - System.currentTimeMillis()).coerceAtLeast(0L)
        val data = Data.Builder()
            .putString(ReminderWorker.KEY_TITLE,      title)
            .putString(ReminderWorker.KEY_CHANNEL,    channelName)
            .putString(ReminderWorker.KEY_STREAM_URL, streamUrl)
            .putInt(ReminderWorker.KEY_STREAM_ID,     streamId)
            .build()
        WorkManager.getInstance(this).enqueue(
            OneTimeWorkRequestBuilder<ReminderWorker>()
                .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
                .setInputData(data)
                .addTag("reminder_${title.hashCode()}")
                .build()
        )
        val timeStr = SimpleDateFormat("HH:mm", Locale.UK).format(Date(startMs))
        Toast.makeText(this, "REMINDER SET: $title at $timeStr", Toast.LENGTH_SHORT).show()
    }

    private fun askForDuration(onChosen: (Long) -> Unit) {
        val options   = arrayOf("30 minutes", "1 hour", "1 hour 30 min", "2 hours", "3 hours")
        val durations = longArrayOf(30, 60, 90, 120, 180)
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("RECORDING DURATION")
            .setMessage("No end time found in EPG. How long should we record?")
            .setItems(options) { _, i -> onChosen(durations[i] * 60_000L) }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun scheduleRecording(streamId: Int, channelName: String, url: String, title: String, startMs: Long, endMs: Long) {
        lifecycleScope.launch(kotlinx.coroutines.Dispatchers.IO) {
            try {
                val recording = RecordingEntity(
                    channelName    = channelName,
                    channelUrl     = url,
                    streamId       = streamId,
                    epgTitle       = title,
                    scheduledStart = startMs,
                    scheduledEnd   = endMs,
                    status         = RecordingStatus.SCHEDULED
                )
                val id = RecordingDatabase.get(this@HomeActivity).dao().insert(recording).toInt()
                val delayMs = startMs - System.currentTimeMillis()
                if (delayMs <= 0L) {
                    androidx.core.content.ContextCompat.startForegroundService(
                        this@HomeActivity,
                        Intent(this@HomeActivity, RecordingService::class.java).apply {
                            putExtra(RecordingService.EXTRA_RECORDING_ID, id)
                        }
                    )
                } else {
                    WorkManager.getInstance(this@HomeActivity).enqueue(
                        OneTimeWorkRequestBuilder<RecordingWorker>()
                            .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
                            .setInputData(workDataOf("recording_id" to id))
                            .addTag("rec_$id")
                            .build()
                    )
                }
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                    Toast.makeText(this@HomeActivity, "RECORDING SCHEDULED: $title", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                    Toast.makeText(this@HomeActivity, "SCHEDULE FAILED: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun onChannelLongPressed(stream: LiveStream) {
        val inFavourites = viewModel.uiState.value?.selectedXtreamCategory?.categoryId == HomeViewModel.FAV_CATEGORY_ID
        if (inFavourites) {
            androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
                .setTitle(stream.name.uppercase())
                .setItems(arrayOf("REMOVE FROM FAVOURITES", "CANCEL")) { _, which ->
                    if (which == 0) {
                        FavouritesManager.removeLive(this, stream.streamId)
                        val ids = FavouritesManager.getLiveChannels(this).map { it.streamId }.toSet()
                        val recentIds = com.orbital.iptv.utils.RecentChannelsManager.getAll(this).map { it.streamId }
                        viewModel.selectFavouriteChannels(ids, recentIds)
                    }
                }
                .show()
        } else {
            val streamUrl = viewModel.buildStreamUrl(stream.streamId)
            FavouritesManager.addLiveChannel(this, stream.name, stream.streamId, streamUrl, stream.streamIcon)
            android.widget.Toast.makeText(this, "ADDED TO FAVOURITES", android.widget.Toast.LENGTH_SHORT).show()
        }
    }

    private fun onChannelSelected(stream: LiveStream) {
        val url=viewModel.buildStreamUrl(stream.streamId)
        if (binding.miniPlayer.player==null) return
        binding.miniPlayer.player?.setMediaItem(MediaItem.fromUri(url)); binding.miniPlayer.player?.prepare(); binding.miniPlayer.player?.play()
        binding.miniPlayer.setOnClickListener { launchChannel(stream) }
        // First tap previews in the small screen; second tap on the same channel opens full player.
        if (lastPreviewStreamId == stream.streamId) launchChannel(stream) else lastPreviewStreamId=stream.streamId
    }

    private var lastPreviewStreamId=-1


    private fun launchChannel(stream: LiveStream) {
        miniPlayer?.stop()
        miniPlayer?.clearMediaItems()
        // Keep the Preview Player attached. Detaching it here made the first
        // tap work, but every later channel tap returned immediately because
        // onChannelSelected() saw a null PlayerView.player after coming back.
        if (binding.miniPlayer.player == null && miniPlayer != null) binding.miniPlayer.player = miniPlayer
        lastPreviewStreamId = -1
        if (PrefsManager.isTvModeEnabled(this)) {
            val streamUrl = viewModel.buildStreamUrl(stream.streamId)
            val catId = viewModel.uiState.value?.selectedXtreamCategory?.categoryId
                ?.takeIf { it != HomeViewModel.FAV_CATEGORY_ID } ?: ""
            TvModeHolder.allChannels = viewModel.getAllStreams()
            TvModeHolder.categories  = viewModel.uiState.value?.xtreamCategories ?: emptyList()
            PrefsManager.setLastTvChannel(this, streamUrl, stream.name, stream.streamId, catId)
            com.orbital.iptv.utils.RecentChannelsManager.record(this, stream.name, stream.streamId, streamUrl, stream.streamIcon)
            startActivity(Intent(this, TvModeActivity::class.java).apply {
                putExtra(TvModeActivity.EXTRA_STREAM_URL,   streamUrl)
                putExtra(TvModeActivity.EXTRA_CHANNEL_NAME, stream.name)
                putExtra(TvModeActivity.EXTRA_STREAM_ID,    stream.streamId)
                putExtra(TvModeActivity.EXTRA_CATEGORY_ID,  catId)
            })
            return
        }

        val channels = viewModel.uiState.value?.channels ?: emptyList()
        ChannelQueue.entries = channels.map { ch ->
            ChannelQueue.Entry(streamId = ch.streamId, name = ch.name, num = ch.num ?: -1)
        }
        ChannelQueue.currentIndex = channels.indexOf(stream).coerceAtLeast(0)

        val streamUrl = viewModel.buildStreamUrl(stream.streamId)
        com.orbital.iptv.utils.RecentChannelsManager.record(this, stream.name, stream.streamId, streamUrl, stream.streamIcon)
        val intent = Intent(this, PlayerActivity::class.java).apply {
            putExtra(PlayerActivity.EXTRA_STREAM_URL, streamUrl)
            putExtra(PlayerActivity.EXTRA_CHANNEL_NAME, stream.name)
            putExtra(PlayerActivity.EXTRA_STREAM_ID, stream.streamId)
            putExtra(PlayerActivity.EXTRA_IS_LIVE, true)
            stream.num?.let { putExtra(PlayerActivity.EXTRA_CHANNEL_NUM, it) }
        }
        startActivity(intent)
    }

    // ── PIN helpers ───────────────────────────────────────────────────────────

    private fun pinEditText(hint: String) = com.orbital.iptv.utils.SEKeyboardController.prepare(android.widget.EditText(this).apply {
        inputType = android.text.InputType.TYPE_CLASS_NUMBER or
                    android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD
        filters = arrayOf(android.text.InputFilter.LengthFilter(4))
        this.hint = hint
        gravity = android.view.Gravity.CENTER
        textSize = 22f
        setPadding(48, 32, 48, 16)
    })

    private fun promptPin(title: String, onCorrect: () -> Unit) {
        val et = pinEditText("ENTER PIN")
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle(title)
            .setView(et)
            .setPositiveButton("OK") { _, _ ->
                if (et.text.toString() == PinManager.getPin(this)) onCorrect()
                else Toast.makeText(this, "INCORRECT PIN", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }

    private fun showPinProtectedCategories() {
        promptPin("ENTER PIN TO MANAGE LOCKED CATEGORIES") { showLockedCategoryPicker() }
    }

    private fun showLockedCategoryPicker() {
        val categories = viewModel.uiState.value?.xtreamCategories ?: emptyList()
        if (categories.isEmpty()) {
            Toast.makeText(this, "NO CATEGORIES LOADED", Toast.LENGTH_SHORT).show()
            return
        }
        val lockedIds = PinManager.getLockedCategoryIds(this).toMutableSet()
        val labels  = categories.map { it.categoryName.uppercase() }.toTypedArray()
        val checked = categories.map { it.categoryId in lockedIds }.toBooleanArray()
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("PIN PROTECTED CATEGORIES")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked ->
                if (isChecked) lockedIds.add(categories[which].categoryId)
                else           lockedIds.remove(categories[which].categoryId)
            }
            .setPositiveButton("SAVE") { _, _ ->
                PinManager.setLockedCategoryIds(this, lockedIds)
                Toast.makeText(this, "SAVED", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun showChangePinDialog() {
        promptPin("ENTER CURRENT PIN") { promptNewPin() }
    }

    private fun promptNewPin() {
        val et = pinEditText("ENTER NEW PIN")
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("ENTER NEW PIN")
            .setView(et)
            .setPositiveButton("NEXT") { _, _ ->
                val pin = et.text.toString()
                if (pin.length == 4) confirmNewPin(pin)
                else Toast.makeText(this, "PIN MUST BE 4 DIGITS", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }

    private fun confirmNewPin(newPin: String) {
        val et = pinEditText("CONFIRM NEW PIN")
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("CONFIRM NEW PIN")
            .setView(et)
            .setPositiveButton("SAVE") { _, _ ->
                if (et.text.toString() == newPin) {
                    PinManager.setPin(this, newPin)
                    Toast.makeText(this, "PIN CHANGED", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(this, "PINS DO NOT MATCH", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("CANCEL", null)
            .create().also { dlg ->
                dlg.setOnShowListener { dlg.window?.decorView?.let { root -> com.orbital.iptv.utils.SEKeyboardController.showFocused(root) } }
                dlg.show()
            }
    }
}