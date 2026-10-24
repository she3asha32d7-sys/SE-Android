#!/usr/bin/env python3
"""Apply the focused CastLab local-file/discovery fix on the reconstructed V178 source tree."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v179.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
assert player.is_file() and gradle.is_file() and settings.is_file(), f"Not an SE Android source root: {root}"

java_root = root / "app/src/main/java"
engine_root = java_root / "com/orbital/iptv/utils/originaldlna"
engine_root.mkdir(parents=True, exist_ok=True)
for name in ("CastLabDlnaEngine.kt", "CastLabMediaServer.kt"):
    source = repo / ".github/integrations/v179" / name
    assert source.is_file(), f"Missing V179 payload: {source}"
    shutil.copy2(source, engine_root / name)

# Increment the SE Android version while preserving every V178 feature.
g = gradle.read_text(encoding="utf-8")
assert 'versionCode 1000178' in g and 'versionName "100.0.178"' in g, "Expected V178 app/build.gradle"
g = g.replace("versionCode 1000178", "versionCode 1000179", 1)
g = g.replace('versionName "100.0.178"', 'versionName "100.0.179"', 1)
gradle.write_text(g, encoding="utf-8")

s = settings.read_text(encoding="utf-8")
assert 'rootProject.name = "SEAndroid_v100.0.178"' in s, "Expected V178 settings.gradle"
settings.write_text(
    s.replace('rootProject.name = "SEAndroid_v100.0.178"', 'rootProject.name = "SEAndroid_v100.0.179"', 1),
    encoding="utf-8"
)

p = player.read_text(encoding="utf-8")
anchor = "import com.orbital.iptv.utils.originaldlna.CastLabDlnaEngine"
assert anchor in p
if "import com.orbital.iptv.utils.originaldlna.CastLabMediaServer" not in p:
    p = p.replace(anchor, anchor + "\nimport com.orbital.iptv.utils.originaldlna.CastLabMediaServer", 1)

# Local-file playback previously hid its cast button and refused to open the cast chooser.
p = p.replace(
    "b.btnGencCast.setOnClickListener { if (!isLocalFile) showCastChooser() }",
    "b.btnGencCast.setOnClickListener { showCastChooser() }"
)
p = p.replace("b.btnGencCast.visibility = if (isLocalFile) View.GONE else View.VISIBLE",
              "b.btnGencCast.visibility = View.VISIBLE")
assert "b.btnGencCast.setOnClickListener { showCastChooser() }" in p
assert "b.btnGencCast.visibility = if (isLocalFile) View.GONE else View.VISIBLE" not in p

old_uri = '''        return current?.takeIf { it.startsWith("http://", true) || it.startsWith("https://", true) }
            ?: streamUrl'''
new_uri = '''        // Keep file:// and content:// URIs for local files; CastLab prepares them into a
        // private HTTP webroot file before telling the TV to play them.
        if (isLocalFile) return current?.takeIf { it.isNotBlank() } ?: streamUrl
        return current?.takeIf { it.startsWith("http://", true) || it.startsWith("https://", true) }
            ?: streamUrl'''
assert old_uri in p, "Unable to locate currentCastMediaUri return logic"
p = p.replace(old_uri, new_uri, 1)

# For local files expose CastLab only until the other engines also have a local-media server.
old_menu = '''        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("CAST")
            .setItems(arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)")) { _, which ->
                when (which) {'''
new_menu = '''        val castChoices = if (isLocalFile) {
            arrayOf("DLNA 3 (CastLab)")
        } else {
            arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)")
        }
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("CAST")
            .setItems(castChoices) { _, which ->
                if (isLocalFile) {
                    showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                } else when (which) {'''
assert old_menu in p, "Unable to find Cast menu options"
p = p.replace(old_menu, new_menu, 1)

# Correct malformed Kotlin string templates from V178.
p = p.replace('"$engine.label} discovery failed"', '"${engine.label} discovery failed"')
p = p.replace('"$engine.label} — SELECT TV"', '"${engine.label} — SELECT TV"')
p = p.replace('"$it.name}  ($it.host})"', '"${it.name}  (${it.host})"')
p = p.replace('"$engine.label} CASTING TO $device.name}"', '"${engine.label} CASTING TO ${device.name}"')

old_cast = '''                    lifecycleScope.launch {
                        val result = when (engine) {
                            OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.VEGA -> VegaDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, mediaUri, channelName, isLive)
                        }'''
new_cast = '''                    lifecycleScope.launch {
                        val castUri = if (engine == OriginalDlnaEngine.CASTLAB) {
                            try {
                                CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName)
                            } catch (error: Exception) {
                                android.util.Log.e("SE-CastLab", "Could not prepare local media for DLNA", error)
                                Toast.makeText(
                                    this@PlayerActivity,
                                    "CASTLAB MEDIA PREPARATION FAILED: " + (error.message ?: "UNKNOWN ERROR"),
                                    Toast.LENGTH_LONG
                                ).show()
                                return@launch
                            }
                        } else mediaUri

                        val result = when (engine) {
                            OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.VEGA -> VegaDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, castUri, channelName, isLive)
                        }'''
assert old_cast in p, "Unable to find original engine dispatch block"
p = p.replace(old_cast, new_cast, 1)
player.write_text(p, encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
notice_text = notices.read_text(encoding="utf-8") if notices.exists() else ""
notice_text += """

