#!/usr/bin/env python3
from pathlib import Path

ROOT = Path.cwd()

def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly 1 match, found {count}")
    p.write_text(s.replace(old, new), encoding="utf-8")

replace_once(
    "app/build.gradle",
    '        versionCode 1000138\n        versionName "100.0.138"',
    '        versionCode 1000139\n        versionName "100.0.139"',
)

replace_once(
    "settings.gradle",
    'rootProject.name = "SEAndroid_v100.0.138"',
    'rootProject.name = "SEAndroid_v100.0.139"',
)

replace_once(
    "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt",
    '                    text = "NO DLNA/LG webOS TV FOUND.\\n\\nGoogle Cast/Chromecast devices can still be selected from the system Cast dialog."',
    '                    text = "NO DLNA/UPnP TV FOUND.\\n\\nGoogle Cast/Chromecast remains available from the system Cast dialog."',
)

replace_once(
    "app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt",
    '''            // Prefer the LG webOS socket path over a second DLNA entry for the same LG host.
            val webOsHosts = devices.filter { it.protocol == Protocol.WEBOS }.map { it.host }
            devices
                .filter { it.protocol == Protocol.WEBOS || it.host !in webOsHosts }
                .distinctBy { "\${it.protocol}:\$it.host:\${it.controlUrl ?: it.port}" }
                .sortedWith(compareBy<Device> { it.friendlyName.lowercase(Locale.US) }.thenBy { it.protocol.label })''',
    '''            // Prefer standard DLNA for an LG host when both DLNA and SSAP are advertised.
            // DLNA avoids the webOS pairing prompt. Keep SSAP as fallback when DLNA is absent.
            val dlnaHosts = devices.filter { it.protocol == Protocol.DLNA }.map { it.host }.toSet()
            devices
                .filter { it.protocol == Protocol.DLNA || it.host !in dlnaHosts }
                .distinctBy { "\${it.protocol}:\$it.host:\${it.controlUrl ?: it.port}" }
                .sortedWith(
                    compareBy<Device> { if (it.protocol == Protocol.DLNA) 0 else 1 }
                        .thenBy { it.friendlyName.lowercase(Locale.US) }
                        .thenBy { it.protocol.label }
                )''',
)

replace_once(
    "app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt",
    '''        // A renderer may legitimately reject Stop while idle. Never let that prevent SetURI/Play.
        runCatching { soap(controlUrl, serviceType, "Stop", "<InstanceID>0</InstanceID>") }

        val mimeCandidates = mimeCandidates(mediaUrl, isLive)
        var lastError: Throwable? = null
        for (mime in mimeCandidates) {
            try {
                val protocolInfo = "http-get:*:$mime:*"
                val didl = buildDidl(title, mediaUrl, mime, protocolInfo, isLive)
                val setUriBody = "<InstanceID>0</InstanceID>" +
                    "<CurrentURI>\${xmlEscape(mediaUrl)}</CurrentURI>" +
                    "<CurrentURIMetaData>\${xmlEscape(didl)}</CurrentURIMetaData>"
                soap(controlUrl, serviceType, "SetAVTransportURI", setUriBody)
                Thread.sleep(PLAY_DELAY_MS)
                soap(
                    controlUrl,
                    serviceType,
                    "Play",
                    "<InstanceID>0</InstanceID><Speed>1</Speed>"
                )
                return
            } catch (t: Throwable) {
                lastError = t
            }
        }
        throw lastError ?: IllegalStateException("DLNA PLAY FAILED")''',
    '''        // Keep Google Cast separate. This custom route is only for DLNA renderers.
        runCatching { soap(controlUrl, serviceType, "Stop", "<InstanceID>0</InstanceID>") }

        // LG webOS/UQ-series renderers can behave differently with HLS and MPEG-TS.
        // Try the active HLS URL first, then its Xtream-style .ts equivalent.
        val urlCandidates = buildList {
            add(mediaUrl)
            GencMediaPlayer.swapLiveFormat(mediaUrl, "ts")?.takeIf { it != mediaUrl }?.let(::add)
        }.distinct()

        var lastError: Throwable? = null
        for (loadUrl in urlCandidates) {
            for (mime in mimeCandidates(loadUrl, isLive)) {
                try {
                    val protocolInfo = "http-get:*:$mime:*"
                    val didl = buildDidl(title, loadUrl, mime, protocolInfo, isLive)
                    soap(
                        controlUrl, serviceType, "SetAVTransportURI",
                        "<InstanceID>0</InstanceID><CurrentURI>\${xmlEscape(loadUrl)}</CurrentURI>" +
                            "<CurrentURIMetaData>\${xmlEscape(didl)}</CurrentURIMetaData>"
                    )
                    Thread.sleep(900L)
                    soap(controlUrl, serviceType, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
                    activeDlnaDevice = device
                    return
                } catch (t: Throwable) {
                    lastError = t
                }
            }
        }
        throw lastError ?: IllegalStateException("DLNA PLAY FAILED")''',
)

