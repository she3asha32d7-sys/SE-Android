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
 * CastLab-focused DLNA engine for SE.
 *
 * This follows the behavior in CastLab's original CastManager.ts: multiple SSDP searches with
 * distinct ST values, a separate port-1900 SSDP NOTIFY listener, Wi-Fi-interface binding, renderer
 * description/service resolution, DIDL-Lite metadata, retrying SetAVTransportURI, and a single
 * fast Play action. Local file URLs must be prepared first by CastLabMediaServer.
 */
object CastLabDlnaEngine {
    private const val TAG = "SE-CastLab"
    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val RENDERER_ST = "urn:schemas-upnp-org:device:MediaRenderer:1"
    private const val AV_SERVICE = "urn:schemas-upnp-org:service:AVTransport:1"

    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .callTimeout(13, TimeUnit.SECONDS)
        .build()

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val app = context.applicationContext
        val wifi = app.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val multicastLock = wifi?.createMulticastLock("castlab_ssdp_discovery")
        val receivers = linkedMapOf<String, DlnaReceiver>()
        var searchSocket: MulticastSocket? = null
        var notifySocket: MulticastSocket? = null

        try {
            multicastLock?.setReferenceCounted(false)
            if (multicastLock != null && !multicastLock.isHeld) multicastLock.acquire()

            val networkInterface = findWifiInterface()
            val localAddress = networkInterface?.inetAddresses?.toList()
                ?.filterIsInstance<Inet4Address>()
                ?.firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress }
            val wifiNetwork = (app.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager)
                ?.activeNetwork
                ?.takeIf { network ->
                    val cm = app.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
                    cm?.getNetworkCapabilities(network)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
                }

            val multicastAddress = InetAddress.getByName(GROUP)
            searchSocket = MulticastSocket(null).apply {
                reuseAddress = true
                soTimeout = 250
                bind(if (localAddress != null) InetSocketAddress(localAddress, 0) else InetSocketAddress(0))
                if (networkInterface != null) runCatching { this.networkInterface = networkInterface }
                if (wifiNetwork != null) runCatching { wifiNetwork.bindSocket(this) }
                if (networkInterface != null) {
                    runCatching { joinGroup(InetSocketAddress(multicastAddress, PORT), networkInterface) }
                        .onFailure { Log.d(TAG, "CastLab M-SEARCH multicast membership failed", it) }
                } else {
                    runCatching { joinGroup(multicastAddress) }
                }
            }

            // CastLab listens independently for NOTIFY announcements on UDP/1900. This catches
            // renderers that advertise themselves but answer M-SEARCH unreliably.
            notifySocket = runCatching {
                MulticastSocket(null).apply {
                    reuseAddress = true
                    soTimeout = 250
                    bind(InetSocketAddress(InetAddress.getByName("0.0.0.0"), PORT))
                    if (networkInterface != null) this.networkInterface = networkInterface
                    if (networkInterface != null) {
                        joinGroup(InetSocketAddress(multicastAddress, PORT), networkInterface)
                    } else {
                        joinGroup(multicastAddress)
                    }
                    if (wifiNetwork != null) runCatching { wifiNetwork.bindSocket(this) }
                }
            }.onFailure { Log.w(TAG, "CastLab NOTIFY listener unavailable; M-SEARCH will continue", it) }
                .getOrNull()

            val scheduledTargets = listOf(
                0L to "ssdp:all",
                2000L to RENDERER_ST,
                5000L to "ssdp:all",
                8000L to RENDERER_ST,
                11000L to "ssdp:all"
            )
            var targetIndex = 0
            val startAt = System.currentTimeMillis()
            var lastNewLocationAt = startAt
            val locations = linkedSetOf<String>()

            fun sendSearch(target: String) {
                val message = (
                    "M-SEARCH * HTTP/1.1\r\n" +
                        "HOST: $GROUP:$PORT\r\n" +
                        "MAN: \"ssdp:discover\"\r\n" +
                        "MX: 3\r\n" +
                        "ST: $target\r\n\r\n"
                    ).toByteArray(StandardCharsets.UTF_8)
                val packet = DatagramPacket(message, message.size, multicastAddress, PORT)
                searchSocket?.send(packet)
                Log.d(TAG, "CastLab SSDP M-SEARCH sent; ST=$target")
            }

