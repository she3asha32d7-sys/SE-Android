from pathlib import Path

ROOT = Path(".")

vlc = r'''package com.orbital.iptv.ui.player

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.ViewGroup
import android.widget.FrameLayout
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout
import java.io.File

/**
 * LibVLC playback adapter based on MaterialTV's lifecycle pattern, with an extra
 * hardware->software decoder retry for IPTV devices where HW output fails.
 */
class VlcPlaybackEngine(private val context: Context) : PlaybackEngine {

    private var libVlc: LibVLC? = null
    private var mediaPlayer: MediaPlayer? = null
    private var videoLayout: VLCVideoLayout? = null
    private var currentContainer: ViewGroup? = null
    private var buffering = false
    private var pendingStartPosition = -1L
    private var currentUrl: String? = null
    private var currentStartPosition = 0L
    private var hardwareAttempt = true
    private var softwareRetryUsed = false
    private var released = false

    private var stateCallback: ((Boolean, Boolean) -> Unit)? = null
    private var endedCallback: (() -> Unit)? = null
    private var errorCallback: ((Throwable) -> Unit)? = null

    private val handler = Handler(Looper.getMainLooper())

    override fun initialize() {
        released = false
        val args = arrayListOf(
            "--network-caching=1000",
            "--file-caching=300",
            "--http-reconnect",
            "--rtsp-tcp",
            "--no-stats",
            "--no-osd",
            "--no-video-title-show",
            "--drop-late-frames",
            "--skip-frames"
        )
        try {
            libVlc = LibVLC(context.applicationContext, args)
            mediaPlayer = MediaPlayer(libVlc).apply {
                videoScale = MediaPlayer.ScaleType.SURFACE_BEST_FIT
                setEventListener { event ->
                    when (event.type) {
                        MediaPlayer.Event.Opening -> {
                            buffering = true
                            log("Opening")
                            stateCallback?.invoke(false, true)
                        }
                        MediaPlayer.Event.Buffering -> {
                            buffering = event.buffering < 100f
                            log("Buffering " + event.buffering + "%")
                            stateCallback?.invoke(isPlayingSafe(), buffering)
                        }
                        MediaPlayer.Event.Playing -> {
                            buffering = false
                            log("Playing")
                            applyPendingSeek()
                            stateCallback?.invoke(true, false)
                        }
                        MediaPlayer.Event.Paused -> {
                            buffering = false
                            log("Paused")
                            stateCallback?.invoke(false, false)
                        }
                        MediaPlayer.Event.Stopped -> {
                            buffering = false
                            log("Stopped")
                            stateCallback?.invoke(false, false)
                        }
                        MediaPlayer.Event.EndReached -> {
                            buffering = false
                            log("EndReached")
                            endedCallback?.invoke()
                            stateCallback?.invoke(false, false)
                        }
                        MediaPlayer.Event.EncounteredError -> {
                            buffering = false
                            log("EncounteredError; hardwareAttempt=" + hardwareAttempt + ", softwareRetryUsed=" + softwareRetryUsed)
                            if (hardwareAttempt && !softwareRetryUsed && currentUrl != null && !released) {
                                softwareRetryUsed = true
                                handler.post { retryWithSoftwareDecoder() }
                            } else {
                                errorCallback?.invoke(Exception("VLC playback error"))
                                stateCallback?.invoke(false, false)
                            }
                        }
                        else -> Unit
                    }
                }
            }
        } catch (t: Throwable) {
            log("initialize failed: " + t)
            errorCallback?.invoke(t)
            throw t
        }
    }

    override fun attach(container: ViewGroup) {
        currentContainer = container
        if (videoLayout != null && videoLayout?.parent === container) {
            videoLayout?.requestLayout()
            return
        }
        detachViews()
        val layout = VLCVideoLayout(context).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }
        container.addView(layout)
        videoLayout = layout
        try {
            mediaPlayer?.attachViews(layout, null, false, false)
            log("attachViews success")
        } catch (t: Throwable) {
            log("attachViews failed: " + t)
            errorCallback?.invoke(t)
        }
    }

    private fun detachViews() {
        try { mediaPlayer?.detachViews() } catch (t: Throwable) { log("detachViews: " + t.message) }
        videoLayout?.let { (it.parent as? ViewGroup)?.removeView(it) }
        videoLayout = null
    }

    override fun prepare(url: String, startPositionMs: Long) {
        currentUrl = url
        currentStartPosition = startPositionMs.coerceAtLeast(0L)
        pendingStartPosition = currentStartPosition.takeIf { it > 0L } ?: -1L
        hardwareAttempt = true
        softwareRetryUsed = false
        loadMedia(url, currentStartPosition, useHardware = true)
    }

    private fun loadMedia(url: String, startPositionMs: Long, useHardware: Boolean) {
        val vlc = libVlc ?: return
        try {
            mediaPlayer?.stop()
        } catch (_: Throwable) {}

        val isNetwork = url.startsWith("http://", true) || url.startsWith("https://", true)
        val media = when {
            isNetwork -> Media(vlc, Uri.parse(url))
            url.startsWith("content://", true) -> Media(vlc, Uri.parse(url))
            url.startsWith("file://", true) -> Media(vlc, Uri.parse(url))
            else -> Media(vlc, Uri.fromFile(File(url)))
        }.apply {
            if (startPositionMs > 0L) {
                addOption(":start-time=" + (startPositionMs / 1000L))
            }
            if (useHardware) {
                setHWDecoderEnabled(true, false)
            } else {
                setHWDecoderEnabled(false, false)
                addOption(":avcodec-hw=none")
            }

            if (isNetwork) {
                addOption(":network-caching=1000")
                addOption(":http-reconnect=true")
                addOption(":http-user-agent=Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 Chrome/121 Safari/537.36")
            } else {
                addOption(":file-caching=300")
            }
        }

        try {
            mediaPlayer?.media = media
            log("media assigned, hardware=" + useHardware + ", url=" + sanitize(url))
        } catch (t: Throwable) {
            log("media assignment failed: " + t)
            errorCallback?.invoke(t)
        } finally {
            media.release()
        }

        // Delay play very slightly so VLC has completed its media assignment and vout binding.
        handler.postDelayed({
            if (!released) {
                try {
                    mediaPlayer?.play()
                    stateCallback?.invoke(false, true)
                    log("play() dispatched")
                } catch (t: Throwable) {
                    log("play() failed: " + t)
                    if (useHardware && !softwareRetryUsed) {
                        softwareRetryUsed = true
                        retryWithSoftwareDecoder()
                    } else {
                        errorCallback?.invoke(t)
                    }
                }
            }
        }, 80L)
    }

    private fun retryWithSoftwareDecoder() {
        val url = currentUrl ?: return
        log("Retrying VLC with software decoder")
        hardwareAttempt = false
        buffering = true
        stateCallback?.invoke(false, true)
        loadMedia(url, currentStartPosition, useHardware = false)
    }

    private fun applyPendingSeek() {
        val target = pendingStartPosition
        if (target < 0L) return
        pendingStartPosition = -1L
        handler.post {
            try {
                mediaPlayer?.time = target
                val len = mediaPlayer?.length ?: 0L
                if (len > 0L) {
                    mediaPlayer?.position = (target.toDouble() / len.toDouble()).coerceIn(0.0, 1.0).toFloat()
                }
            } catch (t: Throwable) {
                log("pending seek failed: " + t.message)
            }
        }
    }

    private fun isPlayingSafe(): Boolean = try {
        mediaPlayer?.isPlaying == true
    } catch (_: Throwable) {
        false
    }

    private fun log(message: String) {
        Log.d("SE_VLC", message)
    }

    private fun sanitize(url: String): String {
        return try {
            url.substringBefore('|').take(160)
        } catch (_: Throwable) {
            "<url>"
        }
    }

    override fun play() { try { mediaPlayer?.play() } catch (t: Throwable) { errorCallback?.invoke(t) } }
    override fun pause() { try { mediaPlayer?.pause() } catch (t: Throwable) { errorCallback?.invoke(t) } }
    override fun stop() { try { mediaPlayer?.stop() } catch (_: Throwable) {} }
    override fun seekTo(positionMs: Long) { pendingStartPosition = -1L; try { mediaPlayer?.time = positionMs.coerceAtLeast(0L) } catch (_: Throwable) {} }
    override fun seekBack(stepMs: Long) { seekTo((getCurrentPosition() - stepMs).coerceAtLeast(0L)) }
    override fun seekForward(stepMs: Long) {
        val duration = getDuration()
        val target = getCurrentPosition() + stepMs
        seekTo(if (duration > 0L) target.coerceAtMost(duration) else target)
    }
    override fun isPlaying(): Boolean = isPlayingSafe()
    override fun isBuffering(): Boolean = buffering
    override fun getDuration(): Long = try { mediaPlayer?.length ?: 0L } catch (_: Throwable) { 0L }
    override fun getCurrentPosition(): Long = try { mediaPlayer?.time ?: 0L } catch (_: Throwable) { 0L }
    override fun setVolume(volume: Float) { try { mediaPlayer?.volume = (volume * 100f).toInt().coerceIn(0, 100) } catch (_: Throwable) {} }
    override fun setPlaybackSpeed(speed: Float) { try { mediaPlayer?.rate = speed.coerceIn(0.25f, 4f) } catch (_: Throwable) {} }
    override fun getPlaybackSpeed(): Float = try { mediaPlayer?.rate ?: 1f } catch (_: Throwable) { 1f }
    override fun setOnStateChanged(callback: (Boolean, Boolean) -> Unit) { stateCallback = callback }
    override fun setOnEnded(callback: () -> Unit) { endedCallback = callback }
    override fun setOnError(callback: (Throwable) -> Unit) { errorCallback = callback }

    fun reattach() {
        val container = currentContainer ?: return
        attach(container)
    }

    override fun release() {
        released = true
        handler.removeCallbacksAndMessages(null)
        try { mediaPlayer?.stop() } catch (_: Throwable) {}
        try { mediaPlayer?.setEventListener(null) } catch (_: Throwable) {}
        try { mediaPlayer?.detachViews() } catch (_: Throwable) {}
        try { mediaPlayer?.release() } catch (_: Throwable) {}
        try { libVlc?.release() } catch (_: Throwable) {}
        mediaPlayer = null
        libVlc = null
        detachViews()
        currentContainer = null
        currentUrl = null
        pendingStartPosition = -1L
    }
}
'''
(ROOT / "app/src/main/java/com/orbital/iptv/ui/player/VlcPlaybackEngine.kt").write_text(vlc)

# Packaging: MaterialTV explicitly protects these shared native dependencies.
p = ROOT / "app/build.gradle"
s = p.read_text()
if "pickFirst '**/libcrypto.so'" not in s:
    s = s.replace(
        "    pickFirst '**/libc++_shared.so'\n",
        "    pickFirst '**/libc++_shared.so'\n    pickFirst '**/libcrypto.so'\n    pickFirst '**/libssl.so'\n"
    )
s = s.replace('versionCode 1000028', 'versionCode 1000029', 1)
s = s.replace('versionName "100.0.28"', 'versionName "100.0.29"', 1)
p.write_text(s)

# Remove any forced refresh of native video track from the old implementation if present.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/EnginePlayerActivity.kt"
s = p.read_text()
s = s.replace('playerType = when (PrefsManager.getPlayerType(this)) {', 'playerType = when (PrefsManager.getPlayerType(this)) {')
p.write_text(s)

print("VLC fix V100.0.29 applied")
