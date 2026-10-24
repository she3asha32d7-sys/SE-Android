#!/usr/bin/env python3
"""Apply the V100.0.189 CAST DISCONNECT chooser update to the V188 signed source artifact."""
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v189.py <source-root>")
root = Path(sys.argv[1]).resolve()
payload = Path(__file__).resolve().parent / "payload"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player_file = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert all(path.is_file() for path in (gradle, settings, player_file))

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(label + ": expected exactly one match, found " + str(count))
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player_file.read_text(encoding="utf-8")
assert 'versionCode 1000188' in g and 'versionName "100.0.188"' in g
assert 'rootProject.name = "SEAndroid_v100.0.188"' in s

manager_target = root / "app/src/main/java/com/orbital/iptv/utils/CastDisconnectManager.kt"
manager_target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(payload / "CastDisconnectManager.kt", manager_target)

old_menu = '''        // PHONE FILES and streamed videos intentionally share the same SE CAST menu. A local
        // content:// URI is converted to a phone-LAN HTTP URL only after a route is selected.
        // Each receiver engine below stays independent; no cast implementation is substituted.
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
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
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
            .setNegativeButton("CANCEL", null)
            .show()
'''
new_menu = '''        // Keep DISCONNECT at the far left and CANCEL at the far right explicitly.
        val castChoices = arrayOf(
            "TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster",
            "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)",
            "DLNA 6 (YAACC)", "DLNA 7 (FongMi)", "Google Cast 2 (OpenIPTV)"
        )
        val castRoot = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.BLACK)
            setPadding(dp(12), dp(6), dp(12), dp(10))
        }
        val castList = android.widget.ListView(this).apply {
            divider = ColorDrawable(Color.DKGRAY)
            dividerHeight = dp(1)
            selector = ColorDrawable(Color.TRANSPARENT)
            setBackgroundColor(Color.BLACK)
            layoutParams = LinearLayout.LayoutParams(-1, dp(7 * 54))
            adapter = object : ArrayAdapter<String>(this@PlayerActivity, android.R.layout.simple_list_item_1, castChoices.toList()) {
                override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                    val row = super.getView(position, convertView, parent)
                    (row as? TextView)?.apply {
                        setTextColor(Color.WHITE)
                        textSize = 17f
                        setPadding(dp(20), dp(10), dp(20), dp(10))
                        setBackgroundColor(Color.BLACK)
                    }
                    return row
                }
            }
        }
        castRoot.addView(castList)
        val castButtonRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(10), 0, 0)
        }
        val disconnectButton = android.widget.Button(this).apply {
            text = "DISCONNECT"
            isAllCaps = true
            textSize = 13f
            setTextColor(Color.BLACK)
            minHeight = dp(48)
            background = GradientDrawable().apply {
                cornerRadius = dp(7).toFloat()
                setColor(ThemeManager.palette().accent)
            }
            layoutParams = LinearLayout.LayoutParams(0, dp(48), 1f).apply { marginEnd = dp(8) }
        }
        val cancelButton = android.widget.Button(this).apply {
            text = "CANCEL"
            isAllCaps = true
            textSize = 13f
            setTextColor(Color.WHITE)
            minHeight = dp(48)
            background = GradientDrawable().apply {
                cornerRadius = dp(7).toFloat()
                setColor(0xFF252525.toInt())
                setStroke(dp(1), 0xFF68717C.toInt())
            }
            layoutParams = LinearLayout.LayoutParams(0, dp(48), 1f).apply { marginStart = dp(8) }
        }
        castButtonRow.addView(disconnectButton)
        castButtonRow.addView(cancelButton)
        castRoot.addView(castButtonRow)

        val castDialog = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("CAST")
            .setView(castRoot)
            .create()
        castList.setOnItemClickListener { _, _, which, _ ->
            castDialog.dismiss()
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
        cancelButton.setOnClickListener { castDialog.dismiss() }
        disconnectButton.setOnClickListener {
            disconnectButton.isEnabled = false
            lifecycleScope.launch {
                val result = CastDisconnectManager.disconnect(this@PlayerActivity)
                disconnectButton.isEnabled = true
                if (result.isSuccess) {
                    castDialog.dismiss()
                    Toast.makeText(this@PlayerActivity, "CAST DISCONNECTED: " + result.getOrNull(), Toast.LENGTH_LONG).show()
                    showGencOverlay()
                } else {
                    Toast.makeText(this@PlayerActivity, result.exceptionOrNull()?.message ?: "NO ACTIVE CAST SESSION WAS FOUND.", Toast.LENGTH_LONG).show()
                }
            }
        }
        castDialog.setOnShowListener {
            castDialog.window?.setBackgroundDrawable(ColorDrawable(Color.BLACK))
            castDialog.window?.decorView?.setBackgroundColor(Color.BLACK)
            castDialog.findViewById<TextView>(androidx.appcompat.R.id.alertTitle)?.setTextColor(Color.WHITE)
        }
        castDialog.show()
'''
p = replace_once(p, old_menu, new_menu, "replace CAST dialog")

