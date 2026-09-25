package com.orbital.iptv.ui.tv

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.app.PictureInPictureParams
import android.util.Rational
import android.graphics.Typeface
import android.text.TextUtils
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.animation.LinearInterpolator
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import com.bumptech.glide.Glide
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.MediaSession
import androidx.media3.cast.CastPlayer
import androidx.media3.cast.MediaRouteButtonFactory
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.orbital.iptv.ui.player.PcmOnlyRenderersFactory
import com.orbital.iptv.R
import com.orbital.iptv.data.api.ApiClient
import com.orbital.iptv.data.model.EpgListing
import com.orbital.iptv.data.model.LiveCategory
import com.orbital.iptv.data.model.LiveStream
import com.orbital.iptv.data.model.ServerProfile
import com.orbital.iptv.data.model.getDecodedTitle
import com.orbital.iptv.data.model.getDecodedDescription
import com.orbital.iptv.data.repository.XtreamRepository
import com.orbital.iptv.utils.CategoryPrefs
import com.orbital.iptv.utils.ContentCache
import com.orbital.iptv.utils.EpgCache
import com.orbital.iptv.databinding.ActivityTvModeBinding
import com.orbital.iptv.recording.RecordingService
import com.orbital.iptv.recording.RecordingState
import com.orbital.iptv.ui.catchup.CatchupActivity
import com.orbital.iptv.ui.favourites.FavouritesActivity
import com.orbital.iptv.ui.emby.EmbyBrowserActivity
import com.orbital.iptv.ui.emby.EmbyLoginActivity
import com.orbital.iptv.ui.epg.EpgRow
import com.orbital.iptv.ui.games.BubbleShooterActivity
import com.orbital.iptv.ui.games.TeletextActivity
import com.orbital.iptv.ui.home.HomeActivity
import com.orbital.iptv.ui.login.LoginActivity
import com.orbital.iptv.ui.radio.RadioStations
import com.orbital.iptv.ui.plex.PlexBrowserActivity
import com.orbital.iptv.ui.plex.PlexLoginActivity
import com.orbital.iptv.utils.EmbyPrefsManager
import com.orbital.iptv.utils.GoalFlashManager
import com.orbital.iptv.utils.PlexPrefsManager
import com.orbital.iptv.ui.player.PlayerActivity
import com.orbital.iptv.ui.series.SeriesActivity
import com.orbital.iptv.ui.sports.SportsActivity
import com.orbital.iptv.ui.vod.VodActivity
import com.orbital.iptv.utils.FavouritesManager
import com.orbital.iptv.utils.PinManager
import com.orbital.iptv.utils.PrefsManager
import com.orbital.iptv.utils.ThemeManager
import com.orbital.iptv.utils.TickerManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.concurrent.TimeUnit

/** Static holder so the channel/category lists survive intent navigation. */
object TvModeHolder {
    var serverUrl: String = ""
    var allChannels: List<LiveStream> = emptyList()
    var categories: List<LiveCategory> = emptyList()

