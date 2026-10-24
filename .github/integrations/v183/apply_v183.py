#!/usr/bin/env python3
"""Apply V183 CastLab all-stream relay fix to the reconstructed V182 source."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v183.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
assert 'versionCode 1000182' in g and 'versionName "100.0.182"' in g
assert 'rootProject.name = "SEAndroid_v100.0.182"' in s

engine_root = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna"
engine_root.mkdir(parents=True, exist_ok=True)
for name in ("CastLabMediaServer.kt", "CastLabDlnaEngine.kt"):
    source = repo / ".github/integrations/v183" / name
    assert source.is_file(), f"Missing V183 payload: {source}"
    shutil.copy2(source, engine_root / name)

g = g.replace("versionCode 1000182", "versionCode 1000183", 1)
g = g.replace('versionName "100.0.182"', 'versionName "100.0.183"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.182"', 'rootProject.name = "SEAndroid_v100.0.183"', 1),
    encoding="utf-8"
)

p = player.read_text(encoding="utf-8")
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)' in p
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)' in p
assert 'CASTLAB DIAGNOSTICS — FAILED' in p

notices = root / "THIRD_PARTY_NOTICES.md"
notice_text = notices.read_text(encoding="utf-8") if notices.exists() else ""
notice_text += """

V100.0.183 CastLab all-stream network relay
-------------------------------------------
V182 proxied network VOD/movie/episode streams but returned Live TV URLs unchanged when isLive
was true. This was a definite remaining path mismatch and left Live TV using the same TV-native
provider request that had failed. V183 sends every HTTP/HTTPS media URL (Live TV, movie, episode)
through the phone-local CastLab HTTP route. For extensionless Live TV, the route advertises MPEG-TS
rather than incorrectly defaulting to MP4. HLS playlists are served as complete manifests (without
forwarding a byte Range to the manifest request) and their child segment/variant/key URLs are
rewritten to local relay tokens. For generic upstream Content-Types such as application/octet-stream,
the local response uses the source-extension MIME; actual HLS, TS, MP4, HTML or JSON types remain
distinguishable. Provider HTML/JSON error pages are returned as HTTP 502 rather than mislabeled as
playable video, and the error response uses proper CRLF framing.
"""
notices.write_text(notice_text, encoding="utf-8")

audit = root / "CASTLAB_V100_0_183_AUDIT.md"
audit.write_text("""# CastLab V100.0.183 — all-stream casting audit

## Root cause found
In V182, the CastLab preparation function explicitly returned the original remote URL without using
the phone-local server whenever isLive was true. Thus Live TV bypassed the working local-file
handoff entirely and asked the Samsung TV to fetch the IPTV provider URL with the TV's own HTTP
stack. That was not the same network path as CastLab's original local webroot. This explains why
the previous build still failed for Live TV even after the VOD proxy work.

## Changes
1. Removed the Live TV bypass; every HTTP/HTTPS source is routed through the phone-local server.
2. The upstream fetch uses the same VLC/3.0.20 LibVLC/3.0.20 User-Agent as SE's Media3 playback,
   follows redirects, and forwards byte ranges for media segments/files.
3. An HLS manifest request is not sent as a partial byte-range to the provider. Relative variant,
   media-segment and URI-attribute paths are resolved and rewritten to local one-time relay URLs.
4. Extensionless live sources default to MPEG-TS metadata, not MP4. Common upstream generic binary
   Content-Types use the known source-extension MIME. Meaningful upstream media types are preserved.
5. Provider HTML/JSON/text error pages no longer look like successful video: the local server returns
   a framed HTTP 502 and records the upstream type. The diagnostic path can distinguish an upstream
   error from no request reaching the phone.
6. Original CastLab SetAVTransportURI/Play behavior and existing Cast choices remain in place.

## Limits
This remains a byte-level relay, not a transcoder. If the IPTV provider returns codecs that the
Samsung TV cannot decode, or a provider-specific URL requires cookies/headers that SE's playback
source does not use, DLNA may still fail. The resulting phone-side diagnostic should now identify
whether the TV reached the local server and what HTTP response the provider returned. Physical TV
playback remains the final validation; a successful signed CI build does not prove codec support.
""", encoding="utf-8")

g2 = gradle.read_text(encoding="utf-8")
s2 = settings.read_text(encoding="utf-8")
p2 = player.read_text(encoding="utf-8")
m2 = (engine_root / "CastLabMediaServer.kt").read_text(encoding="utf-8")
e2 = (engine_root / "CastLabDlnaEngine.kt").read_text(encoding="utf-8")
assert 'versionCode 1000183' in g2 and 'versionName "100.0.183"' in g2
assert 'rootProject.name = "SEAndroid_v100.0.183"' in s2
assert 'return@withContext prepareNetworkProxy(app, source, titleHint, isLive)' in m2
assert 'if (isLive) return@withContext source' not in m2
assert 'private fun prepareNetworkProxy(context: Context, sourceUrl: String, titleHint: String, isLive: Boolean)' in m2
assert 'if (!pathLooksLikePlaylist)' in m2
assert 'application/octet-stream' in m2
assert 'CASTLAB DIAGNOSTICS — FAILED' in p2
assert 'networkProxy) 10000L else 2600L' in e2
assert 'probe.status >= 400' in e2
print("V183 CastLab all-stream relay static preflight passed.")
