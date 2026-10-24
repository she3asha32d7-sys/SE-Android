#!/usr/bin/env python3
"""V100.0.192: fix PlayOnDlna Samsung DLNA interoperability without changing other cast engines."""
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v192.py <source-root>")
root = Path(sys.argv[1]).resolve()
payload = Path(__file__).resolve().parent / "payload"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player_file = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
notices_file = root / "THIRD_PARTY_NOTICES.md"
assert all(p.is_file() for p in (gradle, settings, player_file, notices_file)), "V191 source files missing"
assert (payload / "PlayOnDlnaEngine.kt").is_file(), "V192 engine payload missing"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player_file.read_text(encoding="utf-8")
notices = notices_file.read_text(encoding="utf-8")
assert 'versionCode 1000191' in g and 'versionName "100.0.191"' in g, "Expected V191 app version"
assert 'rootProject.name = "SEAndroid_v100.0.191"' in s, "Expected V191 root project name"

# V191 sent every network stream through the CastLab relay when PlayOnDlna was selected, unlike
# the known-working TDM-compatible path. This can change provider/HLS behavior. Retain the local
# server only for PHONE FILES; direct IPTV URLs get URL/MIME candidate handling like the TDM route.
p = replace_once(
    p,
    'val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB ||\n'
    '                            engine == OriginalDlnaEngine.PLAYONDLNA) {',
    'val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB) {',
    "Use local relay only for PHONE FILES / CastLab"
)
p = replace_once(
    p,
    'if (engine == OriginalDlnaEngine.CASTLAB || engine == OriginalDlnaEngine.FONGMI) {\n'
    '                                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())\n'
    '                                    .setTitle(if (engine == OriginalDlnaEngine.FONGMI) "FONGMI DLNA — FAILED" else "CASTLAB DIAGNOSTICS — FAILED")',
    'if (engine == OriginalDlnaEngine.CASTLAB || engine == OriginalDlnaEngine.FONGMI ||\n'
    '                                engine == OriginalDlnaEngine.PLAYONDLNA) {\n'
    '                                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())\n'
    '                                    .setTitle(when (engine) {\n'
    '                                        OriginalDlnaEngine.FONGMI -> "FONGMI DLNA — FAILED"\n'
    '                                        OriginalDlnaEngine.PLAYONDLNA -> "PLAYONDlNA DLNA DIAGNOSTICS — FAILED"\n'
    '                                        else -> "CASTLAB DIAGNOSTICS — FAILED"\n'
    '                                    })',
    "PlayOnDlna diagnostic dialog"
)
p = replace_once(
    p,
    'Toast.makeText(this@PlayerActivity, "CASTLAB ERROR DETAILS COPIED", Toast.LENGTH_SHORT).show()',
    'Toast.makeText(this@PlayerActivity, "${engine.label} ERROR DETAILS COPIED", Toast.LENGTH_SHORT).show()',
    "Engine-specific copied-diagnostics toast"
)

engine_dir = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna/playondlna"
engine_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(payload / "PlayOnDlnaEngine.kt", engine_dir / "PlayOnDlnaEngine.kt")

g = g.replace("versionCode 1000191", "versionCode 1000192", 1)
g = g.replace('versionName "100.0.191"', 'versionName "100.0.192"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.191"', 'rootProject.name = "SEAndroid_v100.0.192"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player_file.write_text(p, encoding="utf-8")

notices = notices.rstrip() + """

V100.0.192 — PlayOnDlna Samsung interoperability correction
-----------------------------------------------------------
The PlayOnDlna-inspired sender remains a separate route. SSDP now uses a full MX=5 collection
window, root-device/MediaRenderer/AVTransport targets, multicast-socket binding to Wi-Fi when
available, and DLNA/UPnP user-agent framing used by the in-project TDM-compatible Samsung route.
Playback performs best-effort Stop, URL/MIME candidate retries (including Xtream live .ts/.m3u8
alternatives), fixed-length SOAP requests, transport-state checks when supported, and PHONE FILES
HTTP-transfer diagnostics. Network IPTV links are sent directly to the TV first; only local PHONE
FILES use the local range-capable relay. This adaptation does not replace other cast engines.
"""
notices_file.write_text(notices, encoding="utf-8")

(root / "PLAYONDlNA_CAST_V100_0_192_AUDIT.md").write_text("""# PlayOnDlna / TDM interoperability review — V100.0.192

## Reviewed baseline
- Android baseline: V100.0.191, source artifact SE-Android-v100.0.191-source.zip.
- Upstream PlayOnDlna: https://github.com/scovillo/playondlna (GPL-3.0-only; attribution and license
  remain in THIRD_PARTY_NOTICES.md and THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt).
- In-project known-working reference path: TdmCompatibleDlnaManager, used by CAST > DLNA 2.

## Root-cause findings from code comparison

1. Discovery was less robust. V191 used a basic DatagramSocket, MX=2, short quiet-period early exit,
   and no explicit Wi-Fi interface selection. The TDM-compatible path uses MulticastSocket, selects
   Wi-Fi when available, queries upnp:rootdevice and MediaRenderer, uses MX=5, and waits for responses.
2. Only one media URL/MIME pair was sent. V191 performed a single SetAVTransportURI and Play with a
   250 ms gap and no best-effort Stop. TDM tries live .ts and .m3u8 variants, multiple MIME declarations,
   fixed-length SOAP requests, and a longer delay.
3. Network links were always forced through a second local proxy. V191 prepared every PlayOnDlna
   network source using CastLabMediaServer, unlike TDM, which sends network IPTV links directly. The
   extra relay can alter HLS/source behavior and adds a second failure point. V192 uses the relay for
   local PHONE FILES and leaves network IPTV/VOD links direct by default.
4. SOAP acceptance was treated as playback success. V191 did not inspect transport state or verify
   phone-local file transfer. V192 queries GetTransportInfo when supported, retries alternate candidates
   when the reported state is not PLAYING/TRANSITIONING, and checks HTTP bytes for local files.

## V192 changes
- Kept DLNA 8 as a separate sender; other cast engines and chooser entries remain unchanged.
- Implemented longer SSDP discovery and Wi-Fi-interface selection.
- Added Stop-before-cast, live URL variants, MIME fallback, fixed-length SOAP and actionable errors.
- Added transport-state validation where supported and local HTTP receiver diagnostics.
- Removed forced CastLab proxy use for network IPTV/VOD; PHONE FILES still use the local server.
- Added detailed copyable failure diagnostics.

## Verification boundary
GitHub Actions performs static invariants, Kotlin/Gradle release build, APK signature/certificate
verification, and ZIP/APK integrity checks. Final playback validation still requires a real TV on the
same network; if it fails, the V192 error dialog exposes SOAP/transport or local HTTP failure instead
of only a generic toast.
""", encoding="utf-8")

assert 'versionCode 1000192' in g and 'versionName "100.0.192"' in g
assert 'rootProject.name = "SEAndroid_v100.0.192"' in s
assert 'OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.discover(this@PlayerActivity)' in p
assert 'OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.cast(device, castUri, channelName, isLive)' in p
assert 'val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB) {' in p
assert '.setNegativeButton("DISCONNECT", null)' in p and '.setPositiveButton("CANCEL", null)' in p
assert 'window.decorView.layoutDirection = View.LAYOUT_DIRECTION_LTR' in p
engine = (engine_dir / "PlayOnDlnaEngine.kt").read_text(encoding="utf-8")
assert 'GetTransportInfo' in engine and 'MX: 5' in engine
assert (root / "THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt").is_file()
print("V100.0.192 PlayOnDlna compatibility patch applied; static invariants passed.")
