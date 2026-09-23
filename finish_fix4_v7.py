from pathlib import Path
import re
p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/ui/home/ChannelAdapter.kt')
s=p.read_text()
s=s.replace('import com.orbital.iptv.utils.FavouritesManager\n','')
s=s.replace('        val favButton: TextView? = itemView.findViewById(R.id.btn_fav)\n','')
s=re.sub(r'\n        favButton\?\.let \{ fav ->.*?\n        \}\n\n        // TV D-pad focus highlight', '\n\n        // TV D-pad focus highlight', s, flags=re.S)
p.write_text(s)
p=Path('SEAndroid_v100.0.6/app/src/main/res/layout/item_channel.xml')
s=p.read_text()
s=re.sub(r'\s*<TextView android:id="@\+id/btn_fav"[^>]+/>\s*', '\n', s, count=1)
p.write_text(s)
print('OK')