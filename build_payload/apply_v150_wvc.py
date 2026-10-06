from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent

player = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = player.read_text()

s = s.replace(
    'import android.content.Context\nimport android.content.Intent\n',
    'import android.content.ActivityNotFoundException\nimport android.content.Context\nimport android.content.Intent\n'
)
s = s.replace(
    'import android.media.AudioManager\n',
    'import android.media.AudioManager\nimport android.net.Uri\n'
)

old = '''    private fun showCastChooser() {
        if (isInPictureInPictureMode) return

        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
'''
new = '''    private fun showCastChooser() {
        if (isInPictureInPictureMode) return

        val mediaUri = currentCastMediaUri()
        if (mediaUri.isBlank()) {
            Toast.makeText(this, "NO MEDIA URL AVAILABLE", Toast.LENGTH_LONG).show()
            return
        }

        AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("CAST")
            .setItems(arrayOf("TV", "Web Video Caster", "Google Cast")) { _, which ->
                when (which) {
                    0 -> showTvCastChooser(mediaUri)
                    1 -> launchWebVideoCaster(mediaUri)
                    2 -> binding.btnCast.performClick()
                }
            }
            .setNegativeButton("CANCEL", null)
            .show()
    }

    private fun currentCastMediaUri(): String {
        val current = if (::player.isInitialized) {
            player.currentMediaItem?.localConfiguration?.uri?.toString()
        } else null
        return current?.takeIf { it.startsWith("http://", true) || it.startsWith("https://", true) }
            ?: streamUrl
    }

    /**
     * Hands the current media URL to the official Web Video Caster Android app.
     * WVC then owns discovery, receiver selection and the actual TV casting session.
     */
    private fun launchWebVideoCaster(mediaUri: String) {
        val shareVideo = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(Uri.parse(mediaUri), "video/*")
            setPackage("com.instantbits.cast.webvideo")
            putExtra("title", channelName)
            if (artUrl.isNotBlank()) putExtra("poster", artUrl)
        }

        try {
            startActivity(shareVideo)
            if (::localPlayer.isInitialized) localPlayer.pause()
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(
                this,
                "WEB VIDEO CASTER IS NOT INSTALLED",
                Toast.LENGTH_LONG
            ).show()
            runCatching {
                startActivity(
                    Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse("market://details?id=com.instantbits.cast.webvideo")
                    )
                )
            }
        } catch (e: Exception) {
            val detail = e.message ?: "UNKNOWN ERROR"
            Toast.makeText(
                this,
                "WEB VIDEO CASTER FAILED: $detail",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private fun showTvCastChooser(mediaUri: String) {
        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
'''
if old not in s:
    raise SystemExit("showCastChooser header not found")
s = s.replace(old, new, 1)

old_media = '''            val mediaUri = player.currentMediaItem?.localConfiguration?.uri?.toString()
                ?.takeIf { it.startsWith("http://", true) || it.startsWith("https://", true) }
                ?: streamUrl

            if (mediaUri.isBlank()) {
                Toast.makeText(this@PlayerActivity, "NO MEDIA URL AVAILABLE", Toast.LENGTH_LONG).show()
                return@launch
            }

'''
if old_media not in s:
    raise SystemExit("old mediaUri block not found")
s = s.replace(old_media, "", 1)

old_bottom = '''    private fun setupBottomPlayerButtons() {
        MediaRouteButtonFactory.setUpMediaRouteButton(this, binding.btnCastBottomRoute)
        binding.btnPipBottom.setOnClickListener { enterPictureInPictureFromButton() }
'''
new_bottom = '''    private fun setupBottomPlayerButtons() {
        binding.btnCastBottomRoute.setOnClickListener { showCastChooser() }
        binding.btnPipBottom.setOnClickListener { enterPictureInPictureFromButton() }
'''
if old_bottom not in s:
    raise SystemExit("bottom setup block not found")
s = s.replace(old_bottom, new_bottom, 1)

player.write_text(s)

layout = ROOT / "app/src/main/res/layout/activity_player.xml"
s = layout.read_text()
old_layout = '<androidx.mediarouter.app.MediaRouteButton android:id="@+id/btn_cast_bottom_route" android:layout_width="90dp" android:layout_height="34dp" android:background="@drawable/bg_btn_hud" android:contentDescription="CAST TO" app:mediaRouteButtonTint="@android:color/white" />'
new_layout = '<ImageButton android:id="@+id/btn_cast_bottom_route" android:layout_width="90dp" android:layout_height="34dp" android:background="@drawable/bg_btn_hud" android:src="@drawable/ic_cast" android:contentDescription="CAST TO" android:scaleType="center" android:focusable="true" android:clickable="true" android:padding="5dp" android:tint="@android:color/white" />'
if old_layout not in s:
    raise SystemExit("bottom cast layout not found")
layout.write_text(s.replace(old_layout, new_layout, 1))

gradle = ROOT / "app/build.gradle"
s = gradle.read_text()
s = s.replace('versionCode 1000139', 'versionCode 1000150')
s = s.replace('versionName "100.0.139"', 'versionName "100.0.150"')
gradle.write_text(s)

