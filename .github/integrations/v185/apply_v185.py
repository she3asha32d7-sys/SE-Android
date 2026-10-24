#!/usr/bin/env python3
"""V185: keep CastLab network media on a phone-LAN relay and CastLab's own DLNA transport."""
from __future__ import annotations
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v185.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player.read_text(encoding="utf-8")
assert 'versionCode 1000184' in g and 'versionName "100.0.184"' in g
assert 'rootProject.name = "SEAndroid_v100.0.184"' in s
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)' in p
assert 'OriginalDlnaEngine.CASTLAB -> if (isLocalFile)' in p

# V184 routed CastLab-labelled network streams through UniversalCastManager with the upstream
# IPTV URL. A Samsung TV then had to resolve/fetch the provider resource directly and returned
# UPnP 716 (Resource not found). Keep CastLab's selected stream behind its own phone-LAN relay,
# so the renderer needs to reach only the Android device and the phone retains the provider's
# HTTP redirects/User-Agent behavior.
old_discover = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
                        CastLabDlnaEngine.discover(this@PlayerActivity)
                    } else {
                        UniversalCastManager.discover(this@PlayerActivity)
                            .filter { it.protocol == UniversalCastManager.Protocol.DLNA }
                            .map { tv ->
                                DlnaReceiver(
                                    id = tv.id,
                                    name = tv.friendlyName,
                                    host = tv.host,
                                    descriptionUrl = tv.location,
                                    controlUrl = tv.controlUrl.orEmpty(),
                                    serviceType = tv.serviceType.orEmpty()
                                )
                            }
                    }'''
new_discover = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.discover(this@PlayerActivity)'
assert p.count(old_discover) == 1, "Unexpected V184 CASTLAB discovery implementation"
p = p.replace(old_discover, new_discover, 1)

old_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB && isLocalFile) {'
new_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {'
assert p.count(old_prepare) == 1, "Unexpected V184 CASTLAB media preparation branch"
p = p.replace(old_prepare, new_prepare, 1)

old_cast = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
                                // Local files keep the original CastLab webroot/range-server path.
                                CastLabDlnaEngine.cast(device, castUri, channelName, isLive)
                            } else {
                                // Exact TV-menu path for network streams: direct provider URL,
                                // UniversalCastManager MIME candidates, and SOAP retry.
                                UniversalCastManager.cast(
                                    context = this@PlayerActivity,
                                    device = UniversalCastManager.Device(
                                        id = device.id,
                                        friendlyName = device.name,
                                        protocol = UniversalCastManager.Protocol.DLNA,
                                        host = device.host,
                                        port = runCatching {
                                            java.net.URL(device.descriptionUrl).port.takeIf { it > 0 } ?: 80
                                        }.getOrDefault(80),
                                        location = device.descriptionUrl,
                                        controlUrl = device.controlUrl,
                                        serviceType = device.serviceType
                                    ),
                                    mediaUrl = mediaUri,
                                    title = channelName,
                                    isLive = isLive,
                                    iconUrl = artUrl
                                )
                            }'''
new_cast = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)'
assert p.count(old_cast) == 1, "Unexpected V184 CASTLAB cast dispatch"
p = p.replace(old_cast, new_cast, 1)

g = g.replace("versionCode 1000184", "versionCode 1000185", 1)
g = g.replace('versionName "100.0.184"', 'versionName "100.0.185"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.184"', 'rootProject.name = "SEAndroid_v100.0.185"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player.write_text(p, encoding="utf-8")

audit = root / "CASTLAB_V100_0_185_UPNP_716_FIX_AUDIT.md"
audit.write_text("""# SE IPTV Player V100.0.185 — CastLab UPnP 716 fix

## Reported failure
The V184 CastLab-labelled route sent network media (live, movies, episodes) directly from the IPTV provider URL to the Samsung TV via UniversalCastManager. The renderer returned SOAP HTTP 500 / UPnP 716, Resource not found. This means the renderer could not locate or retrieve the specified network resource; the APK compile result alone cannot prove physical-TV playback.

## Change
1. CastLab network media again passes through CastLabMediaServer's phone-LAN HTTP relay, including the generated opaque local URL and server-side upstream fetching.
2. CastLab uses its own CastLabDlnaEngine for discovery and SetAVTransportURI/Play for both network media and local files.
3. CastLab's existing relay tracks receiver HTTP requests, range headers, status, and bytes sent. If SOAP succeeds but the renderer does not fetch media, the existing compatibility retry and diagnostics can distinguish an unreachable phone URL from an upstream HTTP error.
4. The regular TV/UniversalCastManager route, Google Cast, DLNA 2, Vega, NekoVideo and YAACC remain on their existing separate dispatch paths.

## Validation boundary
GitHub Actions will verify source/version invariants, build and sign the Release APK, verify its release certificate fingerprint, and validate both output ZIP/APK files. A real Samsung-TV test remains necessary to confirm playback and network reachability.
""", encoding="utf-8")

assert 'versionCode 1000185' in g and 'versionName "100.0.185"' in g
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.discover(this@PlayerActivity)' in p
assert 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {' in p
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)' in p
assert 'OriginalDlnaEngine.CASTLAB -> if (isLocalFile)' not in p
print("V185 CastLab routing applied and verified.")
