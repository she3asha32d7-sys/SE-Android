package com.orbital.iptv.utils.originaldlna

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.w3c.dom.Element
import java.io.ByteArrayInputStream
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
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Vega's standalone form of the original native DlnaModule.kt.
 *
 * The upstream React Native Promise/EventEmitter bridge is replaced with SE's suspend API.
 * The distinctive upstream behavior remains here: explicitly bind SSDP to Wi-Fi, send multicast
 * and broadcast M-SEARCH requests, parse the UPnP DOM description, then send AVTransport actions.
 */
object VegaDlnaEngine {
    private const val TAG = "SE-Vega-DLNA"
    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val AV = "urn:schemas-upnp-org:service:AVTransport:1"
    private const val RENDERING = "urn:schemas-upnp-org:service:RenderingControl:1"
    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val app = context.applicationContext
        val wifi = app.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = wifi?.createMulticastLock("VegaDlnaDiscovery")
        val found = linkedMapOf<String, String>()
        var socket: MulticastSocket? = null
        try {
            lock?.setReferenceCounted(false)
            if (lock != null && !lock.isHeld) lock.acquire()
            socket = MulticastSocket(null).apply {
                reuseAddress = true
                broadcast = true
                soTimeout = 450
            }

            val connectivity = app.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            val wifiNetwork = connectivity?.allNetworks?.firstOrNull { network ->
                connectivity.getNetworkCapabilities(network)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
            }
            val wifiInterface = NetworkInterface.getNetworkInterfaces()?.toList()
                ?.firstOrNull { iface ->
                    (iface.name.startsWith("wlan") || iface.name.startsWith("wifi")) &&
                        runCatching { iface.isUp && !iface.isLoopback }.getOrDefault(false)
                }
            if (wifiInterface != null) {
                runCatching { socket.networkInterface = wifiInterface }
                    .onFailure { Log.w(TAG, "Could not bind discovery interface", it) }
                val wifiAddress = wifiInterface.inetAddresses.toList()
                    .filterIsInstance<Inet4Address>()
                    .firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress }
                if (wifiAddress != null) socket.bind(InetSocketAddress(wifiAddress, 0))
                else socket.bind(InetSocketAddress(0))
            } else {
                socket.bind(InetSocketAddress(0))
            }
            if (wifiNetwork != null) {
                runCatching { wifiNetwork.bindSocket(socket) }
                    .onFailure { Log.w(TAG, "Could not bind SSDP socket to Wi-Fi network", it) }
            }

            val multicast = InetAddress.getByName(GROUP)
            val broadcast = InetAddress.getByName("255.255.255.255")
            val targets = listOf("urn:schemas-upnp-org:device:MediaRenderer:1", "ssdp:all")
            fun searchPacket(target: String, destination: InetAddress): DatagramPacket {
                val text = "M-SEARCH * HTTP/1.1\r\nHOST: $GROUP:$PORT\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: $target\r\n\r\n"
                val bytes = text.toByteArray(StandardCharsets.UTF_8)
                return DatagramPacket(bytes, bytes.size, destination, PORT)
            }
            for (target in targets) {
                runCatching { socket.send(searchPacket(target, multicast)) }
                    .onFailure { Log.w(TAG, "SSDP multicast failed for $target", it) }
                runCatching { socket.send(searchPacket(target, broadcast)) }
                    .onFailure { Log.w(TAG, "SSDP broadcast failed for $target", it) }
            }
            Thread.sleep(150L)
            targets.forEach { target -> runCatching { socket.send(searchPacket(target, multicast)) } }

            val deadline = System.currentTimeMillis() + 7000L
            val buffer = ByteArray(8192)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val raw = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val location = parseHeaders(raw)["location"]
                    if (!location.isNullOrBlank() && location.startsWith("http", true)) found.putIfAbsent(location, raw)
                } catch (_: SocketTimeoutException) {
                    // A timeout is not the end of the discovery window; keep collecting.
                }
            }
            found.keys.mapNotNull { location ->
                runCatching { readDeviceDescription(location) }
                    .onFailure { Log.w(TAG, "Vega device description failed: $location", it) }
                    .getOrNull()
            }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
        } finally {
            runCatching { socket?.close() }
            runCatching { if (lock?.isHeld == true) lock.release() }
        }
    }

    suspend fun cast(receiver: DlnaReceiver, mediaUrl: String, title: String, isLive: Boolean): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "Vega DLNA requires an HTTP/HTTPS URL reachable by the TV."
                }
                val mime = dlnaMimeFor(mediaUrl, isLive)
                val didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="1"><dc:title>${dlnaXmlEscape(title)}</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo="http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_CI=0">${dlnaXmlEscape(mediaUrl)}</res></item></DIDL-Lite>"""
                soap(receiver.controlUrl, receiver.serviceType, "SetAVTransportURI",
                    "<InstanceID>0</InstanceID><CurrentURI>${dlnaXmlEscape(mediaUrl)}</CurrentURI><CurrentURIMetaData>${dlnaXmlEscape(didl)}</CurrentURIMetaData>")
                soap(receiver.controlUrl, receiver.serviceType, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
            }
        }

    private fun readDeviceDescription(location: String): DlnaReceiver? {
        val request = Request.Builder().url(location).build()
        val xml = http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            response.body?.string() ?: return null
        }
        val base = URL(location)
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        val doc = factory.newDocumentBuilder().parse(ByteArrayInputStream(xml.toByteArray(StandardCharsets.UTF_8)))
        val friendlyName = doc.getElementsByTagName("friendlyName").item(0)?.textContent?.trim().orEmpty()
        val udn = doc.getElementsByTagName("UDN").item(0)?.textContent?.trim().orEmpty().ifBlank { location }
        var avControl: String? = null
        var avType = AV
        var renderingControl: String? = null
        val services = doc.getElementsByTagName("service")
        for (index in 0 until services.length) {
            val service = services.item(index) as? Element ?: continue
            val type = service.getElementsByTagName("serviceType").item(0)?.textContent?.trim().orEmpty()
            val relative = service.getElementsByTagName("controlURL").item(0)?.textContent?.trim().orEmpty()
            if (type.contains(":AVTransport:", ignoreCase = true)) {
                avType = type
                avControl = resolve(base, relative)
            } else if (type.contains(":RenderingControl:", ignoreCase = true)) {
                renderingControl = resolve(base, relative)
            }
        }
        if (avControl.isNullOrBlank()) return null
        return DlnaReceiver(
            id = udn,
            name = friendlyName.ifBlank { base.host },
            host = base.host,
            descriptionUrl = location,
            controlUrl = avControl!!,
            serviceType = avType,
            renderingControlUrl = renderingControl
        )
    }

    private fun resolve(base: URL, relative: String): String =
        runCatching { URL(base, relative).toString() }.getOrElse { relative }

    private fun soap(controlUrl: String, serviceType: String, action: String, arguments: String) {
        val body = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:$action xmlns:u="$serviceType">$arguments</u:$action></s:Body></s:Envelope>"""
        val request = Request.Builder()
            .url(controlUrl)
            .header("SOAPAction", "\"$serviceType#$action\"")
            .post(body.toRequestBody("text/xml; charset=utf-8".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IllegalStateException("$action failed (HTTP ${response.code}): ${text.take(350)}")
        }
    }

    private fun parseHeaders(raw: String): Map<String, String> = raw.split("\r\n")
        .mapNotNull { line ->
            val index = line.indexOf(':')
            if (index <= 0) null else line.substring(0, index).trim().lowercase(Locale.US) to line.substring(index + 1).trim()
        }.toMap()
}
