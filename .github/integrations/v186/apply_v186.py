#!/usr/bin/env python3
"""V100.0.186 integration patch: independent FongMi jUPnP and OpenIPTV Google Cast routes."""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v186.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
base = Path(__file__).resolve().parent
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
manifest = root / "app/src/main/AndroidManifest.xml"
assert gradle.is_file() and settings.is_file() and player.is_file() and manifest.is_file()

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player.read_text(encoding="utf-8")
m = manifest.read_text(encoding="utf-8")

assert 'versionCode 1000185' in g and 'versionName "100.0.185"' in g
assert 'rootProject.name = "SEAndroid_v100.0.185"' in s

g = replace_once(
    g,
    "    implementation 'androidx.media3:media3-cast:1.9.0'\n",
    "    implementation 'androidx.media3:media3-cast:1.9.0'\n"
    "    // FongMi-inspired DLNA option with its own jUPnP control point.\n"
    "    implementation 'org.jupnp:org.jupnp:3.0.5'\n"
    "    implementation 'org.jupnp:org.jupnp.android:3.0.5'\n"
    "    implementation 'org.jupnp:org.jupnp.support:3.0.5'\n",
    "jUPnP dependency insertion"
)

p = replace_once(
    p,
    "import com.orbital.iptv.utils.originaldlna.YaaccDlnaEngine\n",
    "import com.orbital.iptv.utils.originaldlna.YaaccDlnaEngine\n"
    "import com.orbital.iptv.utils.originaldlna.fongmi.FongMiDlnaEngine\n"
    "import com.orbital.iptv.utils.originalcast.OpenIptvCastCompatibility\n",
    "new cast imports"
)

p = replace_once(
    p,
    '            arrayOf("DLNA 3 (CastLab)")\n',
    '            arrayOf("DLNA 3 (CastLab)", "DLNA 7 (FongMi)", "Google Cast 2 (OpenIPTV)")\n',
    "local cast menu"
)
p = replace_once(
    p,
    '            arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)")\n',
    '            arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)", "DLNA 7 (FongMi)", "Google Cast 2 (OpenIPTV)")\n',
    "network cast menu"
)
p = replace_once(
    p,
    '''                if (isLocalFile) {
                    showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                } else when (which) {
                    0 -> showTvCastChooser(mediaUri)
                    1 -> showDlnaCastChooser(mediaUri)
                    2 -> showDlna2Chooser(mediaUri)
                    3 -> openWirelessDisplaySettings()
                    4 -> launchWebVideoCaster(mediaUri)
                    5 -> binding.btnCast.performClick()
                    6 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                    7 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.VEGA)
                    8 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.NEKOVIDEO)
                    9 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.YAACC)
                }''',
    '''                if (isLocalFile) {
                    when (which) {
                        0 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                        1 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.FONGMI)
                        2 -> showOpenIptvCastChooser(mediaUri)
                    }
                } else when (which) {
                    0 -> showTvCastChooser(mediaUri)
                    1 -> showDlnaCastChooser(mediaUri)
                    2 -> showDlna2Chooser(mediaUri)
                    3 -> openWirelessDisplaySettings()
                    4 -> launchWebVideoCaster(mediaUri)
                    5 -> binding.btnCast.performClick()
                    6 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                    7 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.VEGA)
                    8 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.NEKOVIDEO)
                    9 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.YAACC)
                    10 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.FONGMI)
                    11 -> showOpenIptvCastChooser(mediaUri)
                }''',
    "menu index dispatch"
)

p = replace_once(
    p,
    '''        YAACC("DLNA 6 (YAACC)")
    }''',
    '''        YAACC("DLNA 6 (YAACC)"),
        FONGMI("DLNA 7 (FongMi)")
    }''',
    "engine enum"
)
p = replace_once(
    p,
    '''                    OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.discover(this@PlayerActivity)
                }''',
    '''                    OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.discover(this@PlayerActivity)
                    OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.discover(this@PlayerActivity)
                }''',
    "FongMi discovery dispatch"
)
p = replace_once(
    p,
    '                        val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {',
    '                        val castUri = if (engine == OriginalDlnaEngine.CASTLAB || (engine == OriginalDlnaEngine.FONGMI && isLocalFile)) {',
    "local file URL preparation"
)
p = replace_once(
    p,
    '''                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, castUri, channelName, isLive)
                        }''',
    '''                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(
                                this@PlayerActivity,
                                device,
                                castUri,
                                channelName,
                                isLive,
                                if (isLive || !::player.isInitialized) 0L else player.currentPosition.coerceAtLeast(0L)
                            )
                        }''',
    "FongMi cast dispatch"
)