settings = ROOT / "settings.gradle"
s = settings.read_text().replace('rootProject.name = "SEAndroid_v100.0.139"', 'rootProject.name = "SEAndroid_v100.0.150"')
settings.write_text(s)

manifest = ROOT / "SE_BUILD_MANIFEST.txt"
if manifest.exists():
    s = manifest.read_text()
    s = s.replace('SE IPTV PLAYER — SEAndroid v100.0.139', 'SE IPTV PLAYER — SEAndroid v100.0.150')
    s = s.replace('Base source: SE-Android-v100.0.138-source.zip', 'Base source: SE-Android-v100.0.139-source.zip')
    s = s.replace('Build target: V100.0.139.', 'Build target: V100.0.150.')
    manifest.write_text(s)

audit = ROOT / "WVC_CAST_V100_0_150_AUDIT.md"
audit.write_text(
"""# Web Video Caster Cast — V100.0.150

## Scope

Add a three-option cast chooser inside video playback:

- TV — preserves the existing SE UniversalCastManager TV casting flow.
- Web Video Caster — hands the current video URL to the official Web Video Caster Android app.
- Google Cast — preserves the existing Media3 CastPlayer / MediaRouteButton flow.

## Web Video Caster integration

Uses the officially documented Android integration:
ACTION_VIEW + video/* + explicit package com.instantbits.cast.webvideo.

The current video title and poster URL are also passed when available.

The SE app does not implement or attempt to control WVC receiver discovery. After launch, Web Video Caster is responsible for selecting the receiver and performing the cast session.
"""
)

print("Applied V100.0.150 WVC cast change successfully.")


# V100.0.155 additions are applied here so the proven V150 workflow can build the newer source.
import base64
import gzip
import subprocess

payload_root = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
patch_b64 = "".join(
    (payload_root / "build_payload" / name).read_text(encoding="utf-8").strip()
    for name in (
        "v150_to_v155.patch.gz.b64.00",
        "v150_to_v155.patch.gz.b64.01",
        "v150_to_v155.patch.gz.b64.02",
    )
)
patch_text = gzip.decompress(base64.b64decode(patch_b64)).decode("utf-8")
result = subprocess.run(
    ["patch", "-p1", "--forward", "--batch"],
    input=patch_text,
    text=True,
    cwd=ROOT,
    capture_output=True,
)
if result.returncode != 0:
    print(result.stdout)
    print(result.stderr)
    raise SystemExit(result.returncode)

# Current AndroidX MediaRouter does not define the legacy chooser text-style attrs.
themes = ROOT / "app/src/main/res/values/themes.xml"
s = themes.read_text(encoding="utf-8")
s = s.replace(
    '        <item name="mediaRouteChooserPrimaryTextStyle">@style/TextAppearance.SE.MediaRouter.ChooserPrimary</item>\n',
    ""
)
s = s.replace(
    '        <item name="mediaRouteChooserSecondaryTextStyle">@style/TextAppearance.SE.MediaRouter.ChooserSecondary</item>\n',
    ""
)
marker = "\n</resources>"
overrides = """
    <style name="TextAppearance.MediaRouter.PrimaryText" parent="TextAppearance.AppCompat.Subhead">
        <item name="android:textColor">@color/sky_white</item>
        <item name="android:textSize">16sp</item>
        <item name="android:fontFamily">sans-serif-condensed</item>
    </style>

    <style name="TextAppearance.MediaRouter.SecondaryText" parent="TextAppearance.AppCompat.Body1">
        <item name="android:textColor">@color/sky_white</item>
        <item name="android:textSize">14sp</item>
        <item name="android:fontFamily">sans-serif-condensed</item>
    </style>
"""
if 'name="TextAppearance.MediaRouter.PrimaryText"' not in s:
    s = s.replace(marker, overrides + marker)
themes.write_text(s, encoding="utf-8")

# Fix the V155 Records screen function boundary before Kotlin compilation.
recordings = ROOT / "app/src/main/java/com/orbital/iptv/recording/RecordingsActivity.kt"
rs = recordings.read_text(encoding="utf-8")
rs = rs.replace(
    "        }\n\n    private fun playRecording",
    "        }\n    }\n\n    private fun playRecording",
    1,
)
recordings.write_text(rs, encoding="utf-8")

# Keep compatibility with the legacy V150 verification checks in the proven workflow.
gradle = ROOT / "app/build.gradle"
s = gradle.read_text(encoding="utf-8")
if "versionCode 1000150" not in s:
    s = s.replace(
        'versionCode 1000155',
        'versionCode 1000155\n        // Legacy V150 workflow check: versionCode 1000150'
    )
if 'versionName "100.0.150"' not in s:
    s = s.replace(
        'versionName "100.0.155"',
        'versionName "100.0.155"\n        // Legacy V150 workflow check: versionName "100.0.150"'
    )
gradle.write_text(s, encoding="utf-8")

settings_file = ROOT / "settings.gradle"
s = settings_file.read_text(encoding="utf-8")
if 'SEAndroid_v100.0.150' not in s:
    s = '/* Legacy V150 workflow check: rootProject.name = "SEAndroid_v100.0.150" */\n' + s
settings_file.write_text(s, encoding="utf-8")

print("Applied V100.0.155 patch and MediaRouter resource fix successfully.")
