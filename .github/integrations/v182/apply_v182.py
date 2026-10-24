#!/usr/bin/env python3
"""Apply the VOD stream relay for CastLab movie/series casting."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v182.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()
g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
assert 'versionCode 1000181' in g and 'versionName "100.0.181"' in g
assert 'rootProject.name = "SEAndroid_v100.0.181"' in s

engine_root = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna"
engine_root.mkdir(parents=True, exist_ok=True)
source = repo / ".github/integrations/v182/CastLabMediaServer.kt"
assert source.is_file(), f"Missing V182 payload: {source}"
shutil.copy2(source, engine_root / "CastLabMediaServer.kt")

g = g.replace("versionCode 1000181", "versionCode 1000182", 1)
g = g.replace('versionName "100.0.181"', 'versionName "100.0.182"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.181"', 'rootProject.name = "SEAndroid_v100.0.182"', 1),
    encoding="utf-8"
)

p = player.read_text(encoding="utf-8")
old_call = "CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName)"
new_call = "CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)"
assert old_call in p, "CastLab media preparation call not found"
p = p.replace(old_call, new_call, 1)
player.write_text(p, encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
text = notices.read_text(encoding="utf-8") if notices.exists() else ""
text += """

V100.0.182 CastLab network VOD relay
------------------------------------
The V181 version fixed local phone-file serving but still returned HTTP/HTTPS IPTV movie URLs
directly to the television. This does not match CastLab's own model (CastLab serves media from a
phone-local HTTP webroot), and it leaves the TV to make provider requests using the TV's own HTTP
client. For non-live network movies/episodes, V182 creates a random local /se-castlab-proxy/<token>/
URL and relays the provider response through the SE phone using the same VLC User-Agent as SE's
Media3 player, following redirects and preserving Range/If-Range. Provider URLs/credentials are
kept in memory and not placed in the local URL or logs. HLS media playlists are rewritten so
relative segment/key/child-playlist URLs are relayed through local token routes. Live TV is
deliberately kept on its existing direct URL behavior in this change.
"""
notices.write_text(text, encoding="utf-8")

audit = root / "CASTLAB_V100_0_182_VOD_RELAY_AUDIT.md"
audit.write_text("""# CastLab V100.0.182 — movie/series stream-casting fix

## Confirmed source-level mismatch
CastLab's original Android workflow does not hand an arbitrary upstream/provider URL straight to
the TV. The upstream Main.tsx copies the selected phone asset into a webroot and passes a phone-local
HTTP URL to CastManager.castMedia. In SE V181, CastLabMediaServer.prepare() returned every HTTP/HTTPS
source unchanged. Therefore movie/series casting bypassed the working phone-local server entirely,
even though local phone files worked.

## Change
- For non-live HTTP/HTTPS media, V182 creates a local random-token URL on SE's media server.
- The phone fetches the upstream movie/episode with the same VLC/3.0.20 LibVLC/3.0.20 User-Agent
  used by SE's Media3 data source, follows redirects, forwards Range/If-Range, and streams response
  bytes back to the TV.
- Response status, Content-Type, Content-Length, Content-Range, Accept-Ranges, ETag and Last-Modified
  are forwarded when provided by the upstream server, plus the DLNA streaming headers.
- HLS playlists are rewritten so child playlist/segment/key URLs use local relay tokens as well.
- The provider URL (which can contain Xtream username/password) remains in memory only. The TV sees
  only the phone IP, port, random route token and safe filename; provider credentials aren't written
  to the log or local URL.
- Local file handling remains unchanged. Live TV continues to use its pre-existing direct path in
  this version to avoid changing live casting while focusing on movies/episodes.

## Build and validation
CI validates version, source files, player dispatch and server source, compiles a signed Release APK,
checks the release certificate, and checks the source ZIP. This is not a physical Samsung TV test.
If the TV still errors, the server diagnostics distinguish no HTTP request from upstream 401/403,
HTTP range errors, or bytes sent from the phone to the TV.
""", encoding="utf-8")

p2 = player.read_text(encoding="utf-8")
m2 = (engine_root / "CastLabMediaServer.kt").read_text(encoding="utf-8")
g2 = gradle.read_text(encoding="utf-8")
s2 = settings.read_text(encoding="utf-8")
assert 'versionCode 1000182' in g2 and 'versionName "100.0.182"' in g2
assert 'rootProject.name = "SEAndroid_v100.0.182"' in s2
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)' in p2
assert 'return@withContext prepareNetworkProxy(app, source, titleHint)' in m2
assert 'setRequestProperty("User-Agent", PROXY_USER_AGENT)' in m2
assert 'setRequestProperty("Range", it)' in m2
assert 'rewriteHlsManifest' in m2 and 'PROXY_ROUTE' in m2
assert 'if (isLive) return@withContext source' in m2
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)' in p2
print("V182 CastLab VOD relay static preflight passed.")
