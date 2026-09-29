from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()

home = ROOT / "app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt"
s = home.read_text()

old = """            isFillViewport = true
            isVerticalScrollBarEnabled = true
            overScrollMode = View.OVER_SCROLL_IF_CONTENT_SCROLLS"""
new = """            isFillViewport = true
            // Hide the native scrollbar thumb on the far right, but keep the
            // ScrollView itself fully touch-scrollable.
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_IF_CONTENT_SCROLLS"""

if old not in s:
    raise SystemExit("Home ScrollView scrollbar block not found")
home.write_text(s.replace(old, new, 1))

# Keep the XML scroll behavior explicit as well. This does not disable touch scrolling.
layout = ROOT / "app/src/main/res/layout/activity_home.xml"
s = layout.read_text()
s = re.sub(
    r'(<ScrollView\b[^>]*?)android:scrollbars="[^"]*"',
    r'\1android:scrollbars="none"',
    s,
    count=1,
)
layout.write_text(s)

build = ROOT / "app/build.gradle"
s = build.read_text()
s = re.sub(r"versionCode\s+\d+", "versionCode 1000097", s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.97"', s, count=1)
build.write_text(s)

settings = ROOT / "settings.gradle"
s = settings.read_text()
s = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.97"', s, count=1)
settings.write_text(s)

print("V100.0.97 Home scrollbar-only fix applied")
