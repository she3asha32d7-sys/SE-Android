from pathlib import Path
import re
R=Path("work")
def read(p): return (R/p).read_text()
def write(p,s): (R/p).write_text(s)
def must(p,old,new,n=1):
    s=read(p)
    if old not in s: raise SystemExit("MISSING "+p+" :: "+old[:80])
    write(p,s.replace(old,new,n))

p="app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt"
old=''' private fun click(i:FavouriteItem){when(i.type){FavType.MOVIE,FavType.SERIES->PlayerLauncher.launch(this,i.streamUrl,i.title,i.streamId,false,i.id,i.artUrl,i.resumePositionMs,i.seriesId,i.season,i.episodeNum,i.episodeId,i.nextEpisodeUrl,i.nextEpisodeTitle,i.nextEpisodeNum,i.nextEpisodeSeason,i.nextEpisodeId);FavType.LIVE->PlayerLauncher.launch(this,i.streamUrl,i.title,i.streamId,true,i.id,i.artUrl);FavType.CATEGORY->cat(i);else->Unit}}'''
new=''' private fun click(i:FavouriteItem){
  when(i.type){
   FavType.MOVIE -> openMovie(i)
   FavType.SERIES -> openSeries(i)
   FavType.LIVE -> startActivity(Intent(this,HomeActivity::class.java).apply{addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);putExtra(HomeActivity.EXTRA_SECTION,"LIVE")})
   FavType.CATEGORY -> cat(i)
   else -> Unit
  }
 }
 private fun profileFor(i:FavouriteItem)=PrefsManager.getProfiles(this).firstOrNull{it.id==i.profileId}?:PrefsManager.getActiveProfile(this)
 private fun openMovie(i:FavouriteItem){val p=profileFor(i)?:return;startActivity(Intent(this,com.orbital.iptv.ui.vod.MovieDetailActivity::class.java).apply{
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_ID,i.streamId)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_NAME,i.title)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_ICON,i.artUrl)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_CONTAINER_EXT,"mp4")
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_SERVER_URL,p.serverUrl)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_USERNAME,p.username)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_PASSWORD,p.password)
  putExtra(com.orbital.iptv.ui.vod.MovieDetailActivity.EXTRA_STREAM_URL_OVERRIDE,i.streamUrl)
 })}
 private fun openSeries(i:FavouriteItem){val p=profileFor(i)?:return;startActivity(Intent(this,com.orbital.iptv.ui.series.SeriesDetailActivity::class.java).apply{
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_ID,i.streamId)
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_NAME,i.title)
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERIES_COVER,i.artUrl)
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_SERVER_URL,p.serverUrl)
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_USERNAME,p.username)
  putExtra(com.orbital.iptv.ui.series.SeriesDetailActivity.EXTRA_PASSWORD,p.password)
 })}'''
must(p,old,new)

p="app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt"
must(p,'''    private fun launchChannel(stream: LiveStream) {
''','''    private fun launchChannel(stream: LiveStream) {
        miniPlayer?.stop()
        miniPlayer?.clearMediaItems()
        binding.miniPlayer.player = null
        lastPreviewStreamId = -1
''')
must(p,'layoutManager = androidx.recyclerview.widget.GridLayoutManager(this@HomeActivity, 1)','layoutManager = androidx.recyclerview.widget.GridLayoutManager(this@HomeActivity, 2)')
old='''    fun showSection(mode:String) {
        val home = mode.equals("HOME",true)
        binding.root.findViewById<View>(R.id.dashboard_container)?.visibility=if(home) View.VISIBLE else View.GONE
        binding.root.findViewById<View>(R.id.layout_live_categories)?.visibility=if(home) View.GONE else View.VISIBLE
        binding.root.findViewById<View>(R.id.layout_live_content)?.visibility=if(home) View.GONE else View.VISIBLE
        val selected=if(home) Section.HOME else Section.LIVE_TV
        MainSidebarController.setup(this,binding.root,selected,onSettings={startActivity(Intent(this,SettingsActivity::class.java))},onHome={showSection("HOME")},onLiveTv={showSection("LIVE")})
        if(home) buildHomeDashboard()
    }'''
