package com.orbital.iptv.utils.originaldlna

/**
 * Small UI-facing device record only. The four engines below retain independent discovery and
 * transport implementations; this type does not provide a shared DLNA engine.
 */
data class DlnaReceiver(
    val id: String,
    val name: String,
    val host: String,
    val descriptionUrl: String,
    val controlUrl: String,
    val serviceType: String = "urn:schemas-upnp-org:service:AVTransport:1",
    val renderingControlUrl: String? = null
)

internal fun dlnaXmlEscape(value: String): String = value
    .replace("&", "&amp;")
    .replace("<", "&lt;")
    .replace(">", "&gt;")
    .replace("\"", "&quot;")
    .replace("'", "&apos;")

internal fun dlnaMimeFor(url: String, live: Boolean): String {
    val lower = url.substringBefore('?').lowercase()
    return when {
        lower.endsWith(".m3u8") -> "application/vnd.apple.mpegurl"
        lower.endsWith(".mpd") -> "application/dash+xml"
        lower.endsWith(".mp4") -> "video/mp4"
        lower.endsWith(".mkv") -> "video/x-matroska"
        lower.endsWith(".ts") || live -> "video/mpeg"
        lower.endsWith(".mp3") -> "audio/mpeg"
        else -> "video/mp4"
    }
}
