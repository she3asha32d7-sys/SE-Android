package com.orbital.iptv.ui.player

import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.orbital.iptv.databinding.ActivityEnginePlayerBinding
import com.orbital.iptv.recording.RecordingRepository
import com.orbital.iptv.recording.RecordingService
import com.orbital.iptv.recording.RecordingState
import com.orbital.iptv.utils.PlayerType
import com.orbital.iptv.utils.PrefsManager
import com.orbital.iptv.utils.ThemeManager
import java.util.Locale

class EnginePlayerActivity : AppCompatActivity() {
    private lateinit var binding: ActivityEnginePlayerBinding
    private var engine: PlaybackEngine? = null
    private var playerType = PlayerType.VLC
    private var streamUrl = ""
    private var channelName = "UNKNOWN"
    private var streamId = -1
    private var isLive = true
    private var resumeMs = 0L
    private var recording = false

    private val handler = Handler(Looper.getMainLooper())
    private val positionRunnable = object : Runnable {
        override fun run() {
            updatePosition()
            handler.postDelayed(this, 500L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        ThemeManager.load(this)

        streamUrl = intent.getStringExtra(PlayerActivity.EXTRA_STREAM_URL).orEmpty()
        channelName = intent.getStringExtra(PlayerActivity.EXTRA_CHANNEL_NAME) ?: "UNKNOWN"
        streamId = intent.getIntExtra(PlayerActivity.EXTRA_STREAM_ID, -1)
        isLive = intent.getBooleanExtra(PlayerActivity.EXTRA_IS_LIVE, true)
        resumeMs = intent.getLongExtra(PlayerActivity.EXTRA_RESUME_MS, 0L)
        playerType = when (PrefsManager.getPlayerType(this)) {
            PlayerType.MPV -> PlayerType.MPV
            else -> PlayerType.VLC
        }

        binding = ActivityEnginePlayerBinding.inflate(layoutInflater)
        setContentView(binding.root)
        enterFullscreen()
        applyTheme()

        binding.tvEngineTitle.text = channelName
        binding.tvEngineName.text = if (playerType == PlayerType.MPV) "MPV + FFmpeg" else "VLC"
        binding.btnEngineBack.setOnClickListener { finish() }
        binding.btnEnginePrev.setOnClickListener { engine?.seekBack(10_000L) }
        binding.btnEngineNext.setOnClickListener { engine?.seekForward(10_000L) }
        binding.btnEnginePlay.setOnClickListener { togglePlayback() }
        binding.btnEngineSpeed.setOnClickListener { showSpeedPicker() }
        binding.btnEngineRecord.visibility = if (isLive) View.VISIBLE else View.GONE
        binding.btnEngineRecord.setOnClickListener { onRecordClicked() }

        binding.engineSeek.setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: android.widget.SeekBar?, progress: Int, fromUser: Boolean) {
                if (!fromUser) return
                val duration = engine?.getDuration() ?: 0L
                if (duration > 0L) engine?.seekTo((duration * progress / 1000L).coerceIn(0L, duration))
            }
            override fun onStartTrackingTouch(seekBar: android.widget.SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: android.widget.SeekBar?) {}
        })

