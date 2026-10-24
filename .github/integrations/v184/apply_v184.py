#!/usr/bin/env python3
"""V184: retain CastLab for local files; use the proven TDM-compatible direct URL route for IPTV streams."""
from __future__ import annotations
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v184.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player.read_text(encoding="utf-8")
assert 'versionCode 1000183' in g and 'versionName "100.0.183"' in g
assert 'rootProject.name = "SEAndroid_v100.0.183"' in s

old_discover = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.discover(this@PlayerActivity)'
new_discover = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
                        CastLabDlnaEngine.discover(this@PlayerActivity)
                    } else {
                        // Use TDM-compatible discovery details for streams too, preserving the
                        // service/control URL resolution from the known-good route.
                        TdmCompatibleDlnaManager.discover(this@PlayerActivity).map { tdm ->
                            DlnaReceiver(
                                id = tdm.id,
                                name = tdm.name,
                                host = tdm.host,
                                descriptionUrl = tdm.location,
                                controlUrl = tdm.controlUrl,
                                serviceType = tdm.serviceType
                            )
                        }
                    }'''
assert p.count(old_discover) == 1, "Unexpected CASTLAB discovery implementation"
p = p.replace(old_discover, new_discover, 1)

old_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {'
new_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB && isLocalFile) {'
assert p.count(old_prepare) == 1, "Unexpected CASTLAB preparation branch"
p = p.replace(old_prepare, new_prepare, 1)

old_cast = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)'
new_cast = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
                                // Keep CastLab's phone-local webroot for local files.
                                CastLabDlnaEngine.cast(device, castUri, channelName, isLive)
                            } else {
                                // Match the known-good SE DLNA 2 / TDM-compatible stream path:
                                // direct provider URL plus retrying MPEG-TS/HLS MIME candidates.
                                TdmCompatibleDlnaManager.cast(
                                    device = TdmCompatibleDlnaManager.Device(
                                        id = device.id,
                                        name = device.name,
                                        host = device.host,
                                        location = device.descriptionUrl,
                                        controlUrl = device.controlUrl,
                                        serviceType = device.serviceType
                                    ),
                                    mediaUrl = mediaUri,
                                    title = channelName,
                                    isLive = isLive
                                )
                            }'''
assert p.count(old_cast) == 1, "Unexpected CASTLAB cast dispatch"
p = p.replace(old_cast, new_cast, 1)

assert 'OriginalDlnaEngine.CASTLAB -> if (isLocalFile)' in p
assert 'TdmCompatibleDlnaManager.discover(this@PlayerActivity).map { tdm ->' in p
assert 'TdmCompatibleDlnaManager.cast(' in p
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)' in p

g = g.replace("versionCode 1000183", "versionCode 1000184", 1)
g = g.replace('versionName "100.0.183"', 'versionName "100.0.184"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.183"', 'rootProject.name = "SEAndroid_v100.0.184"', 1),
    encoding="utf-8"
)
player.write_text(p, encoding="utf-8")

audit = root / "CASTLAB_V100_0_184_AUDIT.md"
audit.write_text("""# SE IPTV Player V100.0.184 — CastLab / TDM stream route audit

## Code-level issue identified
V183 forced every HTTP/HTTPS stream through the custom CastLab phone-side proxy. That is materially different from the existing TDM-compatible DLNA route in this app: the proxy fetches the provider URL itself and re-serves the response from the phone, while TDM's known-good route sends the provider URL directly to the renderer and retries compatible MIME metadata (including MPEG-TS/HLS candidates for Live TV). The prior relay changes therefore did not reproduce the route already known to work with the Samsung TV.

This architectural mismatch is a concrete issue found by comparing the V183 CastLab flow with the in-app TDM-compatible TdmCompatibleDlnaManager. It is not possible to name the provider's exact per-stream HTTP error without a phone-side diagnostic capture; no such capture was supplied.

## V184 changes
1. For network streams (Live TV, Movies, Episodes), the entry labelled DLNA 3 (CastLab) now uses the same TDM-compatible SSDP discovery data and direct-URL SOAP handoff as the working DLNA 2 path.
2. It inherits TDM-compatible Stop best-effort, SetAVTransportURI, Play, and MIME candidate retries rather than making the TV fetch a rewritten proxy URL.
3. For local files, the entry continues to use CastLab's phone-local HTTP media server and CastLab DLNA engine. The local-file behavior and all separate cast menu entries remain intact.
4. No transcoder is added. Playback still depends on the Samsung TV supporting the source container/codecs and the provider URL being reachable from the TV's LAN.

## Validation
The release workflow checks the resulting source route, version identity, third-party licenses/notices, signed APK certificate, APK ZIP integrity, and source ZIP integrity. Static/CI validation does not replace a real playback test on the Samsung TV.
""", encoding="utf-8")

print("V184 route integration and static preflight passed.")