            sendSearch("ssdp:all")
            targetIndex = 1
            val responseBuffer = ByteArray(8192)

            while (System.currentTimeMillis() - startAt < 13000L) {
                val elapsed = System.currentTimeMillis() - startAt
                while (targetIndex < scheduledTargets.size && elapsed >= scheduledTargets[targetIndex].first) {
                    sendSearch(scheduledTargets[targetIndex].second)
                    targetIndex++
                }

                var receivedAny = false
                val sockets = listOfNotNull(searchSocket, notifySocket)
                for (socket in sockets) {
                    try {
                        val packet = DatagramPacket(responseBuffer, responseBuffer.size)
                        socket.receive(packet)
                        val text = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                        val headers = parseHeaders(text)
                        val nts = headers["nts"].orEmpty()
                        if (nts.equals("ssdp:byebye", true)) continue
                        val location = headers["location"]?.trim().orEmpty()
                        val target = (headers["st"] ?: headers["nt"]).orEmpty()
                        val usn = headers["usn"].orEmpty()
                        if (location.startsWith("http", true) && target.isNotBlank()) {
                            val acceptedTarget = target.equals("ssdp:all", true) ||
                                target.contains("upnp", true) ||
                                target.contains("schemas-upnp-org", true) ||
                                target.contains("MediaRenderer", true) ||
                                usn.contains("uuid:", true)
                            if (acceptedTarget && locations.add(location)) {
                                lastNewLocationAt = System.currentTimeMillis()
                                receivedAny = true
                                Log.d(TAG, "CastLab discovered LOCATION=$location ST/NT=$target USN=$usn")
                            }
                        }
                    } catch (_: SocketTimeoutException) {
                        // Expected while UDP responses are arriving asynchronously.
                    } catch (e: Exception) {
                        if (!socket.isClosed) Log.d(TAG, "CastLab SSDP receive error", e)
                    }
                }

                // Do not hold the chooser open for the whole upstream 30-second search duration
                // once the current LAN has answered and a short quiet period has elapsed.
                val totalElapsed = System.currentTimeMillis() - startAt
                val quietFor = System.currentTimeMillis() - lastNewLocationAt
                if (locations.isNotEmpty() && totalElapsed >= 3500L && quietFor >= 1800L &&
                    targetIndex >= 3) break
            }

