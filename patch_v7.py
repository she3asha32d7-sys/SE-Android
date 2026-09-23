from pathlib import Path
ROOT=Path('SEAndroid_v100.0.6')
def f(x): return ROOT/x
def t(x): return f(x).read_text(encoding='utf-8')
def w(x,s): f(x).write_text(s,encoding='utf-8')

s=t('settings.gradle').replace('SEAndroid_v100.0.6','SEAndroid_v100.0.7'); w('settings.gradle',s)
s=t('app/build.gradle').replace('versionCode 201','versionCode 1000007',1).replace('versionName "2.0.1"','versionName "100.0.7"',1); w('app/build.gradle',s)

w('app/src/main/res/drawable/se_launcher_scaled.xml','''<?xml version="1.0" encoding="utf-8"?>
<scale xmlns:android="http://schemas.android.com/apk/res/android" android:drawable="@drawable/se_launcher" android:scaleWidth="130%" android:scaleHeight="130%" android:gravity="center"/>
''')
s=t('app/src/main/res/layout/activity_login.xml').replace('android:layout_width="96dp"\n            android:layout_height="96dp"','android:layout_width="115dp"\n            android:layout_height="115dp"',1); w('app/src/main/res/layout/activity_login.xml',s)

for x in ('activity_movie_detail.xml','activity_series_detail.xml'):
    if 'NestedScrollView' not in t('app/src/main/res/layout/'+x): raise SystemExit(x+' missing NestedScrollView')

s=t('app/src/main/res/layout/activity_home.xml')
s=s.replace('android:id="@+id/layout_live_categories" android:layout_width="220dp"','android:id="@+id/layout_live_categories" android:layout_width="200dp"',1)
s=s.replace('android:layout_width="210dp" android:layout_height="140dp" android:layout_margin="10dp"','android:layout_width="180dp" android:layout_height="120dp" android:layout_margin="10dp"',1)
w('app/src/main/res/layout/activity_home.xml',s)

s=t('app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt')
s=s.replace('''data class Iptv(
        val serverName: String,
        val streamUrl: String,''','''data class Iptv(
        val serverName: String,
        val serverUrl: String,
        val username: String,
        val streamUrl: String,''',1)
s=s.replace('''    ) : SearchSource() {
        override val label get() = serverName
    }

    data class Emby''','''    ) : SearchSource() {
        private val host get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')
        override val label get() = "$serverName  •  $username @ $host"
    }

    data class Emby''',1)
s=s.replace('''    ) : SearchSource() {
        override val label get() = "$serverName  •  SERIES #${show.seriesId}"
    }''','''    ) : SearchSource() {
        private val host get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')
        override val label get() = "$serverName  •  $username @ $host"
    }''',1)
s=s.replace('''SearchSource.Iptv(
                                serverName = profile.name,
                                streamUrl  = url,''','''SearchSource.Iptv(
                                serverName = profile.name,
                                serverUrl  = profile.serverUrl,
                                username   = profile.username,
                                streamUrl  = url,''',1)