new='''    fun showSection(mode:String) {
        val home = mode.equals("HOME",true)
        binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility=if(home) View.VISIBLE else View.GONE
        binding.root.findViewById<View>(R.id.dashboard_container)?.visibility=if(home) View.VISIBLE else View.GONE
        binding.root.findViewById<View>(R.id.layout_live_categories)?.visibility=if(home) View.GONE else View.VISIBLE
        binding.root.findViewById<View>(R.id.layout_live_content)?.visibility=if(home) View.GONE else View.VISIBLE
        val selected=if(home) Section.HOME else Section.LIVE_TV
        MainSidebarController.setup(this,binding.root,selected,onSettings={startActivity(Intent(this,SettingsActivity::class.java))},onHome={showSection("HOME")},onLiveTv={showSection("LIVE")})
        binding.root.findViewById<TextView>(R.id.btn_live_category_back)?.apply{visibility=if(home) View.GONE else View.VISIBLE;setOnClickListener{showSection("HOME")}}
        if(home) buildHomeDashboard() else binding.root.findViewById<View>(R.id.btn_live_category_back)?.requestFocus()
    }'''
must(p,old,new)
must(p,'''            override fun handleOnBackPressed() {
''','''            override fun handleOnBackPressed() {
                if (binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility == View.GONE) { showSection("HOME"); return }
''')

p="app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt"
must(p,'''                    Section.MOVIES -> go(activity, VodActivity::class.java)
                    Section.SERIES -> go(activity, SeriesActivity::class.java)''','''                    Section.MOVIES -> go(activity, VodActivity::class.java, "open_category_only", true)
                    Section.SERIES -> go(activity, SeriesActivity::class.java, "open_category_only", true)''')
must(p,'''    private fun <T : Activity> go(activity: AppCompatActivity, target: Class<T>) {
        if (activity::class.java == target) return
        activity.startActivity(Intent(activity, target).apply { addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT) })
        noAnimation(activity)
    }''','''    private fun <T : Activity> go(activity: AppCompatActivity, target: Class<T>, extraKey: String? = null, extraValue: Boolean = false) {
        if (activity::class.java == target && extraKey == null) return
        activity.startActivity(Intent(activity, target).apply { addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT); if(extraKey!=null) putExtra(extraKey,extraValue) })
        noAnimation(activity)
    }''')

for p,cls,section in [("app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt","VodActivity","MOVIES"),("app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt","SeriesActivity","SERIES")]:
    s=read(p)
    if "companion object { const val EXTRA_OPEN_FAVOURITE_" not in s:
        name="MOVIE" if cls=="VodActivity" else "SERIES"
        s=s.replace(f"class {cls} : AppCompatActivity() {{",f'class {cls} : AppCompatActivity() {{\n\n    companion object {{ const val EXTRA_OPEN_FAVOURITE_{name} = "open_favourite_{name}" }}',1)
    old=f'''        MainSidebarController.setup(this, binding.root, Section.{section}, onSettings = {{ startActivity(Intent(this, SettingsActivity::class.java)) }})'''
    new=old+'''\n        val categoryOnly=intent.getBooleanExtra("open_category_only",false)
        if(categoryOnly){binding.root.findViewById<View>(R.id.main_sidebar_container)?.visibility=View.GONE;binding.root.findViewById<View>(R.id.btn_category_back)?.visibility=View.VISIBLE;binding.root.findViewById<View>(R.id.btn_category_back)?.setOnClickListener{openHome()}}'''
    if old not in s: raise SystemExit("sidebar setup missing "+p)
    s=s.replace(old,new,1)
    s=s.replace(f"GridLayoutManager(this@{cls}, 2)",f"GridLayoutManager(this@{cls}, 3)",1)
    s=s.replace('''            override fun handleOnBackPressed() {''','''            override fun handleOnBackPressed() {
                if(intent.getBooleanExtra("open_category_only",false)){openHome();return}''',1)
    s=s.replace("    override fun onDestroy() {",'''    private fun openHome(){startActivity(Intent(this,com.orbital.iptv.ui.home.HomeActivity::class.java).apply{addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);putExtra(com.orbital.iptv.ui.home.HomeActivity.EXTRA_SECTION,"HOME")})}

    override fun onDestroy() {''',1)
    write(p,s)

