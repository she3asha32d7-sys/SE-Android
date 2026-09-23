from pathlib import Path
import re
R=Path('SEAndroid_v100.0.6')
def t(p): return (R/p).read_text()
def w(p,s): (R/p).write_text(s)

p='app/src/main/res/layout/activity_login.xml'; s=t(p).replace('android:layout_width="80dp"\n            android:layout_height="80dp"','android:layout_width="96dp"\n            android:layout_height="96dp"',1); w(p,s)
p='app/src/main/res/layout/activity_home.xml'; s=t(p).replace('layout_width="240dp"','layout_width="200dp"',1).replace('android:layout_width="280dp" android:layout_height="190dp"','android:layout_width="180dp" android:layout_height="120dp"',1); w(p,s)
for p in ['app/src/main/res/layout/activity_vod.xml','app/src/main/res/layout/activity_series.xml']:
    s=t(p).replace('android:layout_width="240dp"','android:layout_width="200dp"',1); w(p,s)

p='app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt'; s=t(p)
pos=s.find('data class IptvSeries'); end=s.find('data class EmbyShow',pos)
if pos>=0 and end>pos:
    block=s[pos:end]
    block=block.replace('override val label get() = serverName','private val host get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')\n        override val label get() = "$serverName  •  $username @ $host"')
    s=s[:pos]+block+s[end:]
s=s.replace('is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.show.seriesId}"','is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
w(p,s)

p='app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt'; s=t(p)
lines=s.splitlines()
for i,line in enumerate(lines):
    if 'fun categoryFavoriteId' in line:
        lines[i]='    fun categoryFavoriteId(categoryType: String, serverUrl: String, categoryId: String): String = "category_${categoryType}_${serverUrl.hashCode()}_$categoryId"'
w(p,'\n'.join(lines)+'\n')
p='app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt'; s=t(p)
s=s.replace('"${{m.size+s.size+l.size+c.size} ITEMS"','"${m.size+s.size+l.size+c.size} ITEMS"')
w(p,s)

p='app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt'; s=t(p)
s=s.replace('import com.orbital.iptv.utils.FavouritesManager\n','')
s=s.replace('        val favButton: TextView? = itemView.findViewById(R.id.btn_fav)\n','')
s=re.sub(r'\n        favButton\?\.let \{ fav ->.*?\n        \}\n\n        // TV D-pad focus highlight','\n\n        // TV D-pad focus highlight',s,flags=re.S)
w(p,s)
p='app/src/main/res/layout/item_channel.xml'; s=t(p); s=re.sub(r'\s*<TextView android:id="@\+id/btn_fav"[^>]+/>\s*','\n',s,count=1); w(p,s)
w('SE_BUILD_MANIFEST.txt','''SE IPTV PLAYER — SEAndroid v100.0.7
Base source: SEAndroid_v100.0.6.zip
APK: SEAndroid_v100.0.7.apk
Source: SEAndroid_v100.0.7.zip
10 requested changes: launcher +30%; Xtream logo +20%; touch-scroll detail pages; smaller Live TV preview and sidebar; provider/account-aware Search; narrower category sidebars; movie year beside rating; 2-column Movies/Series; category and live-channel hearts; Favorites split into Movies/Series/Live/Categories with no Continue Watching.
''')
print('OK')