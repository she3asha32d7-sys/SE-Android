from pathlib import Path
import re

ROOT = Path(".")

# Version + engine dependencies.
p = ROOT / "app/build.gradle"
s = p.read_text()
s = re.sub(r'versionCode\s+\d+', 'versionCode 1000028', s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.28"', s, count=1)
dep = "    implementation 'org.videolan.android:libvlc-all:3.5.1'\n    implementation 'dev.jdtech.mpv:libmpv:1.0.0'\n"
if "org.videolan.android:libvlc-all:3.5.1" not in s:
    s = s.replace("    implementation 'androidx.work:work-runtime-ktx:2.9.0'\n",
                  "    implementation 'androidx.work:work-runtime-ktx:2.9.0'\n\n    // Additional built-in playback engines, implemented natively in SE.\n" + dep)
p.write_text(s)

# Persist the selected built-in engine while keeping old stored values compatible.
p = ROOT / "app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt"
s = p.read_text()
s = s.replace(
    "enum class PlayerType { EXOPLAYER, GENC_MEDIA3, EXTERNAL }",
    "enum class PlayerType { EXOPLAYER, GENC_MEDIA3, VLC, MPV, EXTERNAL }"
)
old = '''    /** Genç Media3 is the only built-in player UI in v100.0.14.
     * Keep the legacy enum/API so old call sites and stored preferences migrate safely.
     */
    fun setPlayerType(context: Context, type: PlayerType) {
        prefs(context).edit().putString(KEY_PLAYER_TYPE, PlayerType.GENC_MEDIA3.name).apply()
    }

    fun getPlayerType(context: Context): PlayerType = PlayerType.GENC_MEDIA3
'''
new = '''    /** Stores the selected built-in playback engine. */
    fun setPlayerType(context: Context, type: PlayerType) {
        prefs(context).edit().putString(KEY_PLAYER_TYPE, type.name).apply()
    }

    fun getPlayerType(context: Context): PlayerType = runCatching {
        PlayerType.valueOf(
            prefs(context).getString(KEY_PLAYER_TYPE, PlayerType.GENC_MEDIA3.name)
                ?: PlayerType.GENC_MEDIA3.name
        )
    }.getOrDefault(PlayerType.GENC_MEDIA3)
'''
if old in s:
    s = s.replace(old, new)
else:
    # Fallback for the exact v27 source comments.
    s = re.sub(
        r'fun setPlayerType\(context: Context, type: PlayerType\) \{.*?\
    \}\
\
    fun getPlayerType\(context: Context\): PlayerType = PlayerType\.GENC_MEDIA3',
        new.rstrip(),
        s,
        flags=re.S,
        count=1
    )
p.write_text(s)

# Route VLC/MPV selections to the multi-engine host before constructing the SE/Media3 UI.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = p.read_text()
needle = '''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
'''
replacement = '''    override fun onCreate(savedInstanceState: Bundle?) {
        if (!intent.getBooleanExtra("MULTI_ENGINE_HANDOFF", false)) {
            when (PrefsManager.getPlayerType(this)) {
                PlayerType.VLC, PlayerType.MPV -> {
                    startActivity(Intent(this, EnginePlayerActivity::class.java).apply {
                        putExtras(intent)
                        putExtra("MULTI_ENGINE_HANDOFF", true)
                    })
                    finish()
                    return
                }
                else -> Unit
            }
        }
        super.onCreate(savedInstanceState)
'''
if needle not in s:
    raise SystemExit("PlayerActivity onCreate anchor not found")
s = s.replace(needle, replacement, 1)
p.write_text(s)

# Add the engine selector to Settings.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt"
s = p.read_text()
s = s.replace(
    '        b.tvBuiltinPlayerValue.text = "SE PLAYER"\n',
    '        b.tvBuiltinPlayerValue.text = "SE PLAYER / MULTI ENGINE"\n'
    '        updatePlayerEngineButton()\n'
    '        b.btnPlayerEngine.setOnClickListener { showPlayerEngineDialog() }\n',
    1
)
s = s.replace(
    'b.btnThemeColor, b.btnClearHistory, b.btnClearFavorite, b.btnResetApp)',
    'b.btnThemeColor, b.btnPlayerEngine, b.btnClearHistory, b.btnClearFavorite, b.btnResetApp)',
    1
)
marker = '    private fun qualityLabel(v: PrefsManager.DefaultQuality) = when (v) {'
helper = '''    private fun playerEngineLabel(type: PrefsManager.PlayerType): String = when (type) {
        PrefsManager.PlayerType.VLC -> "VLC"
        PrefsManager.PlayerType.MPV -> "MPV + FFmpeg"
        PrefsManager.PlayerType.EXTERNAL -> "External Player"
        PrefsManager.PlayerType.EXOPLAYER, PrefsManager.PlayerType.GENC_MEDIA3 -> "SE / Media3"
    }

    private fun updatePlayerEngineButton() {
        b.btnPlayerEngine.text = "PLAYER ENGINE: " + playerEngineLabel(PrefsManager.getPlayerType(this))
    }

    private fun showPlayerEngineDialog() {
        val values = arrayOf(
            PrefsManager.PlayerType.GENC_MEDIA3,
            PrefsManager.PlayerType.VLC,
            PrefsManager.PlayerType.MPV
        )
        val labels = values.map(::playerEngineLabel).toTypedArray()
        val current = PrefsManager.getPlayerType(this)
        val selected = values.indexOf(current).takeIf { it >= 0 } ?: 0

        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("PLAYER ENGINE")
            .setSingleChoiceItems(labels, selected) { dialog, which ->
                PrefsManager.setPlayerType(this, values[which])
                updatePlayerEngineButton()
                dialog.dismiss()
            }
            .show()
    }

'''
if marker not in s:
    raise SystemExit("SettingsActivity helper anchor not found")
s = s.replace(marker, helper + marker, 1)
p.write_text(s)

p = ROOT / "app/src/main/res/layout/activity_settings.xml"
s = p.read_text()
anchor = '<TextView android:id="@+id/tv_player_settings_header"'
idx = s.find(anchor)
if idx < 0:
    raise SystemExit("settings layout anchor not found")
line_end = s.find(">\n", idx)
if 'android:id="@+id/btn_player_engine"' not in s:
    s = s[:line_end+2] + '                <Button android:id="@+id/btn_player_engine" android:text="PLAYER ENGINE: SE / MEDIA3" android:layout_width="match_parent" android:layout_height="50dp" android:layout_marginTop="8dp"/>\n' + s[line_end+2:]
s = s.replace("V100.0.25", "V100.0.28")
p.write_text(s)

# Manifest declaration.
p = ROOT / "app/src/main/AndroidManifest.xml"
s = p.read_text()
if ".ui.player.EnginePlayerActivity" not in s:
    marker = '''        <activity
            android:name=".ui.player.PlayerActivity"
'''
    if marker not in s:
        raise SystemExit("manifest PlayerActivity anchor not found")
    insert = '''        <activity
            android:name=".ui.player.EnginePlayerActivity"
            android:exported="false"
            android:supportsPictureInPicture="true"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden" />

'''
    s = s.replace(marker, insert + marker, 1)
p.write_text(s)

# Build manifest.
p = ROOT / "SE_BUILD_MANIFEST.txt"
if p.exists():
    s = p.read_text().replace("V100.0.27", "V100.0.28")
    s += "\nMulti-engine playback: SE/Media3 (default), LibVLC 3.5.1, libmpv 1.0.0. Exactly one selected engine is active per playback session.\n"
    p.write_text(s)
