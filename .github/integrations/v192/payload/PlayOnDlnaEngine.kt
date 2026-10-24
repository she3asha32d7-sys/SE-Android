/*
 * PlayOnDlna-inspired DLNA sender integration for SE IPTV Player.
 * Upstream: https://github.com/scovillo/playondlna (GPL-3.0-only).
 * Independent sender; local PHONE FILES use SE's range-capable HTTP server, while IPTV network
 * URLs are tried directly first with live .ts/.m3u8 alternatives and Samsung-friendly MIME retries.
 * See THIRD_PARTY_NOTICES.md and PLAYONDlNA_CAST_V100_0_192_AUDIT.md.
 */
package com.orbital.iptv.utils.originaldlna.playondlna

import android.content.Context
import android.content.Context.WIFI_SERVICE
import android.net.wifi.WifiManager
import android.util.Log
import com.orbital.iptv.utils.GencMediaPlayer
import com.orbital.iptv.utils.originaldlna.CastLabMediaServer
import com.orbital.iptv.utils.originaldlna.DlnaReceiver
import com.orbital.iptv.utils.originaldlna.dlnaXmlEscape
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.w3c.dom.Element
import java.net.DatagramPacket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.HttpURLConnection
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Locale
import javax.xml.parsers.DocumentBuilderFactory

