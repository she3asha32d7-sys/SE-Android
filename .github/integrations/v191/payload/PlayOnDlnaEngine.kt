/*
 * PlayOnDlna-style DLNA sender integration for SE IPTV Player.
 *
 * Architecture adapted with attribution to PlayOnDlna by Lukas Scheerer:
 * https://github.com/scovillo/playondlna (GPL-3.0-only), inspected main tree commit
 * 8bc3b29b6ebbb1b0e63f5d23ca9077d1afd528e6.
 *
 * This is not a copy of the standalone PlayOnDlna application. It preserves an independent
 * discovery + AVTransport sender path while using SE's own HTTP media relay for IPTV and local files.
 * See THIRD_PARTY_NOTICES.md and THIRD_PARTY_LICENSES/PLAYONDlNA-GPL-3.0.txt.
 */
package com.orbital.iptv.utils.originaldlna.playondlna

import android.content.Context
import android.content.Context.CONNECTIVITY_SERVICE
import android.content.Context.WIFI_SERVICE
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.util.Log
import com.orbital.iptv.utils.originaldlna.DlnaReceiver
import com.orbital.iptv.utils.originaldlna.dlnaXmlEscape
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.w3c.dom.Element
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.TimeUnit
import javax.xml.XMLConstants
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Independent PlayOnDlna-inspired SSDP + UPnP AVTransport sender.
 * Uses the same useful SSDP target classes and the SetAVTransportURI -> Play sequence. Media
 * preparation and serving remain SE-owned because IPTV live sources cannot be pre-downloaded.
 */