p = replace_once(p, 'import com.orbital.iptv.utils.UniversalCastManager\n',
    'import com.orbital.iptv.utils.UniversalCastManager\nimport com.orbital.iptv.utils.CastDisconnectManager\n', "CastDisconnectManager import")
p = replace_once(p,
'''                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "DLNA 2 CASTING TO \${device.name}", Toast.LENGTH_SHORT).show()''',
'''                        if (result.isSuccess) {
                            CastDisconnectManager.registerDlna("DLNA 2 — " + device.name, device.controlUrl, device.serviceType)
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "DLNA 2 CASTING TO \${device.name}", Toast.LENGTH_SHORT).show()''',
    "register DLNA 2")
p = replace_once(p,
'''                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            if (engine == OriginalDlnaEngine.CASTLAB && CastLabMediaServer.isServing(castUri)) {''',
'''                        if (result.isSuccess) {
                            CastDisconnectManager.registerDlna(engine.label + " — " + device.name, device.controlUrl, device.serviceType)
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            if (engine == OriginalDlnaEngine.CASTLAB && CastLabMediaServer.isServing(castUri)) {''',
    "register original DLNA")
p = replace_once(p,
'''        if (result.isSuccess) {
            if (::localPlayer.isInitialized) localPlayer.pause()
            Toast.makeText(
                this@PlayerActivity,
                "CASTING TO \${device.friendlyName}",''',
'''        if (result.isSuccess) {
            CastDisconnectManager.registerUniversal("TV / DLNA — " + device.friendlyName)
            if (::localPlayer.isInitialized) localPlayer.pause()
            Toast.makeText(
                this@PlayerActivity,
                "CASTING TO \${device.friendlyName}",''',
    "register Universal TV route")
p = replace_once(p,
'''                            if (::localPlayer.isInitialized) localPlayer.pause()
                            val path = Uri.parse(acceptedUrl).path.orEmpty()''',
'''                            CastDisconnectManager.registerGoogleCast("Google Cast 2 (OpenIPTV) — " + target.name)
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            val path = Uri.parse(acceptedUrl).path.orEmpty()''',
    "register OpenIPTV Google Cast")
p = replace_once(p,
'''            try {
                startActivity(shareVideo)
                if (::localPlayer.isInitialized) localPlayer.pause()''',
'''            try {
                startActivity(shareVideo)
                CastDisconnectManager.registerExternal("Web Video Caster")
                if (::localPlayer.isInitialized) localPlayer.pause()''',
    "register Web Video Caster external session")
p = replace_once(p,
'''        for (action in actions) {
            runCatching {
                startActivity(Intent(action))
                return
            }
        }''',
'''        for (action in actions) {
            runCatching {
                startActivity(Intent(action))
                CastDisconnectManager.registerExternal("Screen Mirror / Wireless Display")
                return
            }
        }''',
    "register wireless display external session")

g = g.replace("versionCode 1000188", "versionCode 1000189", 1)
g = g.replace('versionName "100.0.188"', 'versionName "100.0.189"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.188"', 'rootProject.name = "SEAndroid_v100.0.189"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player_file.write_text(p, encoding="utf-8")
(root / "CAST_DISCONNECT_BUTTON_V100_0_189_AUDIT.md").write_text("""# CAST chooser DISCONNECT button — V100.0.189

The root CAST chooser uses a custom button row so DISCONNECT is anchored at the far left and CANCEL
at the far right. The existing twelve cast choices and their routes remain intact.

Successful Universal TV/DLNA, DLNA 2, each independent UPnP engine, and OpenIPTV Google Cast routes
are tracked. DISCONNECT sends UPnP AVTransport Stop to the last-successful renderer or asks the
UniversalCastManager to stop its active TV/webOS route. For Google Cast, it invokes
RemoteMediaClient stop best-effort and ends the session with SessionManager.endCurrentSession(true).
A selected app-owned MediaRouter route is a secondary fallback.

Web Video Caster and Android Screen Mirror are owned by an external app or the system. Android
exposes no public SE-side API to terminate an external app's session; those paths explain the
limitation instead of falsely claiming that casting stopped. Per-engine play/discovery routes remain
independent and unchanged.

The GitHub build verifies source invariants, signing certificate, and APK package integrity.
""", encoding="utf-8")
notices = root / "THIRD_PARTY_NOTICES.md"
if notices.is_file():
    notices.write_text(notices.read_text(encoding="utf-8") + """

V100.0.189 — CAST DISCONNECT BUTTON
-----------------------------------
The DISCONNECT control uses UPnP AVTransport Stop and public Google Cast SDK session shutdown APIs
for SE-managed receiver sessions. It does not replace any third-party cast engine's play path.
""", encoding="utf-8")

assert 'versionCode 1000189' in g and 'versionName "100.0.189"' in g
assert 'rootProject.name = "SEAndroid_v100.0.189"' in s
assert 'CastDisconnectManager.disconnect(this@PlayerActivity)' in p
assert 'CastDisconnectManager.registerDlna' in p
assert 'CastDisconnectManager.registerUniversal' in p
assert 'CastDisconnectManager.registerGoogleCast' in p
assert 'CastDisconnectManager.registerExternal' in p
print("V100.0.189 patch applied.")
