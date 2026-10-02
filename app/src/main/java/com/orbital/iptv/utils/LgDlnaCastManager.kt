package com.orbital.iptv.utils

import android.content.Context
import android.net.wifi.WifiManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.net.DatagramPacket
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetAddress
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.LinkedHashMap

object LgDlnaCastManager {

    data class Device(
        val friendlyName: String,
        val location: String,
        val controlUrl: String,
        val serviceType: String
    )

    private const val SSDP_HOST = "239.255.255.250"
    private const val SSDP_PORT = 1900
    private const val DISCOVERY_MS = 4500L
    private const val SOCKET_TIMEOUT_MS = 350
    private const val HTTP_TIMEOUT_MS = 8000
    private const val PLAY_DELAY_MS = 1500L
    private const val USER_AGENT = "SE IPTV PLAYER/1.0 UPnP-DLNA"

    private val SEARCH_TARGETS = listOf(
        "urn:schemas-upnp-org:service:AVTransport:1",
        "urn:schemas-upnp-org:device:MediaRenderer:1",
        "upnp:rootdevice",
        "ssdp:all"
    )

    suspend fun discover(context: Context): List<Device> = withContext(Dispatchers.IO) {
        val wifi = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as? WifiManager

        val multicastLock = wifi?.createMulticastLock("SE_IPTV_DLNA_DISCOVERY")?.apply {
            setReferenceCounted(false)
            acquire()
        }

        try {
            val locations = LinkedHashMap<String, String>()

            MulticastSocket().use { socket ->
                socket.reuseAddress = true
                socket.broadcast = true
                socket.soTimeout = SOCKET_TIMEOUT_MS
                findMulticastInterface()?.let { socket.networkInterface = it }

                val destination = InetAddress.getByName(SSDP_HOST)

                for (target in SEARCH_TARGETS) {
                    val bytes = buildSearchPacket(target)
                        .toByteArray(StandardCharsets.US_ASCII)

                    repeat(2) {
                        socket.send(
                            DatagramPacket(
                                bytes,
                                bytes.size,
                                destination,
                                SSDP_PORT
                            )
                        )
                    }
                }

                val deadline = System.currentTimeMillis() + DISCOVERY_MS
                val buffer = ByteArray(16 * 1024)

                while (System.currentTimeMillis() < deadline) {
                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)

                        val response = String(
                            packet.data,
                            packet.offset,
                            packet.length,
                            StandardCharsets.UTF_8
                        )

                        val headers = parseHeaders(response)
                        val location = headers["location"].orEmpty()

                        if (location.isNotBlank()) {
                            locations[location] = headers["server"].orEmpty()
                        }
                    } catch (_: java.net.SocketTimeoutException) {
                    }
                }
            }

