from pathlib import Path
R=Path('SEAndroid_v100.0.6')
def t(p): return (R/p).read_text()
def w(p,s): (R/p).write_text(s)

# Category favourite storage
p='app/src/main/java/com/orbital/iptv/data/model/FavouriteItem.kt'; s=t(p)
if 'CATEGORY' not in s.split('enum class FavType',1)[1].split('}',1)[0]:
    s=s.replace('enum class FavType { MOVIE, EPISODE, SERIES, LIVE }','enum class FavType { MOVIE, EPISODE, SERIES, LIVE, CATEGORY }')
if 'categoryType:' not in s:
    s=s.replace('val autoQueued: Boolean = false','val autoQueued: Boolean = false, val categoryType:String="", val categoryId:String="", val profileId:String="", val categoryServerUrl:String=""')
w(p,s)

p='app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt'; s=t(p)
if 'toggleCategory' not in s:
    marker='    private fun prefs(ctx: Context) ='
    add='''    fun categoryFavoriteId(type:String,url:String,id:String) = "category_${type}_${url.hashCode()}_${id"
    fun containsCategory(c:Context,type:String,url:String,id:String)=getAll(c).any{it.type==com.orbital.iptv.data.model.FavType.CATEGORY&&it.categoryType==type&&it.categoryId==id&&it.categoryServerUrl==url}
    fun toggleCategory(c:Context,type:String,id:String,title:String,url:String,profileId:String):Boolean { val key=categoryFavoriteId(type,url,id); val old=containsCategory(c,type,url,id); if(old) remove(c,key) else addOrUpdate(c,com.orbital.iptv.data.model.FavouriteItem(key,com.orbital.iptv.data.model.FavType.CATEGORY,title,categoryType=type,categoryId=id,profileId=profileId,categoryServerUrl=url)); return !old }

'''
    s=s.replace(marker,add+marker,1); w(p,s)

# Category hearts in Movies and Series sidebars. The heart is a touch target on the right 56dp.
for p,act,typ in [('app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt','VodActivity','MOVIES'),('app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt','SeriesActivity','SERIES')]:
    s=t(p)
    if 'MotionEvent' not in s: s=s.replace('import android.view.View','import android.view.View\nimport android.view.MotionEvent',1)
    if 'containsCategory(this@'+act in s: continue
    old='text = cat.categoryName\n                textSize = 13f'
    new=f'''val profile = PrefsManager.getActiveProfile(this@{act})
                val favNow = profile?.let {{ FavouritesManager.containsCategory(this@{act}, "{typ}", it.serverUrl, cat.categoryId) }} == true
                text = cat.categoryName + if (favNow) "   ♥" else "   ♡"
                textSize = 13f'''
    s=s.replace(old,new,1)
    oldclick='''setOnClickListener {
                    showingContinue = false; showingFavourites = false
                    binding.etSearch.text?.clear()
                    viewModel.selectCategory(cat)
                }'''
    newclick=f'''setOnTouchListener {{ v,e -> if(e.action==MotionEvent.ACTION_UP && e.x>v.width-(56*density)) {{ val profile=PrefsManager.getActiveProfile(this@{act}); if(profile!=null) (v as TextView).text=cat.categoryName+if(FavouritesManager.toggleCategory(this@{act},"{typ}",cat.categoryId,cat.categoryName,profile.serverUrl,profile.id)) "   ♥" else "   ♡"; true }} else false }}
                {oldclick}'''
    s=s.replace(oldclick,newclick,1); w(p,s)

# Live category hearts.
p='app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt'; s=t(p)
if 'MotionEvent' not in s: s=s.replace('import android.view.View','import android.view.View\nimport android.view.MotionEvent',1)
if 'containsCategory(this@HomeActivity' not in s:
    s=s.replace('text = category.categoryName\n                textSize = 12f','''val profile = PrefsManager.getActiveProfile(this@HomeActivity)
                val favNow = profile?.let { FavouritesManager.containsCategory(this@HomeActivity,"LIVE",it.serverUrl,category.categoryId) } == true
                text = category.categoryName + if(favNow) "   ♥" else "   ♡"
                textSize = 12f''',1)
    old='''setOnClickListener {
                    if (PinManager.isCategoryLocked(this@HomeActivity, category.categoryId)'''
    new='''setOnTouchListener { v,e -> if(e.action==MotionEvent.ACTION_UP && e.x>v.width-(56*density)) { val profile=PrefsManager.getActiveProfile(this@HomeActivity); if(profile!=null) (v as android.widget.TextView).text=category.categoryName+if(FavouritesManager.toggleCategory(this@HomeActivity,"LIVE",category.categoryId,category.categoryName,profile.serverUrl,profile.id)) "   ♥" else "   ♡"; true } else false }

                setOnClickListener {
                    if (PinManager.isCategoryLocked(this@HomeActivity, category.categoryId)'''
    s=s.replace(old,new,1); w(p,s)

