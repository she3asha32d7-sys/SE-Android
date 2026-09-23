from pathlib import Path
import re

ROOT = Path(__import__('sys').argv[1]).resolve()


def p(rel): return ROOT / rel
def read(rel): return p(rel).read_text(encoding='utf-8')
def write(rel, s): p(rel).write_text(s, encoding='utf-8')


def replace_once(rel, old, new):
    s = read(rel)
    if old not in s:
        raise RuntimeError(f'MISSING in {rel}: {old[:180]!r}')
    write(rel, s.replace(old, new, 1))


# Version / project metadata: v0.8 content becomes final v0.9.
replace_once('settings.gradle', 'rootProject.name = "SEAndroid_v100.0.7"', 'rootProject.name = "SEAndroid_v100.0.9"')
s = read('app/build.gradle').replace('versionCode 1000007', 'versionCode 1000009').replace('versionName "100.0.7"', 'versionName "100.0.9"')
write('app/build.gradle', s)

for rel in ['README.md', 'SE_BUILD_MANIFEST.txt', 'FINAL_33_AUDIT.md']:
    s = read(rel)
    s = s.replace('SEAndroid_v100.0.7', 'SEAndroid_v100.0.9')
    s = s.replace('SEAndroid_v100.0.6', 'SEAndroid_v100.0.9')
    s = s.replace('1000007', '1000009')
    s = s.replace('100.0.7', '100.0.9')
    write(rel, s)

# Remove any stale source-package workflow; the final build workflow is in the repository.
stale_workflow = p('.github/workflows/build-apk.yml')
if stale_workflow.exists():
    stale_workflow.unlink()

# Remove the small arrow beside Movies / Series / Live TV headers.
for rel in ['app/src/main/res/layout/activity_vod.xml', 'app/src/main/res/layout/activity_series.xml']:
    s = read(rel)
    s = re.sub(r'\s*<TextView android:id="@\+id/btn_category_back"[^>]+/>', '', s, count=1)
    write(rel, s)

rel = 'app/src/main/res/layout/activity_home.xml'
s = read(rel)
s = re.sub(r'\s*<TextView android:id="@\+id/btn_live_category_back"[^>]+/>', '', s, count=1)
write(rel, s)

for rel in ['app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt',
            'app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt']:
    s = read(rel)
    s = re.sub(
        r'\n\s*if\(categoryOnly\)\{binding\.root\.findViewById<View>\(R\.id\.main_sidebar_container\)\?\.visibility=View\.GONE;binding\.root\.findViewById<View>\(R\.id\.btn_category_back\)\?\.visibility=View\.VISIBLE;binding\.root\.findViewById<View>\(R\.id\.btn_category_back\)\?\.setOnClickListener\{openHome\(\)\}\}',
        '\n        if (categoryOnly) binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility = View.GONE',
        s, count=1)
    write(rel, s)

rel = 'app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt'
s = read(rel)
s = re.sub(
    r'\n\s*binding\.root\.findViewById<TextView>\(R\.id\.btn_live_category_back\)\?\.apply\{visibility=if\(home\) View\.GONE else View\.VISIBLE;setOnClickListener\{showSection\("HOME"\)\}\}',
    '', s, count=1)
s = re.sub(r'\s*else binding\.root\.findViewById<View>\(R\.id\.btn_live_category_back\)\?\.requestFocus\(\)', '', s, count=1)
s = s.replace('GridLayoutManager(this@HomeActivity, 2)', 'GridLayoutManager(this@HomeActivity, 1)', 1)
write(rel, s)

# Movie year already mirrors the Series card and releaseDate is already mapped in VodStream.
# Keep the explicit year+rating composition intact in VodAdapter.

# Search persistence shared by content screens during main-sidebar navigation.
search_state = '''package com.orbital.iptv.utils

import android.content.Context

/** Small per-screen search persistence used when the main sidebar reorders activities. */
object SearchStateManager {
    private const val PREFS = "se_search_state"

    fun save(context: Context, key: String, query: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(key, query).apply()
    }

    fun load(context: Context, key: String): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(key, "") ?: ""
}
'''
p('app/src/main/java/com/orbital/iptv/utils/SearchStateManager.kt').write_text(search_state, encoding='utf-8')

