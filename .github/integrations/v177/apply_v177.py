#!/usr/bin/env python3
import re
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v177.py <source-project-root>")

root = Path(sys.argv[1]).resolve()
workspace = Path(__file__).resolve().parents[2]
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
assert player.is_file() and gradle.is_file() and settings.is_file(), f"Not an SE Android project root: {root}"

# Put the new engine into the native Android source tree.
source_engine = workspace / ".github/integrations/v177/OpenSourceDlnaAdapters.kt"
assert source_engine.is_file(), f"Missing integration source: {source_engine}"
target_engine = root / "app/src/main/java/com/orbital/iptv/utils/OpenSourceDlnaAdapters.kt"
shutil.copy2(source_engine, target_engine)

# Preserve the upstream GPL license and include the license for the Apache-2.0 Vega revision.
shutil.copy2(workspace / "LICENSE", root / "LICENSE")
third_party = root / "THIRD_PARTY_LICENSES"
third_party.mkdir(exist_ok=True)
shutil.copy2(workspace / ".github/integrations/v177/VEGA-APACHE-2.0.txt", third_party / "VEGA-APACHE-2.0.txt")
shutil.copy2(workspace / ".github/integrations/v177/THIRD_PARTY_NOTICES.md", root / "THIRD_PARTY_NOTICES.md")
shutil.copy2(workspace / ".github/integrations/v177/CAST_OPEN_SOURCE_DLNA_V100_0_177_AUDIT.md", root / "CAST_OPEN_SOURCE_DLNA_V100_0_177_AUDIT.md")

text = player.read_text(encoding="utf-8")
if "import com.orbital.iptv.utils.OpenSourceDlnaAdapters" not in text:
    anchor = "import com.orbital.iptv.utils.TdmCompatibleDlnaManager"
    assert anchor in text, "Unable to locate existing TDM import"
    text = text.replace(anchor, anchor + "\nimport com.orbital.iptv.utils.OpenSourceDlnaAdapters", 1)

old_items = 'arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast")'
new_items = ('arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", '
             '"Google Cast", "DLNA 1 (TDM)", "DLNA 2 (CastLab)", "DLNA 3 (Vega)", '
             '"DLNA 4 (NekoVideo)", "DLNA 5 (YAACC)")')
assert old_items in text, "Could not find the exact original CAST menu; stop rather than overwrite unknown code"
text = text.replace(old_items, new_items, 1)
dispatch = '''                    5 -> binding.btnCast.performClick()
                }'''
dispatch_new = '''                    5 -> binding.btnCast.performClick()
                    6 -> showDlna1TdmChooser(mediaUri)
                    7 -> showOpenSourceDlnaChooser(mediaUri, OpenSourceDlnaAdapters.Engine.CASTLAB)
                    8 -> showOpenSourceDlnaChooser(mediaUri, OpenSourceDlnaAdapters.Engine.VEGA)
                    9 -> showOpenSourceDlnaChooser(mediaUri, OpenSourceDlnaAdapters.Engine.NEKOVIDEO)
                    10 -> showOpenSourceDlnaChooser(mediaUri, OpenSourceDlnaAdapters.Engine.YAACC)
                }'''
assert dispatch in text, "Could not find original CAST dispatch; stop rather than risk changing old choices"
text = text.replace(dispatch, dispatch_new, 1)

# GPL-required notice is reachable from the cast dialog, without removing an existing cast choice.
cast_end = '''                    10 -> showOpenSourceDlnaChooser(mediaUri, OpenSourceDlnaAdapters.Engine.YAACC)
                }
            }
            .setNegativeButton("CANCEL", null)
            .show()
'''
cast_end_new = cast_end.replace(
    '            .setNegativeButton("CANCEL", null)',
    '            .setNeutralButton("OPEN-SOURCE LICENSES") { showOpenSourceDlnaLicenseDialog() }\\n            .setNegativeButton("CANCEL", null)'
)
assert cast_end in text, "Could not locate CAST dialog footer for license notice"
text = text.replace(cast_end, cast_end_new, 1)

