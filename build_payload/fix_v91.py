from pathlib import Path

def replace_exact(path: str, old: str, new: str, expected: int | None = None) -> None:
    p = Path(path)
    s = p.read_text()
    count = s.count(old)
    if expected is not None and count != expected:
        raise SystemExit(f"{path}: expected {expected} replacements, found {count} for {old!r}")
    if count:
        s = s.replace(old, new)
        p.write_text(s)

# Main sidebar Kotlin 2.1+ compatibility: typed function references cannot carry type args.
replace_exact(
    "app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt",
    "?.let(root::findViewById<TextView>) ?: return",
    "?.let { root.findViewById<TextView>(it) } ?: return",
    expected=2,
)

# Downloads compile fixes.
p = Path("app/src/main/java/com/orbital/iptv/ui/downloads/DownloadsActivity.kt")
s = p.read_text()
needle = "import com.orbital.iptv.utils.DownloadItem"
if "import com.orbital.iptv.utils.DownloadFileOperations" not in s:
    s = s.replace(needle, "import com.orbital.iptv.utils.DownloadFileOperations\n" + needle)
p.write_text(s)

replace_exact(
    "app/src/main/java/com/orbital/iptv/utils/DownloadFileOperations.kt",
    "delete(context, sourceUri)",
    "delete(context, source.uri)",
    expected=1,
)

# RecordingService: correct coroutine activity check and FileOutputStream append API.
p = Path("app/src/main/java/com/orbital/iptv/recording/RecordingService.kt")
s = p.read_text()
for old in ("while (isActive)", "if (!isActive)"):
    s = s.replace(old, old.replace("isActive", "currentCoroutineContext().isActive"))
s = s.replace(
    "java.io.BufferedOutputStream(file.outputStream(append), 128 * 1024)",
    "java.io.BufferedOutputStream(java.io.FileOutputStream(file, append), 128 * 1024)"
)
p.write_text(s)

# PlayerActivity compile corrections while preserving the v91 player behavior.
p = Path("app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt")
s = p.read_text()

s = s.replace(
    "stopPlayerRecording(exitAfter = true)",
    "stopDirectPlayerRecording()",
)

s = s.replace(
    "            player.setSeekBackIncrementMs(seekStepMs)\n"
    "            player.setSeekForwardIncrementMs(seekStepMs)",
    "            localPlayer.setSeekBackIncrementMs(seekStepMs)\n"
    "            localPlayer.setSeekForwardIncrementMs(seekStepMs)",
)

# Move the v91 gesture constants into PlayerActivity.companion object.
top_level_constants = """    private const val SEEK_SIDE_TAP_DELAY_MS = 320L
    private const val SEEK_SIDE_LONG_PRESS_MS = 500L
    private const val SEEK_SIDE_REPEAT_MS = 180L
    private const val SPEED_PLAYING_REVERSE_TICK_MS = 100L
    private const val SIDE_GESTURE_START_DISTANCE_DP = 22
    private const val SIDE_GESTURE_BRIGHTNESS_STEP_DP = 14
    private const val SIDE_GESTURE_VOLUME_STEP_DP = 18
    private const val GESTURE_HUD_HIDE_MS = 1200L
"""
if s.count(top_level_constants) == 1:
    s = s.replace(top_level_constants, "")
elif s.count(top_level_constants) != 0:
    raise SystemExit("Unexpected duplicate gesture constant block in PlayerActivity.kt")

companion_anchor = "        private val COLOR_LIVE      = 0xFFFF2222.toInt()\n"
companion_constants = """        private val COLOR_LIVE      = 0xFFFF2222.toInt()

        private const val SEEK_SIDE_TAP_DELAY_MS = 320L
        private const val SEEK_SIDE_LONG_PRESS_MS = 500L
        private const val SEEK_SIDE_REPEAT_MS = 180L
        private const val SPEED_PLAYING_REVERSE_TICK_MS = 100L
        private const val SIDE_GESTURE_START_DISTANCE_DP = 22
        private const val SIDE_GESTURE_BRIGHTNESS_STEP_DP = 14
        private const val SIDE_GESTURE_VOLUME_STEP_DP = 18
        private const val GESTURE_HUD_HIDE_MS = 1200L
"""
if companion_constants not in s:
    if companion_anchor not in s:
        raise SystemExit("PlayerActivity companion anchor not found")
    s = s.replace(companion_anchor, companion_constants, 1)

# Add player width helper used by side gesture hit testing.
if "private fun widthOfPlayer(): Float" not in s:
    anchor = "    private fun isInSideSeekZone(x: Float, y: Float): Boolean {"
    helper = "    private fun widthOfPlayer(): Float = binding.root.width.toFloat().coerceAtLeast(1f)\n\n"
    if anchor not in s:
        raise SystemExit("PlayerActivity side-seek anchor not found")
    s = s.replace(anchor, helper + anchor, 1)

# Palette does not expose textPrimary in this project.
s = s.replace("ThemeManager.palette().textPrimary", "0xFFFFFFFF.toInt()")

p.write_text(s)

# Final assertions.
checks = {
    "app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt": [
        "?.let { root.findViewById<TextView>(it) } ?: return"
    ],
    "app/src/main/java/com/orbital/iptv/ui/downloads/DownloadsActivity.kt": [
        "import com.orbital.iptv.utils.DownloadFileOperations"
    ],
    "app/src/main/java/com/orbital/iptv/recording/RecordingService.kt": [
        "currentCoroutineContext().isActive",
        "java.io.FileOutputStream(file, append)"
    ],
    "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt": [
        "stopDirectPlayerRecording()",
        "localPlayer.setSeekBackIncrementMs(seekStepMs)",
        "private const val SEEK_SIDE_TAP_DELAY_MS = 320L",
        "private fun widthOfPlayer(): Float",
        "0xFFFFFFFF.toInt()"
    ],
    "app/src/main/java/com/orbital/iptv/utils/DownloadFileOperations.kt": [
        "delete(context, source.uri)"
    ],
}
for fn, needles in checks.items():
    txt = Path(fn).read_text()
    for needle in needles:
        if needle not in txt:
            raise SystemExit(f"Missing expected build fix in {fn}: {needle}")

print("v100.0.91 compile-fix script completed successfully.")
