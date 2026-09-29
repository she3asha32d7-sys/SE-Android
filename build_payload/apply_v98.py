from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = p.read_text()

# One playback session has one "first double-tap opens the picker" opportunity.
# After a value is chosen, later double taps seek using that same value until this
# PlayerActivity/video ends. Pressing the +/- SEEK buttons always opens the picker again.
anchor='''    private var seekStepMs = DEFAULT_SEEK_STEP_MS
    private var showRemainingOnLeft = false
'''
replacement='''    private var seekStepMs = DEFAULT_SEEK_STEP_MS
    private var seekPickerArmedForSideDoubleTap = true
    private var showRemainingOnLeft = false
'''
if anchor not in s:
    raise SystemExit("seekStep field anchor not found")
s=s.replace(anchor,replacement,1)

# A single tap on the player never hides the UI; it only shows it.
old='''        binding.gencPlayerView.setOnClickListener {
            if (isGencMode()) {
                if (binding.gencPlayerOverlayInclude.root.visibility == View.VISIBLE) hideGencOverlay() else showGencOverlay()
            }
        }
'''
new='''        binding.gencPlayerView.setOnClickListener {
            if (isGencMode()) showGencOverlay()
        }
'''
if old not in s:
    raise SystemExit("player single-tap listener not found")
s=s.replace(old,new,1)

# Replace the old side-tap/long-press behavior. Side vertical swipes continue to
# control brightness/volume. Side taps now have exactly two states:
#   1) first double tap before a choice -> picker
#   2) all later double taps -> seek by selected step
# The first single tap only reveals the controls.
start=s.find('    private val sideSeekSingleRunnable = Runnable {')
end=s.find('    private fun startSpeedPlayingIfEnabled(side: Int): Boolean {', start)
if start < 0 or end < 0:
    raise SystemExit("side seek runnable region not found")
new_runnables='''    private val sideSeekSingleRunnable = Runnable {
        if (!sideSeekPointerDown && pendingSideSeekSide != 0) {
            showGencOverlay()
            pendingSideSeekSide = 0
            lastTapAt = 0L
        }
    }

    // Side long-press no longer performs seek/speed-playing. Long-press behavior conflicted
    // with the requested rule that a single tap only reveals the player controls.
    private val sideSeekLongPressRunnable = Runnable { }
    private val sideSeekRepeatRunnable = object : Runnable {
        override fun run() = Unit
    }

'''
s=s[:start]+new_runnables+s[end:]

# Replace the entire Activity touch dispatcher with explicit tap semantics.
start=s.find('    override fun dispatchTouchEvent(e: MotionEvent): Boolean {')
end=s.find('    private fun showSeekStepPicker() {', start)
if start < 0 or end < 0:
    raise SystemExit("dispatchTouchEvent region not found")

