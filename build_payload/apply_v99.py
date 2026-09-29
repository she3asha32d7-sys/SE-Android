from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()
player = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = player.read_text()

new = '''    // Speed Playing is available only after a non-1x speed is selected in the player UI.
    // The action starts only after the Android long-press timeout while the finger remains down.
    private val sideSeekLongPressRunnable = Runnable {
        if (sideSeekPointerDown && pendingSideSeekSide != 0 && !isLive) {
            if (startSpeedPlayingIfEnabled(pendingSideSeekSide)) {
                sideSeekLongPressActive = true
                sideSeekHandler.removeCallbacks(sideSeekSingleRunnable)
            }
        }
    }
    private val sideSeekRepeatRunnable = object : Runnable {
        override fun run() = Unit
    }
'''
start = s.find('    private val sideSeekLongPressRunnable = Runnable {')
end = s.find('    private val sideSeekRepeatRunnable', start)
if start < 0 or end < 0:
    raise SystemExit("Speed Playing runnable anchors not found")
end = s.find('    }', end) + len('    }')
s = s[:start] + new + s[end:]
if old not in s:
    raise SystemExit("V98 disabled long-press block not found")
s = s.replace(old, new, 1)

old = '''                lastTapAt = now
                sideSeekHandler.postDelayed(sideSeekSingleRunnable, SEEK_SIDE_TAP_DELAY_MS)
                return true
'''
new = '''                lastTapAt = now
                sideSeekHandler.postDelayed(sideSeekSingleRunnable, SEEK_SIDE_TAP_DELAY_MS)
                if (!isLive) {
                    val longPressTimeout = android.view.ViewConfiguration.getLongPressTimeout().toLong()
                    sideSeekHandler.postDelayed(sideSeekLongPressRunnable, longPressTimeout)
                }
                return true
'''
if old not in s:
    raise SystemExit("V98 ACTION_DOWN scheduling block not found")
s = s.replace(old, new, 1)

old = '''                if (sideSeekPointerDown) {
                    sideSeekPointerDown = false
                    // Do not seek on ACTION_UP. A single tap remains a controls-only action;
                    // the delayed runnable determines that it was not followed by a second tap.
                    if (e.actionMasked == MotionEvent.ACTION_CANCEL) {
                        resetSideTouchState()
                    }
                    return true
                }
'''
new = '''                if (sideSeekPointerDown) {
                    sideSeekHandler.removeCallbacks(sideSeekLongPressRunnable)
                    if (sideSeekLongPressActive) {
                        stopSpeedPlaying(restoreNormalPlayback = true)
                        sideSeekLongPressActive = false
                        resetSideTouchState()
                        return true
                    }

                    sideSeekPointerDown = false
                    // Do not seek on ACTION_UP. A single tap remains a controls-only action;
                    // a long press at 1x intentionally does nothing.
                    if (e.actionMasked == MotionEvent.ACTION_CANCEL) {
                        resetSideTouchState()
                    }
                    return true
                }
'''
if old not in s:
    raise SystemExit("V98 ACTION_UP block not found")
s = s.replace(old, new, 1)

old = '''        if (isLive || !::player.isInitialized || !player.isPlaying) return false
        val speed = normalizeSpeedPlayingSetting(PrefsManager.getPlaybackSpeed(this))
        if (kotlin.math.abs(speed - 1f) < 0.001f) return false
'''
new = '''        if (isLive || !::player.isInitialized || !player.isPlaying) return false

        // Speed Playing is disabled at the default 1x. It can only be enabled by
        // explicitly selecting another value from the SPEED PLAYING control.
        val speed = normalizeSpeedPlayingSetting(PrefsManager.getPlaybackSpeed(this))
        if (kotlin.math.abs(speed - 1f) < 0.001f) return false
'''
if old not in s:
    raise SystemExit("speed eligibility block not found")
s = s.replace(old, new, 1)

build = ROOT / "app/build.gradle"
bs = build.read_text()
bs = re.sub(r"versionCode\s+\d+", "versionCode 1000099", bs, count=1)
bs = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.99"', bs, count=1)
build.write_text(bs)

settings = ROOT / "settings.gradle"
ss = settings.read_text()
ss = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.99"', ss, count=1)
settings.write_text(ss)

print("V100.0.99 Speed Playing long-press fix applied")
