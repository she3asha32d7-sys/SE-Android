from pathlib import Path
import re

ROOT=Path(".")
targets=[
    "app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt",
    "app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt",
    "app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt",
    "app/src/main/java/com/orbital/iptv/ui/series/SeriesDetailActivity.kt",
    "app/src/main/java/com/orbital/iptv/ui/tv/TvModeActivity.kt",
]
for p in ROOT.rglob("*.kt"):
    s=p.as_posix()
    low=s.lower()
    if any(k in low for k in ("favorite","favourite","search","sidebar","adapter","dialog","detail")) and p not in [ROOT/x for x in targets]:
        targets.append(s)

print("===V6_SOURCE_INSPECTION===")
for rel in targets:
    p=ROOT/rel
    if not p.exists():
        continue
    try: text=p.read_text(encoding="utf-8")
    except: continue
    low=text.lower()
    interesting=("favorite","favourite","search","setSingleChoiceItems","alertdialog","gridlayoutmanager","spanCount","logo","preview","sidebar","recyclerview","year","rating","tv_season","lina")
    if any(x in low for x in interesting):
        print(f"\n---FILE {rel}---")
        lines=text.splitlines()
        hits=[i for i,l in enumerate(lines) if any(x in l.lower() for x in interesting)]
        shown=set()
        for i in hits:
            a=max(0,i-4); b=min(len(lines),i+9)
            if a in shown: continue
            shown.add(a)
            print(f"[lines {a+1}-{b}]")
            print("\n".join(f"{j+1}: {lines[j]}" for j in range(a,b)))
print("===END_V6_SOURCE_INSPECTION===")
