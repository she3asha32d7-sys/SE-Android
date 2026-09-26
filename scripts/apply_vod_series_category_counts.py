from pathlib import Path

def replace_once(path: Path, old: str, new: str):
    s = path.read_text()
    if old not in s:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    path.write_text(s.replace(old, new, 1))

# Movies: add a Live-TV-style count footer under the category sidebar.
p = Path("app/src/main/res/layout/activity_vod.xml")
s = p.read_text()
old = """            </ScrollView>
        </LinearLayout>
        <View android:layout_width="2dp" android:layout_height="match_parent" android:background="@color/sky_cyan"/>"""
new = """            </ScrollView>
            <LinearLayout android:layout_width="match_parent" android:layout_height="36dp" android:gravity="center_vertical" android:paddingStart="12dp">
                <TextView android:id="@+id/tv_movie_count" android:layout_width="wrap_content" android:layout_height="wrap_content"
                    android:text="0 MOVIES" android:textColor="@color/sky_cyan" android:textSize="9sp" android:textStyle="bold" />
            </LinearLayout>
        </LinearLayout>
        <View android:layout_width="2dp" android:layout_height="match_parent" android:background="@color/sky_cyan"/>"""
replace_once(p, old, new)

# Series: same footer.
p = Path("app/src/main/res/layout/activity_series.xml")
s = p.read_text()
old = """            </ScrollView>
        </LinearLayout>
        <View android:layout_width="2dp" android:layout_height="match_parent" android:background="@color/sky_cyan"/>"""
new = """            </ScrollView>
            <LinearLayout android:layout_width="match_parent" android:layout_height="36dp" android:gravity="center_vertical" android:paddingStart="12dp">
                <TextView android:id="@+id/tv_series_count" android:layout_width="wrap_content" android:layout_height="wrap_content"
                    android:text="0 SERIES" android:textColor="@color/sky_cyan" android:textSize="9sp" android:textStyle="bold" />
            </LinearLayout>
        </LinearLayout>
        <View android:layout_width="2dp" android:layout_height="match_parent" android:background="@color/sky_cyan"/>"""
replace_once(p, old, new)

# Movies.
p = Path("app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt")
s = p.read_text()
old = """            if (!showingContinue && !showingFavourites && !showingSearch && !showingLastAdded && !showingAll) {
                adapter.submitList(state.movies)
            }
            if (state.categories.isNotEmpty()) {"""
new = """            if (!showingContinue && !showingFavourites && !showingSearch && !showingLastAdded && !showingAll) {
                adapter.submitList(state.movies)
                binding.tvMovieCount.text = "${state.movies.size} MOVIES"
            }
            if (state.categories.isNotEmpty()) {"""
replace_once(p, old, new)

old = """    private fun showAllMovies() {
        scope.launch { adapter.submitList(ensureAllMovies()) }
    }
"""
new = """    private fun showAllMovies() {
        scope.launch {
            val list = ensureAllMovies()
            adapter.submitList(list)
            binding.tvMovieCount.text = "${list.size} MOVIES"
        }
    }
"""
replace_once(p, old, new)

old = """        adapter.submitList(favMovies)
    }

    private fun showContinueWatching() {"""
new = """        adapter.submitList(favMovies)
        binding.tvMovieCount.text = "${favMovies.size} MOVIES"
    }

    private fun showContinueWatching() {"""
replace_once(p, old, new)

old = """        val resumeMovies = allMovies.filter { it.streamId in resumeLabels }
        adapter.submitList(resumeMovies, resumeLabels)
    }
"""
new = """        val resumeMovies = allMovies.filter { it.streamId in resumeLabels }
        adapter.submitList(resumeMovies, resumeLabels)
        binding.tvMovieCount.text = "${resumeMovies.size} MOVIES"
    }
"""
replace_once(p, old, new)

old = """                val list = ensureAllMovies()
                    .sortedByDescending { recentSortKey(it.added) }
                    .take(30)
                adapter.submitList(list)
"""
new = """                val list = ensureAllMovies()
                    .sortedByDescending { recentSortKey(it.added) }
                    .take(30)
                adapter.submitList(list)
                binding.tvMovieCount.text = "${list.size} MOVIES"
"""
replace_once(p, old, new)

old = """                    val list = ensureAllMovies()
                    adapter.submitList(list.filter { it.name.contains(query, ignoreCase = true) })
"""
new = """                    val list = ensureAllMovies()
                    val results = list.filter { it.name.contains(query, ignoreCase = true) }
                    adapter.submitList(results)
                    binding.tvMovieCount.text = "${results.size} MOVIES"
"""
replace_once(p, old, new)

# Series.
p = Path("app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt")
s = p.read_text()
old = """            if (!showingContinue && !showingFavourites && !showingSearch && !showingAll && !showingLastAdded) {
                adapter.submitList(state.shows)
            }
            if (state.categories.isNotEmpty()) {"""
new = """            if (!showingContinue && !showingFavourites && !showingSearch && !showingAll && !showingLastAdded) {
                adapter.submitList(state.shows)
                binding.tvSeriesCount.text = "${state.shows.size} SERIES"
            }
            if (state.categories.isNotEmpty()) {"""
replace_once(p, old, new)

old = """    private fun showAllSeries() {
        scope.launch { adapter.submitList(ensureAllSeries()) }
    }
"""
new = """    private fun showAllSeries() {
        scope.launch {
            val list = ensureAllSeries()
            adapter.submitList(list)
            binding.tvSeriesCount.text = "${list.size} SERIES"
        }
    }
"""
replace_once(p, old, new)

old = """        adapter.submitList(favShows)
    }

    private fun showContinueWatching() {"""
new = """        adapter.submitList(favShows)
        binding.tvSeriesCount.text = "${favShows.size} SERIES"
    }

    private fun showContinueWatching() {"""
replace_once(p, old, new)

old = """        val resumeShows = allShows.filter { it.seriesId in resumeLabels }
        adapter.submitList(resumeShows, resumeLabels)
    }
"""
new = """        val resumeShows = allShows.filter { it.seriesId in resumeLabels }
        adapter.submitList(resumeShows, resumeLabels)
        binding.tvSeriesCount.text = "${resumeShows.size} SERIES"
    }
"""
replace_once(p, old, new)

old = """                val list = ensureAllSeries().sortedByDescending { recentSortKey(it.added ?: it.lastModified) }.take(30)
                adapter.submitList(list)
"""
new = """                val list = ensureAllSeries().sortedByDescending { recentSortKey(it.added ?: it.lastModified) }.take(30)
                adapter.submitList(list)
                binding.tvSeriesCount.text = "${list.size} SERIES"
"""
replace_once(p, old, new)

old = """                    val list = ensureAllSeries().filter { it.name.contains(query, ignoreCase = true) }
                    adapter.submitList(list)
"""
new = """                    val list = ensureAllSeries().filter { it.name.contains(query, ignoreCase = true) }
                    adapter.submitList(list)
                    binding.tvSeriesCount.text = "${list.size} SERIES"
"""
replace_once(p, old, new)

print("Movies and Series category count footers applied")
