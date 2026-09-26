package com.orbital.iptv.ui.player

import android.view.ViewGroup

interface PlaybackEngine {
    fun initialize()
    fun attach(container: ViewGroup)
    fun prepare(url: String, startPositionMs: Long = 0L)
    fun play()
    fun pause()
    fun stop()
    fun seekTo(positionMs: Long)
    fun seekBack(stepMs: Long = 10_000L)
    fun seekForward(stepMs: Long = 10_000L)
    fun isPlaying(): Boolean
    fun isBuffering(): Boolean
    fun getDuration(): Long
    fun getCurrentPosition(): Long
    fun setVolume(volume: Float)
    fun setPlaybackSpeed(speed: Float)
    fun getPlaybackSpeed(): Float
    fun release()
    fun setOnStateChanged(callback: (playing: Boolean, buffering: Boolean) -> Unit)
    fun setOnEnded(callback: () -> Unit)
    fun setOnError(callback: (Throwable) -> Unit)
}