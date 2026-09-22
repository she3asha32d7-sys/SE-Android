#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
files = []
for p in root.rglob("*"):
    if p.is_file() and not any(part in {".gradle", "build", ".idea"} for part in p.parts):
        files.append(p)

text_files = []
for p in files:
    try:
        data = p.read_text(encoding="utf-8", errors="ignore")
        if "\x00" not in data[:4096]:
            text_files.append((p, data))
    except Exception:
        pass

all_text = "\n".join(data for _, data in text_files)
low = all_text.lower()

def paths_matching(patterns):
    out = []
    for p, data in text_files:
        d = data.lower()
        if any(re.search(pat, d, re.I | re.M) for pat in patterns):
            out.append(str(p.relative_to(root)))
    return out

def evidence(patterns):
    return paths_matching(patterns)[:8]

checks = [
("01","Main sidebar: Search below Favorites + persistent sidebar + category sidebar",
 [r"favorites", r"search", r"main.?sidebar|sidebar"], "Static evidence only; exact focus/persistence needs runtime test"),
("02","Main sidebar touch scrolling",
 [r"NestedScrollView|ScrollView|vertical.*scroll|onTouchEvent"], "Scroll/touch evidence detected"),
("03","Logo rules",
 [r"se_logo_full|se_logo|se_launcher|launcher|IPTV"], "Logo resources/code detected; visual size/color requires asset review"),
("04","Series search duplicate poster/data bug",
 [r"series.*search|search.*series|distinct|dedup|filterNot"], "Series/search data path detected; duplicate rendering needs runtime dataset test"),
("05","Live TV: one row + larger item + mini preview + full playback",
 [r"live.*(recycler|adapter)|LinearLayoutManager|mini(player|_player)|preview|small.*player|full.*screen"], "Live list/player evidence detected"),
("06","Home: top 3 buttons + 15 history + trash",
 [r"continue watching|watch history|take\(\s*15|remove.*history|trash"], "History/continue/trash evidence detected"),
("07","Remove Back text from specified pages",
 [r"\bback\b|btn.?back|text.*back"], "Back references detected; exact forbidden locations need UI review"),
("08","Movies release year beside rating",
 [r"release.?year|year.*rating|rating.*year"], "Movie year/rating evidence detected"),
("09","Remove app version from main sidebar",
 [r"versionName|version.*sidebar|sidebar.*version"], "Version/sidebar references detected; placement needs UI review"),
("10","Heart favorites on all movies/series",
 [r"favorite|favourite|heart|isFavorite"], "Favorite/heart evidence detected"),
("11","Remove Box Office text",
 [r"box.?office"], "Box Office references detected; exact visible location needs UI review"),
("12","Landscape only / auto rotate",
 [r"screenOrientation|landscape|sensorLandscape"], "Orientation evidence detected"),
("13","Remove clock below Settings",
 [r"tv_sidebar_time|clock|sidebar.*time"], "Sidebar clock references detected; placement needs UI review"),
("14","Fixed header: app name + date/time, DD/M/Y, 12h AM/PM",
 [r"SE IPTV PLAYER|SimpleDateFormat|dd.?MM.?yyyy|hh.*a|AM|PM"], "Header/date/time evidence detected"),
("15","New Settings options and confirmations",
 [r"HLS|MPEG.?TS|auto.?rotate|0\.5x|1\.5x|2x|3x|4x|clear watch history|clear favorite|reset app|about SE IPTV"], "Settings-option evidence detected"),
("16","Search labels ALL/LIVE TV + live channel search",
 [r"EVERYTHING|LIVE TV|live.*channel|channel.*search"], "Search/live evidence detected"),
("17","Remove breadcrumb SE IPTV PLAYER + dynamic page text",
 [r"SE IPTV PLAYER.*Movies|SE IPTV PLAYER.*Series|breadcrumb"], "Breadcrumb/header references detected"),
("18","Search keyboard immediately + results while typing",
 [r"requestFocus|showSoftInput|InputMethodManager|TextWatcher|afterTextChanged|doOnTextChanged"], "Keyboard/focus/typing-search evidence detected"),
("19","List Users: labels, masked password, ADD USER, active, Edit/Disconnect",
 [r"ADD USER|Edit User|Disconnect Provider|password|active.*user|selected.*user|host"], "User-management evidence detected"),
("20","Category sidebar favorites heart",
 [r"category.*favorite|category.*heart|favorite.*category|heart"], "Category/favorite evidence detected"),
("21","Player redesign: seek, swipes, records, speed",
 [r"Score|News|Goal Flash|Seek|5 sec|10 sec|30 sec|1 min|5 min|10 min|brightness|volume|RECORDS|recording|speed"], "Player-control evidence detected"),
("22","Main sidebar touch scrolling",
 [r"MainSidebar|main.?sidebar|NestedScrollView|ScrollView"], "Main sidebar/scroll evidence detected"),
("23","Category sidebar only for Live/Movies/Series",
 [r"category.*sidebar|LIVE|MOVIES|SERIES|main.?sidebar"], "Sidebar-routing evidence detected"),
("24","Live/Movies/Series focus first option",
 [r"requestFocus|focus.*first|setSelection\(0|scrollToPosition\(0"], "Focus-first evidence detected"),
("25","Live TV search top-center, not category sidebar; content-only Movies/Series",
 [r"search.*live|live.*search|category.*search|searchView|EditText"], "Search/routing evidence detected; exact location needs UI review"),
("26","Movies/Series search fields top-center",
 [r"movie.*search|series.*search|search.*movie|search.*series"], "Movie/series search evidence detected"),
("27","Exit dialog exact wording",
 [r"Do You Want To Exit The App|Yes|No"], "Exit-dialog evidence detected"),
("28","Movies/Series 3 per row + larger sidebars/fonts",
 [r"spanCount.*3|GridLayoutManager|textSize|sidebar.*width|width.*sidebar"], "Grid/font/sidebar sizing evidence detected"),
("29","Movies reference design + no Back under Play Movie",
 [r"Play Movie|Movie Detail|MoviesActivity|VodActivity"], "Movie page evidence detected; screenshot comparison required"),
("30","Series reference design + no Back beside Favorites",
 [r"SeriesActivity|SeriesDetailActivity|Favorites"], "Series page evidence detected; screenshot comparison required"),
("31","Resume/player choice/Open With/poster/DOWNLOAD/Downloads controls",
 [r"Continue From|Start From Beginning|Player For This Movie|Open With|DOWNLOAD|Downloads|FIND FILE LOCATION|COPY|REMOVE FROM LIST|DELETE FILE"], "Resume/download evidence detected"),
("32","Live player HLS <-> MPEG-TS switch",
 [r"HLS.*MPEG|MPEG.*HLS|switch.*format|stream.*format"], "Live-format evidence detected"),
("33","Records page unified + file controls",
 [r"Records|Recordings|FIND FILE LOCATION|COPY|REMOVE FROM LIST|DELETE FILE"], "Record-page evidence detected"),
]