/** Independent PlayOnDlna-style SSDP + UPnP AVTransport sender. */
object PlayOnDlnaEngine {
    private const val TAG = "SE-PlayOnDlna"
    private const val SSDP_GROUP = "239.255.255.250"
    private const val SSDP_PORT = 1900
    private const val AV_TRANSPORT_V1 = "urn:schemas-upnp-org:service:AVTransport:1"
    private const val USER_AGENT = "DLNA/1.0 UPnP/1.0"
    private const val DISCOVERY_WINDOW_MS = 5500L
    private const val RECEIVE_TIMEOUT_MS = 400
    private const val SOAP_TIMEOUT_MS = 9000

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        discoverBlocking(context.applicationContext)
    }

    private fun discoverBlocking(context: Context): List<DlnaReceiver> {
        val wifi = context.getSystemService(WIFI_SERVICE) as? WifiManager
        val multicastLock = runCatching {
            wifi?.createMulticastLock("SE_PlayOnDlna_SSDP")?.apply {
                setReferenceCounted(false)
                acquire()
            }
        }.getOrNull()
        try {
            val locations = linkedMapOf<String, String>()
            MulticastSocket(null).use { socket ->
                socket.reuseAddress = true
                socket.bind(InetSocketAddress(0))
                socket.soTimeout = RECEIVE_TIMEOUT_MS
                chooseWifiInterface()?.let { iface ->
                    runCatching { socket.networkInterface = iface }
                        .onFailure { Log.w(TAG, "Could not select Wi-Fi interface ${iface.name}", it) }
                }
                runCatching { socket.timeToLive = 2 }
                val group = InetAddress.getByName(SSDP_GROUP)
                val targets = listOf(
                    "upnp:rootdevice",
                    "urn:schemas-upnp-org:device:MediaRenderer:1",
                    AV_TRANSPORT_V1,
                    "ssdp:all"
                )
                for (target in targets) {
                    val bytes = buildSearch(target).toByteArray(StandardCharsets.US_ASCII)
                    repeat(2) { attempt ->
                        runCatching { socket.send(DatagramPacket(bytes, bytes.size, group, SSDP_PORT)) }
                            .onFailure { Log.w(TAG, "SSDP search send failed for $target", it) }
                        if (attempt == 0) Thread.sleep(80L)
                    }
                }
                val deadline = System.currentTimeMillis() + DISCOVERY_WINDOW_MS
                while (System.currentTimeMillis() < deadline) {
                    try {
                        val buffer = ByteArray(16 * 1024)
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        val raw = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                        val headers = parseHeaders(raw)
                        val location = headers["location"].orEmpty().trim()
                        if (location.startsWith("http://", true) || location.startsWith("https://", true)) {
                            locations.putIfAbsent(location, headers["usn"].orEmpty())
                            Log.d(TAG, "SSDP response: ${headers["st"].orEmpty()} at $location")
                        }
                    } catch (_: SocketTimeoutException) {
                        // Keep the full MX=5 window; some Samsung TVs answer late.
                    }
                }
            }
            val receivers = locations.mapNotNull { (location, usn) ->
                runCatching { readDeviceDescription(location, usn) }
                    .onFailure { Log.w(TAG, "Could not read DLNA description at $location", it) }
                    .getOrNull()
            }.filter { it.controlUrl.isNotBlank() }
                .distinctBy { it.id }
                .sortedBy { it.name.lowercase(Locale.US) }
            Log.i(TAG, "Discovery completed: ${receivers.size} renderer(s)")
            return receivers
        } finally {
            runCatching { if (multicastLock?.isHeld == true) multicastLock.release() }
        }
    }

    suspend fun cast(receiver: DlnaReceiver, mediaUrl: String, title: String, isLive: Boolean): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "PlayOnDlna requires an HTTP/HTTPS URL reachable by the TV. PHONE FILES must use the local media server."
                }
                require(receiver.controlUrl.startsWith("http://", true) || receiver.controlUrl.startsWith("https://", true)) {
                    "The selected renderer has no usable AVTransport control URL."
                }
                val localMedia = CastLabMediaServer.isServing(mediaUrl)
                if (localMedia) CastLabMediaServer.resetReceiverProbe()
                // Best-effort Stop; a TV with no active session may return UPnP 701.
                runCatching { soapAction(receiver.controlUrl, receiver.serviceType, "Stop", "<InstanceID>0</InstanceID>") }
                    .onFailure { Log.d(TAG, "Stop-before-play ignored: ${it.message}") }

                val urls = buildList {
                    add(mediaUrl)
                    if (isLive) {
                        GencMediaPlayer.swapLiveFormat(mediaUrl, "ts")?.takeIf { it != mediaUrl }?.let(::add)
                        GencMediaPlayer.swapLiveFormat(mediaUrl, "m3u8")?.takeIf { it != mediaUrl }?.let(::add)
                    }
                }.distinct()
                var lastFailure: Throwable? = null
                var selectedMime = ""
                var success = false
                for (candidateUrl in urls) {
                    for (mime in mimeCandidates(candidateUrl, isLive)) {
                        try {
                            Log.i(TAG, "Try TV=${receiver.name}, host=${runCatching { URL(candidateUrl).host }.getOrDefault("unknown")}, mime=$mime")
                            val metadata = buildDidl(title, candidateUrl, mime)
                            val args = "<InstanceID>0</InstanceID>" +
                                "<CurrentURI>${dlnaXmlEscape(candidateUrl)}</CurrentURI>" +
                                "<CurrentURIMetaData>${dlnaXmlEscape(metadata)}</CurrentURIMetaData>"
                            soapAction(receiver.controlUrl, receiver.serviceType, "SetAVTransportURI", args)
                            Thread.sleep(700L)
                            soapAction(receiver.controlUrl, receiver.serviceType, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")

                            val state = readTransportState(receiver)
                            if (state != null && state !in setOf("PLAYING", "TRANSITIONING")) {
                                throw IllegalStateException("TV transport state after Play was $state")
                            }
                            if (localMedia && !CastLabMediaServer.awaitReceiverBytes(2200L, 1024L)) {
                                val probe = CastLabMediaServer.receiverProbe()
                                throw IllegalStateException(
                                    "TV did not fetch PHONE FILE bytes: host=${probe.host.ifBlank { "NO REQUEST RECEIVED" }}; " +
                                        "HTTP=${probe.status}; bytes=${probe.bytesServed}; range=${probe.range}; " +
                                        "serverError=${probe.error.ifBlank { "none" }}"
                                )
                            }
                            val probe = if (localMedia) CastLabMediaServer.receiverProbe() else null
                            if (probe != null && probe.status >= 400) {
                                throw IllegalStateException("TV media request returned HTTP ${probe.status}: ${probe.error}")
                            }
                            selectedMime = mime
                            success = true
                            Log.i(TAG, "Candidate accepted: state=${state ?: "unknown"}, mime=$mime")
                            break
                        } catch (failure: Throwable) {
                            lastFailure = failure
                            Log.w(TAG, "Candidate failed (TV=${receiver.name}, MIME=$mime): ${failure.message}")
                            runCatching { soapAction(receiver.controlUrl, receiver.serviceType, "Stop", "<InstanceID>0</InstanceID>") }
                        }
                    }
                    if (success) break
                }
                if (!success) {
                    val probe = if (localMedia) CastLabMediaServer.receiverProbe() else null
                    throw IllegalStateException(
                        "All PlayOnDlna-compatible attempts failed on ${receiver.name}. " +
                            "Tried ${urls.size} URL variant(s); last error: ${lastFailure?.message ?: "no renderer response"}" +
                            (probe?.let {
                                "; TV HTTP=${it.status}; host=${it.host.ifBlank { "NO REQUEST RECEIVED" }}; " +
                                    "bytes=${it.bytesServed}; range=${it.range}; serverError=${it.error.ifBlank { "none" }}"
                            }.orEmpty()),
                        lastFailure
                    )
                }
                Log.i(TAG, "Playback commands accepted by ${receiver.name}; mime=$selectedMime")
                Unit
            }
        }

    private fun readTransportState(receiver: DlnaReceiver): String? {
        var lastState: String? = null
        repeat(3) { attempt ->
            val state = runCatching {
                val response = soapAction(
                    receiver.controlUrl, receiver.serviceType, "GetTransportInfo", "<InstanceID>0</InstanceID>"
                )
                Regex("<(?:\\w+:)?CurrentTransportState[^>]*>\\s*(.*?)\\s*</(?:\\w+:)?CurrentTransportState>", RegexOption.IGNORE_CASE)
                    .find(response)?.groupValues?.getOrNull(1)?.trim()?.uppercase(Locale.US)
            }.onFailure { Log.d(TAG, "GetTransportInfo unavailable for ${receiver.name}: ${it.message}") }.getOrNull()
                ?: return null
            lastState = state
            if (state == "PLAYING" || state == "TRANSITIONING") return state
            if (attempt < 2) Thread.sleep(350L)
        }
        return lastState
    }

    private fun chooseWifiInterface(): NetworkInterface? = runCatching {
        NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
            .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
            .sortedWith(compareBy<NetworkInterface> {
                val name = it.name.lowercase(Locale.US)
                when {
                    name.contains("wlan") || name.contains("wifi") -> 0
                    name.contains("eth") -> 1
                    else -> 2
                }
            })
            .firstOrNull { iface ->
                iface.inetAddresses.toList().filterIsInstance<java.net.Inet4Address>()
                    .any { !it.isLoopbackAddress && !it.isLinkLocalAddress }
            }
    }.getOrNull()

    private fun buildSearch(target: String): String =
        "M-SEARCH * HTTP/1.1\r\nHOST: $SSDP_GROUP:$SSDP_PORT\r\nMAN: \"ssdp:discover\"\r\nMX: 5\r\n" +
            "ST: $target\r\nUSER-AGENT: $USER_AGENT\r\n\r\n"

    private fun parseHeaders(raw: String): Map<String, String> = raw.split("\r\n", "\n").drop(1).mapNotNull { line ->
        val colon = line.indexOf(':')
        if (colon <= 0) null else line.substring(0, colon).trim().lowercase(Locale.US) to line.substring(colon + 1).trim()
    }.toMap()

    private fun readDeviceDescription(location: String, usn: String): DlnaReceiver? {
        val connection = (URL(location).openConnection() as HttpURLConnection).apply {
            connectTimeout = SOAP_TIMEOUT_MS
            readTimeout = SOAP_TIMEOUT_MS
            requestMethod = "GET"
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "text/xml, application/xml, */*")
            setRequestProperty("Connection", "close")
        }
        val xml = try {
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            require(status in 200..299) { "Device description HTTP $status at $location" }
            requireNotNull(stream) { "Empty device description at $location" }.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
            runCatching { setFeature("http://apache.org/xml/features/disallow-doctype-decl", true) }
            runCatching { setFeature("http://xml.org/sax/features/external-general-entities", false) }
            runCatching { setFeature("http://xml.org/sax/features/external-parameter-entities", false) }
        }
        val root = factory.newDocumentBuilder().parse(xml.byteInputStream(StandardCharsets.UTF_8)).documentElement ?: return null
        val deviceType = firstText(root, "deviceType").orEmpty()
        val friendlyName = firstText(root, "friendlyName").orEmpty()
        val udn = firstText(root, "UDN").orEmpty().ifBlank { usn.ifBlank { location } }
        val base = firstText(root, "URLBase").orEmpty().ifBlank { location }
        var v1Control: String? = null
        var v1Service = AV_TRANSPORT_V1
        var otherControl: String? = null
        var otherService = AV_TRANSPORT_V1
        val services = root.getElementsByTagNameNS("*", "service")
        for (index in 0 until services.length) {
            val service = services.item(index) as? Element ?: continue
            val type = firstText(service, "serviceType").orEmpty()
            val controlPath = firstText(service, "controlURL").orEmpty()
            if (type.isBlank() || controlPath.isBlank()) continue
            when {
                type.equals(AV_TRANSPORT_V1, true) -> {
                    v1Service = type
                    v1Control = URL(URL(base), controlPath).toString()
                }
                type.contains(":AVTransport:", true) -> {
                    otherService = type
                    otherControl = URL(URL(base), controlPath).toString()
                }
            }
        }
        val control = v1Control ?: otherControl ?: return null
        if (deviceType.isNotBlank() && !deviceType.contains("MediaRenderer", true)) return null
        val host = runCatching { URL(location).host }.getOrDefault(location)
        return DlnaReceiver(
            id = udn.ifBlank { location },
            name = friendlyName.ifBlank { "DLNA TV ($host)" },
            host = host,
            descriptionUrl = location,
            controlUrl = control,
            serviceType = if (v1Control != null) v1Service else otherService
        )
    }

    private fun firstText(element: Element, name: String): String? {
        val node = element.getElementsByTagName(name).item(0) ?: element.getElementsByTagNameNS("*", name).item(0)
        return node?.textContent?.trim()?.takeIf { it.isNotBlank() }
    }

    private fun mimeCandidates(url: String, live: Boolean): List<String> {
        val path = runCatching { URL(url).path.lowercase(Locale.US) }
            .getOrDefault(url.substringBefore('?').lowercase(Locale.US))
        return when {
            path.endsWith(".ts") || path.endsWith(".mpeg") || path.endsWith(".mpg") -> listOf("video/mp2t", "video/mpeg")
            path.endsWith(".m3u8") || path.endsWith(".m3u") -> listOf("application/vnd.apple.mpegurl", "application/x-mpegurl", "application/x-mpegURL")
            path.endsWith(".mpd") -> listOf("application/dash+xml", "video/mp4")
            path.endsWith(".mkv") -> listOf("video/x-matroska", "video/mkv")
            path.endsWith(".avi") -> listOf("video/x-msvideo", "video/avi")
            path.endsWith(".mov") -> listOf("video/quicktime")
            path.endsWith(".webm") -> listOf("video/webm", "application/webm")
            path.endsWith(".mp4") || path.endsWith(".m4v") -> listOf("video/mp4", "application/mp4")
            path.endsWith(".3gp") -> listOf("video/3gpp")
            path.endsWith(".mp3") -> listOf("audio/mpeg")
            path.endsWith(".m4a") -> listOf("audio/mp4")
            live -> listOf("video/mp2t", "video/mpeg", "application/vnd.apple.mpegurl", "application/x-mpegurl")
            else -> listOf("video/mp4", "application/mp4")
        }.distinct()
    }

    private fun buildDidl(title: String, url: String, mime: String): String {
        val safeTitle = dlnaXmlEscape(title.ifBlank { "SE IPTV PLAYER" })
        val safeUrl = dlnaXmlEscape(url)
        return "<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" " +
            "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" " +
            "xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\">" +
            "<item id=\"0\" parentID=\"-1\" restricted=\"1\"><dc:title>$safeTitle</dc:title>" +
            "<upnp:class>object.item.videoItem</upnp:class>" +
            "<res protocolInfo=\"http-get:*:${dlnaXmlEscape(mime)}:*\">$safeUrl</res></item></DIDL-Lite>"
    }

    private fun soapAction(controlUrl: String, serviceType: String, action: String, arguments: String): String {
        val actualServiceType = serviceType.ifBlank { AV_TRANSPORT_V1 }
        val envelope = "<?xml version=\"1.0\" encoding=\"utf-8\"?>" +
            "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\">" +
            "<s:Body><u:$action xmlns:u=\"$actualServiceType\">$arguments</u:$action></s:Body></s:Envelope>"
        val bytes = envelope.toByteArray(StandardCharsets.UTF_8)
        val connection = (URL(controlUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = SOAP_TIMEOUT_MS
            readTimeout = SOAP_TIMEOUT_MS
            requestMethod = "POST"
            doOutput = true
            setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
            setRequestProperty("SOAPAction", "\"$actualServiceType#$action\"")
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "*/*")
            setRequestProperty("Connection", "close")
            setFixedLengthStreamingMode(bytes.size)
        }
        try {
            connection.outputStream.use { it.write(bytes) }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val responseText = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }.orEmpty()
            val code = Regex("<(?:\\w+:)?errorCode>\\s*(.*?)\\s*</(?:\\w+:)?errorCode>", RegexOption.IGNORE_CASE)
                .find(responseText)?.groupValues?.getOrNull(1)?.trim()
            val description = Regex("<(?:\\w+:)?errorDescription>\\s*(.*?)\\s*</(?:\\w+:)?errorDescription>", RegexOption.IGNORE_CASE)
                .find(responseText)?.groupValues?.getOrNull(1)?.trim()
            if (status !in 200..299 || responseText.contains(":Fault", true) || !code.isNullOrBlank()) {
                throw IllegalStateException(
                    "$action rejected: HTTP $status" +
                        (code?.let { " / UPnP $it" }.orEmpty()) +
                        (description?.let { ": $it" }.orEmpty()) +
                        (if (description.isNullOrBlank() && responseText.isNotBlank()) " / ${responseText.take(240)}" else "")
                )
            }
            return responseText
        } finally {
            connection.disconnect()
        }
    }
}