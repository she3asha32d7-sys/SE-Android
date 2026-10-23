package com.orbital.iptv.utils.originaldlna

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
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
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import javax.xml.parsers.DocumentBuilderFactory

/**
 * NekoVideo-specific DLNA path adapted from DLNACastManager.kt and LocalVideoServer.kt.
 *
 * The discovery routine follows NekoVideo's key behavior: scan each active IPv4 interface in
 * parallel, bind each socket to its interface/address, join the SSDP multicast group, and resolve
 * each device description before declaring a renderer usable. For IPTV URLs SE sends the same
 * reachable HTTP resource directly; the original NanoHTTPD file server source is included in
 * THIRD_PARTY_SOURCE_CODE for local-file casting integration/reference.
 */
object NekoVideoDlnaEngine {
    private const val TAG = "SE-NekoVideo-DLNA"
    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val AV = "urn:schemas-upnp-org:service:AVTransport:1"
    private val http = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .callTimeout(10, TimeUnit.SECONDS)
        .build()

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = wifi?.createMulticastLock("nekovideo_ssdp")
        val devices = ConcurrentHashMap<String, DlnaReceiver>()
        try {
            lock?.setReferenceCounted(false)
            if (lock != null && !lock.isHeld) lock.acquire()
            val interfaces = activeIpv4Interfaces().take(8)
            coroutineScope {
                interfaces.map { (iface, address) ->
                    async(Dispatchers.IO) {
                        discoverOnInterface(iface, address).forEach { receiver ->
                            devices.putIfAbsent(receiver.id, receiver)
                        }
                    }
                }.awaitAll()
            }
            devices.values.toList().sortedBy { it.name.lowercase(Locale.US) }
        } finally {
            runCatching { if (lock?.isHeld == true) lock.release() }
        }
    }

    suspend fun cast(receiver: DlnaReceiver, mediaUrl: String, title: String, isLive: Boolean): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "NekoVideo DLNA needs an HTTP/HTTPS media URL reachable by the TV."
                }
                val mime = dlnaMimeFor(mediaUrl, isLive)
                // Matches NekoVideo's resource advertisement (operation/byte-range support).
                val didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="false"><dc:title>${dlnaXmlEscape(title)}</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo="http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01500000000000000000000000000000">${dlnaXmlEscape(mediaUrl)}</res></item></DIDL-Lite>"""
                soap(receiver, "SetAVTransportURI",
                    "<CurrentURI>${dlnaXmlEscape(mediaUrl)}</CurrentURI><CurrentURIMetaData>${dlnaXmlEscape(didl)}</CurrentURIMetaData>")
                // NekoVideo delays Play after SetAVTransportURI to accommodate receivers that
                // briefly report STOPPED while replacing the current resource.
                kotlinx.coroutines.delay(500L)
                soap(receiver, "Play", "<Speed>1</Speed>")
            }
        }

    private fun activeIpv4Interfaces(): List<Pair<NetworkInterface, Inet4Address>> =
        runCatching {
            NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
                .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
                .flatMap { iface ->
                    iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                        .filterNot { it.isLoopbackAddress || it.isLinkLocalAddress }
                        .map { iface to it }
                }
        }.getOrDefault(emptyList())

    private fun discoverOnInterface(
        networkInterface: NetworkInterface,
        localAddress: Inet4Address
    ): List<DlnaReceiver> {
        val found = linkedMapOf<String, DlnaReceiver>()
        val multicast = InetAddress.getByName(GROUP)
        val search = "M-SEARCH * HTTP/1.1\r\nHOST: $GROUP:$PORT\r\nMAN: \"ssdp:discover\"\r\nMX: 3\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
            .toByteArray(StandardCharsets.UTF_8)
        try {
            MulticastSocket(null).use { socket ->
                socket.reuseAddress = true
                socket.bind(InetSocketAddress(localAddress, 0))
                socket.soTimeout = 500
                socket.networkInterface = networkInterface
                runCatching { socket.joinGroup(InetSocketAddress(multicast, PORT), networkInterface) }
                    .onFailure { Log.d(TAG, "Cannot join SSDP on ${networkInterface.name}", it) }
                repeat(2) {
                    socket.send(DatagramPacket(search, search.size, multicast, PORT))
                    Thread.sleep(200L)
                }
                val deadline = System.currentTimeMillis() + 4200L
                val buffer = ByteArray(4096)
                while (System.currentTimeMillis() < deadline) {
                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                        val location = header(response, "LOCATION") ?: continue
                        val device = readDescription(location)
                        if (device != null) found.putIfAbsent(device.id, device)
                    } catch (_: SocketTimeoutException) {
                        // Keep scanning the individual network until its discovery window closes.
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Discovery failed on ${networkInterface.name}/${localAddress.hostAddress}", e)
        }
        return found.values.toList()
    }

    private fun readDescription(location: String): DlnaReceiver? {
        return try {
            val request = Request.Builder().url(location).header("User-Agent", "NekoVideo/1.x UPnP/1.0").get().build()
            val xml = http.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                response.body?.string() ?: return null
            }
            val base = URL(location)
            val document = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
                .newDocumentBuilder().parse(ByteArrayInputStream(xml.toByteArray(StandardCharsets.UTF_8)))
            val name = document.getElementsByTagName("friendlyName").item(0)?.textContent?.trim().orEmpty()
            val udn = document.getElementsByTagName("UDN").item(0)?.textContent?.trim().orEmpty().ifBlank { location }
            var control: String? = null
            var serviceType = AV
            val services = document.getElementsByTagName("service")
            for (index in 0 until services.length) {
                val service = services.item(index) as? Element ?: continue
                val type = service.getElementsByTagName("serviceType").item(0)?.textContent?.trim().orEmpty()
                if (type.contains("AVTransport", true)) {
                    val relative = service.getElementsByTagName("controlURL").item(0)?.textContent?.trim().orEmpty()
                    if (relative.isNotBlank()) {
                        control = URL(base, relative).toString()
                        serviceType = type.ifBlank { AV }
                        break
                    }
                }
            }
            if (control.isNullOrBlank()) return null
            DlnaReceiver(udn, name.ifBlank { base.host }, base.host, location, control!!, serviceType)
        } catch (e: Exception) {
            Log.d(TAG, "Invalid renderer description $location", e)
            null
        }
    }

    private fun soap(receiver: DlnaReceiver, action: String, arguments: String) {
        val envelope = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:$action xmlns:u="${receiver.serviceType}"><InstanceID>0</InstanceID>$arguments</u:$action></s:Body></s:Envelope>"""
        val request = Request.Builder().url(receiver.controlUrl)
            .header("User-Agent", "NekoVideo/1.x UPnP/1.0")
            .header("SOAPAction", "\" ${receiver.serviceType}#$action \"".trim().replace("\" ", "\"").replace(" \"", "\""))
            .post(envelope.toRequestBody("text/xml; charset=utf-8".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IllegalStateException("$action failed (HTTP ${response.code}): ${body.take(300)}")
        }
    }

    private fun header(response: String, key: String): String? =
        response.lineSequence().firstOrNull { it.substringBefore(':').equals(key, true) }
            ?.substringAfter(':')?.trim()?.takeIf { it.isNotEmpty() }
}