s=s.replace('distinctBy { "${it.serverUrl}|${it.show.seriesId}" }','distinctBy { "${it.serverUrl}|${it.username}|${it.show.seriesId}" }')
s=s.replace('is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.show.seriesId}"','is SearchSource.IptvSeries -> "IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
anchor='''SearchResultItem(bucket.canonical, bucket.year, thumb, bucket.sources)
        }
    }

    private fun groupSeriesResults'''
replace='''val uniqueSources = bucket.sources.distinctBy { src -> when (src) {
                is SearchSource.Iptv -> "IPTV|${src.serverUrl}|${src.username}|${src.streamUrl}"
                is SearchSource.Emby -> "EMBY|${src.serverUrl}|${src.itemId}"
                is SearchSource.Plex -> "PLEX|${src.serverUrl}|${src.item.ratingKey}"
                else -> src.label
            } }
            SearchResultItem(bucket.canonical, bucket.year, thumb, uniqueSources)
        }
    }

    private fun groupSeriesResults'''
if anchor not in s: raise SystemExit('search group anchor missing')
s=s.replace(anchor,replace,1); w('app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt',s)

for x in ('activity_vod.xml','activity_series.xml'):
    s=t('app/src/main/res/layout/'+x).replace('android:layout_width="220dp" android:layout_height="match_parent" android:orientation="vertical" android:background="@color/se_panel"','android:layout_width="200dp" android:layout_height="match_parent" android:orientation="vertical" android:background="@color/se_panel"',1); w('app/src/main/res/layout/'+x,s)

md=t('app/src/main/java/com/orbital/iptv/ui/vod/MovieDetailActivity.kt')
if 'movieYear = Regex("\\\\d{4}")' not in md: raise SystemExit('movie year logic missing')
for x in ('app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt','app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt'):
    if 'GridLayoutManager(this@' not in t(x) or ', 2)' not in t(x): raise SystemExit(x+' is not 2-column')

s=t('app/src/main/res/layout/item_channel.xml')
if 'btn_fav' not in s:
    s=s.replace('''    <!-- Live indicator dot -->''','''    <TextView android:id="@+id/btn_fav" android:layout_width="38dp" android:layout_height="match_parent" android:gravity="center" android:text="♡" android:textColor="@color/sky_white" android:textSize="22sp" android:textStyle="bold" android:focusable="true" android:clickable="true" android:contentDescription="Favorite channel" />

    <!-- Live indicator dot -->''',1)
w('app/src/main/res/layout/item_channel.xml',s)
ca=t('app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt')
if 'favButton' not in ca:
    ca=ca.replace('import com.orbital.iptv.utils.ThemeManager','import com.orbital.iptv.utils.ThemeManager\nimport com.orbital.iptv.utils.FavouritesManager')
    ca=ca.replace('val epgNow: TextView? = itemView.findViewById(R.id.tv_epg_now)','val epgNow: TextView? = itemView.findViewById(R.id.tv_epg_now)\n        val favButton: TextView? = itemView.findViewById(R.id.btn_fav)')
    marker='''holder.channelName.setTextColor(textColor)

        // TV D-pad focus highlight'''
    inject='''holder.channelName.setTextColor(textColor)
        favButton?.let { fav ->
            val ctx = holder.itemView.context
            val on = FavouritesManager.containsLive(ctx, stream.streamId)
            fav.text = if (on) "♥" else "♡"
            fav.setTextColor(if (on) 0xFFFF2222.toInt() else textColor)
            fav.setOnClickListener {
                if (FavouritesManager.containsLive(ctx, stream.streamId)) {
                    FavouritesManager.removeLive(ctx, stream.streamId); fav.text="♡"; fav.setTextColor(0xFFFFFFFF.toInt())
                } else {
                    val c=PrefsManager.getCredentials(ctx); val url=c?.let { com.orbital.iptv.data.repository.XtreamRepository().buildStreamUrl(it.serverUrl,it.username,it.password,stream.streamId) } ?: ""
                    FavouritesManager.addLiveChannel(ctx,stream.name,stream.streamId,url,stream.streamIcon); fav.text="♥"; fav.setTextColor(0xFFFF2222.toInt())
                }
            }
        }

        // TV D-pad focus highlight'''
    if marker not in ca: raise SystemExit('channel adapter marker missing')
    ca=ca.replace(marker,inject,1)
w('app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt',ca)

fa=t('app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt')
fa=fa.replace('val movies = all.filter { it.type == FavType.MOVIE }','val movies = all.filter { it.type == FavType.MOVIE && !it.hasResume }')
fa=fa.replace('val series = all.filter { it.type == FavType.SERIES }','val series = all.filter { it.type == FavType.SERIES && !it.hasResume && !it.isUpNext }')
w('app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt',fa)

w('SE_BUILD_MANIFEST.txt','''SE IPTV PLAYER — SEAndroid v100.0.7
=================================
Base: SEAndroid_v100.0.6.zip
APK: SEAndroid_v100.0.7.apk
Source: SEAndroid_v100.0.7.zip
Application ID: com.se.iptv.player
Version name: 100.0.7
Version code: 1000007

10 changes: launcher +30%; Xtream logo +20%; detail touch-scroll; live sidebar/preview sizing; provider/account-aware search sources; narrower left category sidebars with left-aligned readable text; movie year next to rating; 2-column Movies/Series; category and live-channel hearts; Favorites split into Movies/Series/Live/Categories without Continue Watching.
''')
print('OK')