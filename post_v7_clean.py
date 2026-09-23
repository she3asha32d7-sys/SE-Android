from pathlib import Path
R=Path('SEAndroid_v100.0.6')
def t(p): return (R/p).read_text()
def w(p,s): (R/p).write_text(s)
d=chr(36)

p='app/src/main/res/layout/activity_login.xml'; s=t(p).replace('android:layout_width="80dp"\n            android:layout_height="80dp"','android:layout_width="96dp"\n            android:layout_height="96dp"',1); w(p,s)
p='app/src/main/res/layout/activity_home.xml'; s=t(p).replace('layout_width="240dp"','layout_width="200dp"',1).replace('android:layout_width="280dp" android:layout_height="190dp"','android:layout_width="180dp" android:layout_height="120dp"',1); w(p,s)
for p in ['app/src/main/res/layout/activity_vod.xml','app/src/main/res/layout/activity_series.xml']:
    s=t(p).replace('android:layout_width="240dp"','android:layout_width="200dp"',1); w(p,s)

p='app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt'; s=t(p)
a=s.find('data class IptvSeries'); b=s.find('data class EmbyShow',a)
if a>=0 and b>a:
    block=s[a:b]
    block=block.replace('override val label get() = serverName','private val host get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd(chr(47)).substringBefore(chr(47))\n        override val label get() = "'+d+'serverName  •  '+d+'username @ '+d+'host"')
    s=s[:a]+block+s[b:]
s=s.replace('is SearchSource.IptvSeries -> "IPTV|'+d+'{src.serverUrl}|'+d+'{src.show.seriesId}"','is SearchSource.IptvSeries -> "IPTV|'+d+'{src.serverUrl}|'+d+'{src.username}|'+d+'{src.show.seriesId}"')
w(p,s)

p='app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt'; lines=t(p).splitlines()
for i,line in enumerate(lines):
    if 'fun categoryFavoriteId' in line:
        lines[i]='    fun categoryFavoriteId(categoryType: String, serverUrl: String, categoryId: String): String = "category_'+d+'{categoryType}_'+d+'{serverUrl.hashCode()}_'+d+'categoryId"'
w(p,'\n'.join(lines)+'\n')

p='app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt'; s=t(p)
s=s.replace('tvCount.text="'+d+'{m.size+s.size+l.size+c.size} ITEMS"','tvCount.text="'+d+'{m.size+s.size+l.size+c.size} ITEMS"')
w(p,s)

# Restore the two files touched by the redundant core-patch heart hook from the exact v100.0.6 source.
import zipfile
base=next(Path('../base-artifact').rglob('SEAndroid_v100.0.6.zip'))
with zipfile.ZipFile(base) as z:
    for rel in ['app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt','app/src/main/res/layout/item_channel.xml']:
        data=z.read('SEAndroid_v100.0.6/'+rel)
        (R/rel).write_bytes(data)
print('OK')