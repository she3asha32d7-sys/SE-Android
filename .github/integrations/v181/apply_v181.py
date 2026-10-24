#!/usr/bin/env python3
"""Apply the V181 CastLab transport-observation fix to the reconstructed V180 source."""
from __future__ import annotations

import sys
from pathlib import Path
import shutil

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v181.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()
assert 'versionCode 1000180' in gradle.read_text(encoding="utf-8")
assert 'versionName "100.0.180"' in gradle.read_text(encoding="utf-8")
assert 'rootProject.name = "SEAndroid_v100.0.180"' in settings.read_text(encoding="utf-8")

engine_root = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna"
engine_root.mkdir(parents=True, exist_ok=True)
for name in ("CastLabDlnaEngine.kt", "CastLabMediaServer.kt"):
    source = repo / ".github/integrations/v181" / name
    assert source.is_file(), f"Missing V181 payload: {source}"
    shutil.copy2(source, engine_root / name)

g = gradle.read_text(encoding="utf-8")
g = g.replace("versionCode 1000180", "versionCode 1000181", 1)
g = g.replace('versionName "100.0.180"', 'versionName "100.0.181"', 1)
gradle.write_text(g, encoding="utf-8")

s = settings.read_text(encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.180"', 'rootProject.name = "SEAndroid_v100.0.181"', 1),
    encoding="utf-8"
)

p = player.read_text(encoding="utf-8")
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)' in p
old = '''                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "${engine.label} CASTING TO ${device.name}", Toast.LENGTH_SHORT).show()
                            showGencOverlay()
                        } else {
                            Toast.makeText(this@PlayerActivity, engine.label + " FAILED: " + (result.exceptionOrNull()?.message ?: "UNKNOWN ERROR"), Toast.LENGTH_LONG).show()
                        }'''
new = '''                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            if (engine == OriginalDlnaEngine.CASTLAB && CastLabMediaServer.isServing(castUri)) {
                                val probe = CastLabMediaServer.receiverProbe()
                                Toast.makeText(
                                    this@PlayerActivity,
                                    "CASTLAB TV TRANSFER: ${probe.bytesServed / 1024L} KB FROM PHONE",
                                    Toast.LENGTH_LONG
                                ).show()
                            } else {
                                Toast.makeText(this@PlayerActivity, "${engine.label} CASTING TO ${device.name}", Toast.LENGTH_SHORT).show()
                            }
                            showGencOverlay()
                        } else {
                            val errorMessage = result.exceptionOrNull()?.message ?: "UNKNOWN ERROR"
                            if (engine == OriginalDlnaEngine.CASTLAB) {
                                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                                    .setTitle("CASTLAB DIAGNOSTICS — FAILED")
                                    .setMessage(errorMessage)
                                    .setPositiveButton("COPY DETAILS") { _, _ ->
                                        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                                        clipboard.setPrimaryClip(android.content.ClipData.newPlainText("SE CastLab failure", errorMessage))
                                        Toast.makeText(this@PlayerActivity, "CASTLAB ERROR DETAILS COPIED", Toast.LENGTH_SHORT).show()
                                    }
                                    .setNegativeButton("CLOSE", null)
                                    .show()
                            } else {
                                Toast.makeText(this@PlayerActivity, engine.label + " FAILED: " + errorMessage, Toast.LENGTH_LONG).show()
                            }
                        }'''
if old not in p:
    raise SystemExit("Unable to find V180 CastLab result handling block")
