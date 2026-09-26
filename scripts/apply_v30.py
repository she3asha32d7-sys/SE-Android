from pathlib import Path
import re

ROOT = Path(".")
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/VlcPlaybackEngine.kt"
s = p.read_text()

assert "private var hardwareAttempt = true" in s
assert "private var softwareRetryUsed = false" in s
s = s.replace("    private var hardwareAttempt = true\n", "    private var softwareDecoder = true\n", 1)
s = s.replace("    private var softwareRetryUsed = false\n", "", 1)

old_err = '''                        MediaPlayer.Event.EncounteredError -> {
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
'''
new_err = '''                        MediaPlayer.Event.EncounteredError -> {
                            buffering = false
                            log("EncounteredError; softwareDecoder=" + softwareDecoder)
                            errorCallback?.invoke(Exception("VLC playback error"))
                            stateCallback?.invoke(false, false)
                        }
'''
assert old_err in s
s = s.replace(old_err, new_err, 1)

old_prepare = '''        hardwareAttempt = true
        softwareRetryUsed = false
        loadMedia(url, currentStartPosition, useHardware = true)
'''
new_prepare = '''        // V30 starts VLC in software-decoding mode. This avoids the V29
        // hardware->software retry loop that repeatedly disturbed the video surface.
        softwareDecoder = true
        loadMedia(url, currentStartPosition, useHardware = false)
'''
assert old_prepare in s
s = s.replace(old_prepare, new_prepare, 1)

old_soft = '''            } else {
                setHWDecoderEnabled(false, false)
                addOption(":avcodec-hw=none")
            }
'''
new_soft = '''            } else {
                setHWDecoderEnabled(false, false)
                addOption(":avcodec-hw=none")
                addOption(":no-mediacodec-dr")
                addOption(":no-omxil-dr")
            }
'''
assert old_soft in s
s = s.replace(old_soft, new_soft, 1)

start = s.find("        // Delay play very slightly so VLC has completed its media assignment and vout binding.")
assert start >= 0, "V29 delayed-play block not found"
end = s.find("    private fun applyPendingSeek", start)
assert end >= 0, "applyPendingSeek anchor not found"
replacement = '''        // Do not call play() from prepare(). EnginePlayerActivity calls play() after
        // prepare(), and V29 was effectively issuing two play() calls. Keeping media
        // preparation and playback as separate operations also prevents a race with
        // the VLC video-output lifecycle.
        stateCallback?.invoke(false, true)
        log("media prepared, waiting for explicit play(); software=" + !useHardware)
    }

'''
s = s[:start] + replacement + s[end:]

old_play = '''    override fun play() { try { mediaPlayer?.play() } catch (t: Throwable) { errorCallback?.invoke(t) } }
'''
new_play = '''    override fun play() {
        if (released) return
        try {
            mediaPlayer?.play()
            stateCallback?.invoke(false, true)
            log("play() dispatched")
        } catch (t: Throwable) {
            log("play() failed: " + t)
            errorCallback?.invoke(t)
        }
    }
'''
assert old_play in s
s = s.replace(old_play, new_play, 1)

assert "hardwareAttempt" not in s
assert "softwareRetryUsed" not in s
assert 'setHWDecoderEnabled(false, false)' in s
assert ':avcodec-hw=none' in s
assert ':no-mediacodec-dr' in s
assert ':no-omxil-dr' in s
assert 'Retrying VLC with software decoder' not in s
assert 'Do not call play() from prepare()' in s

p.write_text(s)

g = ROOT / "app/build.gradle"
gs = g.read_text()
gs = re.sub(r'versionCode\s+\d+', 'versionCode 1000030', gs, count=1)
gs = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.30"', gs, count=1)
g.write_text(gs)

print("V100.0.30 VLC fix applied")
