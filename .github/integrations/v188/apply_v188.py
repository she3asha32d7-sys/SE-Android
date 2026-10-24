#!/usr/bin/env python3
"""Apply V100.0.188 PHONE FILES cast-menu support to the V187 source artifact."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v188.py <source-root>")
root = Path(sys.argv[1]).resolve()
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player_file = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
assert all(x.is_file() for x in (gradle, settings, player_file))

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player_file.read_text(encoding="utf-8")
assert 'versionCode 1000187' in g and 'versionName "100.0.187"' in g
assert 'rootProject.name = "SEAndroid_v100.0.187"' in s
assert 'implementation \'androidx.media3:media3-cast:1.9.0\'' in g

old_menu = '''        // Preserve every existing SE CAST path. DLNA 2 is an independent TDM-compatible
        // protocol adapter; it does not replace or alter the legacy DLNA implementation.
        val castChoices = if (isLocalFile) {
            arrayOf("DLNA 3 (CastLab)", "DLNA 7 (FongMi)", "Google Cast 2 (OpenIPTV)")
        } else {
            arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)", "DLNA 7 (FongMi)", "Google Cast 2 (OpenIPTV)")
        }
'''
new_menu = '''        // PHONE FILES and streamed videos intentionally share the same SE CAST menu. A local
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
'''
p = replace_once(p, old_menu, new_menu, "unify cast menu choices")

old_dispatch = '''                if (isLocalFile) {
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
                }
'''
new_dispatch = '''                when (which) {
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
'''
p = replace_once(p, old_dispatch, new_dispatch, "unify cast menu routing")

helpers = '''    /**
     * DLNA receivers and external cast apps cannot fetch Android content:// URIs directly.
     * Reuse SE's local HTTP file server for PHONE FILES; network IPTV/VOD URLs stay unchanged.
     */
    private fun withCastReadyMedia(mediaUri: String, onReady: (String) -> Unit) {
        if (!isLocalFile || mediaUri.startsWith("http://", true) || mediaUri.startsWith("https://", true)) {
            onReady(mediaUri)
            return
        }
        val preparing = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle("PREPARING PHONE VIDEO")
            .setMessage("PREPARING A LOCAL NETWORK STREAM FOR THE SELECTED CAST RECEIVER...")
            .setCancelable(false)
            .create()
        preparing.show()
        lifecycleScope.launch {
            val result = runCatching {
                CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive)
            }
            if (isFinishing || isDestroyed) {
                runCatching { preparing.dismiss() }
                return@launch
            }
            runCatching { preparing.dismiss() }
            result.onSuccess(onReady).onFailure { error ->
                android.util.Log.e("SEPhoneFileCast", "Could not prepare phone video for casting", error)
                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                    .setTitle("PHONE FILE CAST FAILED")
                    .setMessage(error.message ?: "Could not open this phone video for network casting.")
                    .setPositiveButton("OK", null)
                    .show()
            }
        }
    }

    private var localFileGoogleCastMediaUrl: String? = null
    private var localFileGoogleCastButtonReady = false
    private var localFileGoogleCastButtonSetupRunning = false

    private fun openGoogleCastChooser(mediaUri: String) {
        if (!isLocalFile) {
            binding.btnCast.performClick()
            return
        }
        withCastReadyMedia(mediaUri) { lanUrl ->
            try {
                localFileGoogleCastMediaUrl = lanUrl
                if (!::localPlayer.isInitialized || !::player.isInitialized) {
                    throw IllegalStateException("The local player is not ready for Google Cast.")
                }
                if (castPlayer == null) {
                    // Instantiate CastPlayer only on explicit request; ordinary phone playback stays local-only.
                    player.removeListener(playerListener)
                    castPlayer = CastPlayer.Builder(this)
                        .setLocalPlayer(localPlayer)
                        .setTransferCallback(phoneFileGoogleCastTransferCallback())
                        .build()
                    player = castPlayer!!
                    player.addListener(playerListener)
                    mediaSession?.release()
                    mediaSession = MediaSession.Builder(this, player).build()
                    if (playerType == PlayerType.GENC_MEDIA3) binding.gencPlayerView.player = player
                }
                if (localFileGoogleCastButtonReady) {
                    binding.btnCast.performClick()
                    return@withCastReadyMedia
                }
                if (localFileGoogleCastButtonSetupRunning) return@withCastReadyMedia
                localFileGoogleCastButtonSetupRunning = true
                val setup = MediaRouteButtonFactory.setUpMediaRouteButton(this, binding.btnCast)
                setup.addListener({
                    try {
                        setup.get()
                        runOnUiThread {
                            localFileGoogleCastButtonSetupRunning = false
                            if (isFinishing || isDestroyed) return@runOnUiThread
                            localFileGoogleCastButtonReady = true
                            binding.btnCast.performClick()
                        }
                    } catch (error: Exception) {
                        runOnUiThread {
                            localFileGoogleCastButtonSetupRunning = false
                            if (!isFinishing && !isDestroyed) {
                                Toast.makeText(this@PlayerActivity, "GOOGLE CAST FAILED: " + (error.cause?.message ?: error.message ?: "ROUTE SETUP FAILED"), Toast.LENGTH_LONG).show()
                            }
                        }
                    }
                }, java.util.concurrent.Executor { command -> command.run() })
            } catch (error: Exception) {
                android.util.Log.e("SEPhoneFileCast", "Could not start native Google Cast for a phone file", error)
                Toast.makeText(this@PlayerActivity, "GOOGLE CAST FAILED: " + (error.message ?: "UNKNOWN ERROR"), Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun phoneFileGoogleCastTransferCallback(): CastPlayer.TransferCallback =
        object : CastPlayer.TransferCallback {
            override fun transferState(sourcePlayer: Player, targetPlayer: Player) {
                val sourceItem = sourcePlayer.currentMediaItem
                if (!isLocalFile || sourceItem == null) {
                    CastPlayer.TransferCallback.DEFAULT.transferState(sourcePlayer, targetPlayer)
                    return
                }
                // Receivers must fetch a LAN HTTP URL. On return to the phone, restore its SAF URI.
                val targetUriText = when {
                    sourcePlayer === localPlayer && targetPlayer !== localPlayer -> localFileGoogleCastMediaUrl
                    targetPlayer === localPlayer -> streamUrl
                    else -> null
                }
                if (targetUriText.isNullOrBlank()) {
                    CastPlayer.TransferCallback.DEFAULT.transferState(sourcePlayer, targetPlayer)
                    return
                }
                val positionMs = sourcePlayer.currentPosition.coerceAtLeast(0L)
                val targetItem = sourceItem.buildUpon().setUri(Uri.parse(targetUriText)).build()
                targetPlayer.setMediaItem(targetItem, positionMs)
                runCatching { targetPlayer.repeatMode = sourcePlayer.repeatMode }
                runCatching { targetPlayer.shuffleModeEnabled = sourcePlayer.shuffleModeEnabled }
                runCatching { targetPlayer.playbackParameters = sourcePlayer.playbackParameters }
                targetPlayer.prepare()
                targetPlayer.playWhenReady = sourcePlayer.playWhenReady
            }
        }

'''
p = replace_once(p, '    private fun showOpenIptvCastChooser(mediaUri: String) {', helpers + '    private fun showOpenIptvCastChooser(mediaUri: String) {', "insert local-file cast helpers")

old_wvc = '''    private fun launchWebVideoCaster(mediaUri: String) {
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
'''
new_wvc = '''    private fun launchWebVideoCaster(mediaUri: String) {
        withCastReadyMedia(mediaUri) { readyMediaUri ->
            val shareVideo = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(Uri.parse(readyMediaUri), "video/*")
                setPackage("com.instantbits.cast.webvideo")
                putExtra("title", channelName)
                if (artUrl.isNotBlank()) putExtra("poster", artUrl)
            }
            try {
                startActivity(shareVideo)
                if (::localPlayer.isInitialized) localPlayer.pause()
            } catch (_: ActivityNotFoundException) {
                Toast.makeText(this, "WEB VIDEO CASTER IS NOT INSTALLED", Toast.LENGTH_LONG).show()
                runCatching {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=com.instantbits.cast.webvideo")))
                }
            } catch (e: Exception) {
                Toast.makeText(this, "WEB VIDEO CASTER FAILED: " + (e.message ?: "UNKNOWN ERROR"), Toast.LENGTH_LONG).show()
            }
        }
    }
'''
p = replace_once(p, old_wvc, new_wvc, "Web Video Caster local URL support")

old_dlna2 = '''                    lifecycleScope.launch {
                        val result = TdmCompatibleDlnaManager.cast(
                            device = device,
                            mediaUrl = mediaUri,
                            title = channelName,
                            isLive = isLive
                        )
                        if (result.isSuccess) {'''
new_dlna2 = '''                    lifecycleScope.launch {
                        val readyMediaUri = try {
                            if (isLocalFile) CastLabMediaServer.prepare(this@PlayerActivity, mediaUri, channelName, isLive) else mediaUri
                        } catch (error: Exception) {
                            Toast.makeText(this@PlayerActivity, "PHONE FILE PREPARATION FAILED: " + (error.message ?: "UNKNOWN ERROR"), Toast.LENGTH_LONG).show()
                            return@launch
                        }
                        val result = TdmCompatibleDlnaManager.cast(
                            device = device,
                            mediaUrl = readyMediaUri,
                            title = channelName,
                            isLive = isLive
                        )
                        if (result.isSuccess) {'''
p = replace_once(p, old_dlna2, new_dlna2, "DLNA 2 local-media server URL")

p = replace_once(
    p,
    'val castUri = if (engine == OriginalDlnaEngine.CASTLAB || (engine == OriginalDlnaEngine.FONGMI && isLocalFile)) {',
    'val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB) {',
    "local prep for all original DLNA engines"
)

old_universal = '''    private fun castToSelectedDevice(device: UniversalCastManager.Device, mediaUri: String) {
        lifecycleScope.launch {
            val result = UniversalCastManager.cast(
                context = this@PlayerActivity,
                device = device,
                mediaUrl = mediaUri,
                title = channelName,
                isLive = isLive,
                iconUrl = artUrl
            )

            finishCastResult(device, result)
        }
    }
'''
new_universal = '''    private fun castToSelectedDevice(device: UniversalCastManager.Device, mediaUri: String) {
        withCastReadyMedia(mediaUri) { readyMediaUri ->
            lifecycleScope.launch {
                val result = UniversalCastManager.cast(
                    context = this@PlayerActivity,
                    device = device,
                    mediaUrl = readyMediaUri,
                    title = channelName,
                    isLive = isLive,
                    iconUrl = artUrl
                )
                finishCastResult(device, result)
            }
        }
    }
'''
p = replace_once(p, old_universal, new_universal, "TV and universal DLNA local cast support")

g = g.replace("versionCode 1000187", "versionCode 1000188", 1)
g = g.replace('versionName "100.0.187"', 'versionName "100.0.188"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.187"', 'rootProject.name = "SEAndroid_v100.0.188"', 1)
assert 'versionCode 1000188' in g and 'versionName "100.0.188"' in g
assert 'rootProject.name = "SEAndroid_v100.0.188"' in s
for item in (
    '"TV"', '"DLNA"', '"DLNA 2"', '"Screen Mirror / Wireless Display"', '"Web Video Caster"',
    '"Google Cast"', '"DLNA 3 (CastLab)"', '"DLNA 4 (Vega)"', '"DLNA 5 (NekoVideo)"',
    '"DLNA 6 (YAACC)"', '"DLNA 7 (FongMi)"', '"Google Cast 2 (OpenIPTV)"'
):
    assert item in p, "Missing cast item: " + item
assert 'withCastReadyMedia(mediaUri)' in p
assert 'setDataAndType(Uri.parse(readyMediaUri), "video/*")' in p
assert 'setTransferCallback(phoneFileGoogleCastTransferCallback())' in p
assert 'val castUri = if (isLocalFile || engine == OriginalDlnaEngine.CASTLAB)' in p
assert 'mediaUrl = readyMediaUri' in p

(root / "PHONE_FILES_ALL_CAST_ROUTES_V100_0_188_AUDIT.md").write_text("""# PHONE FILES — all SE CAST routes — V100.0.188

