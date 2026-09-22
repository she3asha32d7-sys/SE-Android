from pathlib import Path
import re

def text(path):
    return Path(path).read_text(encoding="utf-8")

def write(path, s):
    Path(path).write_text(s, encoding="utf-8")

# Release identity.
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

start = s.index("data class IptvSeries")
end = s.index("data class EmbyShow", start)
block = s[start:end]

D = "$"
old_label = '        override val label get() = "' + D + 'serverName  •  SERIES #' + D + '{show.seriesId}"'
new_label = (
    '        private val host: String\n'
    '            get() = serverUrl.removePrefix("https://").removePrefix("http://").trimEnd('/').substringBefore('/')\n\n'
    '        override val label: String\n'
    '            get() = "' + D + 'serverName  •  "' + ' + "' + D + 'username @ "' + ' + host\n'
)
block2, n = re.subn(r'(?m)^\s*override val label get\(\) = .*\n', new_label, block, count=1)
if n != 1 or old_label not in block:
    raise SystemExit("IptvSeries label context not found")
s = s[:start] + block2 + s[end:]

old_key = '"IPTV|' + D + '{src.serverUrl}|' + D + '{src.show.seriesId}"'
new_key = '"IPTV|' + D + '{src.serverUrl}|' + D + '{src.username}|' + D + '{src.password.hashCode()}|' + D + '{src.show.seriesId}"'
if old_key not in s:
    raise SystemExit("IPTV source dedupe key context not found")
s = s.replace(old_key, new_key, 1)
write(g, s)

checks = [
    ("settings.gradle", 'rootProject.name = "SEAndroid_v100.0.7"'),
    ("app/build.gradle", "versionCode 1000007"),
    ("app/build.gradle", 'versionName "100.0.7"'),
    ("GlobalSearchActivity.kt", "$username @ "),
]
for fn, needle in checks:
    if needle not in text(fn):
        raise SystemExit(f"verification failed: {fn}: {needle}")
print("SEAndroid v100.0.7 identity/search fixes applied.")
