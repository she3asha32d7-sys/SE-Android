from pathlib import Path
R=Path(__file__).resolve().parent/'SE-Android-v10.1.0'
def e(p,a,b):
 q=R/p;s=q.read_text();
 if a in s:q.write_text(s.replace(a,b))
e('app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt','private val clockFmt = SimpleDateFormat("HH:mm", Locale.UK)','private val clockFmt = SimpleDateFormat("h:mm a", Locale.US)\n    private val dateFmt = SimpleDateFormat("MMM dd, yyyy", Locale.US)')
e('app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt','binding.root.findViewById<TextView>(R.id.tv_sidebar_time)?.text = clockFmt.format(Date())','val now = Date()\n            binding.root.findViewById<TextView>(R.id.tv_sidebar_time)?.text = clockFmt.format(now)\n            binding.root.findViewById<TextView>(R.id.tv_sidebar_date)?.text = dateFmt.format(now).uppercase(Locale.US)')
for p,x in [('app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt','GridLayoutManager(this@HomeActivity, 3)'),('app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt','GridLayoutManager(this@VodActivity, 3)'),('app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt','GridLayoutManager(this@SeriesActivity, 3)')]:e(p,x,x.replace(', 3)',', 4)'))
e('app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt','import androidx.recyclerview.widget.LinearLayoutManager','import androidx.recyclerview.widget.GridLayoutManager');e('app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt','layoutManager = LinearLayoutManager(this@FavouritesActivity)','layoutManager = GridLayoutManager(this@FavouritesActivity, 4)')
p=R/'app/src/main/res/layout/layout_main_sidebar.xml';s=p.read_text();s=s.replace('''    <TextView
        android:id="@+id/nav_live_tv"''','''    <TextView
        android:id="@+id/nav_home"
        android:layout_width="98dp" android:layout_height="36dp" android:gravity="center" android:text="HOME" android:textColor="@color/sky_white" android:textSize="10sp" android:textStyle="bold" android:focusable="true" android:clickable="true" />

    <TextView
        android:id="@+id/nav_live_tv"''')
s=s.replace('''    <TextView
        android:id="@+id/nav_search"''','''    <TextView android:id="@+id/nav_downloads" android:layout_width="98dp" android:layout_height="36dp" android:gravity="center" android:text="DOWNLOADS" android:textColor="@color/sky_white" android:textSize="9sp" android:textStyle="bold" android:focusable="true" android:clickable="true" />
    <TextView android:id="@+id/nav_records" android:layout_width="98dp" android:layout_height="36dp" android:gravity="center" android:text="RECORDS" android:textColor="@color/sky_white" android:textSize="9sp" android:textStyle="bold" android:focusable="true" android:clickable="true" />

    <TextView
        android:id="@+id/nav_search"''')
s=s.replace('''    <TextView
        android:id="@+id/tv_sidebar_time"''','''    <TextView android:id="@+id/tv_sidebar_date" android:layout_width="match_parent" android:layout_height="18dp" android:gravity="center" android:text="JAN 01, 2026" android:textColor="#7983A8" android:textSize="8sp" />

    <TextView
        android:id="@+id/tv_sidebar_time"''');p.write_text(s)
p=R/'app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt';s=p.read_text();s=s.replace('import com.orbital.iptv.ui.vod.VodActivity','import com.orbital.iptv.ui.vod.VodActivity\nimport com.orbital.iptv.recording.RecordingsActivity\nimport com.orbital.iptv.ui.downloads.DownloadsActivity');s=s.replace('enum class Section { LIVE_TV, MOVIES, SERIES, FAVOURITES, SEARCH, SETTINGS, LIST_USERS }','enum class Section { HOME, LIVE_TV, MOVIES, SERIES, FAVOURITES, DOWNLOADS, RECORDS, SEARCH, SETTINGS, LIST_USERS }');s=s.replace('Section.LIVE_TV to R.id.nav_live_tv,','Section.HOME to R.id.nav_home,\n            Section.LIVE_TV to R.id.nav_live_tv,');s=s.replace('Section.FAVOURITES to R.id.nav_favourites,\n            Section.SEARCH','Section.FAVOURITES to R.id.nav_favourites,\n            Section.DOWNLOADS to R.id.nav_downloads,\n            Section.RECORDS to R.id.nav_records,\n            Section.SEARCH');s=s.replace('Section.LIVE_TV -> go(activity, HomeActivity::class.java)','Section.HOME -> go(activity, HomeActivity::class.java)\n                    Section.LIVE_TV -> go(activity, HomeActivity::class.java)');s=s.replace('Section.FAVOURITES -> go(activity, FavouritesActivity::class.java)\n                    Section.SEARCH','Section.FAVOURITES -> go(activity, FavouritesActivity::class.java)\n                    Section.DOWNLOADS -> go(activity, DownloadsActivity::class.java)\n                    Section.RECORDS -> go(activity, RecordingsActivity::class.java)\n                    Section.SEARCH');p.write_text(s)
p=R/'app/src/main/res/layout/activity_home.xml';e('app/src/main/res/layout/activity_home.xml','SE IPTV PLAYER  •  SELECT A CHANNEL','SELECT A CHANNEL')
D=R/'app/src/main/java/com/orbital/iptv/ui/downloads';D.mkdir(parents=True,exist_ok=True)
(D/'DownloadsActivity.kt').write_text('''package com.orbital.iptv.ui.downloads
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.orbital.iptv.databinding.ActivityDownloadsBinding
import com.orbital.iptv.utils.MainSidebarController
import com.orbital.iptv.utils.ThemeManager
class DownloadsActivity: AppCompatActivity(){
 private lateinit var b:ActivityDownloadsBinding
 override fun onCreate(x:Bundle?){super.onCreate(x);supportActionBar?.hide();b=ActivityDownloadsBinding.inflate(layoutInflater);setContentView(b.root);ThemeManager.load(this);b.root.setBackgroundColor(ThemeManager.palette().bgPrimary);MainSidebarController.setup(this,b.root,MainSidebarController.Section.DOWNLOADS);b.btnBack.setOnClickListener{finish()}}
}
''')
(R/'app/src/main/res/layout/activity_downloads.xml').write_text('''<?xml version="1.0" encoding="utf-8"?><LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="horizontal" android:background="@color/orbital_dark_blue"><include layout="@layout/layout_main_sidebar"/><LinearLayout android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" android:orientation="vertical"><TextView android:id="@+id/btnBack" android:layout_width="100dp" android:layout_height="48dp" android:gravity="center" android:text="BACK" android:textColor="@color/sky_white" android:focusable="true"/><TextView android:layout_width="match_parent" android:layout_height="60dp" android:gravity="center" android:text="DOWNLOADS" android:textColor="@color/sky_white" android:textSize="18sp" android:textStyle="bold"/><TextView android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:gravity="center" android:text="NO DOWNLOADED FILES" android:textColor="@color/sky_white" android:textSize="15sp"/></LinearLayout></LinearLayout>
''')
e('app/src/main/AndroidManifest.xml','''        <activity
            android:name=".ui.users.ListUsersActivity"''','''        <activity android:name=".ui.downloads.DownloadsActivity" android:exported="false" android:screenOrientation="landscape" />

        <activity
            android:name=".ui.users.ListUsersActivity"''')
print('patched')