package com.orbital.iptv.ui.player

import android.content.Context
import android.net.Uri
import android.view.ViewGroup
import android.widget.FrameLayout
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout
import java.io.File

class VlcPlaybackEngine(private val context: Context) : PlaybackEngine {
    private var libVlc: LibVLC? = null
    private var mediaPlayer: MediaPlayer? = null
    private var videoLayout: VLCVideoLayout? = null
    private var buffering = false
    private var pendingStartPosition = -1L
    private var stateCallback: ((Boolean, Boolean) -> Unit)? = null
    private var endedCallback: (() -> Unit)? = null
    private var errorCallback: ((Throwable) -> Unit)? = null

    override fun initialize() {
        try {
            libVlc = LibVLC(context, arrayListOf(
                "--network-caching=1000",
                "--http-reconnect",
                "--no-stats",
                "--no-osd",
                "--no-video-title-show"
            ))
            mediaPlayer = MediaPlayer(libVlc).apply {
                videoScale = MediaPlayer.ScaleType.SURFACE_BEST_FIT
                setEventListener { event ->
                    when (event.type) {
                        MediaPlayer.Event.EncounteredError -> errorCallback?.invoke(Exception("VLC playback error"))
                        MediaPlayer.Event.EndReached -> {
                            endedCallback?.invoke()
                            stateCallback?.invoke(false, false)
                        }
                        MediaPlayer.Event.Buffering -> {
                            buffering = event.buffering < 100f
                            stateCallback?.invoke(isPlaying, buffering)
                        }
                        MediaPlayer.Event.Playing -> {
                            if (pendingStartPosition >= 0L) {
                                val target = pendingStartPosition
                                pendingStartPosition = -1L
                                time = target
                            }
                            stateCallback?.invoke(true, false)
                        }
                        MediaPlayer.Event.Paused,
                        MediaPlayer.Event.Stopped -> stateCallback?.invoke(false, false)
                    }
                }
            }
        } catch (t: Throwable) {
            errorCallback?.invoke(t)
            throw t
        }
    }

    override fun attach(container: ViewGroup) {
        detachViewOnly()
        val layout = VLCVideoLayout(context).apply {
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }
        container.addView(layout)
        videoLayout = layout
        mediaPlayer?.attachViews(layout, null, false, false)
    }

    private fun detachViewOnly() {
        try { mediaPlayer?.detachViews() } catch (_: Exception) {}
        videoLayout?.let { (it.parent as? ViewGroup)?.removeView(it) }
        videoLayout = null
    }

    override fun prepare(url: String, startPositionMs: Long) {
        pendingStartPosition = if (startPositionMs > 0L) startPositionMs else -1L
        val vlc = libVlc ?: return
        val isNetwork = url.startsWith("http://") || url.startsWith("https://")
        val media = when {
            isNetwork -> Media(vlc, Uri.parse(url))
            url.startsWith("content://") || url.startsWith("file://") -> Media(vlc, Uri.parse(url))
            else -> Media(vlc, Uri.fromFile(File(url)))
        }.apply {
            setHWDecoderEnabled(true, false)
            if (isNetwork) {
                addOption(":network-caching=1000")
                addOption(":http-user-agent=Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 Chrome/121 Safari/537.36")
            } else {
                addOption(":file-caching=300")
            }
        }
        try {
            mediaPlayer?.media = media
            mediaPlayer?.play()
        } catch (t: Throwable) {
            errorCallback?.invoke(Exception("VLC prepare failed", t))
        } finally {
            media.release()
        }
    }

    override fun play() { mediaPlayer?.play() }
    override fun pause() { mediaPlayer?.pause() }
    override fun stop() { mediaPlayer?.stop(); buffering = false }
    override fun seekTo(positionMs: Long) { mediaPlayer?.time = positionMs.coerceAtLeast(0L) }
    override fun seekBack(stepMs: Long) { seekTo((getCurrentPosition() - stepMs).coerceAtLeast(0L)) }
    override fun seekForward(stepMs: Long) {
        val duration = getDuration()
        val target = getCurrentPosition() + stepMs
        seekTo(if (duration > 0L) target.coerceAtMost(duration) else target)
    }
    override fun isPlaying(): Boolean = mediaPlayer?.isPlaying == true
    override fun isBuffering(): Boolean = buffering
    override fun getDuration(): Long = mediaPlayer?.length ?: 0L
    override fun getCurrentPosition(): Long = mediaPlayer?.time ?: 0L
    override fun setVolume(volume: Float) { mediaPlayer?.volume = (volume * 100f).toInt().coerceIn(0, 100) }
    override fun setPlaybackSpeed(speed: Float) { mediaPlayer?.rate = speed.coerceIn(0.25f, 4f) }
    override fun getPlaybackSpeed(): Float = mediaPlayer?.rate ?: 1f
    override fun setOnStateChanged(callback: (Boolean, Boolean) -> Unit) { stateCallback = callback }
    override fun setOnEnded(callback: () -> Unit) { endedCallback = callback }
    override fun setOnError(callback: (Throwable) -> Unit) { errorCallback = callback }

    override fun release() {
        try { mediaPlayer?.stop() } catch (_: Exception) {}
        try { mediaPlayer?.detachViews() } catch (_: Exception) {}
        try { mediaPlayer?.release() } catch (_: Exception) {}
        try { libVlc?.release() } catch (_: Exception) {}
        detachViewOnly()
        mediaPlayer = null
        libVlc = null
    }
}