p="app/src/main/res/layout/item_live_channel.xml"; s=read(p)
s=s.replace('android:textSize="20sp"','android:textSize="13sp"',1).replace('android:layout_width="54dp"\n        android:layout_height="54dp"','android:layout_width="38dp"\n        android:layout_height="38dp"',1).replace('android:textSize="28sp"','android:textSize="13sp"',1); write(p,s)

for p,title,head in [("app/src/main/res/layout/activity_vod.xml","MOVIES","movies"),("app/src/main/res/layout/activity_series.xml","SERIES","series")]:
    s=read(p)
    old='''<LinearLayout android:layout_width="200dp" android:layout_height="match_parent" android:orientation="vertical" android:background="@color/se_panel">
                <ScrollView'''
    new=f'''<LinearLayout android:layout_width="200dp" android:layout_height="match_parent" android:orientation="vertical" android:background="@color/se_panel">
                <LinearLayout android:layout_width="match_parent" android:layout_height="46dp" android:orientation="horizontal" android:gravity="center_vertical" android:background="@color/se_panel_alt">
                    <TextView android:id="@+id/btn_category_back" android:layout_width="40dp" android:layout_height="match_parent" android:gravity="center" android:text="←" android:textColor="@color/sky_white" android:textSize="20sp" android:textStyle="bold" android:focusable="true" android:clickable="true" android:visibility="gone"/>
                    <TextView android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:gravity="start|center_vertical" android:paddingStart="6dp" android:text="{title}" android:textColor="@color/sky_white" android:textSize="13sp" android:textStyle="bold"/>
                </LinearLayout>
                <ScrollView'''
    if old not in s: raise SystemExit("category layout missing "+p)
    s=s.replace(old,new,1)
    s=re.sub(r'<TextView android:id="@\+id/header_'+head+r'".*?/>\n',' ',s,count=1)
    write(p,s)

p="app/src/main/res/layout/activity_home.xml"; s=read(p)
old='''<TextView android:id="@+id/header_tv_listings" android:layout_width="match_parent" android:layout_height="46dp" android:gravity="center_vertical"
            android:paddingStart="12dp" android:text="LIVE TV" android:textColor="@color/sky_white" android:textSize="13sp" android:textStyle="bold"
            android:background="@color/se_panel_alt" android:focusable="true" android:clickable="true" android:nextFocusRight="@id/rv_live_channels" />'''
new='''<LinearLayout android:layout_width="match_parent" android:layout_height="46dp" android:orientation="horizontal" android:gravity="center_vertical" android:background="@color/se_panel_alt">
            <TextView android:id="@+id/btn_live_category_back" android:layout_width="40dp" android:layout_height="match_parent" android:gravity="center" android:text="←" android:textColor="@color/sky_white" android:textSize="20sp" android:textStyle="bold" android:focusable="true" android:clickable="true" android:visibility="gone"/>
            <TextView android:id="@+id/header_tv_listings" android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:gravity="start|center_vertical" android:paddingStart="6dp" android:text="LIVE TV" android:textColor="@color/sky_white" android:textSize="13sp" android:textStyle="bold" android:focusable="true" android:clickable="true" android:nextFocusRight="@id/rv_live_channels" />
        </LinearLayout>'''
must(p,old,new)