start = text.find("    private fun showDlna2Chooser(mediaUri: String) {")
end = text.find("    private fun showCastDeviceChooser(mediaUri: String, dlnaOnly: Boolean) {", start)
assert start >= 0 and end > start, "Could not locate the TDM DLNA chooser block"
chooser = '''    // The pre-existing DLNA 2 choice is deliberately preserved and still uses the V176 TDM route.
    private fun showDlna2Chooser(mediaUri: String) = showTdmDlnaChooser(mediaUri, "DLNA 2")

    private fun showDlna1TdmChooser(mediaUri: String) =
        showTdmDlnaChooser(mediaUri, "DLNA 1 (TDM)")

    private fun showTdmDlnaChooser(mediaUri: String, dialogLabel: String) {
        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle(dialogLabel)
            .setMessage("SEARCHING FOR DLNA TVs...")
            .setNegativeButton("CANCEL", null)
            .create()
        searching.show()

        lifecycleScope.launch {
            val devices = runCatching { TdmCompatibleDlnaManager.discover(this@PlayerActivity) }
                .getOrDefault(emptyList())
            if (isFinishing || isDestroyed) {
                searching.dismiss()
                return@launch
            }
            searching.dismiss()

            if (devices.isEmpty()) {
                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                    .setTitle(dialogLabel)
                    .setMessage("NO DLNA TVs FOUND.\\\\n\\\\nMake sure the TV and phone are on the same Wi-Fi network and that DLNA is enabled on the TV.")
                    .setPositiveButton("OK", null)
                    .show()
                return@launch
            }

            AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                .setTitle("$dialogLabel — SELECT TV")
                .setItems(devices.map { "\${it.name}  (\${it.host})" }.toTypedArray()) { _, selected ->
                    val device = devices[selected]
                    lifecycleScope.launch {
                        val result = TdmCompatibleDlnaManager.cast(
                            device = device,
                            mediaUrl = mediaUri,
                            title = channelName,
                            isLive = isLive
                        )
                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "$dialogLabel CASTING TO \${device.name}", Toast.LENGTH_SHORT).show()
                            showGencOverlay()
                        } else {
                            Toast.makeText(
                                this@PlayerActivity,
                                "$dialogLabel FAILED: \${result.exceptionOrNull()?.message ?: "UNKNOWN ERROR"}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                }
                .setNegativeButton("CANCEL", null)
                .show()
        }
    }

    private fun showOpenSourceDlnaChooser(
        mediaUri: String,
        engine: OpenSourceDlnaAdapters.Engine
    ) {
        val label = engine.label
        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle(label)
            .setMessage("SEARCHING FOR DLNA TVs...")
            .setNegativeButton("CANCEL", null)
            .create()
        searching.show()

        lifecycleScope.launch {
            val devices = runCatching {
                OpenSourceDlnaAdapters.discover(this@PlayerActivity, engine)
            }.onFailure {
                android.util.Log.w("SEOpenSourceDLNA", "$label discovery failed", it)
            }.getOrDefault(emptyList())

            if (isFinishing || isDestroyed) {
                searching.dismiss()
                return@launch
            }
            searching.dismiss()

            if (devices.isEmpty()) {
                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                    .setTitle(label)
                    .setMessage("NO DLNA TVs FOUND. Make sure the TV and phone are on the same Wi-Fi network and retry.")
                    .setPositiveButton("OK", null)
                    .show()
                return@launch
            }

            AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                .setTitle("$label — SELECT TV")
                .setItems(devices.map { "\${it.name}  (\${it.host})" }.toTypedArray()) { _, selected ->
                    val device = devices[selected]
                    lifecycleScope.launch {
                        val result = OpenSourceDlnaAdapters.cast(
                            this@PlayerActivity,
                            engine,
                            device,
                            mediaUri,
                            channelName,
                            isLive
                        )
                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "$label CASTING TO \${device.name}", Toast.LENGTH_SHORT).show()
                            showGencOverlay()
                        } else {
                            Toast.makeText(
                                this@PlayerActivity,
                                "$label FAILED: \${result.exceptionOrNull()?.message ?: "UNKNOWN ERROR"}",
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
license_helper = '''    private fun showOpenSourceDlnaLicenseDialog() {
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("OPEN-SOURCE DLNA LICENSES")
            .setMessage(
                "This release includes an adapted NekoVideo DLNA discovery component under GNU GPL v3.0. " +
                    "Vega's native DLNA approach is adapted from Apache-2.0 revision 9ccc0c8. " +
                    "CastLab and YAACC are listed as separate compatibility adapters. " +
                    "TDM's proprietary source is not copied.\n\n" +
                    "These components are provided WITHOUT WARRANTY. The full GPLv3 text, third-party " +
                    "notices, and source references are included in the Source Code ZIP."
            )
            .setPositiveButton("OK", null)
            .show()
    }

'''
chooser = chooser.replace("    private fun showOpenSourceDlnaChooser(", license_helper + "    private fun showOpenSourceDlnaChooser(", 1)
text = text[:start] + chooser + text[end:]

player.write_text(text, encoding="utf-8")

gtext = gradle.read_text(encoding="utf-8")
assert "versionCode 1000176" in gtext and 'versionName "100.0.176"' in gtext, "Unexpected base version in app/build.gradle"
gtext = gtext.replace("versionCode 1000176", "versionCode 1000177", 1)
gtext = gtext.replace('versionName "100.0.176"', 'versionName "100.0.177"', 1)
gradle.write_text(gtext, encoding="utf-8")

stext = settings.read_text(encoding="utf-8")
assert 'rootProject.name = "SEAndroid_v100.0.176"' in stext, "Unexpected root project name"
stext = stext.replace('rootProject.name = "SEAndroid_v100.0.176"', 'rootProject.name = "SEAndroid_v100.0.177"', 1)
settings.write_text(stext, encoding="utf-8")

# Safety checks applied before Gradle starts; they do not substitute for a TV playback test.
assert text.count('arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 1 (TDM)", "DLNA 2 (CastLab)", "DLNA 3 (Vega)", "DLNA 4 (NekoVideo)", "DLNA 5 (YAACC)")') == 1
for label in ("DLNA 1 (TDM)", "DLNA 2 (CastLab)", "DLNA 3 (Vega)", "DLNA 4 (NekoVideo)", "DLNA 5 (YAACC)"):
    assert label in text
assert "showCastDeviceChooser(mediaUri, dlnaOnly = false)" in text
assert "showCastDeviceChooser(mediaUri, dlnaOnly = true)" in text
assert "binding.btnCast.performClick()" in text
assert target_engine.is_file()
print("V177 applied: existing six cast paths preserved; five separate named DLNA adapters appended.")
print("Version 100.0.177, GPL license, Apache Vega license, and third-party notices installed.")