rows = []
for num, title, pats, note in checks:
    ev = evidence(pats)
    rows.append((num, title, "EVIDENCE" if ev else "NO EVIDENCE", "; ".join(ev) if ev else "-", note))

Path("AUDIT_FILES.txt").write_text(
    "\n".join(str(p.relative_to(root)) for p in sorted(files)) + "\n",
    encoding="utf-8"
)

md = [
    "# SEAndroid v100.0.1 — 33 Change Source Audit",
    "",
    "Source root: " + str(root),
    "",
    "This is a static source audit. EVIDENCE means implementation markers were found. It is not proof of runtime behavior or pixel-perfect UI.",
    "",
    "| # | Requested change | Result | Evidence files | Notes |",
    "|---:|---|---|---|---|"
]
for row in rows:
    vals = [v.replace("|", "\\|").replace("\n", " ") for v in row]
    md.append("| " + " | ".join(vals) + " |")

md += [
    "",
    "## Summary",
    f"- Source files scanned: **{len(files)}**",
    f"- Text files scanned: **{len(text_files)}**",
    f"- Items with evidence markers: **{sum(1 for r in rows if r[2] == 'EVIDENCE')} / 33**",
    f"- Items with no evidence markers: **{sum(1 for r in rows if r[2] == 'NO EVIDENCE')} / 33**",
]
Path("AUDIT_33.md").write_text("\n".join(md), encoding="utf-8")