object PlayOnDlnaEngine {
    private const val TAG = "SE-PlayOnDlna"
    private const val SSDP_GROUP = "239.255.255.250"
    private const val SSDP_PORT = 1900
    private const val AV_TRANSPORT_V1 = "urn:schemas-upnp-org:service:AVTransport:1"
    private const val DISCOVERY_WINDOW_MS = 6500L
    private const val RECEIVE_TIMEOUT_MS = 250
    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val app = context.applicationContext
        val wifi = app.getSystemService(WIFI_SERVICE) as? WifiManager
        val connectivity = app.getSystemService(CONNECTIVITY_SERVICE) as? ConnectivityManager
        val wifiNetwork: Network? = connectivity?.activeNetwork?.takeIf { network ->
            val caps = connectivity.getNetworkCapabilities(network)
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true &&
                caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
        }
        val multicastLock = runCatching { wifi?.createMulticastLock("PlayOnDlna:SE-SSDP") }.getOrNull()
        var socket: DatagramSocket? = null
        val locations = linkedMapOf<String, String>()
        try {
            multicastLock?.setReferenceCounted(false)
            if (multicastLock != null && !multicastLock.isHeld) multicastLock.acquire()
            socket = DatagramSocket(0).apply {
                soTimeout = RECEIVE_TIMEOUT_MS
                runCatching { wifiNetwork?.bindSocket(this) }
                    .onFailure { Log.w(TAG, "Could not bind SSDP socket to active Wi-Fi", it) }
            }
            val multicast = InetAddress.getByName(SSDP_GROUP)
            val targets = listOf(
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                AV_TRANSPORT_V1,
                "ssdp:all"
            )
            for (target in targets) {
                val bytes = createSearchRequest(target).toByteArray(StandardCharsets.UTF_8)
                val packet = DatagramPacket(bytes, bytes.size, multicast, SSDP_PORT)
                repeat(2) { round ->
                    socket.send(packet)
                    if (round == 0) Thread.sleep(120L)
                }
            }

            val startedAt = System.currentTimeMillis()
            var lastResponseAt = startedAt
            val buffer = ByteArray(8192)
            while (System.currentTimeMillis() - startedAt < DISCOVERY_WINDOW_MS) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val text = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val headers = parseHeaders(text)
                    val location = headers["location"].orEmpty().trim()
                    if (location.startsWith("http://", true) || location.startsWith("https://", true)) {
                        locations.putIfAbsent(location, headers["usn"].orEmpty())
                        lastResponseAt = System.currentTimeMillis()
                    }
                } catch (_: java.net.SocketTimeoutException) {
                    val elapsed = System.currentTimeMillis() - startedAt
                    val quiet = System.currentTimeMillis() - lastResponseAt
                    if (locations.isNotEmpty() && elapsed >= 1800L && quiet >= 900L) break
                }
            }

            val receivers = locations.entries.mapNotNull { (location, usn) ->
                runCatching { readDeviceDescription(location, usn) }
                    .onFailure { Log.w(TAG, "Device-description fetch failed: $location", it) }
                    .getOrNull()
            }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
            Log.i(TAG, "SSDP discovery complete: ${receivers.size} PlayOnDlna-style renderer(s)")
            receivers
        } finally {
            runCatching { socket?.close() }
            runCatching { if (multicastLock?.isHeld == true) multicastLock.release() }
        }
    }

    suspend fun cast(
        receiver: DlnaReceiver,
        mediaUrl: String,
        title: String,
        isLive: Boolean
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                "PlayOnDlna needs a TV-reachable HTTP/HTTPS URL. Local files must use the SE media relay."
            }
            require(receiver.controlUrl.startsWith("http://", true) || receiver.controlUrl.startsWith("https://", true)) {
                "PlayOnDlna found a renderer without a valid AVTransport control URL."
            }
            val mime = mimeFor(mediaUrl, isLive)
            val safeTitle = dlnaXmlEscape(
                title.ifBlank {
                    mediaUrl.substringAfterLast('/').substringBefore('?').ifBlank { "Media" }
                }
            )
            val safeUrl = dlnaXmlEscape(mediaUrl)
            val didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/"><item id="se-playondlna-${System.currentTimeMillis()}" parentID="0" restricted="1"><dc:title>${safeTitle}</dc:title><upnp:class>object.item.videoItem.movie</upnp:class><res protocolInfo="http-get:*:${mime}:*">${safeUrl}</res></item></DIDL-Lite>"""
            // CurrentURIMetaData is XML text within SOAP, so escape the embedded DIDL document.
            val mediaMetadata = dlnaXmlEscape(didl)
            Log.i(TAG, "SetAVTransportURI to ${receiver.name}; mime=$mime; host=${runCatching { URL(mediaUrl).host }.getOrDefault("unknown")}")
            soapAction(
                receiver.controlUrl,
                receiver.serviceType.ifBlank { AV_TRANSPORT_V1 },
                "SetAVTransportURI",
                "<InstanceID>0</InstanceID><CurrentURI>$safeUrl</CurrentURI><CurrentURIMetaData>$mediaMetadata</CurrentURIMetaData>"
            )
            // The upstream transport hand-off assigns a resource, then explicitly starts playback.
            Thread.sleep(250L)
            soapAction(
                receiver.controlUrl,
                receiver.serviceType.ifBlank { AV_TRANSPORT_V1 },
                "Play",
                "<InstanceID>0</InstanceID><Speed>1</Speed>"
            )
            Log.i(TAG, "PlayOnDlna-style AVTransport accepted by ${receiver.name}")
            Unit
        }
    }

    private fun createSearchRequest(target: String): String =
        "M-SEARCH * HTTP/1.1\r\n" +
            "HOST: $SSDP_GROUP:$SSDP_PORT\r\n" +
            "MAN: \"ssdp:discover\"\r\n" +
            "MX: 2\r\n" +
            "ST: $target\r\n\r\n"

    private fun parseHeaders(raw: String): Map<String, String> = raw.lineSequence()
        .drop(1)
        .mapNotNull { line ->
            val colon = line.indexOf(':')
            if (colon <= 0) null else line.substring(0, colon).trim().lowercase(Locale.US) to line.substring(colon + 1).trim()
        }.toMap()

    private fun readDeviceDescription(location: String, usn: String): DlnaReceiver? {
        val request = Request.Builder()
            .url(location)
            .header("User-Agent", "SE-PlayOnDlna/1.0 UPnP/1.0")
            .get()
            .build()
        val xml = http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.d(TAG, "Device description HTTP ${response.code} at $location")
                return null
            }
            response.body?.string() ?: return null
        }
        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
            runCatching { setFeature("http://apache.org/xml/features/disallow-doctype-decl", true) }
            runCatching { setFeature("http://xml.org/sax/features/external-general-entities", false) }
            runCatching { setFeature("http://xml.org/sax/features/external-parameter-entities", false) }
            runCatching { setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "") }
            runCatching { setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "") }
        }
        val document = factory.newDocumentBuilder().parse(xml.byteInputStream(StandardCharsets.UTF_8))
        val root = document.documentElement ?: return null
        val deviceType = firstText(root, "deviceType").orEmpty()
        val friendlyName = firstText(root, "friendlyName").orEmpty()
        val udn = firstText(root, "UDN").orEmpty().ifBlank { usn.ifBlank { location } }
        val baseText = firstText(root, "URLBase").orEmpty().ifBlank { location }
        val baseUrl = URL(baseText)

        var avControlUrlV1: String? = null
        var avControlUrlOther: String? = null
        var avTypeV1 = AV_TRANSPORT_V1
        var avTypeOther = AV_TRANSPORT_V1
        val services = root.getElementsByTagNameNS("*", "service")
        for (index in 0 until services.length) {
            val service = services.item(index) as? Element ?: continue
            val serviceType = firstText(service, "serviceType").orEmpty()
            val controlPath = firstText(service, "controlURL").orEmpty()
            if (serviceType.isBlank() || controlPath.isBlank()) continue
            when {
                serviceType.equals(AV_TRANSPORT_V1, true) -> {
                    avTypeV1 = serviceType
                    avControlUrlV1 = URL(baseUrl, controlPath).toString()
                }
                serviceType.contains(":AVTransport:", true) -> {
                    avTypeOther = serviceType
                    avControlUrlOther = URL(baseUrl, controlPath).toString()
                }
            }
        }
        val controlUrl = avControlUrlV1 ?: avControlUrlOther ?: return null
        if (deviceType.isNotBlank() && !deviceType.contains("MediaRenderer", true)) {
            Log.d(TAG, "AVTransport exists although root type is not MediaRenderer: $deviceType")
        }
        val host = runCatching { URL(location).host }.getOrDefault(location)
        return DlnaReceiver(
            id = udn.ifBlank { location },
            name = friendlyName.ifBlank { host },
            host = host,
            descriptionUrl = location,
            controlUrl = controlUrl,
            serviceType = if (avControlUrlV1 != null) avTypeV1 else avTypeOther
        )
    }

    private fun firstText(element: Element, name: String): String? {
        val plain = element.getElementsByTagName(name).item(0)
        val node = plain ?: element.getElementsByTagNameNS("*", name).item(0)
        return node?.textContent?.trim()?.takeIf { it.isNotBlank() }
    }

    private fun mimeFor(url: String, live: Boolean): String {
        val path = runCatching { URL(url).path.lowercase(Locale.US) }
            .getOrDefault(url.substringBefore('?').lowercase(Locale.US))
        return when (path.substringAfterLast('.', "")) {
            "m3u8", "m3u" -> "application/vnd.apple.mpegurl"
            "mpd" -> "application/dash+xml"
            "mp4", "m4v" -> "video/mp4"
            "mkv" -> "video/x-matroska"
            "avi" -> "video/x-msvideo"
            "mov" -> "video/quicktime"
            "webm" -> "video/webm"
            "3gp" -> "video/3gpp"
            "ts", "mts", "m2ts", "mpeg", "mpg" -> "video/mp2t"
            "mp3" -> "audio/mpeg"
            "m4a" -> "audio/mp4"
            "aac" -> "audio/aac"
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            else -> if (live) "video/mp2t" else "video/mp4"
        }
    }

    private fun soapAction(controlUrl: String, serviceType: String, action: String, arguments: String) {
        val envelope = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:$action xmlns:u="$serviceType">$arguments</u:$action></s:Body></s:Envelope>"""
        val request = Request.Builder()
            .url(controlUrl)
            .header("User-Agent", "SE-PlayOnDlna/1.0 UPnP/1.0")
            .header("Content-Type", "text/xml; charset=\"utf-8\"")
            .header("SOAPAction", "\"$serviceType#$action\"")
            .header("Accept", "*/*")
            .header("Connection", "close")
            .post(envelope.toRequestBody("text/xml; charset=utf-8".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            val responseText = response.body?.string().orEmpty()
            val code = Regex("<(?:\\w+:)?errorCode[^>]*>\\s*(.*?)\\s*</(?:\\w+:)?errorCode>", RegexOption.IGNORE_CASE)
                .find(responseText)?.groupValues?.getOrNull(1)?.trim()
            val description = Regex("<(?:\\w+:)?errorDescription[^>]*>\\s*(.*?)\\s*</(?:\\w+:)?errorDescription>", RegexOption.IGNORE_CASE)
                .find(responseText)?.groupValues?.getOrNull(1)?.trim()
            if (!response.isSuccessful || responseText.contains(":Fault", true) || !code.isNullOrBlank()) {
                throw IllegalStateException(
                    "$action rejected by renderer: HTTP ${response.code}" +
                        (code?.let { " / UPnP $it" }.orEmpty()) +
                        (description?.let { ": $it" }.orEmpty()) +
                        (if (description.isNullOrBlank() && responseText.isNotBlank()) " / ${responseText.take(280)}" else "")
                )
            }
        }
    }
}
