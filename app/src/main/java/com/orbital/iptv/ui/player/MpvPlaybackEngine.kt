package com.orbital.iptv.ui.player

import android.content.Context
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.ViewGroup
import android.widget.FrameLayout
import dev.jdtech.mpv.MPVLib

class MpvPlaybackEngine(private val context: Context) : PlaybackEngine {
    private var mpv: MPVLib? = null
    private var surfaceView: SurfaceView? = null
    private var pendingStartPosition = 0L
    private var playingState = false
    private var bufferingState = false
    private var stateCallback: ((Boolean, Boolean) -> Unit)? = null
    private var endedCallback: (() -> Unit)? = null
    private var errorCallback: ((Throwable) -> Unit)? = null

    override fun initialize() {
        try {
            val instance = MPVLib.create(context) ?: throw IllegalStateException("MPVLib.create() returned null")
            instance.setOptionString("vo", "gpu")
            instance.setOptionString("hwdec", "auto")
            instance.setOptionString("tls-verify", "no")
            instance.setOptionString(
                "user-agent",
                "Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 Chrome/121 Safari/537.36"
            )
            instance.init()
            instance.addObserver(object : MPVLib.EventObserver {
                override fun eventProperty(property: String) {}
                override fun eventProperty(property: String, value: Long) {}
                override fun eventProperty(property: String, value: Double) {}
                override fun eventProperty(property: String, value: String) {}
                override fun eventProperty(property: String, value: Boolean) {
                    when (property) {
                        "pause" -> {
                            playingState = !value
                            stateCallback?.invoke(playingState, bufferingState)
                        }
                        "paused-for-cache" -> {
                            bufferingState = value
                            stateCallback?.invoke(playingState, bufferingState)
                        }
                    }
                }

                override fun event(eventId: Int) {
                    when (eventId) {
                        MPVLib.MpvEvent.MPV_EVENT_FILE_LOADED -> {
                            if (pendingStartPosition > 0L) {
                                instance.setPropertyDouble("time-pos", pendingStartPosition / 1000.0)
                                pendingStartPosition = 0L
                            }
                            playingState = true
                            bufferingState = false
                            stateCallback?.invoke(true, false)
                        }
                        MPVLib.MpvEvent.MPV_EVENT_END_FILE -> {
                            playingState = false
                            bufferingState = false
                            stateCallback?.invoke(false, false)
                            endedCallback?.invoke()
                        }
                    }
                }
            })
            instance.observeProperty("pause", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
            instance.observeProperty("paused-for-cache", MPVLib.MpvFormat.MPV_FORMAT_FLAG)
            mpv = instance
        } catch (t: Throwable) {
            Log.e("MpvPlaybackEngine", "Initialization failed", t)
            errorCallback?.invoke(t)
            throw t
        }
    }

    override fun attach(container: ViewGroup) {
        detachSurfaceOnly()
        val sv = SurfaceView(context)
        sv.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                mpv?.attachSurface(holder.surface)
            }
            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {}
            override fun surfaceDestroyed(holder: SurfaceHolder) {
                try { mpv?.detachSurface() } catch (_: Exception) {}
            }
        })
        sv.layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        )
        container.addView(sv)
        surfaceView = sv
        if (sv.holder.surface.isValid) mpv?.attachSurface(sv.holder.surface)
    }

    private fun detachSurfaceOnly() {
        try { mpv?.detachSurface() } catch (_: Exception) {}
        surfaceView?.let { (it.parent as? ViewGroup)?.removeView(it) }
        surfaceView = null
    }

    override fun prepare(url: String, startPositionMs: Long) {
        pendingStartPosition = startPositionMs.coerceAtLeast(0L)
        try {
            val command = if (startPositionMs > 0L) {
                arrayOf("loadfile", url, "replace", "start=" + (startPositionMs / 1000.0))
            } else {
                arrayOf("loadfile", url, "replace")
            }
            mpv?.command(command)
        } catch (t: Throwable) {
            errorCallback?.invoke(t)
        }
    }

    override fun play() {
        mpv?.setPropertyBoolean("pause", false)
        playingState = true
        stateCallback?.invoke(true, bufferingState)
    }

    override fun pause() {
        mpv?.setPropertyBoolean("pause", true)
        playingState = false
        stateCallback?.invoke(false, bufferingState)
    }

    override fun stop() {
        mpv?.command(arrayOf("stop"))
        playingState = false
        bufferingState = false
    }

    override fun seekTo(positionMs: Long) {
        mpv?.setPropertyDouble("time-pos", positionMs.coerceAtLeast(0L) / 1000.0)
    }

    override fun seekBack(stepMs: Long) {
        seekTo((getCurrentPosition() - stepMs).coerceAtLeast(0L))
    }

    override fun seekForward(stepMs: Long) {
        val duration = getDuration()
        val target = getCurrentPosition() + stepMs
        seekTo(if (duration > 0L) target.coerceAtMost(duration) else target)
    }

    override fun isPlaying(): Boolean =
        mpv?.getPropertyBoolean("pause")?.not() ?: playingState

    override fun isBuffering(): Boolean = bufferingState

    override fun getDuration(): Long =
        ((mpv?.getPropertyDouble("duration") ?: 0.0) * 1000.0).toLong().coerceAtLeast(0L)

    override fun getCurrentPosition(): Long =
        ((mpv?.getPropertyDouble("time-pos") ?: 0.0) * 1000.0).toLong().coerceAtLeast(0L)

    override fun setVolume(volume: Float) {
        mpv?.setPropertyInt("volume", (volume * 100f).toInt().coerceIn(0, 100))
    }

    override fun setPlaybackSpeed(speed: Float) {
        mpv?.setPropertyDouble("speed", speed.coerceIn(0.25f, 4f).toDouble())
    }

    override fun getPlaybackSpeed(): Float =
        (mpv?.getPropertyDouble("speed") ?: 1.0).toFloat()

    override fun setOnStateChanged(callback: (Boolean, Boolean) -> Unit) {
        stateCallback = callback
    }

    override fun setOnEnded(callback: () -> Unit) {
        endedCallback = callback
    }

    override fun setOnError(callback: (Throwable) -> Unit) {
        errorCallback = callback
    }

    override fun release() {
        detachSurfaceOnly()
        try { mpv?.command(arrayOf("stop")) } catch (_: Exception) {}
        try { mpv?.destroy() } catch (_: Exception) {}
        mpv = null
    }
}