#!/usr/bin/env python3
"""Apply the CastLab interoperability corrections to the already reconstructed V179 source."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v180.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert gradle.is_file() and settings.is_file() and player.is_file()
assert 'versionCode 1000179' in gradle.read_text(encoding="utf-8")
assert 'versionName "100.0.179"' in gradle.read_text(encoding="utf-8")
assert 'rootProject.name = "SEAndroid_v100.0.179"' in settings.read_text(encoding="utf-8")

engine_root = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna"
engine_root.mkdir(parents=True, exist_ok=True)
for name in ("CastLabDlnaEngine.kt", "CastLabMediaServer.kt"):
    source = repo / ".github/integrations/v180" / name
    assert source.is_file(), f"Missing V180 payload: {source}"
    shutil.copy2(source, engine_root / name)

g = gradle.read_text(encoding="utf-8")
g = g.replace("versionCode 1000179", "versionCode 1000180", 1)
g = g.replace('versionName "100.0.179"', 'versionName "100.0.180"', 1)
gradle.write_text(g, encoding="utf-8")

s = settings.read_text(encoding="utf-8")
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.179"', 'rootProject.name = "SEAndroid_v100.0.180"', 1),
    encoding="utf-8"
)

p = player.read_text(encoding="utf-8")
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName)' in p
assert 'OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)' in p
assert 'arrayOf("DLNA 3 (CastLab)")' in p

notices = root / "THIRD_PARTY_NOTICES.md"
notice_text = notices.read_text(encoding="utf-8") if notices.exists() else ""
notice_text += """

V100.0.180 CastLab interoperability correction
----------------------------------------------
The local media server now uses the same direct webroot URL pattern as CastLab:
http://<phone-lan-ip>:9125/<safe-filename>. The active cached filename is the only item served.
Before the URL is sent to a TV, a local HTTP Range self-test must obtain 206 and Content-Range
bytes 0-0/<file-size>; otherwise the app reports a precise local-server error.

CastLab SSDP discovery additionally tries upnp:rootdevice and uses TTL=2. If CastLab's own SSDP
responses contain no usable AVTransport renderer, discovery falls back to SE's independently
implemented TDM-compatible DLNA2 device scanner. Casting always tries the CastLab-shaped
SetAVTransportURI/Play flow first. If a TV rejects that flow, it retries using the existing
Samsung-compatible HttpURLConnection SOAP framing, waits 700ms after SetAVTransportURI, and
tries multiple MIME candidates with generic videoItem DIDL metadata. This fallback is restricted
to the CastLab menu item and does not replace the CastLab primary method or alter other cast menu
entries. Error messages include both the original and fallback transport failure details.
"""
notices.write_text(notice_text, encoding="utf-8")

audit = root / "CASTLAB_V100_0_180_AUDIT.md"
audit.write_text("""# CastLab V100.0.180 focused correction audit

## Root-cause comparison with the upstream CastLab snapshot
The V179 version still differed from CastLab's original local-file URL pattern: upstream copies the
media into its webroot and passes a plain http://<phone-ip>:9125/<filename> to AVTransport. V179
instead invented /castlab/<token>/<filename>. Although valid in principle, it had no benefit for
Samsung interoperability and complicated the URL path. V180 uses the upstream direct-webroot path.

The original CastManager sends SOAP requests with the receiver's AVTransport control URL, uses
Content-Type: text/xml; charset="utf-8" and quoted SOAPAction, builds a videoItem DIDL-Lite entry,
calls SetAVTransportURI, then Play. V180 preserves that flow as the primary attempt but adds an
independent compatibility fallback modeled on SE's TDM-style DLNA2 path, which is useful on Samsung
renderers that reject metadata/MIME framing.

## Changes
1. Direct webroot path (port 9125 preferred) instead of a nested /castlab/... path.
2. HTTP range self-test before handing a local file URL to the TV; checks status 206 and Content-Range.
3. CastLab SSDP gets an additional root-device target and multicast TTL 2.
4. When the CastLab scanner returns no usable renderer, use the already-implemented, separately
   tested TDM-compatible renderer discovery, then represent the result as a receiver for CastLab's
   primary transport.
5. If CastLab-shaped SetAVTransportURI/Play fails, retry using Samsung-compatible HttpURLConnection
   SOAP framing and a 700ms URI-to-Play delay; try multiple MIME types and include the exact failure
   in the final UI toast.
6. Existing cast options remain unchanged; local files expose CastLab only until other engines gain
   local media server support.

## Test limits
GitHub CI checks compilation, version/source checks, signed APK certificate, and ZIP integrity. A
physical Samsung TV test remains necessary. In particular, the self-test confirms the phone can
serve its own URL; it cannot prove the television can reach the phone on a given Wi-Fi/router.
""", encoding="utf-8")

assert 'versionCode 1000180' in gradle.read_text(encoding="utf-8")
assert 'versionName "100.0.180"' in gradle.read_text(encoding="utf-8")
assert 'rootProject.name = "SEAndroid_v100.0.180"' in settings.read_text(encoding="utf-8")
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName)' in player.read_text(encoding="utf-8")
assert (engine_root / "CastLabMediaServer.kt").is_file()
assert (engine_root / "CastLabDlnaEngine.kt").is_file()
print("V180 CastLab static preflight passed.")
