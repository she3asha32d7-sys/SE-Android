from pathlib import Path

def text(path):
    return Path(path).read_text(encoding="utf-8")

def write(path, s):
    Path(path).write_text(s, encoding="utf-8")

p = Path("settings.gradle")
s = text(p).replace('rootProject.name = "SEAndroid_v100.0.6"',
                   'rootProject.name = "SEAndroid_v100.0.7"')
if 'rootProject.name = "SEAndroid_v100.0.7"' not in s:
    raise SystemExit("settings.gradle version marker not found")
write(p, s)

p = Path("app/build.gradle")
s = text(p)
if "versionCode 201" not in s or 'versionName "2.0.1"' not in s:
    raise SystemExit("expected old app version markers not found")
s = s.replace("versionCode 201", "versionCode 1000007", 1)
s = s.replace('versionName "2.0.1"', 'versionName "100.0.7"', 1)
write(p, s)

g = Path("app/src/main/java/com/orbital/iptv/ui/search/GlobalSearchActivity.kt")
s = text(g)
old_label = '        override val label get() = "$serverName  •  SERIES #${show.seriesId}"'
new_label = '''        private val host: String
            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')

        override val label: String
            get() = "$serverName  •  $username @ $host"'''
if old_label not in s:
    raise SystemExit("IptvSeries label context not found")
s = s.replace(old_label, new_label, 1)

old_key = '"IPTV|${src.serverUrl}|${src.show.seriesId}"'
new_key = '"IPTV|${src.serverUrl}|${src.username}|${src.password.hashCode()}|${src.show.seriesId}"'
if old_key not in s:
    raise SystemExit("IPTV source dedupe key context not found")
s = s.replace(old_key, new_key, 1)
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle", "versionCode 1000007"),
    ("app/build.gradle", 'versionName "100.0.7"'),
    ("GlobalSearchActivity.kt", "$username @ $host"),
]
for fn, needle in checks:
    if needle not in text(fn):
        raise SystemExit(f"verification failed: {fn}: {needle}")
print("SEAndroid v100.0.7 identity/search fixes applied.")