fongmi_dir = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna/fongmi"
cast_dir = root / "app/src/main/java/com/orbital/iptv/utils/originalcast"
fongmi_dir.mkdir(parents=True, exist_ok=True)
cast_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(base / "payload/FongMiDlnaService.kt", fongmi_dir / "FongMiDlnaService.kt")
shutil.copyfile(base / "payload/FongMiDlnaEngine.kt", fongmi_dir / "FongMiDlnaEngine.kt")
shutil.copyfile(base / "payload/OpenIptvCastCompatibility.kt", cast_dir / "OpenIptvCastCompatibility.kt")

m = replace_once(
    m,
    '''        <service
            android:name=".recording.RecordingService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback|dataSync" />
''',
    '''        <service
            android:name=".recording.RecordingService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback|dataSync" />

        <service
            android:name=".utils.originaldlna.fongmi.FongMiDlnaService"
            android:exported="false" />
''',
    "FongMi Android service registration"
)

ui_marker = '''    private fun currentCastMediaUri(): String {
'''
ui_code = r'''    private fun showOpenIptvCastChooser(mediaUri: String) {
        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("GOOGLE CAST 2 (OPENIPTV)")
            .setMessage("SEARCHING FOR CAST RECEIVERS...")
            .setNegativeButton("CANCEL", null)
            .create()
        searching.show()
        lifecycleScope.launch {
            val targets = try {
                OpenIptvCastCompatibility.discover(this@PlayerActivity)
            } catch (error: Exception) {
                android.util.Log.w("SEOpenIptvCast", "Cast discovery failed", error)
                emptyList()
            }
            if (isFinishing || isDestroyed || !searching.isShowing) {
                searching.dismiss()
                return@launch
            }
            searching.dismiss()
            if (targets.isEmpty()) {
                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                    .setTitle("GOOGLE CAST 2 (OPENIPTV)")
                    .setMessage("NO CAST RECEIVERS FOUND. Make sure Google Cast is available and the phone and receiver share the same Wi-Fi network.")
                    .setPositiveButton("OK", null).show()
                return@launch
            }
            AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                .setTitle("OPENIPTV - SELECT RECEIVER")
                .setItems(targets.map { it.name }.toTypedArray()) { _, selected ->
                    val target = targets[selected]
                    lifecycleScope.launch {
                        try {
                            val castUri = if (isLocalFile) {
                                CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)
                            } else mediaUri
                            val startMs = if (isLive || !::player.isInitialized) 0L
                                else player.currentPosition.coerceAtLeast(0L)
                            val acceptedUrl = OpenIptvCastCompatibility.cast(
                                target = target,
                                mediaUrl = castUri,
                                title = channelName,
                                isLive = isLive,
                                imageUrl = artUrl.takeIf { it.isNotBlank() },
                                startPositionMs = startMs
                            )
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            val path = Uri.parse(acceptedUrl).path.orEmpty()
                            val format = if (path.endsWith(".m3u8", true)) "HLS" else OpenIptvCastCompatibility.contentType(acceptedUrl)
                            Toast.makeText(
                                this@PlayerActivity,
                                "OPENIPTV CAST REQUEST ACCEPTED (${target.name} - ${format})",
                                Toast.LENGTH_LONG
                            ).show()
                            showGencOverlay()
                        } catch (error: Exception) {
                            android.util.Log.w("SEOpenIptvCast", "Cast load failed", error)
                            Toast.makeText(
                                this@PlayerActivity,
                                "OPENIPTV CAST FAILED: ${error.message ?: "UNKNOWN ERROR"}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                }
                .setNegativeButton("CANCEL", null)
                .show()
        }
    }

'''
p = replace_once(p, ui_marker, ui_code + ui_marker, "OpenIPTV cast chooser")

