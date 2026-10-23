package com.orbital.iptv.utils.originaldlna

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.io.StringReader
import java.net.DatagramPacket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * CastLab-specific DLNA control path.
 *
 * Integration basis: CastLab's Android/React-Native project and its SSDP/UPnP discovery flow.
 * The Activity/React bridge is replaced by this SE-native entry point; SSDP collection,
 * renderer-description resolution, and AVTransport commands stay isolated in this engine.
 */
object CastLabDlnaEngine {
    private const val TAG = "SE-CastLab"
    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val AV = "urn:schemas-upnp-org:service:AVTransport:1"
    private val http by lazy {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .callTimeout(14, TimeUnit.SECONDS)
            .build()
    }

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val lock = (context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager)
            ?.createMulticastLock("castlab_upnp_discovery")
        try {
            lock?.setReferenceCounted(false)
            if (lock != null && !lock.isHeld) lock.acquire()
            val locations = linkedMapOf<String, String>()
            val wifi = NetworkInterface.getNetworkInterfaces()?.toList()
                ?.firstOrNull { it.isUp && !it.isLoopback && (it.name.startsWith("wlan") || it.name.startsWith("wifi")) }
            MulticastSocket(null).use { socket ->
                socket.reuseAddress = true
                socket.broadcast = true
                socket.soTimeout = 450
                if (wifi != null) runCatching { socket.networkInterface = wifi }
                socket.bind(InetSocketAddress(0))
                val multicast = InetAddress.getByName(GROUP)
                val broadcast = InetAddress.getByName("255.255.255.255")
                val targets = listOf("upnp:rootdevice", "urn:schemas-upnp-org:device:MediaRenderer:1", AV, "ssdp:all")
                repeat(2) {
                    targets.forEach { target ->
                        val packetText = "M-SEARCH * HTTP/1.1\r\nHOST: $GROUP:$PORT\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: $target\r\nUSER-AGENT: CastLab/1.5 UPnP/1.0\r\n\r\n"
                        val bytes = packetText.toByteArray(StandardCharsets.UTF_8)
                        listOf(multicast, broadcast).forEach { address ->
                            runCatching { socket.send(DatagramPacket(bytes, bytes.size, address, PORT)) }
                        }
                    }
                    Thread.sleep(160L)
                }
                val deadline = System.currentTimeMillis() + 6500L
                val buffer = ByteArray(8192)
                while (System.currentTimeMillis() < deadline) {
                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                        val location = headers(response)["location"]
                        if (!location.isNullOrBlank() && location.startsWith("http", true)) {
                            locations.putIfAbsent(location, response)
                        }
                    } catch (_: SocketTimeoutException) {
                        // Continue until the discovery window completes; some TVs respond late.
                    }
                }
            }
            locations.keys.mapNotNull { location ->
                runCatching { readDescription(location) }
                    .onFailure { Log.d(TAG, "Skipping renderer description $location", it) }
                    .getOrNull()
            }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
        } finally {
            runCatching { if (lock?.isHeld == true) lock.release() }
        }
    }

    suspend fun cast(receiver: DlnaReceiver, mediaUrl: String, title: String, isLive: Boolean): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "CastLab DLNA requires an HTTP/HTTPS stream URL reachable by the TV."
                }
                val mime = dlnaMimeFor(mediaUrl, isLive)
                val didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="1"><dc:title>${dlnaXmlEscape(title)}</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo="http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_CI=0">${dlnaXmlEscape(mediaUrl)}</res></item></DIDL-Lite>"""
                action(receiver, "SetAVTransportURI",
                    "<InstanceID>0</InstanceID><CurrentURI>${dlnaXmlEscape(mediaUrl)}</CurrentURI><CurrentURIMetaData>${dlnaXmlEscape(didl)}</CurrentURIMetaData>")
                action(receiver, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
            }
        }

    private fun readDescription(location: String): DlnaReceiver? {
        val request = Request.Builder().url(location).header("User-Agent", "CastLab/1.5 UPnP/1.0").get().build()
        val xml = http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            response.body?.string() ?: return null
        }
        val parser = XmlPullParserFactory.newInstance().newPullParser()
        parser.setInput(StringReader(xml))
        var friendlyName = ""
        var udn = location
        var currentTag = ""
        var serviceType = ""
        var serviceControl = ""
        var avControl: String? = null
        var renderingControl: String? = null
        var currentServiceType = ""
        var currentControl = ""
        var insideService = false
        var depth = 0
        while (parser.eventType != XmlPullParser.END_DOCUMENT) {
            when (parser.eventType) {
                XmlPullParser.START_TAG -> {
                    depth++
                    currentTag = parser.name.substringAfter(':')
                    if (currentTag == "service") {
                        insideService = true
                        currentServiceType = ""
                        currentControl = ""
                    }
                }
                XmlPullParser.TEXT -> {
                    val value = parser.text?.trim().orEmpty()
                    if (value.isNotEmpty()) when (currentTag) {
                        "friendlyName" -> if (friendlyName.isBlank()) friendlyName = value
                        "UDN" -> if (udn == location) udn = value
                        "serviceType" -> if (insideService) currentServiceType = value
                        "controlURL" -> if (insideService) currentControl = value
                    }
                }
                XmlPullParser.END_TAG -> {
                    val tag = parser.name.substringAfter(':')
                    if (tag == "service") {
                        when {
                            currentServiceType.contains(":AVTransport:", true) -> {
                                serviceType = currentServiceType
                                avControl = currentControl
                            }
                            currentServiceType.contains(":RenderingControl:", true) -> renderingControl = currentControl
                        }
                        insideService = false
                    }
                    depth--
                }
            }
            parser.next()
        }
        if (avControl.isNullOrBlank()) return null
        val description = URL(location)
        fun resolve(path: String): String = URL(description, path).toString()
        return DlnaReceiver(
            id = udn,
            name = friendlyName.ifBlank { description.host },
            host = description.host,
            descriptionUrl = location,
            controlUrl = resolve(avControl!!),
            serviceType = serviceType.ifBlank { AV },
            renderingControlUrl = renderingControl?.let(::resolve)
        )
    }

    private fun action(receiver: DlnaReceiver, name: String, arguments: String) {
        val envelope = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:$name xmlns:u="${receiver.serviceType}">$arguments</u:$name></s:Body></s:Envelope>"""
        val request = Request.Builder()
            .url(receiver.controlUrl)
            .header("User-Agent", "CastLab/1.5 UPnP/1.0")
            .header("SOAPAction", "\"${receiver.serviceType}#$name\"")
            .post(envelope.toRequestBody("text/xml; charset=utf-8".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IllegalStateException("$name failed (HTTP ${response.code}): ${body.take(300)}")
        }
    }

    private fun headers(response: String): Map<String, String> = response.split("\r\n")
        .mapNotNull { line ->
            val at = line.indexOf(':')
            if (at <= 0) null else line.substring(0, at).trim().lowercase(Locale.US) to line.substring(at + 1).trim()
        }.toMap()
}