            locations.keys.mapNotNull { location ->
                runCatching { readRenderer(location) }.getOrNull()
            }
                .distinctBy { it.controlUrl.lowercase() }
                .sortedBy { it.friendlyName.lowercase() }
        } finally {
            runCatching { multicastLock?.release() }
        }
    }

    suspend fun cast(
        device: Device,
        mediaUrl: String,
        title: String,
        isLive: Boolean
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            require(
                mediaUrl.startsWith("http://", true) ||
                    mediaUrl.startsWith("https://", true)
            ) {
                "LG DLNA needs a network-reachable HTTP/HTTPS media URL"
            }

            runCatching {
                soap(
                    device.controlUrl,
                    device.serviceType,
                    "Stop",
                    "<InstanceID>0</InstanceID>"
                )
            }

            val mime = guessMime(mediaUrl)
            val protocolInfo = "http-get:*:$mime:*"
            val didl = buildDidl(title, mediaUrl, protocolInfo, isLive)

            try {
                soap(
                    device.controlUrl,
                    device.serviceType,
                    "SetAVTransportURI",
                    "<InstanceID>0</InstanceID>" +
                        "<CurrentURI>" + xmlEscape(mediaUrl) + "</CurrentURI>" +
                        "<CurrentURIMetaData>" + xmlEscape(didl) +
                        "</CurrentURIMetaData>"
                )
            } catch (_: Exception) {
                soap(
                    device.controlUrl,
                    device.serviceType,
                    "SetAVTransportURI",
                    "<InstanceID>0</InstanceID>" +
                        "<CurrentURI>" + xmlEscape(mediaUrl) + "</CurrentURI>" +
                        "<CurrentURIMetaData></CurrentURIMetaData>"
                )
            }

            Thread.sleep(PLAY_DELAY_MS)

            soap(
                device.controlUrl,
                device.serviceType,
                "Play",
                "<InstanceID>0</InstanceID><Speed>1</Speed>"
            )
        }
    }

    private fun buildSearchPacket(target: String): String =
        "M-SEARCH * HTTP/1.1\r\n" +
            "HOST: $SSDP_HOST:$SSDP_PORT\r\n" +
            "MAN: \"ssdp:discover\"\r\n" +
            "MX: 2\r\n" +
            "ST: $target\r\n" +
            "USER-AGENT: $USER_AGENT\r\n\r\n"

    private fun parseHeaders(response: String): Map<String, String> =
        response.split("\r\n", "\n")
            .drop(1)
            .mapNotNull { line ->
                val index = line.indexOf(':')
                if (index <= 0) null
                else line.substring(0, index).trim().lowercase() to
                    line.substring(index + 1).trim()
            }
            .toMap()

    private fun readRenderer(location: String): Device? {
        val xml = httpGet(location)
        val parser = XmlPullParserFactory.newInstance().newPullParser()
        parser.setInput(xml.reader())

        var currentTag = ""
        var friendlyName = "LG webOS TV"
        var manufacturer = ""
        var modelName = ""
        var modelDescription = ""
        var urlBase = location

        var inService = false
        var serviceType = ""
        var controlUrl = ""
        var selectedServiceType = ""
        var selectedControlUrl = ""

        while (parser.next() != XmlPullParser.END_DOCUMENT) {
            when (parser.eventType) {
                XmlPullParser.START_TAG -> {
                    currentTag = parser.name
                    if (parser.name.equals("service", true)) {
                        inService = true
                        serviceType = ""
                        controlUrl = ""
                    }
                }

                XmlPullParser.TEXT -> {
                    val value = parser.text?.trim().orEmpty()
                    if (value.isBlank()) continue

                    when {
                        !inService && currentTag.equals("friendlyName", true) ->
                            friendlyName = value

                        !inService && currentTag.equals("manufacturer", true) ->
                            manufacturer = value

                        !inService && currentTag.equals("modelName", true) ->
                            modelName = value

                        !inService && currentTag.equals("modelDescription", true) ->
                            modelDescription = value

                        !inService && currentTag.equals("URLBase", true) ->
                            urlBase = value

                        inService && currentTag.equals("serviceType", true) ->
                            serviceType = value

                        inService && currentTag.equals("controlURL", true) ->
                            controlUrl = value
                    }
                }

                XmlPullParser.END_TAG -> {
                    if (parser.name.equals("service", true)) {
                        if (
                            serviceType.contains("AVTransport", true) &&
                            controlUrl.isNotBlank() &&
                            selectedControlUrl.isBlank()
                        ) {
                            selectedServiceType = serviceType
                            selectedControlUrl = controlUrl
                        }

                        inService = false
                    }
                }
            }
        }

        if (selectedControlUrl.isBlank() || selectedServiceType.isBlank()) {
            return null
        }

        val looksLg =
            manufacturer.contains("LG", true) ||
                friendlyName.contains("LG", true) ||
                friendlyName.contains("webOS", true) ||
                modelName.contains("webOS", true) ||
                modelDescription.contains("webOS", true) ||
                modelDescription.contains("LG", true)

        if (!looksLg) return null

        val base = runCatching { URL(urlBase) }.getOrElse { URL(location) }
        val resolvedControlUrl = URL(base, selectedControlUrl).toString()

        return Device(
            friendlyName = friendlyName,
            location = location,
            controlUrl = resolvedControlUrl,
            serviceType = selectedServiceType
        )
    }

    private fun findMulticastInterface(): NetworkInterface? {
        val interfaces = NetworkInterface.getNetworkInterfaces() ?: return null

        while (interfaces.hasMoreElements()) {
            val iface = interfaces.nextElement()

            if (!runCatching { iface.isUp }.getOrDefault(false)) continue
            if (runCatching { iface.isLoopback }.getOrDefault(true)) continue
            if (!runCatching { iface.supportsMulticast() }.getOrDefault(false)) continue

            val hasIpv4 = iface.inetAddresses.toList().any {
                it is Inet4Address &&
                    !it.isLoopbackAddress &&
                    !it.isLinkLocalAddress
            }

            if (hasIpv4) return iface
        }

        return null
    }

    private fun httpGet(url: String): String {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = HTTP_TIMEOUT_MS
            readTimeout = HTTP_TIMEOUT_MS
            requestMethod = "GET"
            setRequestProperty("User-Agent", USER_AGENT)
        }

        return try {
            connection.inputStream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun soap(
        controlUrl: String,
        serviceType: String,
        action: String,
        body: String
    ) {
        val envelope = """
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
                s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
              <s:Body>
                <u:$action xmlns:u="$serviceType">$body</u:$action>
              </s:Body>
            </s:Envelope>
        """.trimIndent()

        val bytes = envelope.toByteArray(StandardCharsets.UTF_8)

        val connection =
            (URL(controlUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = HTTP_TIMEOUT_MS
                readTimeout = HTTP_TIMEOUT_MS
                requestMethod = "POST"
                doOutput = true
                setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
                setRequestProperty("SOAPAction", "\"$serviceType#$action\"")
                setRequestProperty("User-Agent", USER_AGENT)
                setFixedLengthStreamingMode(bytes.size)
            }

        try {
            connection.outputStream.use { it.write(bytes) }

            val code = connection.responseCode
            val stream =
                if (code in 200..299) connection.inputStream
                else connection.errorStream

            val response =
                stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }
                    .orEmpty()

            if (code !in 200..299) {
                throw IllegalStateException(
                    "DLNA $action failed ($code): " + response.take(500)
                )
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun buildDidl(
        title: String,
        url: String,
        protocolInfo: String,
        isLive: Boolean
    ): String {
        val safeTitle = title.ifBlank { "SE IPTV PLAYER" }
        val upnpClass =
            if (isLive) "object.item.videoItem"
            else "object.item.videoItem.movie"

        return """
            <DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
              <item id="0" parentID="-1" restricted="1">
                <dc:title>${xmlEscape(safeTitle)}</dc:title>
                <upnp:class>$upnpClass</upnp:class>
                <res protocolInfo="${xmlEscape(protocolInfo)}">${xmlEscape(url)}</res>
              </item>
            </DIDL-Lite>
        """.trimIndent()
    }

    private fun guessMime(url: String): String {
        val path = runCatching { URL(url).path.lowercase() }
            .getOrDefault(url.lowercase())

        return when {
            path.contains(".m3u8") || path.endsWith(".m3u") ->
                "application/vnd.apple.mpegurl"

            path.contains(".ts") ||
                path.contains(".mpeg") ||
                path.contains(".mpg") ->
                "video/mpeg"

            path.contains(".mkv") -> "video/x-matroska"
            path.contains(".avi") -> "video/x-msvideo"
            path.contains(".mov") -> "video/quicktime"
            path.contains(".webm") -> "video/webm"
            else -> "video/mp4"
        }
    }

    private fun xmlEscape(value: String): String =
        value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