replace_once(
    "app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt",
    '''    @Volatile
    private var activeWebOsCast: ActiveWebOsCast? = null

    fun getActiveCastDevice(): Device? = activeWebOsCast?.device

    suspend fun disconnectActiveCast(): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val active = activeWebOsCast ?: return@runCatching
            activeWebOsCast = null''',
    '''    @Volatile
    private var activeWebOsCast: ActiveWebOsCast? = null

    @Volatile
    private var activeDlnaDevice: Device? = null

    fun getActiveCastDevice(): Device? = activeDlnaDevice ?: activeWebOsCast?.device

    suspend fun disconnectActiveCast(): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val dlna = activeDlnaDevice
            if (dlna != null) {
                activeDlnaDevice = null
                val c = dlna.controlUrl
                val st = dlna.serviceType
                if (c != null && st != null) runCatching {
                    soap(c, st, "Stop", "<InstanceID>0</InstanceID>")
                }
            }

            val active = activeWebOsCast ?: return@runCatching
            activeWebOsCast = null''',
)

(ROOT / "SE_BUILD_MANIFEST.txt").write_text(
    """SE IPTV PLAYER — SEAndroid v100.0.139
Base source: SE-Android-v100.0.138-source.zip
DLNA Cast: preferred DLNA/UPnP route for LG TVs; HLS URL is tried first with automatic Xtream .ts fallback when available.
Google Cast: retained through the existing Media3 CastPlayer / MediaRouteButton flow.
Build target: V100.0.139.
""",
    encoding="utf-8",
)

(ROOT / "CAST_DLNA_LG_V100_0_139_AUDIT.md").write_text(
    """# DLNA / UPnP Cast — V100.0.139

- Based on V100.0.138.
- Google Cast remains enabled through Media3 and is not removed.
- DLNA is preferred for an LG host when both DLNA and webOS SSAP are advertised, avoiding the webOS pairing prompt.
- DLNA playback tries the active URL first and automatically retries an Xtream-style .ts URL when available, with multiple DLNA MIME candidates.
- A 900 ms SetAVTransportURI-to-Play delay is used for LG renderer startup compatibility.
- Version: 100.0.139 / versionCode 1000139.
""",
    encoding="utf-8",
)

checks = [
    ("app/build.gradle", "versionCode 1000139"),
    ("app/build.gradle", 'versionName "100.0.139"'),
    ("settings.gradle", "SEAndroid_v100.0.139"),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "activeDlnaDevice"),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "GencMediaPlayer.swapLiveFormat"),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "Thread.sleep(900L)"),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "Protocol.DLNA"),
    ("app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt", "NO DLNA/UPnP TV FOUND."),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "ssap://webapp/connectToApp"),
    ("app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt", "connectsdk.mediaCommand"),
]
for path, needle in checks:
    if needle not in (ROOT / path).read_text(encoding="utf-8"):
        raise SystemExit(f"verification failed: {path}: {needle}")

print("V139 DLNA patch applied and verified.")