        startEngine()
        handler.post(positionRunnable)
    }

    private fun applyTheme() {
        val p = ThemeManager.palette()
        binding.rootEnginePlayer.setBackgroundColor(p.bgPrimary)
        binding.engineControls.setBackgroundColor(ThemeManager.withAlpha(p.bgHeader, 0xD9))
        binding.tvEngineTitle.setTextColor(p.accent)
        binding.tvEngineName.setTextColor(p.accent)
        binding.tvEngineStatus.setTextColor(p.accent)
        listOf(
            binding.btnEngineBack,
            binding.btnEnginePrev,
            binding.btnEnginePlay,
            binding.btnEngineNext,
            binding.btnEngineSpeed
        ).forEach { v ->
            v.background = ThemeManager.hudButtonDrawable(resources.displayMetrics.density)
            v.setTextColor(0xFFFFFFFF.toInt())
        }
        binding.btnEngineRecord.background = ThemeManager.focusRowDrawable(
            resources.displayMetrics.density,
            0xFF8B0000.toInt(),
            false,
            0xFFFF4444.toInt()
        )
        binding.btnEngineRecord.setTextColor(0xFFFF5555.toInt())
        binding.engineSeek.progressTintList = android.content.res.ColorStateList.valueOf(p.accent)
        binding.engineSeek.thumbTintList = android.content.res.ColorStateList.valueOf(p.accent)
    }

    private fun startEngine() {
        if (streamUrl.isBlank()) {
            binding.tvEngineStatus.text = "STREAM URL NOT FOUND"
            return
        }

        val newEngine: PlaybackEngine = when (playerType) {
            PlayerType.MPV -> MpvPlaybackEngine(this)
            else -> VlcPlaybackEngine(this)
        }
        engine = newEngine

        newEngine.setOnStateChanged { playing, buffering ->
            runOnUiThread {
                binding.tvEngineStatus.text = when {
                    buffering -> "BUFFERING..."
                    playing -> "PLAYING"
                    else -> "PAUSED"
                }
                binding.btnEnginePlay.text = if (playing) "PAUSE" else "PLAY"
            }
        }
        newEngine.setOnEnded {
            runOnUiThread {
                binding.tvEngineStatus.text = "ENDED"
                binding.btnEnginePlay.text = "PLAY"
            }
        }
        newEngine.setOnError { error ->
            runOnUiThread {
                binding.tvEngineStatus.text = "ERROR"
                val engineName = if (playerType == PlayerType.MPV) "MPV" else "VLC"
                Toast.makeText(this, engineName + ": " + (error.message ?: "Playback error"), Toast.LENGTH_LONG).show()
            }
        }

        try {
            newEngine.initialize()
            newEngine.attach(binding.enginePlayerContainer)
            newEngine.prepare(streamUrl, resumeMs)
            newEngine.setPlaybackSpeed(PrefsManager.getPlaybackSpeed(this))
            newEngine.play()
            binding.tvEngineStatus.text = "CONNECTING..."
        } catch (t: Throwable) {
            binding.tvEngineStatus.text = "ENGINE FAILED"
            val engineName = if (playerType == PlayerType.MPV) "MPV" else "VLC"
            Toast.makeText(this, engineName + " engine failed: " + (t.message ?: "unknown error"), Toast.LENGTH_LONG).show()
        }
    }

    private fun togglePlayback() {
        val e = engine ?: return
        if (e.isPlaying()) e.pause() else e.play()
    }

    private fun updatePosition() {
        val e = engine ?: return
        val duration = e.getDuration()
        val position = e.getCurrentPosition()

        if (!isLive && duration > 0L) {
            binding.engineSeek.visibility = View.VISIBLE
            binding.engineSeek.progress = (position * 1000L / duration).toInt().coerceIn(0, 1000)
            binding.tvEngineStatus.text = formatTime(position) + " / " + formatTime(duration)
        } else {
            binding.engineSeek.visibility = View.GONE
            if (e.isBuffering()) binding.tvEngineStatus.text = "BUFFERING..."
        }

        binding.btnEnginePlay.text = if (e.isPlaying()) "PAUSE" else "PLAY"
        binding.btnEngineSpeed.text = formatSpeed(e.getPlaybackSpeed())
        binding.btnEngineRecord.text = if (recording) "■ STOP REC" else "● REC"
    }

    private fun showSpeedPicker() {
        val speeds = listOf(0.5f, 1f, 1.5f, 2f, 3f, 4f)
        val labels = speeds.map(::formatSpeed).toTypedArray()
        val currentSpeed = engine?.getPlaybackSpeed() ?: 1f
        val selected = speeds.indices.minByOrNull { kotlin.math.abs(speeds[it] - currentSpeed) } ?: 1

        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("PLAYBACK SPEED")
            .setSingleChoiceItems(labels, selected) { dialog, which ->
                val speed = speeds[which]
                PrefsManager.setPlaybackSpeed(this, speed)
                engine?.setPlaybackSpeed(speed)
                dialog.dismiss()
            }
            .show()
    }

    private fun onRecordClicked() {
        if (recording) {
            stopRecord()
            return
        }

        val available = RecordingRepository.availableGb(this)
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("● START RECORDING")
            .setMessage(
                "Channel: " + channelName +
                    "\n\nAvailable storage: " +
                    String.format(Locale.getDefault(), "%.1f", available) +
                    " GB\n\nRecording uses a second stream connection."
            )
            .setPositiveButton("RECORD") { _, _ -> startRecord(channelName) }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun startRecord(epgTitle: String) {
        val profile = PrefsManager.getActiveProfile(this)
        val recordingUrl = if (profile != null && streamId > 0) {
            profile.serverUrl.trimEnd('/') + "/live/" + profile.username + "/" + profile.password + "/" + streamId + ".ts"
        } else {
            streamUrl
        }

        ContextCompat.startForegroundService(this, Intent(this, RecordingService::class.java).apply {
            putExtra(RecordingService.EXTRA_CHANNEL_NAME, channelName)
            putExtra(RecordingService.EXTRA_CHANNEL_URL, recordingUrl)
            putExtra(RecordingService.EXTRA_STREAM_ID, streamId)
            putExtra(RecordingService.EXTRA_EPG_TITLE, epgTitle)
            putExtra(RecordingService.EXTRA_SCHEDULED_END, 0L)
        })
        recording = true
        updatePosition()
    }

    private fun stopRecord() {
        startService(Intent(this, RecordingService::class.java).apply {
            action = RecordingService.ACTION_STOP
        })
        RecordingState.activeRecordNowUrl = null
        recording = false
        updatePosition()
    }

    private fun enterFullscreen() {
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        )
    }

    private fun formatTime(ms: Long): String {
        val total = (ms / 1000L).coerceAtLeast(0L)
        val h = total / 3600L
        val m = (total % 3600L) / 60L
        val s = total % 60L
        return if (h > 0L) {
            String.format(Locale.getDefault(), "%d:%02d:%02d", h, m, s)
        } else {
            String.format(Locale.getDefault(), "%02d:%02d", m, s)
        }
    }

    private fun formatSpeed(value: Float): String =
        if (value == value.toInt().toFloat()) value.toInt().toString() + "x"
        else String.format(Locale.getDefault(), "%.2fx", value)

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE -> {
                togglePlayback()
                return true
            }
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                engine?.seekBack(10_000L)
                return true
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                engine?.seekForward(10_000L)
                return true
            }
            KeyEvent.KEYCODE_BACK -> {
                finish()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onPictureInPictureModeChanged(
        isInPictureInPictureMode: Boolean,
        newConfig: Configuration
    ) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        binding.engineControls.visibility = if (isInPictureInPictureMode) View.GONE else View.VISIBLE
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        engine?.release()
        engine = null
        super.onDestroy()
    }
}
