#!/usr/bin/env python3
"""V100.0.191: add an independent PlayOnDlna-style DLNA cast route."""
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v191.py <source-root>")
root = Path(sys.argv[1]).resolve()
payload = Path(__file__).resolve().parent / "payload"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player_file = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
notices_file = root / "THIRD_PARTY_NOTICES.md"
assert all(p.is_file() for p in (gradle, settings, player_file, notices_file))
assert (payload / "PlayOnDlnaEngine.kt").is_file()

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one match, got {n}")
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player_file.read_text(encoding="utf-8")
notices = notices_file.read_text(encoding="utf-8")
assert 'versionCode 1000190' in g and 'versionName "100.0.190"' in g
assert 'rootProject.name = "SEAndroid_v100.0.190"' in s

p = replace_once(p,
    'import com.orbital.iptv.utils.originaldlna.fongmi.FongMiDlnaEngine\n',
    'import com.orbital.iptv.utils.originaldlna.fongmi.FongMiDlnaEngine\n'
    'import com.orbital.iptv.utils.originaldlna.playondlna.PlayOnDlnaEngine\n',
    "PlayOnDlna import")
p = replace_once(p,
    '            "DLNA 7 (FongMi)",\n            "Google Cast 2 (OpenIPTV)"',
    '            "DLNA 7 (FongMi)",\n'
    '            "Google Cast 2 (OpenIPTV)",\n'
    '            "DLNA 8 (PlayOnDlna)"',
    "CAST menu label")
p = replace_once(p,
    '                    10 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.FONGMI)\n'
    '                    11 -> showOpenIptvCastChooser(mediaUri)',
    '                    10 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.FONGMI)\n'
    '                    11 -> showOpenIptvCastChooser(mediaUri)\n'
    '                    12 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.PLAYONDLNA)',
    "CAST menu dispatch")
p = replace_once(p,
    '        FONGMI("DLNA 7 (FongMi)")\n    }',
    '        FONGMI("DLNA 7 (FongMi)"),\n'
    '        PLAYONDLNA("DLNA 8 (PlayOnDlna)")\n'
    '    }',
    "DLNA engine enum")
p = replace_once(p,
    '                    OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.discover(this@PlayerActivity)\n'
    '                }',
    '                    OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.discover(this@PlayerActivity)\n'
    '                    OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.discover(this@PlayerActivity)\n'
    '                }',
    "PlayOnDlna discovery")
p = replace_once(p,
    '                        val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB) {',
    '                        val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB ||\n'
    '                            engine == OriginalDlnaEngine.PLAYONDLNA) {',
    "PlayOnDlna media relay")
p = replace_once(p,
    '                                OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(\n'
    '                                    this@PlayerActivity,\n'
    '                                    device,\n'
    '                                    castUri,\n'
    '                                    channelName,\n'
    '                                    isLive,\n'
    '                                    if (isLive || !::player.isInitialized) 0L else player.currentPosition.coerceAtLeast(0L)\n'
    '                                )\n'
    '                            }',
    '                                OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(\n'
    '                                    this@PlayerActivity,\n'
    '                                    device,\n'
    '                                    castUri,\n'
    '                                    channelName,\n'
    '                                    isLive,\n'
    '                                    if (isLive || !::player.isInitialized) 0L else player.currentPosition.coerceAtLeast(0L)\n'
    '                                )\n'
    '                                OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.cast(device, castUri, channelName, isLive)\n'
    '                            }',
    "PlayOnDlna sender dispatch")

engine_dir = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna/playondlna"
engine_dir.mkdir(parents=True, exist_ok=True)
engine_file = engine_dir / "PlayOnDlnaEngine.kt"
if engine_file.exists():
    raise SystemExit("Refusing to overwrite an existing PlayOnDlna engine")
shutil.copyfile(payload / "PlayOnDlnaEngine.kt", engine_file)

notices = notices.rstrip() + """

V100.0.191 — PlayOnDlna-style DLNA sender
----------------------------------------
PlayOnDlna: https://github.com/scovillo/playondlna; inspected upstream main tree at commit
8bc3b29b6ebbb1b0e63f5d23ca9077d1afd528e6 (GPL-3.0-only). The independent SE DLNA 8 sender adapts
the upstream pattern of SSDP MediaRenderer / AVTransport / ssdp:all discovery, UPnP device-description
service resolution, AVTransport SetAVTransportURI followed by Play, and escaped DIDL-Lite resource
metadata. It does not bundle the standalone PlayOnDlna app, NewPipe Extractor, or FFmpeg preparation
pipeline; SE IPTV sources already have stream URLs, and live TV cannot be pre-downloaded as a file.
Instead, streamed URLs and PHONE FILES pass through SE's existing phone-local HTTP/range-capable relay
before this independent sender hands the resulting URL to the TV. See PLAYONDlNA_CAST_V100_0_191_AUDIT.md.
Full GPLv3 text is supplied in THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt. This route does not replace
CastLab, Vega, NekoVideo, YAACC, FongMi or Google Cast engines.
"""