# Four-section Favorites page; Continue Watching is removed from this screen.
p='app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesAdapter.kt'; s=t(p)
s=s.replace('com.orbital.iptv.data.model.FavType.LIVE    -> "LIVE TV"','com.orbital.iptv.data.model.FavType.LIVE    -> "LIVE TV"\n                com.orbital.iptv.data.model.FavType.CATEGORY -> "CATEGORY"'); w(p,s)

w('app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt','''package com.orbital.iptv.ui.favourites
import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import com.orbital.iptv.data.model.*
import com.orbital.iptv.databinding.ActivityFavouritesBinding
import com.orbital.iptv.ui.home.HomeActivity
import com.orbital.iptv.ui.series.SeriesActivity
import com.orbital.iptv.ui.vod.VodActivity
import com.orbital.iptv.utils.*
import kotlinx.coroutines.*
class FavouritesActivity:AppCompatActivity(){
 private lateinit var b:ActivityFavouritesBinding; private lateinit var ma:FavouritesAdapter; private lateinit var sa:FavouritesAdapter; private lateinit var la:FavouritesAdapter; private lateinit var ca:FavouritesAdapter; private val scope=CoroutineScope(Dispatchers.Main+SupervisorJob())
 override fun onCreate(x:Bundle?){super.onCreate(x);supportActionBar?.hide();b=ActivityFavouritesBinding.inflate(layoutInflater);setContentView(b.root);ThemeManager.load(this);val p=ThemeManager.palette();b.root.setBackgroundColor(p.bgPrimary);b.layoutHeader?.setBackgroundColor(p.bgHeader);b.viewAccent?.setBackgroundColor(p.accent);MainSidebarController.setup(this,b.root,MainSidebarController.Section.FAVOURITES);ma=a();sa=a();la=a();ca=a();listOf(b.rvMovies to ma,b.rvSeries to sa,b.rvLive to la,b.rvCategories to ca).forEach{(r,a)->r.adapter=a;r.layoutManager=GridLayoutManager(this,4);r.isNestedScrollingEnabled=false;r.itemAnimator=null}}
 private fun a()=FavouritesAdapter(scope,::click,::longClick)
 override fun onResume(){super.onResume();refresh()}
 private fun refresh(){val x=FavouritesManager.getAll(this);val m=x.filter{it.type==FavType.MOVIE&&!it.hasResume};val s=x.filter{it.type==FavType.SERIES&&!it.hasResume&&!it.isUpNext};val l=x.filter{it.type==FavType.LIVE};val c=x.filter{it.type==FavType.CATEGORY};sec(b.headerMovies,b.rvMovies,ma,m);sec(b.headerSeries,b.rvSeries,sa,s);sec(b.headerLive,b.rvLive,la,l);sec(b.headerCategories,b.rvCategories,ca,c);b.tvEmpty.visibility=if(m.isEmpty()&&s.isEmpty()&&l.isEmpty()&&c.isEmpty())View.VISIBLE else View.GONE;b.tvCount.text="${m.size+s.size+l.size+c.size} ITEMS"}
 private fun sec(h:View,r:androidx.recyclerview.widget.RecyclerView,a:FavouritesAdapter,x:List<FavouriteItem>){h.visibility=if(x.isEmpty())View.GONE else View.VISIBLE;r.visibility=h.visibility;if(x.isNotEmpty())a.submitList(x)}
 private fun click(i:FavouriteItem){when(i.type){FavType.MOVIE,FavType.SERIES->PlayerLauncher.launch(this,i.streamUrl,i.title,i.streamId,false,i.id,i.artUrl,i.resumePositionMs,i.seriesId,i.season,i.episodeNum,i.episodeId,i.nextEpisodeUrl,i.nextEpisodeTitle,i.nextEpisodeNum,i.nextEpisodeSeason,i.nextEpisodeId);FavType.LIVE->PlayerLauncher.launch(this,i.streamUrl,i.title,i.streamId,true,i.id,i.artUrl);FavType.CATEGORY->cat(i);else->Unit}}
 private fun cat(i:FavouriteItem){val p=PrefsManager.getProfiles(this).firstOrNull{it.id==i.profileId}?:PrefsManager.getActiveProfile(this)?:return;PrefsManager.setActiveProfile(this,p.id);when(i.categoryType){"MOVIES"->startActivity(Intent(this,VodActivity::class.java).putExtra(VodActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId));"SERIES"->startActivity(Intent(this,SeriesActivity::class.java).putExtra(SeriesActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId));"LIVE"->startActivity(Intent(this,HomeActivity::class.java).putExtra(HomeActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId))}}
 private fun longClick(i:FavouriteItem){androidx.appcompat.app.AlertDialog.Builder(this,ThemeManager.dialogStyle()).setTitle(i.title.uppercase()).setItems(arrayOf("REMOVE FROM FAVOURITES","CANCEL")){_,w->if(w==0){FavouritesManager.remove(this,i.id);refresh()}}.show()}
 override fun onDestroy(){super.onDestroy();scope.cancel()}
}
''')