The PHONE FILES local-video player now shows the same twelve CAST choices as streamed videos:
TV, DLNA, DLNA 2, Screen Mirror / Wireless Display, Web Video Caster, Google Cast,
DLNA 3 (CastLab), DLNA 4 (Vega), DLNA 5 (NekoVideo), DLNA 6 (YAACC), DLNA 7 (FongMi),
and Google Cast 2 (OpenIPTV). These are still distinct routes.

Android's document picker provides a content:// URI that remote receivers cannot fetch directly.
The existing CastLab local HTTP server is reused to expose the selected file through an HTTP URL
on the phone's LAN. TV/standard DLNA paths prepare the file only after a receiver is selected;
DLNA 2 uses the same path; Vega/NekoVideo/YAACC gain local-file preparation; Web Video Caster is
given the network URL rather than an ungranted content URI; OpenIPTV's prior local path remains.

For native Google Cast, CastPlayer is initialized lazily only when the user selects that menu item.
A transfer callback changes the outbound URI to the phone's LAN HTTP URL and restores the original
SAF URI on return to phone playback. The default local playback path remains isolated from Cast
discovery unless this option is explicitly selected.

Static CI validation and the signed release build verify source/package integrity. Physical playback
still needs testing with the target TV, network and installed Web Video Caster app. Network casting
requires the phone and receiver to share a reachable LAN/Wi-Fi network.
""", encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
if notices.is_file():
    notices.write_text(notices.read_text(encoding="utf-8") + """

V100.0.188 — PHONE FILES CAST ROUTES
-----------------------------------
PHONE FILES cast support reuses SE IPTV PLAYER's local HTTP media server and existing independent
cast engines. Web Video Caster is launched as an installed external Android app through its intent;
SE does not bundle or redistribute that application.
""", encoding="utf-8")

gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player_file.write_text(p, encoding="utf-8")
print("V100.0.188 PHONE FILES CAST patch applied; source invariants passed.")
