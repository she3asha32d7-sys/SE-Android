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

p='app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt'; lines=t(p).splitlines(); out=[]; skip=False
for line in lines:
    if 'import com.orbital.iptv.utils.FavouritesManager' in line: continue
    if 'val favButton:' in line: continue
    if 'favButton?.let { fav ->' in line:
        skip=True; continue
    if skip:
        if line.strip()=='}': skip=False
        continue
    out.append(line)
w(p,'\n'.join(out)+'\n')
p='app/src/main/res/layout/item_channel.xml'; s=t(p)
s='\n'.join(line for line in s.splitlines() if 'android:id="@+id/btn_fav"' not in line)+'\n'
w(p,s)
print('OK')