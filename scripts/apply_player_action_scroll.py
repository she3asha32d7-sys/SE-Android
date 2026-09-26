from pathlib import Path

path = Path("app/src/main/res/layout/layout_genc_player_overlay.xml")
s = path.read_text()

old = '''        <HorizontalScrollView
            android:id="@+id/genc_action_scroll"
'''
new = '''        <com.orbital.iptv.ui.player.FocusHorizontalScrollView
            android:id="@+id/genc_action_scroll"
'''
if old in s:
    s = s.replace(old, new, 1)
elif '<com.orbital.iptv.ui.player.FocusHorizontalScrollView' not in s:
    raise SystemExit("player action scroll container not found")

path.write_text(s)
print("Player action bar now uses focus-aware horizontal scrolling")
