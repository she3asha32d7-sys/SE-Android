from pathlib import Path

ROOT = Path(".")

def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def replace(rel, old, new):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    if old in s:
        s = s.replace(old, new, 1)
        p.write_text(s, encoding="utf-8")

# XML: keep the PlayerView element and remove only the unsupported attribute.
replace(
    "app/src/main/res/layout/activity_home.xml",
    ' android:useController="false"',
    ""
)

# HomeActivity compile fixes.
replace(
    "app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt",
    'binding.root.findViewById<View>(R.id.tv_sidebar_time)?.let { (it as TextView).setTextColor(p.accent) }\n',
    ""
)
replace(
    "app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt",
    "android.widget.HorizontalScrollView.LayoutParams(-1, (64*d).toInt())",
    "ViewGroup.LayoutParams(-1, (64*d).toInt())"
)

# PlayerActivity: merge duplicate onPause implementations.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = p.read_text(encoding="utf-8")
duplicate = "    override fun onPause(){ super.onPause(); saveWatchHistory() }\n"
if duplicate in s:
    block = """        if (isLive) {
            RecordingState.unregisterStopLiveTv()
        }
    }
"""
    merged = """        if (isLive) {
            RecordingState.unregisterStopLiveTv()
        }
        saveWatchHistory()
    }
"""
    if block in s:
        s = s.replace(block, merged, 1)
    s = s.replace(duplicate, "", 1)
    p.write_text(s, encoding="utf-8")

# SeriesActivity imports.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt"
s = p.read_text(encoding="utf-8")
if "import com.orbital.iptv.R\n" not in s:
    s = s.replace("import com.orbital.iptv.databinding.ActivitySeriesBinding\n",
                  "import com.orbital.iptv.databinding.ActivitySeriesBinding\nimport com.orbital.iptv.R\n", 1)
s = s.replace(
    "import com.orbital.iptv.utils.WatchHistoryManager.Section\n",
    "import com.orbital.iptv.utils.MainSidebarController.Section\n"
)
p.write_text(s, encoding="utf-8")

# SeriesDetailActivity import.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/series/SeriesDetailActivity.kt"
s = p.read_text(encoding="utf-8")
if "import com.orbital.iptv.utils.PrefsManager\n" not in s:
    s = s.replace("import com.orbital.iptv.utils.PlayerLauncher\n",
                  "import com.orbital.iptv.utils.PlayerLauncher\nimport com.orbital.iptv.utils.PrefsManager\n", 1)
p.write_text(s, encoding="utf-8")

# VodActivity imports and generated R reference.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt"
s = p.read_text(encoding="utf-8")
if "import com.orbital.iptv.R\n" not in s:
    s = s.replace("import com.orbital.iptv.databinding.ActivityVodBinding\n",
                  "import com.orbital.iptv.databinding.ActivityVodBinding\nimport com.orbital.iptv.R\n", 1)
s = s.replace(
    "import com.orbital.iptv.ui.settings.SettingsActivity.Section\n",
    "import com.orbital.iptv.utils.MainSidebarController.Section\n"
)
s = s.replace(
    "com.orbital.iptv.com.orbital.iptv.R.id.tv_header_datetime",
    "R.id.tv_header_datetime"
)
p.write_text(s, encoding="utf-8")

# ListUsersActivity malformed LayoutParams.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/users/ListUsersActivity.kt"
s = p.read_text(encoding="utf-8")
old = """card.addView(host, LinearLayout.LayoutParams
            .apply { topMargin=(3*density).toInt() })
        card.addView(username, LinearLayout.LayoutParams
            .apply { topMargin=(3*density).toInt() })
        card.addView(password, LinearLayout.LayoutParams
            .apply { topMargin=(3*density).toInt() })
"""
new = """card.addView(host, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).also { it.topMargin=(3*density).toInt() })
        card.addView(username, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).also { it.topMargin=(3*density).toInt() })
        card.addView(password, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).also { it.topMargin=(3*density).toInt() })
"""
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")

# WatchHistoryManager: make Gson typing explicit and keep history operations valid under Kotlin 1.9.
write(
    "app/src/main/java/com/orbital/iptv/utils/WatchHistoryManager.kt",
    '''package com.orbital.iptv.utils

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

data class WatchHistoryItem(
    val id: String,
    val type: String,
    val title: String,
    val artUrl: String = "",
    val streamUrl: String = "",
    val streamId: Int = -1,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val updatedAt: Long = System.currentTimeMillis()
)

object WatchHistoryManager {
    private const val PREFS = "se_watch_history"
    private const val KEY = "items"
    private const val MAX = 15

    private val gson = Gson()
    private val listType = object : TypeToken<List<WatchHistoryItem>>() {}.type

    private fun prefs(c: Context) =
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun load(c: Context): List<WatchHistoryItem> {
        val raw = prefs(c).getString(KEY, null) ?: return emptyList()
        return try {
            gson.fromJson<List<WatchHistoryItem>>(raw, listType) ?: emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun get(c: Context, type: String): List<WatchHistoryItem> =
        load(c)
            .filter { it.type == type }
            .sortedByDescending { it.updatedAt }
            .take(MAX)

    fun record(c: Context, item: WatchHistoryItem) {
        val list = load(c).filterNot { it.id == item.id }.toMutableList()
        list.add(0, item.copy(updatedAt = System.currentTimeMillis()))
        prefs(c).edit().putString(KEY, gson.toJson(list.take(100), listType)).apply()
    }

    fun update(c: Context, id: String, pos: Long, dur: Long) {
        val list = load(c).toMutableList()
        val index = list.indexOfFirst { it.id == id }
        if (index < 0) return

        list[index] = list[index].copy(
            positionMs = pos,
            durationMs = dur,
            updatedAt = System.currentTimeMillis()
        )
        prefs(c).edit().putString(KEY, gson.toJson(list, listType)).apply()
    }

    fun remove(c: Context, id: String) {
        val list = load(c).filterNot { it.id == id }
        prefs(c).edit().putString(KEY, gson.toJson(list, listType)).apply()
    }

    fun clear(c: Context) {
        prefs(c).edit().clear().apply()
    }
}
'''
)