g = g.replace("versionCode 1000185", "versionCode 1000186", 1)
g = g.replace('versionName "100.0.185"', 'versionName "100.0.186"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.185"', 'rootProject.name = "SEAndroid_v100.0.186"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player.write_text(p, encoding="utf-8")
manifest.write_text(m, encoding="utf-8")

license_dir = root / "THIRD_PARTY_LICENSES"
license_dir.mkdir(exist_ok=True)
gpl_source = license_dir / "YAACC-GPL-3.0.txt"
assert gpl_source.is_file(), "Existing GPL-3.0 license text is missing"
shutil.copyfile(gpl_source, license_dir / "FONGMI-TV-GPL-3.0.txt")
shutil.copyfile(gpl_source, license_dir / "OPENIPTV-GPL-3.0.txt")

audit = root / "CAST_INTEGRATION_REVIEW_V100_0_186.md"
audit.write_text("""# Cast-source review and V100.0.186 integration

Reviewed revisions:
- FongMi/TV: ef58e5551f9a9d8679821b38422c06373185a04e (GPL-3.0)
- OpenIPTV: 8c4d47b9b882af1dd72b337ee8f1d71c8a10e902 (GPL-3.0)
- PlayBridge: 603c2726a5bddd1fdd91ae9e13d304c854bcc94a (MPL-2.0)
- Harbor: 78b2fac6442585f85dc6624cd34b580a5734286f
- dopeIPTV: 809ee519a63d55634861bedc694ee0b078a5ee72

## Added: DLNA 7 (FongMi)
FongMi's Android mobile sender has a jUPnP control point: renderer registry/discovery,
AVTransport:1 lookup, DIDL-Lite VideoItem metadata, SetAVTransportURI followed by Play and
optional time seek. V186 adds a separate jUPnP Android service and engine with that action sequence;
it is not routed through SE's Cling/YAACC/TDM/Vega/NekoVideo/CastLab engines. Local-file URLs are
prepared on the phone before they are sent to the television. Provider media URLs remain direct.

## Added: Google Cast 2 (OpenIPTV)
OpenIPTV uses Google Cast's Default Media Receiver and native URL/MIME selection. V186 adds an
independent receiver picker/load path, and tries the HLS sibling URL before the original Xtream
/live/user/pass/id.ts URL for eligible live streams. The existing Google Cast menu item and
Media3 CastPlayer remain available and unchanged. Local files are first exposed through SE's local
media server because the receiver cannot read Android content:// URIs.

## Reviewed but not imported as full engines
- Harbor is a desktop Tauri/Rust application; its richer vendor-specific DLNA discovery/fallbacks
  live in desktop-gated Rust modules and are not a drop-in Android engine.
- dopeIPTV is a Python/PyQt/libmpv desktop app; its CastHub combines a Python SSDP/SOAP sender and
  PyChromecast, so importing it would require a Python runtime/architecture port rather than a
  small native Android integration.
- PlayBridge uses a multi-platform Rust/UniFFI casting core, a separate Android wrapper and proxy.
  Its inspected Android DLNA wrapper contains an explicit runtime contract check for a live status
  field in the packaged Rust session. Copying only its Kotlin wrapper would not be a correct engine;
  integrating the whole native core would be a much larger port and needs its own validation.

CI verifies source/version invariants and Release packaging. Real playback still needs testing on the
Samsung TV; neither SOAP success nor an accepted cast load request proves that the TV fetched/decoded
the stream.
""", encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
notices.write_text(notices.read_text(encoding="utf-8") + """

V100.0.186 — additional cast routes
-----------------------------------
FongMi/TV: https://github.com/FongMi/TV; inspected revision
ef58e5551f9a9d8679821b38422c06373185a04e; GNU GPL v3. The independent jUPnP Android route
uses the FongMi sender sequence: MediaRenderer discovery, AVTransport:1 lookup, DIDL-Lite
VideoItem resource metadata, SetAVTransportURI, Play, and optional time seek. License text:
THIRD_PARTY_LICENSES/FONGMI-TV-GPL-3.0.txt.

OpenIPTV: https://github.com/Hunter-Clipper/OpenIPTV; inspected revision
8c4d47b9b882af1dd72b337ee8f1d71c8a10e902; GNU GPL v3. The separate Google Cast compatibility
route follows its default-receiver load and URL/MIME candidate policy, including a live Xtream HLS
candidate before the .ts resource. License text: THIRD_PARTY_LICENSES/OPENIPTV-GPL-3.0.txt.

Harbor and dopeIPTV were reviewed as desktop-centric architectures, while PlayBridge's Android
DLNA wrapper depends on a bundled Rust/UniFFI casting core; see CAST_INTEGRATION_REVIEW_V100_0_186.md
for the selection rationale. Their code was not falsely represented as integrated.
""", encoding="utf-8")

assert 'versionCode 1000186' in g and 'versionName "100.0.186"' in g
assert 'OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.discover(this@PlayerActivity)' in p
assert 'OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(' in p
assert 'showOpenIptvCastChooser(mediaUri)' in p
assert "implementation 'org.jupnp:org.jupnp:3.0.5'" in g
assert (fongmi_dir / "FongMiDlnaEngine.kt").is_file()
assert (cast_dir / "OpenIptvCastCompatibility.kt").is_file()
assert audit.is_file()
print("V100.0.186 FongMi/OpenIPTV integration applied and static checks passed.")