(root / "THIRD_PARTY_LICENSES").mkdir(parents=True, exist_ok=True)
shutil.copyfile(root / "LICENSE", root / "THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt")
(root / "PLAYONDlNA_CAST_V100_0_191_AUDIT.md").write_text("""# PlayOnDlna inspection and independent cast route — V100.0.191

## Upstream examined

- Project: https://github.com/scovillo/playondlna
- Inspected upstream tree: 8bc3b29b6ebbb1b0e63f5d23ca9077d1afd528e6 on main
- License: GPL-3.0-only; see THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt and THIRD_PARTY_NOTICES.md.
- Files inspected: SsdpDiscovery.kt, SsdpDeviceClient.kt, DlnaRemoteControl.kt, SoapClient.kt, SoapCommand.kt, SoapPlaybackTransport.kt, DlnaDevice.kt, LibraryItem.kt, DlnaPlaylist.kt, MediaServer.kt, and LocalIpAddress.kt.

## How PlayOnDlna casts

1. It discovers renderers with SSDP M-SEARCH targeting MediaRenderer, AVTransport:1 and ssdp:all, acquiring Android's Wi-Fi multicast lock and binding to the active Wi-Fi network when available.
2. It loads the UPnP device description and resolves the AVTransport service controlURL.
3. Its SOAP sender sends SetAVTransportURI with escaped DIDL-Lite metadata and then sends Play at speed 1.
4. The standalone app prepares supported online-platform media into local compatible files (sometimes using FFmpeg), serves them over its phone-local HTTP server with byte-range support, and hands that local URL to the TV.

## SE route added

DLNA 8 (PlayOnDlna) adds an independent SSDP/service-description/SOAP/DIDL sender. It does not call the CastLab, Vega, YAACC, NekoVideo or FongMi sender engines. The standalone PlayOnDlna UI, NewPipe Extractor and FFmpeg download/remux pipeline are intentionally not bundled: IPTV live streams cannot be pre-downloaded as ordinary media files. Instead, selected IPTV URLs and PHONE FILES use SE's existing phone-local media relay; the new sender hands that URL to the renderer using PlayOnDlna-style AVTransport steps. Successful casts register with CastDisconnectManager, so the common DISCONNECT control issues AVTransport Stop.

## Verification and limitations

The V191 patch checks version metadata, menu label and dispatch, local relay handoff, disconnect registration, and preservation of V190's left DISCONNECT / right CANCEL chooser. GitHub Actions builds a signed APK, checks the signing certificate and archive integrity, and exports APK + source ZIP. Static/build verification is not a physical playback test; target TVs still need validation on the same local network.
""", encoding="utf-8")

g = g.replace("versionCode 1000190", "versionCode 1000191", 1)
g = g.replace('versionName "100.0.190"', 'versionName "100.0.191"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.190"', 'rootProject.name = "SEAndroid_v100.0.191"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
notices_file.write_text(notices, encoding="utf-8")

assert 'versionCode 1000191' in g and 'versionName "100.0.191"' in g
assert 'rootProject.name = "SEAndroid_v100.0.191"' in s
assert '"DLNA 8 (PlayOnDlna)"' in p
assert 'OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.discover(this@PlayerActivity)' in p
assert 'OriginalDlnaEngine.PLAYONDLNA -> PlayOnDlnaEngine.cast(device, castUri, channelName, isLive)' in p
assert 'engine == OriginalDlnaEngine.PLAYONDLNA' in p
assert '.setNegativeButton("DISCONNECT", null)' in p and '.setPositiveButton("CANCEL", null)' in p
assert 'window.decorView.layoutDirection = View.LAYOUT_DIRECTION_LTR' in p
for hook in (
    'binding.btnCastBottomRoute.setOnClickListener { showCastChooser() }',
    'binding.btnCastBottom.setOnClickListener { showCastChooser() }',
    'b.btnGencCast.setOnClickListener { showCastChooser() }',
):
    assert hook in p, hook
assert 'CastDisconnectManager.registerDlna(engine.label + " — " + device.name, device.controlUrl, device.serviceType)' in p
assert (root / "PLAYONDlNA_CAST_V100_0_191_AUDIT.md").is_file()
assert (root / "THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt").is_file()
player_file.write_text(p, encoding="utf-8")
print("V100.0.191 PlayOnDlna route applied; static checks passed.")