    fun invalidateIfServerChanged(url: String) {
        if (url != serverUrl) {
            serverUrl = url
            allChannels = emptyList()
            categories = emptyList()
        }
    }
}

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
class TvModeActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_STREAM_URL   = "tv_stream_url"
        const val EXTRA_CHANNEL_NAME = "tv_channel_name"
        const val EXTRA_STREAM_ID    = "tv_stream_id"
        const val EXTRA_CATEGORY_ID  = "tv_category_id"
        private const val FAV_CATEGORY_ID = "__favourites__"

        // Fires a sample Goal Flash card for previewing the feature, e.g.:
        // adb shell am broadcast -a com.orbital.iptv.DEBUG_GOAL_FLASH [--ez disallowed true]
        const val ACTION_DEBUG_GOAL_FLASH = "com.orbital.iptv.DEBUG_GOAL_FLASH"
    }

    // Three-level left-panel navigation.
    // NONE      – full-screen TV, no panel visible
    // CHANNELS  – channel list + live EPG column for focused channel
    // CATEGORIES– category picker
    // MAIN_MENU – top-level menu (Live TV / Box Office / Radio / Interactive / Settings)
    private enum class PanelState { NONE, CHANNELS, CATEGORIES, MAIN_MENU }

    private lateinit var binding: ActivityTvModeBinding
    private var player: Player? = null
    private var localPlayer: ExoPlayer? = null
    private var castPlayer: CastPlayer? = null
    private var mediaSession: MediaSession? = null
    private var enteringPip = false
    private var panelState = PanelState.NONE
    private var activeDialog: AlertDialog? = null

    private var currentStreamUrl   = ""
    private var currentChannelName = ""
    private var currentStreamId    = -1
    private var currentCategoryId  = ""
    private var categoryChannels: List<LiveStream> = emptyList()

    private var epgLoadingJob: Job? = null
    private var channelPanelAdapter: NowNextAdapter? = null
    private var focusedChannelStreamId = -1
    private var inlineEpgCurrentIdx = 0
    private val inlineEpgHandler = Handler(Looper.getMainLooper())

    // Previous channel — for RIGHT-key "last channel" toggle
    private var prevStreamId    = -1
    private var prevStreamUrl   = ""
    private var prevChannelName = ""
    private var prevCategoryId  = ""

    // Full EPG guide overlay
    private var guideCategoryId = ""
    private var guideLoadJob: Job? = null

    private val hudHandler  = Handler(Looper.getMainLooper())
    private val hideHud     = Runnable { hideHudOverlay() }
    private val zapHandler  = Handler(Looper.getMainLooper())
    private val hideZap     = Runnable { hideZapBar() }
    private val repository  = XtreamRepository()
    private var isRecording = false

    private val tickerHttp = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS).readTimeout(8, TimeUnit.SECONDS).build()
    private val tickerHandler = Handler(Looper.getMainLooper())
    private val newsHandler   = Handler(Looper.getMainLooper())
    private val goalFlashHandler = Handler(Looper.getMainLooper())
    private var pendingTickerText: String? = null
    private var tickerScrollAnim: ValueAnimator? = null
    private var tickerShowingPlaceholder = false

    private val debugGoalFlashReceiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(context: android.content.Context?, intent: Intent?) {
            val sample = GoalFlashManager.debugSample(intent)
            binding.goalFlashOverlay.addFlash(sample, GoalFlashManager.DURATION_SECONDS.toLong() * 1000L)
        }
    }

    private val tickerRunnable = object : Runnable {
        override fun run() {
            fetchTickerScores()
            val hasLive = TickerManager.liveScores.any { it.state == "in" }
            tickerHandler.postDelayed(this, if (hasLive) 30_000L else 60_000L)
        }
    }
    private val newsRunnable = object : Runnable {
        override fun run() {
            fetchNewsHeadlines()
            newsHandler.postDelayed(this, 300_000L)
        }
    }
    private val goalFlashRunnable = object : Runnable {
        override fun run() {
            val self = this
            lifecycleScope.launch {
                GoalFlashManager.poll(this@TvModeActivity)
                goalFlashHandler.postDelayed(self, if (GoalFlashManager.hasLiveGames) 25_000L else 90_000L)
            }
        }
    }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        // Load before inflating — EpgView (in guide_overlay) reads ThemeManager.palette() once
        // in its constructor, so a cold start would otherwise bake in the default SE
        // palette regardless of the user's saved theme (see HomeActivity.onCreate for the same fix).
        ThemeManager.load(this)
        binding = ActivityTvModeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnHudScores.visibility = View.GONE
        binding.btnHudNews.visibility = View.GONE
        binding.btnHudGoalFlash.visibility = View.GONE
        binding.tickerRow.visibility = View.GONE
        binding.newsTickerRow.visibility = View.GONE
        binding.goalFlashOverlay.visibility = View.GONE
        // A raw SurfaceView renders to its own independent hardware surface punched through the
        // window as a "hole", separate from the normal view hierarchy. On some (especially
        // lower-end/TV-box) GPU compositors, overlays animated on top of it — like Goal Flash's
        // slide-in cards — can partially/incorrectly composite. This tells the surface to
        // composite reliably above the window background instead of via the hole-punch path, and
        // must be set before the surface is created.
        binding.surfaceView.setZOrderMediaOverlay(true)
        applyTvTheme()

        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )

        currentStreamUrl   = intent.getStringExtra(EXTRA_STREAM_URL)   ?: PrefsManager.getLastTvChannelUrl(this) ?: ""
        currentChannelName = intent.getStringExtra(EXTRA_CHANNEL_NAME) ?: PrefsManager.getLastTvChannelName(this) ?: ""
        currentStreamId    = intent.getIntExtra(EXTRA_STREAM_ID, -1).takeIf { it >= 0 } ?: PrefsManager.getLastTvStreamId(this)
        currentCategoryId  = intent.getStringExtra(EXTRA_CATEGORY_ID)  ?: PrefsManager.getLastTvCategoryId(this)

        initPlayer()
        setupButtons()
        setupHudButtons()
        updateScoresButton()
        if (TickerManager.tickerEnabled) startTicker()
        updateNewsButton()
        if (TickerManager.newsTickerEnabled) startNewsTicker()
        if (GoalFlashManager.enabled) startGoalFlash()

        TvModeHolder.invalidateIfServerChanged(
            PrefsManager.getCredentials(this)?.serverUrl ?: ""
        )
        if (TvModeHolder.allChannels.isEmpty()) loadChannelsInBackground()
        else refreshCategoryChannels()
    }

    private fun initPlayer() {
        val httpFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .setAllowCrossProtocolRedirects(true)
        val exo = ExoPlayer.Builder(this)
            .setRenderersFactory(
                PcmOnlyRenderersFactory(this, PrefsManager.isSurroundEnabled(this))
                    .setEnableDecoderFallback(true)
                    .setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_PREFER)
            )
            .setMediaSourceFactory(DefaultMediaSourceFactory(httpFactory))
            .build()
        localPlayer = exo
        exo.trackSelectionParameters = exo.trackSelectionParameters.buildUpon()
            .setPreferredAudioMimeTypes(MimeTypes.AUDIO_AAC, MimeTypes.AUDIO_E_AC3, MimeTypes.AUDIO_AC3)
            .build()
        exo.repeatMode = Player.REPEAT_MODE_OFF
        exo.setVideoSurfaceView(binding.surfaceView)

        player = try {
            CastPlayer.Builder(this)
                .setLocalPlayer(exo)
                .build().also { castPlayer = it }
        } catch (_: Exception) {
            exo
        }
        mediaSession?.release()
        mediaSession = MediaSession.Builder(this, exo).build()
        if (currentStreamUrl.isNotBlank()) {
            player?.setMediaItem(MediaItem.fromUri(currentStreamUrl))
            player?.prepare()
            player?.play()
            updateChannelInfo(currentChannelName)
            loadEpgForCurrentChannel()
        }
    }

    /** Toggles PcmOnlyRenderersFactory's stereo-only lock — see its doc comment for the tradeoff. */
    private fun toggleSurroundSound() {
        if (!hasSurroundAudioTrack()) {
            Toast.makeText(this, "NO 5.1/SURROUND AUDIO TRACK ON THIS CHANNEL", Toast.LENGTH_SHORT).show()
            return
        }
        val newState = !PrefsManager.isSurroundEnabled(this)
        PrefsManager.setSurroundEnabled(this, newState)
        updateSurroundButton()
        // RenderersFactory is baked in at ExoPlayer construction, so the only way to apply the
        // new capability setting is to release and rebuild the player against the same channel.
        // initPlayer() reattaches via exo.setVideoSurfaceView(), which (unlike a hand-rolled
        // SurfaceHolder.Callback — see PlayerActivity.initExoPlayer()) attaches immediately when
        // the surface is already valid, so no extra surface handling is needed here.
        localPlayer?.clearVideoSurface()
        player?.release()
        if (castPlayer == null) localPlayer?.release()
        player = null
        castPlayer = null
        localPlayer = null
        initPlayer()
        Toast.makeText(
            this,
            if (newState) "SURROUND: ON — testing real device audio capabilities" else "SURROUND: OFF — forced stereo",
            Toast.LENGTH_SHORT
        ).show()
    }

    private fun updateSurroundButton() {
        val on = PrefsManager.isSurroundEnabled(this)
        binding.btnHudSurround.text = if (on) "5.1 ✓" else "5.1"
        val available = hasSurroundAudioTrack()
        binding.btnHudSurround.isEnabled = available
        binding.btnHudSurround.visibility = if (available) View.VISIBLE else View.GONE
    }

    /**
     * True if the audio track actually SELECTED for playback right now is 5.1/7.1+ (channel
     * count) or explicitly labelled surround — not just any track the stream happens to offer.
     * Many IPTV channels bundle a stereo AAC track alongside a 5.1 AC3 alternate, and
     * setPreferredAudioMimeTypes() picks AAC first, so checking "any available track" let the
     * button light up even while a plain stereo track was the one actually playing.
     */
    private fun hasSurroundAudioTrack(): Boolean {
        val exo = player ?: return false
        return exo.currentTracks.groups.any { group ->
            group.type == C.TRACK_TYPE_AUDIO && (0 until group.length).any { i ->
                group.isTrackSelected(i) && run {
                    val fmt = group.getTrackFormat(i)
                    fmt.channelCount >= 6 ||
                        fmt.label?.contains("5.1", ignoreCase = true) == true ||
                        fmt.label?.contains("surround", ignoreCase = true) == true
                }
            }
        }
    }

    private fun playChannel(url: String, name: String) {
        val exo = player ?: return
        switchStream(exo, url)
        showInfoBar(name)
        loadEpgForCurrentChannel()
        recordRecentChannel(currentStreamId, name, url)
    }

    /** Radio (currentStreamId == -1) is deliberately excluded — "recently watched" means live TV. */
    private fun recordRecentChannel(streamId: Int, name: String, url: String) {
        if (streamId < 0) return
        val icon = TvModeHolder.allChannels.find { it.streamId == streamId }?.streamIcon
        com.orbital.iptv.utils.RecentChannelsManager.record(this, name, streamId, url, icon)
    }

    /**
     * Fully tears down the current playlist/decoders before loading [url]. A seamless
     * setMediaItem() while playing can leave the video renderer holding its last decoded
     * frame (stale picture) while the audio renderer moves on to the new stream — stop()
     * alone doesn't release decoders, so clearMediaItems() is required to force ExoPlayer
     * to rebuild fresh MediaCodec instances on the next prepare().
     */
    private fun switchStream(exo: Player, url: String) {
        exo.stop()
        exo.clearMediaItems()
        exo.setMediaItem(MediaItem.fromUri(url))
        exo.prepare()
        exo.play()
    }

    /**
     * Recolours every static chrome view (panels, HUD, tickers) from the current
     * [ThemeManager] palette. These were originally hardcoded to a fixed dark-blue XML
     * colour, so switching themes (e.g. to BLACK & WHITE) had no visible effect on them.
     * Called once from onCreate — a theme change always goes through showThemePicker()'s
     * recreate(), so onCreate (and this) reruns with the freshly-selected palette.
     */
    /** 0 (fully opaque) – 255 (fully see-through), derived from the TRANSPARENCY setting. */
    private fun panelAlpha(): Int = 255 - (PrefsManager.getTvPanelTransparency(this) * 255 / 100)

    private fun applyTvTheme() {
        val p = ThemeManager.palette()
        val density = resources.displayMetrics.density

        // System-drawn, not a View — normally hidden by the immersive flags below, but still
        // worth matching in case it flashes during a system-UI transition.
        window.statusBarColor = p.bgPrimary
        window.navigationBarColor = p.bgPrimary

        binding.leftPanel.setBackgroundColor(ThemeManager.withAlpha(p.bgHeader, panelAlpha()))
        binding.panelHeader.setBackgroundColor(p.bgHeader)
        binding.panelHeader.setTextColor(p.accent)
        binding.dividerPanelHeader.setBackgroundColor(p.accent)
        binding.dividerChannelsSplit.setBackgroundColor(p.accent)
        val menuDividerColor = ThemeManager.withAlpha(p.accent, 0x40)
        listOf(
            binding.dividerMenu1, binding.dividerMenu2, binding.dividerMenu3,
            binding.dividerMenu4, binding.dividerMenu5
        ).forEach { it.setBackgroundColor(menuDividerColor) }

        binding.guideOverlay.setBackgroundColor(p.bgPrimary)
        binding.guideHeader.setBackgroundColor(p.bgHeader)
        binding.guideHeader.setTextColor(p.accent)
        binding.dividerGuideHeader.setBackgroundColor(p.accent)
        binding.dividerGuideSplit.setBackgroundColor(p.accent)

        binding.hudTop.setBackgroundColor(ThemeManager.withAlpha(p.bgHeader, panelAlpha()))
        binding.tvChannelName.setTextColor(p.accent)
        binding.btnHudMenu.background = ThemeManager.hudButtonDrawable(density)
        listOf(binding.btnHudAudio, binding.btnHudSurround, binding.btnHudScores, binding.btnHudNews).forEach {
            it.background = ThemeManager.hudButtonDrawable(density)
        }

        binding.hudBottom.setBackgroundColor(p.bgHeader)
        binding.dividerHudBottom.setBackgroundColor(p.accent)
        binding.rowHudChannelInfo.setBackgroundColor(p.bgPrimary)
        binding.rowHudNow.setBackgroundColor(p.bgMid)
        binding.labelHudNow.setTextColor(p.accent)
        binding.liveNextRow.setBackgroundColor(p.bgPrimary)
        binding.tvEpgNextTime.setTextColor(p.accent)

        binding.newsTickerRow.setBackgroundColor(ThemeManager.withAlpha(p.bgPrimary, panelAlpha()))
        binding.tickerRow.setBackgroundColor(ThemeManager.withAlpha(p.bgPrimary, panelAlpha()))
        binding.tvTicker.setTextColor(p.accent)
        binding.tvNewsTicker.textColor = p.accent
    }

    private fun setupButtons() {
        val p = ThemeManager.palette()
        val density = resources.displayMetrics.density
        binding.surfaceView.setOnClickListener { showHudOverlay() }

        fun menuItem(view: android.widget.TextView, bg: Int, action: () -> Unit) {
            val bgA = ThemeManager.withAlpha(bg, panelAlpha())
            view.tag = bgA
            view.background = ThemeManager.menuRowDrawable(density, bgA, focused = false)
            view.setOnClickListener { action() }
            view.setOnFocusChangeListener { _, hasFocus ->
                view.background = ThemeManager.menuRowDrawable(
                    density, if (hasFocus) p.focus else bgA, focused = hasFocus
                )
            }
        }

        menuItem(binding.menuItemLiveTv, p.rowEven)      { hidePanel() }
        menuItem(binding.menuItemGuide, p.rowOdd)        { showGuideOverlay() }
        binding.menuItemBoxOffice.visibility = View.GONE
        binding.dividerMenu2.visibility = View.GONE
        binding.dividerMenu3.visibility = View.GONE
        menuItem(binding.menuItemRadio, p.rowOdd)        { showRadioMenu() }
        menuItem(binding.menuItemInteractive, p.rowEven) { showInteractiveMenu() }
        menuItem(binding.menuItemSettings, p.rowOdd)     { startActivity(Intent(this, com.orbital.iptv.ui.settings.SettingsActivity::class.java)) }
    }

    private fun setupHudButtons() {
        val p = ThemeManager.palette()
        val density = resources.displayMetrics.density

        fun timerReset(v: View) {
            v.setOnFocusChangeListener { _, h ->
                if (h) { hudHandler.removeCallbacks(hideHud); hudHandler.postDelayed(hideHud, 5000L) }
            }
        }

        binding.btnHudMenu.setOnClickListener {
            startActivity(Intent(this, HomeActivity::class.java))
        }
        timerReset(binding.btnHudMenu)

        binding.btnHudPip.setOnClickListener { enterPictureInPictureFromButton() }
        timerReset(binding.btnHudPip)
        binding.btnHudFullscreen.setOnClickListener { enterFullscreen() }
        timerReset(binding.btnHudFullscreen)
        MediaRouteButtonFactory.setUpMediaRouteButton(this, binding.btnHudCast)


        binding.btnHudAudio.setOnClickListener { showAudioPicker() }
        timerReset(binding.btnHudAudio)

        updateSurroundButton()
        binding.btnHudSurround.setOnClickListener { toggleSurroundSound() }
        timerReset(binding.btnHudSurround)

        updateRecordButton()
        binding.btnHudRecord.setOnFocusChangeListener { _, hasFocus ->
            val baseColor = if (isRecording) 0xFFCC0000.toInt() else 0xFF8B0000.toInt()
            binding.btnHudRecord.background = ThemeManager.focusRowDrawable(density, baseColor, hasFocus)
            if (hasFocus) { hudHandler.removeCallbacks(hideHud); hudHandler.postDelayed(hideHud, 5000L) }
        }
        binding.btnHudRecord.setOnClickListener {
            if (isRecording) stopRecording() else startRecording()
        }

        binding.btnHudScores.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                binding.btnHudScores.background = ThemeManager.focusRowDrawable(density, p.focus, true)
                hudHandler.removeCallbacks(hideHud); hudHandler.postDelayed(hideHud, 5000L)
            } else if (TickerManager.tickerEnabled) {
                binding.btnHudScores.setBackgroundResource(R.drawable.bg_btn_scores_on)
            } else {
                binding.btnHudScores.background = ThemeManager.hudButtonDrawable(density)
            }
        }
        binding.btnHudScores.setOnClickListener { toggleTicker() }

        binding.btnHudNews.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                binding.btnHudNews.background = ThemeManager.focusRowDrawable(density, p.focus, true)
                hudHandler.removeCallbacks(hideHud); hudHandler.postDelayed(hideHud, 5000L)
            } else if (TickerManager.newsTickerEnabled) {
                binding.btnHudNews.setBackgroundResource(R.drawable.bg_btn_scores_on)
            } else {
                binding.btnHudNews.background = ThemeManager.hudButtonDrawable(density)
            }
        }
        binding.btnHudNews.setOnClickListener { toggleNewsTicker() }

        updateGoalFlashButton()
        binding.btnHudGoalFlash.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                binding.btnHudGoalFlash.background = ThemeManager.focusRowDrawable(density, p.focus, true)
                hudHandler.removeCallbacks(hideHud); hudHandler.postDelayed(hideHud, 5000L)
            } else {
                updateGoalFlashButton()
            }
        }
        binding.btnHudGoalFlash.setOnClickListener { toggleGoalFlash() }
    }

    private fun showHudOverlay() {
        zapHandler.removeCallbacks(hideZap)
        updateClock()
        binding.hudTop.visibility    = View.VISIBLE
        binding.hudBottom.visibility = View.VISIBLE
        hudHandler.removeCallbacks(hideHud)
        hudHandler.postDelayed(hideHud, 5000L)
        binding.btnHudMenu.requestFocus()
        updateSurroundButton()
        // Re-evaluate NOW/NEXT against the current time — loadEpgForCurrentChannel() was only
        // ever called on tune-in, so a channel left playing past the cached programme's end time
        // showed a stale NOW/NEXT until the user changed channel.
        loadEpgForCurrentChannel()
    }

    private fun hideHudOverlay() {
        binding.hudTop.visibility    = View.GONE
        binding.hudBottom.visibility = View.GONE
        if (panelState == PanelState.NONE) binding.surfaceView.requestFocus()
    }

    private fun updateChannelInfo(name: String) {
        binding.tvChannelName.text    = name.uppercase()
        binding.tvHudChannelInfo.text = name.uppercase()
    }

    private fun showInfoBar(name: String) {
        updateChannelInfo(name)
        if (panelState == PanelState.NONE) showHudOverlay()
    }

    private fun showZapBar(name: String) {
        updateChannelInfo(name)
        updateClock()
        // Always force top HUD hidden and cancel its timer — only bottom info bar shows during zap
        hudHandler.removeCallbacks(hideHud)
        binding.hudTop.visibility    = View.GONE
        binding.hudBottom.visibility = View.VISIBLE
        zapHandler.removeCallbacks(hideZap)
        zapHandler.postDelayed(hideZap, 3000L)
        loadEpgForCurrentChannel()
    }

    private fun hideZapBar() {
        zapHandler.removeCallbacks(hideZap)
        // Only collapse the bottom bar if the full HUD (top) is not currently shown
        if (binding.hudTop.visibility != View.VISIBLE) {
            binding.hudBottom.visibility = View.GONE
        }
    }

    private fun loadEpgForCurrentChannel() {
        if (currentStreamId < 0) return
        val creds = PrefsManager.getCredentials(this) ?: return
        val streamIdSnapshot = currentStreamId
        binding.tvEpgNow.text = ""
        binding.tvEpgNextTitle.text = ""
        binding.tvEpgNextTime.text = ""
        binding.liveNextRow.visibility = View.GONE
        lifecycleScope.launch {
            try {
                val cached = EpgCache.get(this@TvModeActivity, streamIdSnapshot, minCount = 2)
                val listings = if (cached != null) {
                    cached
                } else {
                    val result = repository.getFullChannelEpg(
                        creds.serverUrl, creds.username, creds.password, streamIdSnapshot
                    )
                    result.getOrNull()?.listings?.also { l ->
                        EpgCache.put(this@TvModeActivity, streamIdSnapshot, l)
                    } ?: emptyList()
                }
                if (currentStreamId != streamIdSnapshot) return@launch
                val nowSec = System.currentTimeMillis() / 1000
                val sorted = listings.sortedBy { it.startTimestamp?.toLongOrNull() ?: 0L }
                val currentIdx = sorted.indexOfFirst { l ->
                    val start = l.startTimestamp?.toLongOrNull() ?: return@indexOfFirst false
                    val end   = l.stopTimestamp?.toLongOrNull()  ?: return@indexOfFirst false
                    nowSec in start..end
                }
                val current = if (currentIdx >= 0) sorted[currentIdx] else sorted.firstOrNull()
                val next    = if (currentIdx >= 0 && currentIdx + 1 < sorted.size) sorted[currentIdx + 1] else null

                current?.getDecodedTitle().takeIf { !it.isNullOrBlank() }?.let {
                    binding.tvEpgNow.text = it
                }
                next?.let { n ->
                    n.getDecodedTitle().takeIf { it.isNotBlank() }?.let { title ->
                        binding.tvEpgNextTitle.text = title
                        val startSec = n.startTimestamp?.toLongOrNull()
                        if (startSec != null) {
                            val cal = java.util.Calendar.getInstance().apply { timeInMillis = startSec * 1000 }
                            val h = cal.get(java.util.Calendar.HOUR_OF_DAY)
                            val m = cal.get(java.util.Calendar.MINUTE)
                            val ampm = if (h < 12) "am" else "pm"
                            val h12 = if (h % 12 == 0) 12 else h % 12
                            binding.tvEpgNextTime.text = "%d:%02d%s".format(h12, m, ampm)
                        }
                        binding.liveNextRow.visibility = View.VISIBLE
                    }
                }
            } catch (_: Exception) {}
        }
    }

    private fun updateClock() {
        val cal = Calendar.getInstance()
        val h = cal.get(Calendar.HOUR_OF_DAY)
        val m = cal.get(Calendar.MINUTE)
        val ampm = if (h < 12) "am" else "pm"
        val h12 = if (h % 12 == 0) 12 else h % 12
        val date = SimpleDateFormat("EEE dd MMM", Locale.UK).format(cal.time)
        binding.tvClock.text = "%d:%02d%s  %s".format(h12, m, ampm, date.uppercase())
    }

    private fun updateRecordButton() {
        isRecording = RecordingState.activeRecordNowUrl == currentStreamUrl
        binding.btnHudRecord.text = if (isRecording) "■ STOP REC" else "● REC"
        val baseColor = if (isRecording) 0xFFCC0000.toInt() else 0xFF8B0000.toInt()
        binding.btnHudRecord.background = ThemeManager.focusRowDrawable(
            resources.displayMetrics.density, baseColor, binding.btnHudRecord.isFocused
        )
    }

    private fun startRecording() {
        val epgTitle = binding.tvEpgNow.text.toString().ifBlank { currentChannelName }
        activeDialog = AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("● START RECORDING")
            .setMessage("Channel: $currentChannelName\nShow: $epgTitle\n\n⚠ Uses 2 connections.")
            .setPositiveButton("RECORD") { _, _ ->
                androidx.core.content.ContextCompat.startForegroundService(this, Intent(this, RecordingService::class.java).apply {
                    putExtra(RecordingService.EXTRA_CHANNEL_NAME,  currentChannelName)
                    putExtra(RecordingService.EXTRA_CHANNEL_URL,   currentStreamUrl)
                    putExtra(RecordingService.EXTRA_STREAM_ID,     currentStreamId)
                    putExtra(RecordingService.EXTRA_EPG_TITLE,     epgTitle)
                    putExtra(RecordingService.EXTRA_SCHEDULED_END, 0L)
                })
                isRecording = true
                updateRecordButton()
                showHudOverlay()
            }
            .setNegativeButton("CANCEL") { _, _ -> showHudOverlay() }
            .setOnDismissListener { activeDialog = null }
            .show()
    }

    private fun stopRecording() {
        startService(Intent(this, RecordingService::class.java).apply {
            action = RecordingService.ACTION_STOP
        })
        RecordingState.activeRecordNowUrl = null
        isRecording = false
        updateRecordButton()
        showHudOverlay()
    }

    private fun showAudioPicker() {
        val exo = player ?: run { showHudOverlay(); return }
        val audioGroups = exo.currentTracks.groups.filter { it.type == C.TRACK_TYPE_AUDIO }
        if (audioGroups.isEmpty()) {
            Toast.makeText(this, "NO AUDIO TRACKS FOUND", Toast.LENGTH_SHORT).show()
            showHudOverlay()
            return
        }
        data class Entry(val groupIdx: Int, val trackIdx: Int, val label: String, val selected: Boolean)
        val entries = mutableListOf<Entry>()
        audioGroups.forEachIndexed { gi, group ->
            for (ti in 0 until group.length) {
                val fmt  = group.getTrackFormat(ti)
                val lang = fmt.language?.uppercase() ?: ""
                val lbl  = fmt.label?.uppercase() ?: ""
                val name = listOfNotNull(lang.takeIf { it.isNotBlank() }, lbl.takeIf { it.isNotBlank() })
                    .joinToString(" ").ifBlank { "TRACK ${gi + 1}" }
                entries.add(Entry(gi, ti, name, group.isSelected && group.isTrackSelected(ti)))
            }
        }
        val labels = entries.map { "${if (it.selected) "●" else "○"}  ${it.label}" }
        AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("AUDIO LANGUAGE")
            .setItems(labels.toTypedArray()) { _, which ->
                val e = entries[which]
                exo.trackSelectionParameters = exo.trackSelectionParameters.buildUpon()
                    .clearOverridesOfType(C.TRACK_TYPE_AUDIO)
                    .addOverride(TrackSelectionOverride(audioGroups[e.groupIdx].mediaTrackGroup, e.trackIdx))
                    .build()
            }
            .setOnDismissListener { activeDialog = null; showHudOverlay() }
            .show().also { activeDialog = it }
    }

    // ── Sports scores ticker ──────────────────────────────────────────────────

    private fun updateScoresButton() {
        val on = TickerManager.tickerEnabled
        binding.btnHudScores.text = if (on) "SCORES ON" else "SCORES"
        if (on) binding.btnHudScores.setBackgroundResource(R.drawable.bg_btn_scores_on)
        else binding.btnHudScores.background = ThemeManager.hudButtonDrawable(resources.displayMetrics.density)
    }

    private fun toggleTicker() {
        TickerManager.tickerEnabled = !TickerManager.tickerEnabled
        updateScoresButton()
        if (TickerManager.tickerEnabled) startTicker() else stopTicker()
        showHudOverlay()
    }

    private fun startTicker() {
        binding.tickerRow.visibility = View.VISIBLE
        val hasSelected = TickerManager.getSelected(this).isNotEmpty()
        if (TickerManager.liveScores.isEmpty() && hasSelected) {
            tickerShowingPlaceholder = true
            binding.tvTicker.text = "  LOADING SCORES...  "
        } else {
            tickerShowingPlaceholder = false
            binding.tvTicker.text = TickerManager.buildTickerText()
        }
        tickerHandler.removeCallbacks(tickerRunnable)
        tickerHandler.post(tickerRunnable)
        binding.tvTicker.post { loopTickerScroll() }
    }

    private fun stopTicker() {
        tickerHandler.removeCallbacks(tickerRunnable)
        tickerScrollAnim?.cancel(); tickerScrollAnim = null
        pendingTickerText = null
        binding.tickerRow.visibility = View.GONE
    }

    private fun loopTickerScroll() {
        val tv = binding.tvTicker
        if (binding.tickerRow.visibility != View.VISIBLE || !TickerManager.tickerEnabled) return
        pendingTickerText?.let { tv.text = it; pendingTickerText = null }
        val containerWidth = (tv.parent as View).width.toFloat()
        tv.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED)
        val textWidth = tv.measuredWidth.toFloat()
        if (containerWidth <= 0f || textWidth <= 0f) { tv.post { loopTickerScroll() }; return }
        val pxPerSec = 60f * resources.displayMetrics.density
        val duration = ((containerWidth + textWidth) / pxPerSec * 1000f).toLong()
        tv.translationX = containerWidth
        tickerScrollAnim = ValueAnimator.ofFloat(containerWidth, -textWidth).apply {
            this.duration = duration
            interpolator = LinearInterpolator()
            addUpdateListener { tv.translationX = it.animatedValue as Float }
            addListener(object : AnimatorListenerAdapter() {
                private var cancelled = false
                override fun onAnimationCancel(a: Animator) { cancelled = true }
                override fun onAnimationEnd(a: Animator) { if (!cancelled) loopTickerScroll() }
            })
            start()
        }
    }

    private fun fetchTickerScores() {
        val selected = TickerManager.getSelected(this)
        if (selected.isEmpty()) { TickerManager.liveScores = emptyList(); updateTickerText(); return }
        val byLeague = selected.groupBy { it.sportPath to it.leagueId }
        val selectedIds = selected.map { it.id }.toSet()
        lifecycleScope.launch {
            try {
                val scores = mutableListOf<TickerManager.LiveScore>()
                withContext(Dispatchers.IO) {
                    byLeague.keys.forEach { (sportPath, leagueId) ->
                        val url = "https://site.api.espn.com/apis/site/v2/sports/$sportPath/$leagueId/scoreboard"
                        val json = TickerManager.espnGet(url)
                        scores.addAll(parseTickerScores(json, selectedIds))
                    }
                }
                TickerManager.liveScores = scores
                TickerManager.pruneFinished(this@TvModeActivity, scores)
                updateTickerText()
            } catch (_: Exception) {}
        }
    }

    private fun parseTickerScores(json: String, ids: Set<String>): List<TickerManager.LiveScore> {
        val out = mutableListOf<TickerManager.LiveScore>()
        try {
            val events = JSONObject(json).optJSONArray("events") ?: return out
            for (i in 0 until events.length()) {
                val event = events.getJSONObject(i)
                val id = event.optString("id"); if (id !in ids) continue
                val comp = event.optJSONArray("competitions")?.getJSONObject(0) ?: continue
                val competitors = comp.optJSONArray("competitors") ?: continue
                val statusType = comp.optJSONObject("status")?.optJSONObject("type") ?: continue
                val state      = statusType.optString("state", "pre")
                val detail     = statusType.optString("shortDetail", "")
                val statusDesc = statusType.optString("description", "")
                val note = run {
                    val notes = comp.optJSONArray("notes")
                    if (notes != null) {
                        (0 until notes.length())
                            .mapNotNull { notes.optJSONObject(it)?.optString("headline", "")?.takeIf { h -> h.isNotBlank() } }
                            .firstOrNull()
                    } else null
                } ?: when {
                    statusDesc.contains("penalt", ignoreCase = true) -> "AET (Pens)"
                    statusDesc.contains("aet", ignoreCase = true) || statusDesc.contains("extra time", ignoreCase = true) -> "AET"
                    else -> ""
                }
                var home: JSONObject? = null; var away: JSONObject? = null
                for (j in 0 until competitors.length()) {
                    val c = competitors.getJSONObject(j)
                    if (c.optString("homeAway") == "home") home = c else away = c
                }
                if (home == null || away == null) continue
                val ht = home.optJSONObject("team") ?: continue
                val at = away.optJSONObject("team") ?: continue
                out.add(TickerManager.LiveScore(
                    gameId    = id,
                    homeTeam  = ht.optString("shortDisplayName").ifEmpty { ht.optString("displayName") },
                    awayTeam  = at.optString("shortDisplayName").ifEmpty { at.optString("displayName") },
                    homeScore = home.optString("score", ""),
                    awayScore = away.optString("score", ""),
                    state = state, detail = detail, note = note
                ))
            }
        } catch (_: Exception) {}
        return out
    }

    private fun updateTickerText() {
        if (!TickerManager.tickerEnabled) return
        val newText = TickerManager.buildTickerText()
        if (tickerShowingPlaceholder) {
            tickerShowingPlaceholder = false
            tickerScrollAnim?.cancel(); tickerScrollAnim = null
            binding.tvTicker.text = newText
            loopTickerScroll()
        } else { pendingTickerText = newText }
    }

    // ── News headlines ticker ─────────────────────────────────────────────────

    private fun updateNewsButton() {
        val on = TickerManager.newsTickerEnabled
        binding.btnHudNews.text = if (on) "NEWS ON" else "NEWS"
        if (on) binding.btnHudNews.setBackgroundResource(R.drawable.bg_btn_scores_on)
        else binding.btnHudNews.background = ThemeManager.hudButtonDrawable(resources.displayMetrics.density)
    }

    private fun toggleNewsTicker() {
        TickerManager.newsTickerEnabled = !TickerManager.newsTickerEnabled
        updateNewsButton()
        if (TickerManager.newsTickerEnabled) startNewsTicker() else stopNewsTicker()
        showHudOverlay()
    }

    private fun startNewsTicker() {
        binding.newsTickerRow.visibility = View.VISIBLE
        binding.tvNewsTicker.text = TickerManager.buildNewsText()
        binding.tvNewsTicker.start()
        newsHandler.removeCallbacks(newsRunnable)
        newsHandler.post(newsRunnable)
    }

    private fun stopNewsTicker() {
        newsHandler.removeCallbacks(newsRunnable)
        binding.tvNewsTicker.stop()
        binding.newsTickerRow.visibility = View.GONE
    }

    // ── Goal Flash ────────────────────────────────────────────────────────────

    private fun toggleGoalFlash() {
        GoalFlashManager.enabled = !GoalFlashManager.enabled
        updateGoalFlashButton()
        if (GoalFlashManager.enabled) startGoalFlash() else stopGoalFlash()
    }

    private fun updateGoalFlashButton() {
        val density = resources.displayMetrics.density
        if (GoalFlashManager.enabled) binding.btnHudGoalFlash.setBackgroundResource(R.drawable.bg_btn_scores_on)
        else binding.btnHudGoalFlash.background = ThemeManager.hudButtonDrawable(density)
    }

    private fun startGoalFlash() {
        goalFlashHandler.removeCallbacks(goalFlashRunnable)
        goalFlashHandler.post(goalFlashRunnable)
    }

    private fun stopGoalFlash() {
        goalFlashHandler.removeCallbacks(goalFlashRunnable)
    }

    private fun fetchNewsHeadlines() {
        val selectedSports = TickerManager.getSelectedSports(this)
        if (selectedSports.isEmpty()) return
        lifecycleScope.launch {
            val results = LinkedHashMap<String, List<String>>()
            selectedSports.forEach { feed ->
                try {
                    val xml = withContext(Dispatchers.IO) {
                        tickerHttp.newCall(
                            Request.Builder().url(feed.rssUrl).header("User-Agent", "Mozilla/5.0").build()
                        ).execute().use { it.body?.string() ?: "" }
                    }
                    val titles = parseRssTitles(xml)
                    if (titles.isNotEmpty()) results[feed.id] = titles
                } catch (_: Exception) {}
            }
            if (results.isNotEmpty()) { TickerManager.sportHeadlines = results; updateNewsTickerText() }
        }
    }

    private fun parseRssTitles(xml: String): List<String> {
        val titles = mutableListOf<String>()
        try {
            val parser = android.util.Xml.newPullParser()
            parser.setInput(xml.reader())
            var inItem = false; var event = parser.eventType
            while (event != XmlPullParser.END_DOCUMENT && titles.size < 12) {
                when {
                    event == XmlPullParser.START_TAG && parser.name == "item" -> inItem = true
                    event == XmlPullParser.END_TAG   && parser.name == "item" -> inItem = false
                    inItem && event == XmlPullParser.START_TAG && parser.name == "title" ->
                        titles.add(parser.nextText().trim())
                }
                event = parser.next()
            }
        } catch (_: Exception) {}
        return titles
    }

    private fun updateNewsTickerText() {
        if (!TickerManager.newsTickerEnabled) return
        binding.tvNewsTicker.text = TickerManager.buildNewsText()
    }

    // ── Left-panel navigation state machine ───────────────────────────────────

    /** Open the CHANNELS panel (channel list + inline EPG column). */
    private fun showChannelPanel() {
        hideHudOverlay()
        zapHandler.removeCallbacks(hideZap)
        panelState = PanelState.CHANNELS
        binding.leftPanel.visibility           = View.VISIBLE
        binding.layoutChannelsSplit.visibility = View.VISIBLE
        binding.rvPanelCategories.visibility   = View.GONE
        binding.panelMainMenu.visibility       = View.GONE

        val catName = when {
            currentCategoryId == FAV_CATEGORY_ID -> "★  FAVOURITES"
            currentCategoryId.isBlank() -> "ALL CHANNELS"
            else -> TvModeHolder.categories
                .find { it.categoryId == currentCategoryId }
                ?.categoryName?.uppercase() ?: "CHANNELS"
        }
        binding.panelHeader.text = catName

        refreshCategoryChannels()
        loadChannelPanel(categoryChannels)
    }