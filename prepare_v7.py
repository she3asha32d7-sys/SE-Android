from pathlib import Path
R=Path('SEAndroid_v100.0.6')
def t(p): return (R/p).read_text()
def w(p,s): (R/p).write_text(s)

# Make the v100.0.6 artifact source compatible with the verified v7 patch assumptions.
for p,first,nexttag in [('app/src/main/res/layout/activity_movie_detail.xml','android:layout_height="34dp"','android:layout_height="54dp"'),('app/src/main/res/layout/activity_series_detail.xml','android:layout_height="34dp"','android:layout_height="48dp"')]:
    s=t(p)
    if 'NestedScrollView' not in s:
        a=s.find('<LinearLayout android:layout_width="match_parent" '+first); b=s.find('<LinearLayout android:layout_width="match_parent" '+nexttag,a)
        if a<0 or b<0: raise SystemExit('detail anchors missing: '+p)
        mid=s[a:b].replace('android:layout_height="0dp" android:layout_weight="1"','android:layout_height="wrap_content"',1)
        mid=mid.replace('android:id="@+id/tv_plot" android:textColor="@color/sky_white" android:textSize="15sp" android:lineSpacingMultiplier="1.25" android:maxLines="7" android:ellipsize="end" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1"','android:id="@+id/tv_plot" android:textColor="@color/sky_white" android:textSize="15sp" android:lineSpacingMultiplier="1.25" android:layout_width="match_parent" android:layout_height="wrap_content"')
        s=s[:a]+'<androidx.core.widget.NestedScrollView android:id="@+id/detail_info_scroll" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1" android:fillViewport="true" android:scrollbars="none"><LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical">'+mid+'</LinearLayout></androidx.core.widget.NestedScrollView>'+s[b:]
        w(p,s)

for p in ['app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt','app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt']:
    s=t(p).replace(', 3)',', 2)',1); w(p,s)

p='app/src/main/res/layout/item_channel.xml'; s=t(p)
if 'btn_fav' not in s:
    s=s.replace('    <!-- Live indicator dot -->','    <TextView android:id="@+id/btn_fav" android:layout_width="38dp" android:layout_height="match_parent" android:gravity="center" android:text="♡" android:textColor="@color/sky_white" android:textSize="22sp" android:focusable="true" android:clickable="true" />\n    <!-- Live indicator dot -->',1)
w(p,s)
p='app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt'; s=t(p)
if 'favButton' not in s:
    s=s.replace('import com.orbital.iptv.utils.ThemeManager','import com.orbital.iptv.utils.ThemeManager\nimport com.orbital.iptv.utils.FavouritesManager',1)
    s=s.replace('val epgNow: TextView? = itemView.findViewById(R.id.tv_epg_now)','val epgNow: TextView? = itemView.findViewById(R.id.tv_epg_now)\n        val favButton: TextView? = itemView.findViewById(R.id.btn_fav)',1)
    marker='''holder.channelName.setTextColor(textColor)

        // TV D-pad focus highlight'''
    inject='''holder.channelName.setTextColor(textColor)
        favButton?.let { fav ->
            val ctx = holder.itemView.context
            val on = FavouritesManager.containsLive(ctx, stream.streamId)
            fav.text = if (on) "♥" else "♡"
            fav.setTextColor(if (on) 0xFFFF2222.toInt() else textColor)
            fav.setOnClickListener {
                if (FavouritesManager.containsLive(ctx, stream.streamId)) FavouritesManager.removeLive(ctx, stream.streamId)
                else {
                    val c=PrefsManager.getCredentials(ctx)
                    val url=c?.let { com.orbital.iptv.data.repository.XtreamRepository().buildStreamUrl(it.serverUrl,it.username,it.password,stream.streamId) } ?: ""
                    FavouritesManager.addLiveChannel(ctx,stream.name,stream.streamId,url,stream.streamIcon)
                }
                notifyItemChanged(position)
            }
        }

        // TV D-pad focus highlight'''
    if marker not in s: raise SystemExit('channel adapter marker missing')
    s=s.replace(marker,inject,1)
w(p,s)
print('OK')