V100.0.179 CastLab focused fix
------------------------------
The CastLab route now follows the discovery/transport flow of CastLab's pinned CastManager.ts:
multiple M-SEARCH targets/retries, a dedicated SSDP NOTIFY listener when Android permits binding
UDP/1900, Wi-Fi multicast binding, UPnP device/service-description resolution, SetAVTransportURI
retry behavior, CastLab-style SOAP headers, DIDL-Lite metadata, and a single Play action.

Local file casting now mirrors CastLab's Main.tsx handoff: a file:// or content:// source is copied
to SE's private castlab-webroot cache and exposed only through a random-token HTTP URL. The included
CastLabMediaServer.kt serves byte-range GET/HEAD requests and emits Accept-Ranges, Content-Range,
transferMode.dlna.org and contentFeatures.dlna.org. Local-file UI displays only the CastLab choice
until other cast engines receive local-file serving support. Existing six cast choices remain
unchanged and in order for network media.
"""
notices.write_text(notice_text, encoding="utf-8")

audit = root / "CASTLAB_V100_0_179_AUDIT.md"
audit.write_text("""# CastLab V100.0.179 — focused integration audit

## Scope
Fix CastLab only. V100.0.178 built successfully, but its CastLab route was a distinct minimal DLNA
adapter and had no local-file HTTP server. This revision does not claim to have embedded the complete
CastLab React Native app UI. It ports the relevant CastLab discovery/handoff behavior to SE's native
Android UI and keeps the upstream CastLab source snapshot under third_party_sources/CastLab.

## Source comparison
- Upstream: third_party_sources/CastLab/src/DLNACast/CastManager.ts.
- Upstream local-file handoff: third_party_sources/CastLab/src/screens/Main.tsx.
- Upstream defaults: third_party_sources/CastLab/src/DLNACast/config/CastConfig.ts and
  third_party_sources/CastLab/src/constants/Values.ts (server port 9125).

## Problems corrected
1. The V178 engine issued only a short batch of M-SEARCH packets and had no separate listener for
   SSDP NOTIFY advertisements. The CastLab engine now retries ssdp:all and MediaRenderer searches,
   binds to the Wi-Fi interface when possible, and opens a UDP/1900 NOTIFY listener when permitted.
2. Local file:// and content:// sources were being passed to the TV without a LAN-reachable URL.
   CastLabMediaServer copies the chosen file to a private cache webroot and announces its HTTP URL.
3. The local-file cast button was hidden, and the local-file click handler rejected the cast chooser.
   Local files now expose CastLab only; IPTV/network media keep the current menu.
4. The media server supports GET/HEAD and single byte ranges, including 206 Partial Content and 416
   handling, with DLNA headers matching CastLab's local-server approach.
5. The media handoff retries SetAVTransportURI up to three times, then sends one Play action.
6. The V178 cast picker had four malformed Kotlin string templates; the device and status labels are
   corrected.

## Tests performed in CI
The workflow will validate version/source paths and run the signed Release build plus signature and
certificate checks. On-device validation is still required: test a downloaded MP4 through CastLab,
then test an HTTP IPTV stream. CI cannot establish that a particular Samsung TV supports every codec.

## Expected local-file test
1. Open a downloaded MP4 in SE IPTV Player.
2. Open the player controls and tap Cast.
3. Choose DLNA 3 (CastLab), then select the Samsung TV.
4. The app copies the file into its private cache and gives the TV a phone-LAN HTTP URL.
5. On the serving URL, Range: bytes=0-1 should yield HTTP 206, Content-Range: bytes 0-1/<size>,
   and Accept-Ranges: bytes.
""", encoding="utf-8")

g2 = gradle.read_text(encoding="utf-8")
s2 = settings.read_text(encoding="utf-8")
p2 = player.read_text(encoding="utf-8")
assert 'versionCode 1000179' in g2 and 'versionName "100.0.179"' in g2
assert 'rootProject.name = "SEAndroid_v100.0.179"' in s2
assert 'import com.orbital.iptv.utils.originaldlna.CastLabMediaServer' in p2
assert 'CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName)' in p2
assert 'arrayOf("DLNA 3 (CastLab)")' in p2
assert 'b.btnGencCast.setOnClickListener { showCastChooser() }' in p2
assert 'b.btnGencCast.visibility = if (isLocalFile) View.GONE else View.VISIBLE' not in p2
assert all((engine_root / n).is_file() for n in ("CastLabDlnaEngine.kt", "CastLabMediaServer.kt"))
print("V179 CastLab static preflight passed.")