# VOD: preserve search text/results and refresh favorite hearts on return from Settings.
rel = 'app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt'
s = read(rel)
s = s.replace('import com.orbital.iptv.utils.PrefsManager\n',
              'import com.orbital.iptv.utils.PrefsManager\nimport com.orbital.iptv.utils.SearchStateManager\n', 1)
s = s.replace('''    private var showingFavourites = false

    override fun onCreate''', '''    private var showingFavourites = false

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) {
            val saved = SearchStateManager.load(this, "vod")
            if (binding.etSearch.text?.toString() != saved) {
                binding.etSearch.setText(saved)
                binding.etSearch.setSelection(binding.etSearch.text?.length ?: 0)
            }
            adapterOrRefreshFavorites()
        }
    }

    override fun onPause() {
        if (::binding.isInitialized) SearchStateManager.save(this, "vod", binding.etSearch.text?.toString().orEmpty())
        super.onPause()
    }

    private fun adapterOrRefreshFavorites() {
        if (!::adapter.isInitialized || !::viewModel.isInitialized) return
        adapter.notifyDataSetChanged()
        viewModel.uiState.value?.let { state ->
            if (state.categories.isNotEmpty()) buildCategoryMenu(state.categories, state.selectedCategory)
            if (showingFavourites) showFavouritesMovies() else if (showingContinue) showContinueWatching()
        }
    }

    override fun onCreate''', 1)
write(rel, s)

# SERIES: preserve search and refresh hearts; Favorites detail must use seriesId.
rel = 'app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt'
s = read(rel)
s = s.replace('import com.orbital.iptv.utils.PrefsManager\n',
              'import com.orbital.iptv.utils.PrefsManager\nimport com.orbital.iptv.utils.SearchStateManager\n', 1)
s = s.replace('''    private var showingFavourites = false

    override fun onCreate''', '''    private var showingFavourites = false

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) {
            val saved = SearchStateManager.load(this, "series")
            if (binding.etSearch.text?.toString() != saved) {
                binding.etSearch.setText(saved)
                binding.etSearch.setSelection(binding.etSearch.text?.length ?: 0)
            }
            adapterOrRefreshFavorites()
        }
    }

    override fun onPause() {
        if (::binding.isInitialized) SearchStateManager.save(this, "series", binding.etSearch.text?.toString().orEmpty())
        super.onPause()
    }

    private fun adapterOrRefreshFavorites() {
        if (!::adapter.isInitialized || !::viewModel.isInitialized) return
        adapter.notifyDataSetChanged()
        viewModel.uiState.value?.let { state ->
            if (state.categories.isNotEmpty()) buildCategoryMenu(state.categories, state.selectedCategory)
            when {
                showingFavourites -> showFavouritesSeries()
                showingContinue -> showContinueWatching()
            }
        }
    }

    override fun onCreate''', 1)
write(rel, s)

# HOME: preserve live search and refresh live/category hearts after Clear Favorite.
rel = 'app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt'
s = read(rel)
s = s.replace('import com.orbital.iptv.ui.settings.SettingsActivity\n',
              'import com.orbital.iptv.ui.settings.SettingsActivity\nimport com.orbital.iptv.utils.SearchStateManager\n', 1)
s = s.replace('''        ReminderBus.register { r -> showReminderDialog(r) }
    }

    override fun onPause() {''', '''        ReminderBus.register { r -> showReminderDialog(r) }
        if (::binding.isInitialized && ::liveAdapter.isInitialized) {
            val saved = SearchStateManager.load(this, "live")
            if (binding.etLiveSearch.text?.toString() != saved) {
                binding.etLiveSearch.setText(saved)
                binding.etLiveSearch.setSelection(binding.etLiveSearch.text?.length ?: 0)
            }
            liveAdapter.notifyDataSetChanged()
            viewModel.uiState.value?.let { state -> setupCategoryMenu(state.xtreamCategories, state.selectedXtreamCategory) }
        }
    }

    override fun onPause() {
        if (::binding.isInitialized) SearchStateManager.save(this, "live", binding.etLiveSearch.text?.toString().orEmpty())''', 1)
