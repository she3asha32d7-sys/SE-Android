#!/usr/bin/env python3
"""V100.0.190: make the primary CAST chooser show DISCONNECT left and CANCEL right."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v190.py <source-root>")
root = Path(sys.argv[1]).resolve()
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player_file = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert all(path.is_file() for path in (gradle, settings, player_file))

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player_file.read_text(encoding="utf-8")
assert 'versionCode 1000189' in g and 'versionName "100.0.189"' in g
assert 'rootProject.name = "SEAndroid_v100.0.189"' in s

start = p.find("    private fun showCastChooser() {")
end_marker = '''    /**
     * DLNA receivers and external cast apps cannot fetch Android content:// URIs directly.
'''
end = p.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate the complete primary showCastChooser() method")

new_method = '''    private fun showCastChooser() {
        if (isInPictureInPictureMode) return

        val mediaUri = currentCastMediaUri()
        if (mediaUri.isBlank()) {
            Toast.makeText(this, "NO MEDIA URL AVAILABLE", Toast.LENGTH_LONG).show()
            return
        }

        // All visible cast buttons in PlayerActivity route here for streamed and PHONE FILES media.
        // Use AlertDialog's native item list and native button panel so both actions remain visible
        // on small screens and themed/RTL devices. The dialog is forced LTR for stable button order.
        val castChoices = arrayOf(
            "TV",
            "DLNA",
            "DLNA 2",
            "Screen Mirror / Wireless Display",
            "Web Video Caster",
            "Google Cast",
            "DLNA 3 (CastLab)",
            "DLNA 4 (Vega)",
            "DLNA 5 (NekoVideo)",
            "DLNA 6 (YAACC)",
            "DLNA 7 (FongMi)",
            "Google Cast 2 (OpenIPTV)"
        )

        val castDialog = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("CAST")
            .setItems(castChoices) { _, which ->
                when (which) {
                    0 -> showTvCastChooser(mediaUri)
                    1 -> showDlnaCastChooser(mediaUri)
                    2 -> showDlna2Chooser(mediaUri)
                    3 -> openWirelessDisplaySettings()
                    4 -> launchWebVideoCaster(mediaUri)
                    5 -> openGoogleCastChooser(mediaUri)
                    6 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                    7 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.VEGA)
                    8 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.NEKOVIDEO)
                    9 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.YAACC)
                    10 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.FONGMI)
                    11 -> showOpenIptvCastChooser(mediaUri)
                }
            }
            .setNegativeButton("DISCONNECT", null)
            .setPositiveButton("CANCEL", null)
            .create()

        castDialog.setOnShowListener {
            castDialog.window?.let { window ->
                window.decorView.layoutDirection = View.LAYOUT_DIRECTION_LTR
                window.decorView.requestLayout()
                window.setBackgroundDrawable(ColorDrawable(Color.BLACK))
                window.decorView.setBackgroundColor(Color.BLACK)
            }
            castDialog.findViewById<TextView>(androidx.appcompat.R.id.alertTitle)
                ?.setTextColor(Color.WHITE)

            val disconnectButton = castDialog.getButton(AlertDialog.BUTTON_NEGATIVE)
            disconnectButton.text = "DISCONNECT"
            disconnectButton.isAllCaps = true
            disconnectButton.setTextColor(ThemeManager.palette().accent)
            disconnectButton.setOnClickListener {
                if (!disconnectButton.isEnabled) return@setOnClickListener
                disconnectButton.isEnabled = false
                lifecycleScope.launch {
                    val result = CastDisconnectManager.disconnect(this@PlayerActivity)
                    if (isFinishing || isDestroyed) return@launch
                    disconnectButton.isEnabled = true
                    if (result.isSuccess) {
                        castDialog.dismiss()
                        Toast.makeText(
                            this@PlayerActivity,
                            "CAST DISCONNECTED: " + result.getOrNull(),
                            Toast.LENGTH_LONG
                        ).show()
                        showGencOverlay()
                    } else {
                        Toast.makeText(
                            this@PlayerActivity,
                            result.exceptionOrNull()?.message ?: "NO ACTIVE CAST SESSION WAS FOUND.",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                }
            }

            val cancelButton = castDialog.getButton(AlertDialog.BUTTON_POSITIVE)
            cancelButton.text = "CANCEL"
            cancelButton.isAllCaps = true
            cancelButton.setTextColor(Color.WHITE)
            cancelButton.setOnClickListener { castDialog.dismiss() }
        }
        castDialog.show()
    }

'''
p = p[:start] + new_method + p[end:]

# Guard against regressions: each visible player cast entry must call the common chooser.
required_hooks = (
    'binding.btnCastBottomRoute.setOnClickListener { showCastChooser() }',
    'binding.btnCastBottom.setOnClickListener { showCastChooser() }',
    'b.btnGencCast.setOnClickListener { showCastChooser() }',
)
for hook in required_hooks:
    if hook not in p:
        raise SystemExit("Missing common cast-menu trigger: " + hook)

g = g.replace("versionCode 1000189", "versionCode 1000190", 1)
g = g.replace('versionName "100.0.189"', 'versionName "100.0.190"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.189"', 'rootProject.name = "SEAndroid_v100.0.190"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player_file.write_text(p, encoding="utf-8")

(root / "CAST_DIALOG_DISCONNECT_CANCEL_VISIBLE_V100_0_190_AUDIT.md").write_text("""# CAST dialog button visibility correction — V100.0.190

The prior V189 chooser built its options and footer inside a custom fixed-height view. Although that
source compiled, the user reported that DISCONNECT was not visible in the CAST chooser on either
streamed video or PHONE FILES. This release removes that custom footer/list container completely.

The chooser now uses AndroidX AlertDialog's native item list and native dialog button panel. It
declares DISCONNECT as the negative button and CANCEL as the positive button, then forces the dialog
window layout direction to LTR before styling the buttons. This pins DISCONNECT to the far left and
CANCEL to the far right irrespective of the app's Arabic/RTL locale. Native dialog sizing also avoids
the old fixed-height custom ListView pushing its footer below a constrained dialog viewport.

The streamed-video and PHONE FILES cast controls already present in PlayerActivity are validated to
all call this same showCastChooser(): btnCastBottomRoute, btnCastBottom, and btnGencCast. The twelve
independent cast choices and their dispatch targets are unchanged. Disconnect still delegates to
CastDisconnectManager and leaves the chooser open if the operation fails.

Build, static invariants, signed APK certificate, and archive integrity are checked by GitHub Actions.
Physical device validation is still required to confirm receiver-specific disconnect behavior.
""", encoding="utf-8")

assert 'versionCode 1000190' in g and 'versionName "100.0.190"' in g
assert 'rootProject.name = "SEAndroid_v100.0.190"' in s
assert '.setNegativeButton("DISCONNECT", null)' in p
assert '.setPositiveButton("CANCEL", null)' in p
assert 'window.decorView.layoutDirection = View.LAYOUT_DIRECTION_LTR' in p
assert 'CastDisconnectManager.disconnect(this@PlayerActivity)' in p
assert all(hook in p for hook in required_hooks)
print("V100.0.190 dialog-button correction applied; static checks passed.")
