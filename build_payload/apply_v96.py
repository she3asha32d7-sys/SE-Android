from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()

def replace_once(path, old, new):
    p = ROOT / path
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"Missing expected block in {path}")
    p.write_text(s.replace(old, new, 1))

replace_once("app/src/main/res/layout/activity_movie_detail.xml",
    'android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:clipToPadding="false"',
    'android:layout_height="0dp" android:layout_weight="1" android:fillViewport="false" android:clipToPadding="false"')
replace_once("app/src/main/res/layout/activity_movie_detail.xml",
    'android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="900dp" android:layout_margin="28dp" android:background="@color/se_panel" android:padding="26dp"',
    'android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_margin="20dp" android:background="@color/se_panel" android:padding="20dp"')
replace_once("app/src/main/res/layout/activity_movie_detail.xml",
    '<LinearLayout android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="horizontal">',
    '<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal">')
replace_once("app/src/main/res/layout/activity_movie_detail.xml",
    'android:layout_width="286dp" android:layout_height="429dp" android:background="#101B35"',
    'android:layout_width="260dp" android:layout_height="390dp" android:background="#101B35"')
replace_once("app/src/main/res/layout/activity_movie_detail.xml",
    '<LinearLayout android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:orientation="vertical">',
    '<LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:orientation="vertical">')

replace_once("app/src/main/res/layout/activity_series_detail.xml",
    'android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:clipToPadding="false"',
    'android:layout_height="0dp" android:layout_weight="1" android:fillViewport="false" android:clipToPadding="false"')
replace_once("app/src/main/res/layout/activity_series_detail.xml",
    'android:layout_width="match_parent" android:layout_height="360dp" android:orientation="horizontal" android:background="@color/se_panel" android:padding="20dp"',
    'android:layout_width="match_parent" android:layout_height="330dp" android:orientation="horizontal" android:background="@color/se_panel" android:padding="18dp"')
replace_once("app/src/main/res/layout/activity_series_detail.xml",
    'android:layout_width="240dp" android:layout_height="match_parent" android:background="#101B35"',
    'android:layout_width="220dp" android:layout_height="294dp" android:layout_gravity="center_vertical" android:background="#101B35"')
replace_once("app/src/main/res/layout/activity_series_detail.xml",
    'android:layout_width="match_parent" android:layout_height="52dp" android:layout_marginTop="18dp"',
    'android:layout_width="match_parent" android:layout_height="46dp" android:layout_marginTop="14dp"')
replace_once("app/src/main/res/layout/activity_series_detail.xml",
    'android:layout_width="match_parent" android:layout_height="520dp" android:layout_marginTop="8dp" android:focusable="true" android:descendantFocusability="afterDescendants" android:nestedScrollingEnabled="false"',
    'android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="56dp" android:layout_marginTop="6dp" android:focusable="true" android:descendantFocusability="afterDescendants" android:nestedScrollingEnabled="false"')

series = ROOT / "app/src/main/java/com/orbital/iptv/ui/series/SeriesDetailActivity.kt"
s = series.read_text()
anchor = """    private fun selectSeason(season: String) {
        selectedSeason = season
"""
helper = """    private fun updateEpisodeListHeight(episodeCount: Int) {
        val dp = resources.displayMetrics.density
        val rowHeight = (56 * dp).toInt()
        val rowCount = ((episodeCount + 1) / 2).coerceAtLeast(1)
        val maxRows = 6
        val boundedRows = rowCount.coerceAtMost(maxRows)
        val params = binding.rvEpisodes.layoutParams
        params.height = boundedRows * rowHeight
        binding.rvEpisodes.layoutParams = params
        binding.rvEpisodes.isNestedScrollingEnabled = rowCount > maxRows
    }

    private fun selectSeason(season: String) {
        selectedSeason = season
"""
if anchor not in s:
    raise SystemExit("selectSeason anchor not found")
s = s.replace(anchor, helper, 1)
old = """        episodeAdapter.submitList(sorted)
        // postDelayed gives RecyclerView time to bind ViewHolders before we query position 0.
"""
new = """        episodeAdapter.submitList(sorted)
        updateEpisodeListHeight(sorted.size)
        // postDelayed gives RecyclerView time to bind ViewHolders before we query position 0.
"""
if old not in s:
    raise SystemExit("episode submit block not found")
s = s.replace(old, new, 1)
series.write_text(s)

build = ROOT / "app/build.gradle"
s = build.read_text()
s = re.sub(r"versionCode\s+\d+", "versionCode 1000096", s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.96"', s, count=1)
build.write_text(s)

settings = ROOT / "settings.gradle"
s = settings.read_text()
s = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.96"', s, count=1)
settings.write_text(s)
print("V100.0.96 detail sizing fix applied")