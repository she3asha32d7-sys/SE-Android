from pathlib import Path
import os

root = Path(os.environ["ROOT"])

def must_replace(path, old, new, expected=1):
    p = root / path
    s = p.read_text(encoding="utf-8")
    count = s.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrences, found {count}")
    p.write_text(s.replace(old, new), encoding="utf-8")

# PlayerActivity: restore the missing reverse speed-playing tick implementation.
p = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = p.read_text(encoding="utf-8")
marker = "    private fun stopSpeedPlaying(restoreNormalPlayback: Boolean) {"
if "private fun performSpeedPlayingReverseStep()" not in s:
    method = """    private fun performSpeedPlayingReverseStep() {
        if (isLive || !::player.isInitialized || !speedPlaying || speedPlayingDirection >= 0) return
        val speed = normalizeSpeedPlayingSetting(PrefsManager.getPlaybackSpeed(this))
        val stepMs = (SPEED_PLAYING_REVERSE_TICK_MS * speed.toDouble())
            .toLong()
            .coerceAtLeast(1L)
        val target = (player.currentPosition - stepMs).coerceAtLeast(0L)
        player.seekTo(target)
    }

"""
    if s.count(marker) != 1:
        raise SystemExit("PlayerActivity stopSpeedPlaying marker missing")
    s = s.replace(marker, method + marker, 1)
    p.write_text(s, encoding="utf-8")

# Move accidentally top-level onDestroy() back inside each Activity class.
for rel in [
    "app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt",
    "app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt",
]:
    p = root / rel
    s = p.read_text(encoding="utf-8")
    bad = """
}

    override fun onDestroy() {
        FavouritesManager.unregisterListener(favouriteChangeListener)
        super.onDestroy()
    }
"""
    if bad not in s:
        raise SystemExit(f"{rel}: top-level onDestroy pattern not found")
    s = s.replace(bad, """
    override fun onDestroy() {
        FavouritesManager.unregisterListener(favouriteChangeListener)
        super.onDestroy()
    }
""", 1)
    s = s.rstrip() + "\n\n}\n"
    p.write_text(s, encoding="utf-8")

# Merge duplicate RecyclerView detach overrides while preserving listener cleanup and scope cleanup.
for rel in [
    "app/src/main/java/com/orbital/iptv/ui/series/SeriesAdapter.kt",
    "app/src/main/java/com/orbital/iptv/ui/vod/VodAdapter.kt",
]:
    p = root / rel
    s = p.read_text(encoding="utf-8")
    first = """    override fun onDetachedFromRecyclerView(recyclerView: RecyclerView) {
        FavouritesManager.unregisterListener(favouriteChangeListener)
        super.onDetachedFromRecyclerView(recyclerView)
    }"""
    second = """    override fun onDetachedFromRecyclerView(recyclerView: RecyclerView) {
        super.onDetachedFromRecyclerView(recyclerView)
        scope.cancel()
    }"""
    if s.count(first) != 1 or s.count(second) != 1:
        raise SystemExit(f"{rel}: expected duplicate detach methods")
    merged = """    override fun onDetachedFromRecyclerView(recyclerView: RecyclerView) {
        FavouritesManager.unregisterListener(favouriteChangeListener)
        super.onDetachedFromRecyclerView(recyclerView)
        scope.cancel()
    }"""
    s = s.replace(first, merged, 1).replace(second, "", 1)
    p.write_text(s, encoding="utf-8")

# FavouritesManager: keep the filtered list mutable so indexed replacement works.
must_replace(
    "app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt",
    "        val kept = list.filterNot { canonicalLogicalKey(it) == key && it.id != canonical.id }",
    "        val kept = list.filterNot { canonicalLogicalKey(it) == key && it.id != canonical.id }.toMutableList()"
)

# MovieDetailActivity needs the generated R class import.
p = root / "app/src/main/java/com/orbital/iptv/ui/vod/MovieDetailActivity.kt"
s = p.read_text(encoding="utf-8")
if "import com.orbital.iptv.R" not in s:
    s = s.replace("package com.orbital.iptv.ui.vod\n\n", "package com.orbital.iptv.ui.vod\n\nimport com.orbital.iptv.R\n", 1)
    p.write_text(s, encoding="utf-8")

print("V112 compile fixes applied")