dispatch='''    override fun dispatchTouchEvent(e: MotionEvent): Boolean {
        if (!::binding.isInitialized) return super.dispatchTouchEvent(e)

        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                if (!isInSideSeekZone(e.x, e.y)) {
                    return super.dispatchTouchEvent(e)
                }

                val side = if (e.x < widthOfPlayer() / 3f) -1 else 1
                val now = android.os.SystemClock.uptimeMillis()
                val isDoubleTap = !isLive &&
                    pendingSideSeekSide == side &&
                    lastTapAt > 0L &&
                    now - lastTapAt <= SEEK_SIDE_TAP_DELAY_MS

                resetSideTouchState()
                sideSeekPointerDown = true
                pendingSideSeekSide = side
                pendingSideSeekX = e.x
                pendingSideSeekY = e.y

                if (isDoubleTap) {
                    // Second tap completes the double tap. Do not let the first-tap timer
                    // fire after the picker/seek action.
                    sideSeekPointerDown = false
                    pendingSideSeekSide = 0
                    lastTapAt = 0L
                    sideSeekHandler.removeCallbacks(sideSeekSingleRunnable)
                    if (seekPickerArmedForSideDoubleTap) {
                        showSeekStepPicker()
                    } else {
                        performSideSeek(side)
                    }
                    return true
                }

                // First tap: wait briefly to see whether a second tap arrives. If not,
                // the runnable only reveals the media-player controls.
                lastTapAt = now
                sideSeekHandler.postDelayed(sideSeekSingleRunnable, SEEK_SIDE_TAP_DELAY_MS)
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                if (!sideSeekPointerDown) return super.dispatchTouchEvent(e)

                if (sideAdjustmentActive) {
                    updateSideAdjustment(e.y)
                    return true
                }

                val dx = kotlin.math.abs(e.x - pendingSideSeekX)
                val dy = kotlin.math.abs(e.y - pendingSideSeekY)
                val startDistance = dp(SIDE_GESTURE_START_DISTANCE_DP).toFloat()

                // Keep vertical brightness/volume gestures. They are separate from tap counting.
                if (dy >= startDistance && dy > dx) {
                    sideSeekHandler.removeCallbacks(sideSeekSingleRunnable)
                    beginSideAdjustment(pendingSideSeekSide, pendingSideSeekY)
                    updateSideAdjustment(e.y)
                    return true
                }

                // Horizontal swipes are not seek gestures anymore. Cancel the tap sequence
                // so a swipe never accidentally triggers a double-tap seek.
                if (dx >= startDistance && dx >= dy) {
                    sideSeekHandler.removeCallbacks(sideSeekSingleRunnable)
                    sideSeekPointerDown = false
                    pendingSideSeekSide = 0
                    lastTapAt = 0L
                }
                return true
            }

            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                if (sideAdjustmentActive) {
                    finishSideAdjustment()
                    resetSideTouchState()
                    return true
                }

                if (sideSeekPointerDown) {
                    sideSeekPointerDown = false
                    // Do not seek on ACTION_UP. A single tap remains a controls-only action;
                    // the delayed runnable determines that it was not followed by a second tap.
                    if (e.actionMasked == MotionEvent.ACTION_CANCEL) {
                        resetSideTouchState()
                    }
                    return true
                }
            }
        }

        return super.dispatchTouchEvent(e)
    }

'''
s=s[:start]+dispatch+s[end:]

# Selecting any new value consumes the one-time first-double-tap picker state.
old='''                    seekStepMs = values[index]
                    PrefsManager.setSeekStepMs(this@PlayerActivity, seekStepMs)
                    updateSeekStepButton()
'''
new='''                    seekStepMs = values[index]
                    seekPickerArmedForSideDoubleTap = false
                    PrefsManager.setSeekStepMs(this@PlayerActivity, seekStepMs)
                    updateSeekStepButton()
'''
if old not in s:
    raise SystemExit("seek picker selection block not found")
s=s.replace(old,new,1)

# Explicitly keep the displayed +/- SEEK labels synchronized when controls are initialized.
old='''        b.btnGencDownload.visibility = if (!isLive && streamUrl.isNotBlank()) View.VISIBLE else View.GONE
'''
new='''        b.btnGencDownload.visibility = if (!isLive && streamUrl.isNotBlank()) View.VISIBLE else View.GONE
        updateSeekStepButton()
'''
if old not in s:
    raise SystemExit("Genc download anchor not found")
s=s.replace(old,new,1)

# Version 100.0.98.
build=ROOT/"app/build.gradle"
bs=build.read_text()
bs=re.sub(r'versionCode\s+\d+','versionCode 1000098',bs,count=1)
bs=re.sub(r'versionName\s+"[^"]+"','versionName "100.0.98"',bs,count=1)
build.write_text(bs)
settings=ROOT/"settings.gradle"
ss=settings.read_text()
ss=re.sub(r'rootProject\.name\s*=\s*"[^"]+"','rootProject.name = "SEAndroid_v100.0.98"',ss,count=1)
settings.write_text(ss)

print("V100.0.98 seek behavior updated")