            locations.forEach { location ->
                val receiver = runCatching { readDeviceDescription(location) }
                    .onFailure { Log.w(TAG, "CastLab could not read UPnP description: $location", it) }
                    .getOrNull()
                if (receiver != null) receivers.putIfAbsent(receiver.id, receiver)
            }
            receivers.values.sortedBy { it.name.lowercase(Locale.US) }
        } finally {
            runCatching { searchSocket?.close() }
            runCatching { notifySocket?.close() }
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
                "CastLab needs a TV-reachable HTTP/HTTPS media URL. Local files must be prepared by CastLabMediaServer."
            }
            val mediaMime = mimeFromUrl(mediaUrl, isLive)
            val metadata = buildDIDL(mediaUrl, title, mediaMime)
            var lastError: Exception? = null

            // CastLab retries SetAVTransportURI because some receivers respond late during handoff.
            for (attempt in 1..3) {
                try {
                    soapAction(
                        receiver.controlUrl,
                        receiver.serviceType.ifBlank { AV_SERVICE },
                        "SetAVTransportURI",
                        "<InstanceID>0</InstanceID><CurrentURI>${xmlEscape(mediaUrl)}</CurrentURI><CurrentURIMetaData>${xmlEscape(metadata)}</CurrentURIMetaData>",
                        timeoutSeconds = 10
                    )
                    lastError = null
                    break
                } catch (error: Exception) {
                    lastError = error
                    Log.w(TAG, "CastLab SetAVTransportURI attempt $attempt failed: ${error.message}")
                    if (attempt < 3) Thread.sleep(1000L)
                }
            }
            if (lastError != null) throw lastError

            // Match CastLab's fast Play behavior: one command, no repeated Play that can restart playback.
            soapAction(
                receiver.controlUrl,
                receiver.serviceType.ifBlank { AV_SERVICE },
                "Play",
                "<InstanceID>0</InstanceID><Speed>1</Speed>",
                timeoutSeconds = 3
            )
            Log.i(TAG, "CastLab playback handoff succeeded to ${receiver.name}: $mediaUrl")
            Unit
        }
    }

    private fun findWifiInterface(): NetworkInterface? = runCatching {
        NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
            .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
            .sortedBy {
                when {
                    it.name.startsWith("wlan", true) || it.name.startsWith("wifi", true) -> 0
                    else -> 1
                }
            }
            .firstOrNull { iface ->
                iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                    .any { !it.isLoopbackAddress && !it.isLinkLocalAddress }
            }
    }.getOrNull()

    private fun readDeviceDescription(location: String): DlnaReceiver? {
        val request = Request.Builder()
            .url(location)
            .header("User-Agent", "CastLab/1.5 UPnP/1.0")
            .get()
            .build()
        val xml = http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.d(TAG, "Description HTTP ${response.code} for $location")
                return null
            }
            response.body?.string() ?: return null
        }

        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
            runCatching { setFeature("http://apache.org/xml/features/disallow-doctype-decl", true) }
            runCatching { setFeature("http://xml.org/sax/features/external-general-entities", false) }
            runCatching { setFeature("http://xml.org/sax/features/external-parameter-entities", false) }
            runCatching { setAttribute("http://javax.xml.XMLConstants/property/accessExternalDTD", "") }
            runCatching { setAttribute("http://javax.xml.XMLConstants/property/accessExternalSchema", "") }
        }
        val document = factory.newDocumentBuilder()
            .parse(ByteArrayInputStream(xml.toByteArray(StandardCharsets.UTF_8)))
        val friendlyName = firstTagText(document.documentElement, "friendlyName").orEmpty()
        val udn = firstTagText(document.documentElement, "UDN").orEmpty().ifBlank { location }
        val urlBase = firstTagText(document.documentElement, "URLBase").orEmpty().ifBlank { location }
        val baseUrl = URL(urlBase)

        val services = document.getElementsByTagName("service")
        var avControlUrl: String? = null
        var avServiceType = AV_SERVICE
        var renderingControl: String? = null

        for (index in 0 until services.length) {
            val service = services.item(index) as? Element ?: continue
            val serviceType = firstTagText(service, "serviceType").orEmpty()
            val controlPath = firstTagText(service, "controlURL").orEmpty()
            if (controlPath.isBlank()) continue
            when {
                serviceType.contains(":AVTransport:", true) -> {
                    avServiceType = serviceType
                    avControlUrl = URL(baseUrl, controlPath).toString()
                }
                serviceType.contains(":RenderingControl:", true) -> {
                    renderingControl = URL(baseUrl, controlPath).toString()
                }
            }
        }
        val control = avControlUrl ?: return null
        val baseHost = URL(location).host
        return DlnaReceiver(
            id = udn,
            name = friendlyName.ifBlank { baseHost },
            host = baseHost,
            descriptionUrl = location,
            controlUrl = control,
            serviceType = avServiceType,
            renderingControlUrl = renderingControl
        )
    }

    private fun firstTagText(element: Element, name: String): String? {
        val normal = element.getElementsByTagName(name).item(0)
        if (normal != null) return normal.textContent?.trim()
        val namespaced = element.getElementsByTagNameNS("*", name).item(0)
        return namespaced?.textContent?.trim()
    }

    private fun buildDIDL(url: String, title: String, mime: String): String {
        val safeTitle = xmlEscape(title.ifBlank { url.substringAfterLast('/').substringBefore('?').ifBlank { "Media" } })
        val safeUrl = xmlEscape(url)
        val (upnpClass, protocolInfo) = when {
            mime.startsWith("image/", true) -> "object.item.imageItem.photo" to
                "http-get:*:$mime:DLNA.ORG_CI=0;DLNA.ORG_FLAGS=00D00000000000000000000000000000"
            mime.startsWith("audio/", true) -> "object.item.audioItem.musicTrack" to
                "http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01500000000000000000000000000000"
            mime.startsWith("video/", true) || mime.contains("mpegurl", true) || mime.contains("dash", true) ->
                "object.item.videoItem" to "http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_CI=0"
            else -> "object.item" to "http-get:*:$mime:*"
        }
        return """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="media-${System.currentTimeMillis()}" parentID="0" restricted="true"><dc:title>$safeTitle</dc:title><upnp:class>$upnpClass</upnp:class><res protocolInfo="$protocolInfo">$safeUrl</res></item></DIDL-Lite>"""
    }

    private fun mimeFromUrl(url: String, isLive: Boolean): String {
        val path = runCatching { URL(url).path }.getOrDefault(url.substringBefore('?'))
        val extension = path.substringAfterLast('.', "").lowercase(Locale.US)
        return when (extension) {
            "mp4", "m4v" -> "video/mp4"
            "mkv" -> "video/x-matroska"
            "avi" -> "video/x-msvideo"
            "mov" -> "video/quicktime"
            "webm" -> "video/webm"
            "3gp" -> "video/3gpp"
            "ts", "mts", "m2ts" -> "video/mp2t"
            "m3u8" -> "application/vnd.apple.mpegurl"
            "m3u" -> "audio/mpegurl"
            "mp3" -> "audio/mpeg"
            "m4a" -> "audio/mp4"
            "aac" -> "audio/aac"
            "ogg" -> "audio/ogg"
            "wav" -> "audio/wav"
            "flac" -> "audio/flac"
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            "gif" -> "image/gif"
            else -> if (isLive) "video/mpeg" else "video/mp4"
        }
    }

    private fun soapAction(
        controlUrl: String,
        serviceType: String,
        action: String,
        arguments: String,
        timeoutSeconds: Long
    ) {
        val envelope = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:$action xmlns:u="$serviceType">$arguments</u:$action></s:Body></s:Envelope>"""
        val request = Request.Builder()
            .url(controlUrl)
            .header("User-Agent", "CastLab/1.5 UPnP/1.0")
            .header("Content-Type", "text/xml; charset=\"utf-8\"")
            .header("SOAPACTION", "\"$serviceType#$action\"")
            .post(envelope.toRequestBody("text/xml; charset=\"utf-8\"".toMediaType()))
            .build()
        http.newCall(request).apply {
            timeout().timeout(timeoutSeconds, TimeUnit.SECONDS)
        }.execute().use { response ->
            val responseText = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val code = Regex("<(?:\\w+:)?errorCode[^>]*>(.*?)</(?:\\w+:)?errorCode>", RegexOption.IGNORE_CASE)
                    .find(responseText)?.groupValues?.getOrNull(1)?.trim()
                val description = Regex("<(?:\\w+:)?errorDescription[^>]*>(.*?)</(?:\\w+:)?errorDescription>", RegexOption.IGNORE_CASE)
                    .find(responseText)?.groupValues?.getOrNull(1)?.trim()
                val detail = if (!code.isNullOrBlank() && !description.isNullOrBlank()) "UPnP $code: $description"
                    else "HTTP ${response.code}: ${responseText.take(350)}"
                throw IllegalStateException("$action failed at $controlUrl — $detail")
            }
        }
    }

    private fun parseHeaders(response: String): Map<String, String> = response
        .lineSequence()
        .mapNotNull { line ->
            val index = line.indexOf(':')
            if (index <= 0) null else line.substring(0, index).trim().lowercase(Locale.US) to line.substring(index + 1).trim()
        }.toMap()

    private fun xmlEscape(value: String): String = value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")
}
