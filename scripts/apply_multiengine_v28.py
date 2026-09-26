from pathlib import Path
import re

ROOT = Path(".")

# Version + native engine dependencies.
p = ROOT / "app/build.gradle"
s = p.read_text()
s = re.sub(r'versionCode\s+\d+', 'versionCode 1000028', s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.28"', s, count=1)
s = re.sub(r'\bcompileSdk\s+\d+', 'compileSdk 36', s, count=1)
s = re.sub(r'\bminSdk\s+\d+', 'minSdk 26', s, count=1)
if "org.videolan.android:libvlc-all:3.5.1" not in s:
    s = s.replace(
        "    implementation 'androidx.work:work-runtime-ktx:2.9.0'\n",
        "    implementation 'androidx.work:work-runtime-ktx:2.9.0'\n"
        "    implementation 'org.videolan.android:libvlc-all:3.5.1'\n"
        "    implementation 'dev.jdtech.mpv:libmpv:1.0.0'\n"
    )
p.write_text(s)

# API 36 support required by libmpv 1.0.0. Keep target/min SDK unchanged.
p = ROOT / "build.gradle"
s = p.read_text()
s = s.replace('classpath "com.android.tools.build:gradle:8.6.0"', 'classpath "com.android.tools.build:gradle:8.10.0"')
p.write_text(s)

p = ROOT / "gradle/wrapper/gradle-wrapper.properties"
s = p.read_text()
s = s.replace(
    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip",
    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.11.1-bin.zip"
)
p.write_text(s)

# Player selector persistence.
p = ROOT / "app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt"
s = p.read_text()
s = s.replace(
    "enum class PlayerType { EXOPLAYER, GENC_MEDIA3, EXTERNAL }",
    "enum class PlayerType { EXOPLAYER, GENC_MEDIA3, VLC, MPV, EXTERNAL }"
)
start = s.find('    /** Genç Media3 is the only built-in player UI in v100.0.14.')
end = s.find('    fun clearCredentials', start)
if start < 0 or end < 0:
    raise SystemExit("PrefsManager player block not found")
s = s[:start] + '''    /** Stores the selected built-in playback engine. */
    fun setPlayerType(context: Context, type: PlayerType) {
        prefs(context).edit().putString(KEY_PLAYER_TYPE, type.name).apply()
    }

    fun getPlayerType(context: Context): PlayerType = runCatching {
        PlayerType.valueOf(
            prefs(context).getString(KEY_PLAYER_TYPE, PlayerType.GENC_MEDIA3.name)
                ?: PlayerType.GENC_MEDIA3.name
        )
    }.getOrDefault(PlayerType.GENC_MEDIA3)

''' + s[end:]
p.write_text(s)

# Keep the existing PlayerActivity UI for SE/Media3; route only VLC/MPV to the multi-engine host.
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

# Settings selector.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt"
s = p.read_text()
old = '        b.tvBuiltinPlayerValue.text = "SE PLAYER"\n'
if old in s:
    s = s.replace(old, '        b.tvBuiltinPlayerValue.text = "SE PLAYER / MULTI ENGINE"\n        b.btnPlayerEngine.text = "PLAYER ENGINE: " + playerEngineLabel(PrefsManager.getPlayerType(this))\n        b.btnPlayerEngine.setOnClickListener { showPlayerEngineDialog() }\n', 1)
else:
    raise SystemExit("Settings player label anchor not found")

marker = '    private fun qualityLabel(v: PrefsManager.DefaultQuality) = when (v) {'
helper = '''    private fun playerEngineLabel(type: PrefsManager.PlayerType): String = when (type) {
        PrefsManager.PlayerType.VLC -> "VLC"
        PrefsManager.PlayerType.MPV -> "MPV + FFmpeg"
        PrefsManager.PlayerType.EXTERNAL -> "External Player"
        PrefsManager.PlayerType.EXOPLAYER, PrefsManager.PlayerType.GENC_MEDIA3 -> "SE / Media3"
    }

    private fun showPlayerEngineDialog() {
        val values = arrayOf(
            PrefsManager.PlayerType.GENC_MEDIA3,
            PrefsManager.PlayerType.VLC,
            PrefsManager.PlayerType.MPV
        )
        val labels = values.map(::playerEngineLabel).toTypedArray()
        val selected = values.indexOf(PrefsManager.getPlayerType(this)).takeIf { it >= 0 } ?: 0
        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("PLAYER ENGINE")
            .setSingleChoiceItems(labels, selected) { dialog, which ->
                PrefsManager.setPlayerType(this, values[which])
                b.btnPlayerEngine.text = "PLAYER ENGINE: " + playerEngineLabel(values[which])
                dialog.dismiss()
            }
            .show()
    }

'''
if marker not in s:
    raise SystemExit("Settings helper anchor not found")
s = s.replace(marker, helper + marker, 1)
old_list = 'b.btnDefaultQuality, b.btnDecoderPerformance, b.btnSubtitleAppearance, b.btnThemeColor, b.btnClearHistory, b.btnClearFavorite, b.btnResetApp'
if old_list in s:
    s = s.replace(old_list, 'b.btnDefaultQuality, b.btnDecoderPerformance, b.btnSubtitleAppearance, b.btnThemeColor, b.btnPlayerEngine, b.btnClearHistory, b.btnClearFavorite, b.btnResetApp', 1)
p.write_text(s)

# Settings layout: insert selector immediately under PLAYER SETTINGS header.
p = ROOT / "app/src/main/res/layout/activity_settings.xml"
s = p.read_text()
if 'android:id="@+id/btn_player_engine"' not in s:
    marker = '<TextView android:id="@+id/tv_player_settings_header"'
    idx = s.find(marker)
    if idx < 0:
        raise SystemExit("settings header not found")
    line_end = s.find(">\n", idx)
    if line_end < 0:
        raise SystemExit("settings header line end not found")
    row = '                <Button android:id="@+id/btn_player_engine" android:text="PLAYER ENGINE: SE / MEDIA3" android:layout_width="match_parent" android:layout_height="50dp" android:layout_marginTop="8dp"/>\n'
    s = s[:line_end+2] + row + s[line_end+2:]
s = re.sub(r'V100\.0\.\d+', 'V100.0.28', s)
p.write_text(s)

# Manifest: add multi-engine Activity.
p = ROOT / "app/src/main/AndroidManifest.xml"
s = p.read_text()
if '.ui.player.EnginePlayerActivity' not in s:
    marker = '''        <activity
            android:name=".ui.player.PlayerActivity"
'''
    if marker not in s:
        raise SystemExit("manifest PlayerActivity marker not found")
    insert = '''        <activity
            android:name=".ui.player.EnginePlayerActivity"
            android:exported="false"
            android:supportsPictureInPicture="true"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden" />

'''
    s = s.replace(marker, insert + marker, 1)
p.write_text(s)

# Build manifest metadata.
p = ROOT / "SE_BUILD_MANIFEST.txt"
if p.exists():
    s = p.read_text().replace("V100.0.27", "V100.0.28")
    if "Multi-engine playback:" not in s:
        s += "\nMulti-engine playback: SE/Media3 (default), LibVLC 3.5.1, libmpv 1.0.0. Exactly one selected engine is active per playback session.\n"
    p.write_text(s)

print("V100.0.28 multi-engine patch prepared")