p = p.replace(old, new, 1)
player.write_text(p, encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
notice_text = notices.read_text(encoding="utf-8") if notices.exists() else ""
notice_text += """

V100.0.181 CastLab receiver-transfer validation
-----------------------------------------------
This revision does not treat a successful HTTP 200 SOAP response as proof of playback. For locally
served media it observes requests arriving from a peer other than the phone and counts actual
media bytes sent. If the TV never reads at least 4 KiB after the CastLab sequence, the route retries
using Samsung-compatible SOAP/DIDL MIME candidates. If that also fails to trigger a transfer, the
app displays a diagnostic dialog with phone URL, TV peer IP (when observed), Range request, HTTP
status, bytes served and any server-side request error. The diagnostic text can be copied.

The server now prefers the active Android Wi-Fi Network's LinkProperties IPv4 address, uses port
9125 or a nearby deterministic port, handles OPTIONS, ignores unsupported multi-range requests by
serving the full resource instead of returning 416, emits cache/last-modified/entity headers, and
logs each television HTTP request. AVTransport:1 is preferred when present to match CastLab's
original service selection. Existing other Cast menu choices are preserved.
"""
notices.write_text(notice_text, encoding="utf-8")

audit = root / "CASTLAB_V100_0_181_AUDIT.md"
audit.write_text("""# CastLab V100.0.181 — error investigation and transport validation

## Why V180 could still display "Unexpected error"
V180 considered the CastLab handoff successful after the TV's AVTransport service returned
success for SetAVTransportURI and Play. This only confirms that the TV accepted the control
commands. It does not confirm the TV could resolve the right phone Wi-Fi address, connect to the
local HTTP server, request a byte range, or actually read media bytes. A renderer can therefore
show its own generic error while SE has already shown "casting".

## Changes
1. The media server chooses the IPv4 address from Android's active Wi-Fi Network/LinkProperties
   first, rather than assuming the first interface named wlan/wifi is the active route.
2. The service prefers port 9125 and searches a small predictable range if another process (such
   as CastLab itself still running) owns it.
3. GET/HEAD/OPTIONS are handled; OPTIONS returns 200, supported methods are advertised, and an
   unrecognized multi-range header no longer causes a 416 for an otherwise valid media URL.
4. Responses include Accept-Ranges, Content-Range when applicable, DLNA headers, no-cache/pragma,
   Last-Modified and ETag.
5. The server records remote peer IP, request path, Range, HTTP status, bytes actually written and
   server-side exceptions. Local self-test requests from the phone are not counted as TV traffic.
6. On local-file casting, a successful SOAP response is followed by a real HTTP transfer check. If
   the TV has not read 4 KiB, SE retries the Samsung-compatible transport with MIME candidates.
   Persistent failures display a copyable diagnostic dialog.
7. AVTransport:1 is chosen before a newer AVTransport service version when both are advertised,
   matching the fixed service type used by CastLab's original CastManager.

## Diagnostic interpretation
- TV HTTP host=NO REQUEST RECEIVED / bytes-served=0: TV never reached the file server. Check
  phone IP/subnet, Wi-Fi client isolation, port access, and the reported URL.
- A TV peer IP but HTTP 404/416/server error: the TV reached the server but rejected the requested
  path/range. The diagnostic gives the exact request and status.
- bytes-served greater than zero: the TV did retrieve data. If it still shows an error, test the
  same MP4 in CastLab and compare its actual file and codec; an HTTP handoff alone cannot transcode
  a codec unsupported by the receiver.
- Build success proves Kotlin compilation, signed Release, source ZIP integrity and static checks;
  only a physical Samsung TV can prove the external playback outcome.
""", encoding="utf-8")

g2 = gradle.read_text(encoding="utf-8")
s2 = settings.read_text(encoding="utf-8")
p2 = player.read_text(encoding="utf-8")
e2 = (engine_root / "CastLabDlnaEngine.kt").read_text(encoding="utf-8")
m2 = (engine_root / "CastLabMediaServer.kt").read_text(encoding="utf-8")
assert 'versionCode 1000181' in g2 and 'versionName "100.0.181"' in g2
assert 'rootProject.name = "SEAndroid_v100.0.181"' in s2
assert 'awaitReceiverBytes(2600L, 4096L)' in e2
assert 'avControlUrlV1' in e2
assert 'method == "OPTIONS"' in m2
assert 'NetworkCapabilities.TRANSPORT_WIFI' in m2
assert 'CASTLAB DIAGNOSTICS — FAILED' in p2
assert 'TV TRANSFER:' in p2
print("V181 CastLab diagnostic transport preflight passed.")
