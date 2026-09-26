from pathlib import Path
import re

path = Path("app/src/main/res/layout/activity_recordings.xml")
s = path.read_text()

include = '<include android:id="@+id/main_sidebar" android:layout_width="match_parent" android:layout_height="92dp" layout="@layout/layout_main_sidebar"/>'
if include not in s:
    raise SystemExit("main_sidebar include not found")

# Remove the dedicated RECORDS title bar and its old cyan divider.
header_pattern = re.compile(
    r'\n\s*<LinearLayout android:layout_width="match_parent" android:layout_height="62dp"[^>]*>\s*'
    r'<TextView[^>]*android:text="RECORDS"[^>]*/>\s*'
    r'</LinearLayout>\s*'
    r'<View android:layout_width="match_parent" android:layout_height="2dp" android:background="@color/sky_cyan"/>',
    re.S
)
if not header_pattern.search(s):
    raise SystemExit("RECORDS header + old divider not found")

s = header_pattern.sub("", s, count=1)

# Put the divider directly below the main sidebar.
accent = '\n    <View android:id="@+id/records_accent" android:layout_width="match_parent" android:layout_height="2dp" android:background="@color/sky_cyan"/>'
if 'android:id="@+id/records_accent"' not in s:
    s = s.replace(include, include + accent, 1)

path.write_text(s)
print("Records header removed; cyan divider moved under main sidebar.")