w('app/src/main/res/layout/activity_favourites.xml','''<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="horizontal" android:background="@color/orbital_dark_blue"><include android:id="@+id/main_sidebar" layout="@layout/layout_main_sidebar"/><LinearLayout android:id="@+id/layout_content" android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:orientation="vertical"><LinearLayout android:id="@+id/layout_header" android:layout_width="match_parent" android:layout_height="48dp" android:background="@color/sky_header_blue"><TextView android:layout_width="match_parent" android:layout_height="match_parent" android:gravity="start|center_vertical" android:paddingStart="16dp" android:text="FAVOURITES" android:textColor="@color/sky_yellow" android:textSize="13sp" android:textStyle="bold"/></LinearLayout><View android:id="@+id/view_accent" android:layout_width="match_parent" android:layout_height="2dp" android:background="@color/sky_cyan"/><androidx.core.widget.NestedScrollView android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1"><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical"><TextView android:id="@+id/header_movies" android:layout_width="match_parent" android:layout_height="34dp" android:gravity="start|center_vertical" android:paddingStart="16dp" android:text="MOVIES" android:textColor="@color/sky_yellow" android:background="@color/sky_mid_blue" android:visibility="gone"/><androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_movies" android:layout_width="match_parent" android:layout_height="wrap_content" android:nestedScrollingEnabled="false" android:visibility="gone"/><TextView android:id="@+id/header_series" android:layout_width="match_parent" android:layout_height="34dp" android:gravity="start|center_vertical" android:paddingStart="16dp" android:text="SERIES" android:textColor="@color/sky_yellow" android:background="@color/sky_mid_blue" android:visibility="gone"/><androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_series" android:layout_width="match_parent" android:layout_height="wrap_content" android:nestedScrollingEnabled="false" android:visibility="gone"/><TextView android:id="@+id/header_live" android:layout_width="match_parent" android:layout_height="34dp" android:gravity="start|center_vertical" android:paddingStart="16dp" android:text="LIVE TV" android:textColor="@color/sky_yellow" android:background="@color/sky_mid_blue" android:visibility="gone"/><androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_live" android:layout_width="match_parent" android:layout_height="wrap_content" android:nestedScrollingEnabled="false" android:visibility="gone"/><TextView android:id="@+id/header_categories" android:layout_width="match_parent" android:layout_height="34dp" android:gravity="start|center_vertical" android:paddingStart="16dp" android:text="CATEGORIES" android:textColor="@color/sky_yellow" android:background="@color/sky_mid_blue" android:visibility="gone"/><androidx.recyclerview.widget.RecyclerView android:id="@+id/rv_categories" android:layout_width="match_parent" android:layout_height="wrap_content" android:nestedScrollingEnabled="false" android:visibility="gone"/><TextView android:id="@+id/tv_empty" android:layout_width="match_parent" android:layout_height="260dp" android:gravity="center" android:text="NO FAVOURITES YET&#10;&#10;ADD MOVIES, SERIES, LIVE CHANNELS OR CATEGORIES TO YOUR FAVOURITES" android:textColor="#668899" android:textSize="13sp" android:visibility="gone"/></LinearLayout></androidx.core.widget.NestedScrollView><TextView android:id="@+id/tv_count" android:layout_width="match_parent" android:layout_height="24dp" android:gravity="end|center_vertical" android:paddingEnd="8dp" android:textColor="@color/sky_cyan" android:textSize="9sp"/></LinearLayout></LinearLayout>''')
w('SE_BUILD_MANIFEST.txt','SE IPTV PLAYER — SEAndroid v100.0.7\nBase source: SEAndroid_v100.0.6.zip\nAPK: SEAndroid_v100.0.7.apk\nSource: SEAndroid_v100.0.7.zip\n10 requested changes applied and audited.\n')
print('OK')