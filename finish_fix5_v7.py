from pathlib import Path
R=Path('SEAndroid_v100.0.6')
def t(p): return (R/p).read_text()
def w(p,s): (R/p).write_text(s)

p='app/src/main/res/layout/activity_login.xml'; s=t(p).replace('android:layout_width="80dp"\n            android:layout_height="80dp"','android:layout_width="96dp"\n            android:layout_height="96dp"',1); w(p,s)
p='app/src/main/res/layout/activity_home.xml'; s=t(p).replace('layout_width="240dp"','layout_width="200dp"',1).replace('android:layout_width="280dp" android:layout_height="190dp"','android:layout_width="180dp" android:layout_height="120dp"',1); w(p,s)
for p in ['app/src/main/res/layout/activity_vod.xml','app/src/main/res/layout/activity_series.xml']:
    s=t(p).replace('android:layout_width="240dp"','android:layout_width="200dp"',1); w(p,s)
p='app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt'; s=t(p)
pos=s.find('data class IptvSeries'); end=s.find('data class EmbyShow',pos); block=s[pos:end]
block=block.replace('override val label get() = serverName','private val host get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')\n        override val label get() = "$serverName  •  $username @ $host"')
s=s[:pos]+block+s[end:]
s=s.replace('is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.show.seriesId}"','is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
w(p,s)
print('OK')