p="app/src/main/java/com/orbital/iptv/ui/vod/MovieDetailActivity.kt"; s=read(p)
s=s.replace('const val EXTRA_PASSWORD       = "detail_password"','const val EXTRA_PASSWORD       = "detail_password"\n        const val EXTRA_STREAM_URL_OVERRIDE = "detail_stream_url_override"',1)
s=s.replace('val password    = intent.getStringExtra(EXTRA_PASSWORD) ?: ""','val password    = intent.getStringExtra(EXTRA_PASSWORD) ?: ""\n        val streamUrlOverride = intent.getStringExtra(EXTRA_STREAM_URL_OVERRIDE)?.takeIf { it.isNotBlank() }',1)
s=s.replace('val vodUrl = repository.buildVodUrl(serverUrl, username, password, streamId, containerExt)','val vodUrl = streamUrlOverride ?: repository.buildVodUrl(serverUrl, username, password, streamId, containerExt)',1); write(p,s)

p="app/src/main/res/layout/activity_movie_detail.xml"; s=read(p)
s=s.replace('''    <FrameLayout android:id="@+id/detail_card" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:layout_margin="28dp" android:background="@color/se_panel" android:padding="26dp">''','''    <androidx.core.widget.NestedScrollView android:id="@+id/detail_page_scroll" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:clipToPadding="false" android:scrollbars="none">
    <FrameLayout android:id="@+id/detail_card" android:layout_width="match_parent" android:layout_height="wrap_content" android:minHeight="900dp" android:layout_margin="28dp" android:background="@color/se_panel" android:padding="26dp">''',1)
s=s.replace('''</LinearLayout>
    </FrameLayout>
</LinearLayout>''','''</LinearLayout>
    </FrameLayout>
    </androidx.core.widget.NestedScrollView>
</LinearLayout>''',1)
s=s.replace('<androidx.core.widget.NestedScrollView android:id="@+id/detail_info_scroll" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:scrollbars="none">','<LinearLayout android:id="@+id/detail_info_scroll" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical">',1)
s=s.replace('</LinearLayout></androidx.core.widget.NestedScrollView><LinearLayout android:layout_width="match_parent" android:layout_height="54dp"','</LinearLayout></LinearLayout><LinearLayout android:layout_width="match_parent" android:layout_height="54dp"',1)
s=s.replace('android:layout_width="235dp" android:layout_height="match_parent"','android:layout_width="235dp" android:layout_height="430dp"',1); write(p,s)

p="app/src/main/res/layout/activity_series_detail.xml"; s=read(p)
s=s.replace('''    <LinearLayout android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:orientation="vertical" android:padding="24dp">''','''    <androidx.core.widget.NestedScrollView android:id="@+id/detail_page_scroll" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:clipToPadding="false" android:scrollbars="none">
    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="24dp">''',1)
s=s.replace('''        <androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_episodes" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1"''','''        <androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_episodes" android:layout_width="match_parent" android:layout_height="520dp"''',1)
s=s.replace('android:layout_height="260dp" android:orientation="horizontal"','android:layout_height="360dp" android:orientation="horizontal"',1)
s=s.replace('android:descendantFocusability="afterDescendants"/>','android:descendantFocusability="afterDescendants" android:nestedScrollingEnabled="false"/>',1)
s=s.replace('</LinearLayout>\n</LinearLayout>','</LinearLayout>\n    </androidx.core.widget.NestedScrollView>\n</LinearLayout>',1)
s=s.replace('<androidx.core.widget.NestedScrollView android:id="@+id/detail_info_scroll" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:scrollbars="none">','<LinearLayout android:id="@+id/detail_info_scroll" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical">',1)
s=s.replace('</LinearLayout></androidx.core.widget.NestedScrollView><LinearLayout android:layout_width="match_parent" android:layout_height="48dp"','</LinearLayout></LinearLayout><LinearLayout android:layout_width="match_parent" android:layout_height="48dp"',1); write(p,s)
print("PATCH_V7_NEW_OK")