write(rel, s)

# GLOBAL SEARCH: preserve query and re-run the search after sidebar navigation.
rel = 'app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt'
s = read(rel)
s = s.replace('import androidx.recyclerview.widget.GridLayoutManager\n',
              'import androidx.recyclerview.widget.GridLayoutManager\nimport com.orbital.iptv.utils.SearchStateManager\n', 1)
s = s.replace('''    override fun onCreate(savedInstanceState: Bundle?) {''', '''    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) {
            val saved = SearchStateManager.load(this, "global")
            if (binding.etSearch.text?.toString() != saved) {
                binding.etSearch.setText(saved)
                binding.etSearch.setSelection(binding.etSearch.text?.length ?: 0)
            }
            val q = saved.trim()
            if (q.length >= 2 && q != lastSearchQuery) doSearch(q) else if (q.isBlank()) showHint()
        }
    }

    override fun onPause() {
        if (::binding.isInitialized) SearchStateManager.save(this, "global", binding.etSearch.text?.toString().orEmpty())
        super.onPause()
    }

    override fun onCreate(savedInstanceState: Bundle?) {''', 1)
write(rel, s)

# FAVORITES -> SERIES: current model stores the canonical series id in seriesId, while streamId is 0.
rel = 'app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt'
s = read(rel)
old = ''' private fun openSeries(i:FavouriteItem){val p=profileFor(i)?:return;startActivity(Intent(this,com.orbital.iptv.ui.series.SeriesDetailActivity::class.java).apply{
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_ID,i.streamId)'''
new = ''' private fun openSeries(i:FavouriteItem){val p=profileFor(i)?:return;val resolvedSeriesId=i.seriesId.takeIf{it>0}?:i.streamId;if(resolvedSeriesId<=0)return;startActivity(Intent(this,com.orbital.iptv.ui.series.SeriesDetailActivity::class.java).apply{
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_ID,resolvedSeriesId)'''
if old not in s:
    raise RuntimeError('Favorites openSeries block not found')
s = s.replace(old, new, 1)
write(rel, s)

# Xtream API: tolerate a null response body and expose a useful failure instead of Retrofit's
# generated "response ... was null" exception.
rel = 'app/src/main/java/com/orbital/iptv/data/api/XtreamApiService.kt'
s = read(rel).replace('''    ): SeriesInfoResponse
}''', '''    ): SeriesInfoResponse?
}''')
write(rel, s)
rel = 'app/src/main/java/com/orbital/iptv/data/repository/XtreamRepository.kt'
s = read(rel)
old = '''            Result.success(ApiClient.getService(serverUrl).getSeriesInfo(username, password, seriesId = seriesId))'''
new = '''            val body = ApiClient.getService(serverUrl).getSeriesInfo(username, password, seriesId = seriesId)
            if (body == null) Result.failure(IllegalStateException("SERIES INFO EMPTY FOR ID $seriesId"))
            else Result.success(body)'''
if old not in s:
    raise RuntimeError('Series repository call not found')
write(rel, s.replace(old, new, 1))

# Preserve the historically fixed About screen version V10.0.1.

# Xtream login logo +25%.
rel = 'app/src/main/res/layout/activity_login.xml'
s = read(rel).replace('android:layout_width="96dp"\n            android:layout_height="96dp"',
                      'android:layout_width="120dp"\n            android:layout_height="120dp"', 1)
write(rel, s)

# Launcher icon: use the full SE IPTV PLAYER artwork as the adaptive foreground so the text is visible.
rel = 'app/src/main/res/drawable/se_launcher_scaled.xml'
s = read(rel).replace(
    'android:drawable="@drawable/se_launcher" android:scaleWidth="130%" android:scaleHeight="130%"',
    'android:drawable="@drawable/se_logo_full" android:scaleWidth="90%" android:scaleHeight="90%"', 1)
write(rel, s)

print("V09 PATCH APPLIED")
