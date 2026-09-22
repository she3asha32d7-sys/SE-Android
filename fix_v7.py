from pathlib import Path
import re

ROOT = Path(".")
V = "100.0.7"
NAME = "SEAndroid_v100.0.7"

def text(path):
    return Path(path).read_text(encoding="utf-8")

def write(path, s):
    Path(path).write_text(s, encoding="utf-8")

p = ROOT / "settings.gradle"
s = text(p)
s = s.replace('rootProject.name = "SEAndroid_v100.0.6"', 'rootProject.name = "SEAndroid_v100.0.7"')
if 'rootProject.name = "SEAndroid_v100.0.7"' not in s:
    raise SystemExit("settings.gradle version marker not found")
write(p, s)

p = ROOT / "app/build.gradle"
s = text(p)
s, n1 = re.subn(r'(?m)^\s*versionCode\s+\d+\s*, '        versionCode 1000007', s, count=1)
s, n2 = re.subn(r'(?m)^\s*versionName\s+"[^"]+"\s*, '        versionName "100.0.7"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"app/build.gradle version fields not found: code={n1}, name={n2}")
write(p, s)

for name in ["SE_BUILD_MANIFEST.txt", "README.md", "FINAL_33_AUDIT.md", ".github/workflows/build-apk.yml"]:
    p = ROOT / name
    if p.exists():
        s = text(p).replace("SEAndroid_v100.0.6", NAME).replace("SEAndroid v100.0.6", "SEAndroid v100.0.7").replace("v100.0.6", "v100.0.7").replace("100.0.6", V)
        write(p, s)

g = ROOT / "app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt"
s = text(g)
old = '''        override val label get() = "$serverName  •  SERIES #${show.seriesId}"'''
new = '''        private val host: String
            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')

        // A profile/display name alone is not enough when several Xtream accounts exist.
        override val label: String
            get() = "$serverName  •  $username @ $host"'''
if old in s:
    s = s.replace(old, new)
elif new not in s:
    raise SystemExit("IptvSeries label block not found")
s = s.replace('"IPTV|${src.serverUrl}|${src.show.seriesId}"', '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle versionCode", "versionCode 1000007"),
    ("app/build.gradle versionName", 'versionName "100.0.7"'),
    ("GlobalSearchActivity label", "$username @ $host"),
    ("GlobalSearchActivity dedupe", '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"'),
]
for label, needle in checks:
    path = g if label.startswith("GlobalSearchActivity") else ROOT / ("settings.gradle" if label == "settings.gradle" else "app/build.gradle")
    if needle not in text(path):
        raise SystemExit("Verification failed: " + label)
print("v100.0.7 identity/search fixes applied and verified."), '        versionCode 1000007', s, count=1)
s, n2 = re.subn(r'(?m)^\\s*versionName\\s+"[^"]+"\\s*$', '        versionName "100.0.7"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"app/build.gradle version fields not found: code={n1}, name={n2}")
write(p, s)

for name in ["SE_BUILD_MANIFEST.txt", "README.md", "FINAL_33_AUDIT.md", ".github/workflows/build-apk.yml"]:
    p = ROOT / name
    if p.exists():
        s = text(p).replace("SEAndroid_v100.0.6", NAME).replace("SEAndroid v100.0.6", "SEAndroid v100.0.7").replace("v100.0.6", "v100.0.7").replace("100.0.6", V)
        write(p, s)

g = ROOT / "app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt"
s = text(g)
old = '''        override val label get() = "$serverName  •  SERIES #${show.seriesId}"'''
new = '''        private val host: String
            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')

        // A profile/display name alone is not enough when several Xtream accounts exist.
        override val label: String
            get() = "$serverName  •  $username @ $host"'''
if old in s:
    s = s.replace(old, new)
elif new not in s:
    raise SystemExit("IptvSeries label block not found")
s = s.replace('"IPTV|${src.serverUrl}|${src.show.seriesId}"', '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle versionCode", "versionCode 1000007"),
    ("app/build.gradle versionName", 'versionName "100.0.7"'),
    ("GlobalSearchActivity label", "$username @ $host"),
    ("GlobalSearchActivity dedupe", '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"'),
]
for label, needle in checks:
    path = g if label.startswith("GlobalSearchActivity") else ROOT / ("settings.gradle" if label == "settings.gradle" else "app/build.gradle")
    if needle not in text(path):
        raise SystemExit("Verification failed: " + label)
print("v100.0.7 identity/search fixes applied and verified."), '        versionName "100.0.7"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"app/build.gradle version fields not found: code={n1}, name={n2}")
write(p, s)

for name in ["SE_BUILD_MANIFEST.txt", "README.md", "FINAL_33_AUDIT.md", ".github/workflows/build-apk.yml"]:
    p = ROOT / name
    if p.exists():
        s = text(p).replace("SEAndroid_v100.0.6", NAME).replace("SEAndroid v100.0.6", "SEAndroid v100.0.7").replace("v100.0.6", "v100.0.7").replace("100.0.6", V)
        write(p, s)

g = ROOT / "app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt"
s = text(g)
old = '''        override val label get() = "$serverName  •  SERIES #${show.seriesId}"'''
new = '''        private val host: String
            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')

        // A profile/display name alone is not enough when several Xtream accounts exist.
        override val label: String
            get() = "$serverName  •  $username @ $host"'''
if old in s:
    s = s.replace(old, new)
elif new not in s:
    raise SystemExit("IptvSeries label block not found")
s = s.replace('"IPTV|${src.serverUrl}|${src.show.seriesId}"', '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle versionCode", "versionCode 1000007"),
    ("app/build.gradle versionName", 'versionName "100.0.7"'),
    ("GlobalSearchActivity label", "$username @ $host"),
    ("GlobalSearchActivity dedupe", '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"'),
]
for label, needle in checks:
    path = g if label.startswith("GlobalSearchActivity") else ROOT / ("settings.gradle" if label == "settings.gradle" else "app/build.gradle")
    if needle not in text(path):
        raise SystemExit("Verification failed: " + label)
print("v100.0.7 identity/search fixes applied and verified."), '        versionCode 1000007', s, count=1)
s, n2 = re.subn(r'(?m)^\\s*versionName\\s+"[^"]+"\\s*$', '        versionName "100.0.7"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit(f"app/build.gradle version fields not found: code={n1}, name={n2}")
write(p, s)

for name in ["SE_BUILD_MANIFEST.txt", "README.md", "FINAL_33_AUDIT.md", ".github/workflows/build-apk.yml"]:
    p = ROOT / name
    if p.exists():
        s = text(p).replace("SEAndroid_v100.0.6", NAME).replace("SEAndroid v100.0.6", "SEAndroid v100.0.7").replace("v100.0.6", "v100.0.7").replace("100.0.6", V)
        write(p, s)

g = ROOT / "app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt"
s = text(g)
old = '''        override val label get() = "$serverName  •  SERIES #${show.seriesId}"'''
new = '''        private val host: String
            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')

        // A profile/display name alone is not enough when several Xtream accounts exist.
        override val label: String
            get() = "$serverName  •  $username @ $host"'''
if old in s:
    s = s.replace(old, new)
elif new not in s:
    raise SystemExit("IptvSeries label block not found")
s = s.replace('"IPTV|${src.serverUrl}|${src.show.seriesId}"', '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"')
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle versionCode", "versionCode 1000007"),
    ("app/build.gradle versionName", 'versionName "100.0.7"'),
    ("GlobalSearchActivity label", "$username @ $host"),
    ("GlobalSearchActivity dedupe", '"IPTV|${src.serverUrl}|${src.username}|${src.show.seriesId}"'),
]
for label, needle in checks:
    path = g if label.startswith("GlobalSearchActivity") else ROOT / ("settings.gradle" if label == "settings.gradle" else "app/build.gradle")
    if needle not in text(path):
        raise SystemExit("Verification failed: " + label)
print("v100.0.7 identity/search fixes applied and verified.")