from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()
player = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = player.read_text()

# Replace the whole side long-press runnable block by structural anchors, so the
# patch remains valid even if V98 whitespace/comments differ.
start = s.find("    private val sideSeekLongPressRunnable = Runnable {")
end = s.find("    private fun startSpeedPlayingIfEnabled", start)
if start < 0 or end < 0:
    raise SystemExit("V99: Speed Playing insertion anchors not found")

new_runnable = '''    // Speed Playing starts only when a non-1x speed is selected and the pointer is held.
    private val sideSeekLongPressRunnable = Runnable {
        if (sideSeekPointerDown && pendingSideSeekSide != 0 && !isLive) {
            if (startSpeedPlayingIfEnabled(pendingSideSeekSide)) {
                sideSeekLongPressActive = true
                sideSeekHandler.removeCallbacks(sideSeekSingleRunnable)
            }
        }
    }

'''
s = s[:start] + new_runnable + s[end:]

# Ensure ACTION_DOWN schedules the platform long-press timeout. Work from the
# existing first-tap scheduling line so the change survives V98 formatting.
needle = "sideSeekHandler.postDelayed(sideSeekSingleRunnable, SEEK_SIDE_TAP_DELAY_MS)"
pos = s.find(needle)
if pos < 0:
    raise SystemExit("V99: first-tap scheduling line not found")
line_end = s.find("\n", pos)
addition = '''                if (!isLive) {
                    val longPressTimeout = android.view.ViewConfiguration.getLongPressTimeout().toLong()
                    sideSeekHandler.postDelayed(sideSeekLongPressRunnable, longPressTimeout)
                }'''
if "sideSeekHandler.postDelayed(sideSeekLongPressRunnable" not in s[pos:line_end+300]:
    s = s[:line_end+1] + addition + "\n" + s[line_end+1:]

# Replace the side ACTION_UP handling structurally: stop Speed Playing on release
# when it was active; at 1x no action occurs.
pat = re.compile(
    r'''                if \(sideSeekPointerDown\) \{\n'''
    r'''(?:(?:                    .*\n)|(?:\n))*?'''
    r'''                \}\n(?=\s*}\n\s*}\n\s*return super\.dispatchTouchEvent)''',
    re.MULTILINE
)
matches = list(pat.finditer(s))
if not matches:
    # Use a narrower anchor starting at the final branch in dispatchTouchEvent.
    marker = "                if (sideSeekPointerDown) {"
    m = list(re.finditer(re.escape(marker), s))
    if not m:
        raise SystemExit("V99: ACTION_UP pointer block not found")
    # Last occurrence is the ACTION_UP branch.
    up_start = m[-1].start()
    up_end = s.find("\n                }\n            }\n        }\n        return super.dispatchTouchEvent", up_start)
    if up_end < 0:
        raise SystemExit("V99: ACTION_UP end anchor not found")
    up_end += len("\n                }")
else:
    up_start = matches[-1].start()
    up_end = matches[-1].end()

new_up = '''                if (sideSeekPointerDown) {
                    sideSeekHandler.removeCallbacks(sideSeekLongPressRunnable)
                    sideSeekHandler.removeCallbacks(sideSeekRepeatRunnable)

                    if (sideSeekLongPressActive) {
                        stopSpeedPlaying(restoreNormalPlayback = true)
                        sideSeekLongPressActive = false
                        resetSideTouchState()
                        return true
                    }

                    sideSeekPointerDown = false
                    if (e.actionMasked == MotionEvent.ACTION_CANCEL) {
                        resetSideTouchState()
                    }
                    return true
                }'''
s = s[:up_start] + new_up + s[up_end:]

# Make the 1x guard explicit and defensive inside the existing helper.
needle = "val speed = normalizeSpeedPlayingSetting(PrefsManager.getPlaybackSpeed(this))"
p = s.find(needle)
if p < 0:
    raise SystemExit("V99: speed lookup not found")
guard = "if (kotlin.math.abs(speed - 1f) < 0.001f) return false"
gpos = s.find(guard, p)
if gpos < 0:
    endline = s.find("\n", p)
    s = s[:endline+1] + "        // Default 1x explicitly disables Speed Playing.\\n        " + guard + "\\n" + s[endline+1:]
    # The comment+guard is intentionally inserted after the speed lookup.

build = ROOT / "app/build.gradle"
bs = build.read_text()
bs = re.sub(r"versionCode\s+\d+", "versionCode 1000099", bs, count=1)
bs = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.99"', bs, count=1)
build.write_text(bs)

settings = ROOT / "settings.gradle"
ss = settings.read_text()
ss = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.99"', ss, count=1)
settings.write_text(ss)

print("V100.0.99 robust Speed Playing patch applied")
