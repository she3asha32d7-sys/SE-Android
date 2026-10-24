#!/usr/bin/env python3
"""V184: compare with the production TV cast path; retain CastLab's working local-file route."""
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
assert 'import com.orbital.iptv.utils.UniversalCastManager' in p

# The TV menu entry uses UniversalCastManager. For network streams, make the CastLab-labelled
# route use that same Samsung/DLNA discovery and direct-URL behavior. For local files, keep the
# working CastLab copy-to-webroot and byte-range HTTP serving flow.
old_discover = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.discover(this@PlayerActivity)'
new_discover = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
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
assert p.count(old_discover) == 1, "Unexpected CASTLAB discovery implementation"
p = p.replace(old_discover, new_discover, 1)

old_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {'
new_prepare = 'val castUri = if (engine == OriginalDlnaEngine.CASTLAB && isLocalFile) {'
assert p.count(old_prepare) == 1, "Unexpected CASTLAB media preparation branch"
p = p.replace(old_prepare, new_prepare, 1)

old_cast = 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)'
new_cast = '''OriginalDlnaEngine.CASTLAB -> if (isLocalFile) {
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
assert p.count(old_cast) == 1, "Unexpected CASTLAB cast dispatch"
p = p.replace(old_cast, new_cast, 1)

assert 'UniversalCastManager.discover(this@PlayerActivity)' in p
assert 'UniversalCastManager.cast(' in p
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)' in p
assert 'OriginalDlnaEngine.CASTLAB -> if (isLocalFile)' in p

g = g.replace("versionCode 1000183", "versionCode 1000184", 1)
g = g.replace('versionName "100.0.183"', 'versionName "100.0.184"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.183"', 'rootProject.name = "SEAndroid_v100.0.184"', 1),
    encoding="utf-8"
)
player.write_text(p, encoding="utf-8")

audit = root / "CASTLAB_V100_0_184_AUDIT.md"
audit.write_text("""# SE IPTV Player V100.0.184 — TV route vs CastLab route

## Code comparison
The existing CAST > TV option uses UniversalCastManager. For Samsung/DLNA devices it discovers UPnP MediaRenderers and hands the provider HTTP/HTTPS URL directly to the TV using AVTransport SetAVTransportURI and Play. It tries multiple MIME declarations and, for live streams, also tries the Xtream-style .ts alternative. It does not create a phone-side proxy for remote IPTV URLs.

The working CastLab local-file path is different: it copies the selected phone file to a private cache/webroot and announces a phone-LAN HTTP URL served by SE with Content-Length, byte ranges, and DLNA headers. It is a stable single-resource file URL, rather than the IPTV provider URL or a remote provider manifest.

The failed V183 stream path used a third, different architecture: the phone-side HTTP proxy fetched the remote provider stream and re-served it. Since that relay path still did not work on the Samsung TV, V184 tests the existing TV menu's actual DLNA control/URL/MIME behavior for CastLab-labelled network streams, while retaining CastLab's original local-file path unchanged.

## V184 changes
1. For network media (movies, episodes and live streams), the DLNA 3 CastLab chooser uses the same DLNA renderer discovery results as TV, excluding LG webOS SSAP-only devices because this path sends UPnP AVTransport SOAP.
2. It sends the original provider URL using the same UniversalCastManager.cast DLNA code as TV, including its SOAP actions, content metadata, and MIME candidates.
3. For local files, it continues to use CastLab's phone-local cache/webroot HTTP server and CastLab DLNA engine.
4. Other cast options remain separate and unchanged.

## Limit
This identifies and aligns a concrete code-path difference; it cannot prove TV playback without testing on the Samsung TV. The TV's codec support and the provider URL's access rules still matter.
""", encoding="utf-8")

print("V184 implementation changed to match the inspected TV route.")
