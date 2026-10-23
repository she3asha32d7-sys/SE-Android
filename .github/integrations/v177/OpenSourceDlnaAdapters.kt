package com.orbital.iptv.utils

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
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.io.ByteArrayInputStream
import java.net.DatagramPacket
import java.net.HttpURLConnection
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
 * Additional DLNA control-point adapters added in V100.0.177.
 *
 * The named upstream applications are separate apps, not drop-in Android libraries. This file
 * adapts their distinct discovery/control approaches to SE's existing player and device chooser.
 * NekoVideo-origin patterns are GPL-3.0-only; Vega's native DLNA approach is based on its Apache-2.0
 * revision 9ccc0c8. See THIRD_PARTY_NOTICES.md in the source distribution.
 */
object OpenSourceDlnaAdapters {
    enum class Engine(val label: String) {
        CASTLAB("DLNA 2 (CastLab)"),
        VEGA("DLNA 3 (Vega)"),
        NEKOVIDEO("DLNA 4 (NekoVideo)"),
        YAACC("DLNA 5 (YAACC)")
    }

    data class Device(
        val id: String,
        val name: String,
        val host: String,
        val location: String,
        val controlUrl: String,
        val serviceType: String,
        val engine: Engine
    )

    private data class ServiceInfo(val type: String, val control: String)
    private data class Description(
        val name: String,
        val deviceType: String,
        val services: List<ServiceInfo>,
        val urlBase: String?
    )

    private const val TAG = "SEOpenSourceDLNA"
    private const val SSDP_ADDRESS = "239.255.255.250"
    private const val SSDP_PORT = 1900
    private const val AVTRANSPORT_V1 = "urn:schemas-upnp-org:service:AVTransport:1"
    private val okHttp by lazy {
        OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .callTimeout(12, TimeUnit.SECONDS)
            .build()
    }

    suspend fun discover(context: Context, engine: Engine): List<Device> =
        withContext(Dispatchers.IO) {
            when (engine) {
                Engine.CASTLAB -> discoverCastLab(context.applicationContext)
                Engine.VEGA -> discoverVega(context.applicationContext)
                Engine.NEKOVIDEO -> discoverNekoVideo(context.applicationContext)
                Engine.YAACC -> discoverYaacc(context.applicationContext)
            }
        }

    suspend fun cast(
        context: Context,
        engine: Engine,
        device: Device,
        mediaUrl: String,
        title: String,
        isLive: Boolean
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                "DLNA CAST NEEDS AN HTTP/HTTPS URL REACHABLE BY THE TV"
            }
            when (engine) {
                Engine.CASTLAB -> castLab(device, mediaUrl, title, isLive)
                Engine.VEGA -> castVega(device, mediaUrl, title, isLive)
                Engine.NEKOVIDEO -> castNekoVideo(device, mediaUrl, title, isLive)
                Engine.YAACC -> castYaacc(device, mediaUrl, title, isLive)
            }
        }
    }

    /*
     * CastLab-style discovery: ask for all/root/rendering-service targets, listen on the Wi-Fi
     * interface, and deduplicate by LOCATION before resolving each device's AVTransport endpoint.
     */
    private fun discoverCastLab(context: Context): List<Device> = withMulticastLock(context, "SE_CASTLAB_SSDP") {
        val found = linkedMapOf<String, String>()
        val wifiInterface = findWifiInterface()
        MulticastSocket(null).use { socket ->
            socket.reuseAddress = true
            socket.broadcast = true
            socket.soTimeout = 450
            if (wifiInterface != null) runCatching { socket.networkInterface = wifiInterface }
            socket.bind(InetSocketAddress(0))
            val group = InetAddress.getByName(SSDP_ADDRESS)
            val broadcast = InetAddress.getByName("255.255.255.255")
            val targets = listOf(
                "upnp:rootdevice",
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                AVTRANSPORT_V1,
                "ssdp:all"
            )
            repeat(2) {
                targets.forEach { st ->
                    val bytes = searchPacket(st, 5, "CastLab/1.6 UPnP/1.0").toByteArray(StandardCharsets.UTF_8)
                    listOf(group, broadcast).forEach { destination ->
                        runCatching {
                            socket.send(DatagramPacket(bytes, bytes.size, destination, SSDP_PORT))
                        }
                    }
                }
                Thread.sleep(140L)
            }
            val deadline = System.currentTimeMillis() + 6200L
            val buffer = ByteArray(8192)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val headers = parseHeaders(response)
                    val location = headers["location"]
                    if (!location.isNullOrBlank() && location.startsWith("http", true)) {
                        if (!found.containsKey(location)) found[location] = headers["st"].orEmpty()
                    }
                } catch (_: SocketTimeoutException) {
                    // Continue collecting delayed renderer responses until the search window ends.
                }
            }
        }
        found.keys.mapNotNull { location ->
            runCatching { parsePullDescription(location, Engine.CASTLAB) }.getOrNull()
        }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
    }

    /*
     * Vega's native Android implementation explicitly binds discovery to Wi-Fi to avoid sending
     * SSDP via cellular. This is the adapted Kotlin-native variant (Vega revision 9ccc0c8, Apache-2.0).
     */
    private fun discoverVega(context: Context): List<Device> = withMulticastLock(context, "SE_VEGA_SSDP") {
        val found = linkedMapOf<String, String>()
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        val wifiNetwork = cm?.allNetworks?.firstOrNull { network ->
            cm.getNetworkCapabilities(network)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
        val wifiInterface = findWifiInterface()
        val wifiIp = wifiInterface?.inetAddresses?.toList()
            ?.filterIsInstance<Inet4Address>()
            ?.firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress }

        MulticastSocket(null).use { socket ->
            socket.reuseAddress = true
            socket.broadcast = true
            socket.soTimeout = 500
            if (wifiInterface != null) runCatching { socket.networkInterface = wifiInterface }
            if (wifiIp != null) socket.bind(InetSocketAddress(wifiIp, 0))
            else socket.bind(InetSocketAddress(0))
            if (wifiNetwork != null) runCatching { wifiNetwork.bindSocket(socket) }

            val group = InetAddress.getByName(SSDP_ADDRESS)
            val broadcast = InetAddress.getByName("255.255.255.255")
            val targets = listOf("urn:schemas-upnp-org:device:MediaRenderer:1", "ssdp:all")
            targets.forEach { st ->
                val bytes = searchPacket(st, 3, "Android/SE-Vega-DLNA").toByteArray(StandardCharsets.UTF_8)
                listOf(group, broadcast).forEach { destination ->
                    runCatching { socket.send(DatagramPacket(bytes, bytes.size, destination, SSDP_PORT)) }
                }
            }
            Thread.sleep(160L)
            targets.forEach { st ->
                val bytes = searchPacket(st, 3, "Android/SE-Vega-DLNA").toByteArray(StandardCharsets.UTF_8)
                runCatching { socket.send(DatagramPacket(bytes, bytes.size, group, SSDP_PORT)) }
            }
            val deadline = System.currentTimeMillis() + 7000L
            val buffer = ByteArray(8192)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val location = parseHeaders(response)["location"]
                    if (!location.isNullOrBlank() && location.startsWith("http", true)) {
                        if (!found.containsKey(location)) found[location] = response
                    }
                } catch (_: SocketTimeoutException) {
                    // Continue until the Vega-style discovery timeout expires.
                }
            }
        }
        found.keys.mapNotNull { location ->
            runCatching { parseDomDescription(location, Engine.VEGA) }.getOrNull()
        }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
    }

    /*
     * NekoVideo-style discovery scans active IPv4 interfaces separately and joins the SSDP group
     * on each interface. That is useful on phones exposing more than one local network interface.
     */
    private fun discoverNekoVideo(context: Context): List<Device> = withMulticastLock(context, "NEKOVIDEO_SSDP") {
        val results = linkedMapOf<String, Device>()
        val interfaces = activeIpv4Interfaces().take(4)
        for ((networkInterface, localAddress) in interfaces) {
            val group = InetAddress.getByName(SSDP_ADDRESS)
            runCatching {
                MulticastSocket(null).use { socket ->
                    socket.reuseAddress = true
                    socket.bind(InetSocketAddress(localAddress, 0))
                    socket.soTimeout = 500
                    socket.networkInterface = networkInterface
                    runCatching { socket.joinGroup(group) }
                    val bytes = searchPacket(
                        "urn:schemas-upnp-org:device:MediaRenderer:1",
                        3,
                        "NekoVideo/1.x UPnP/1.0"
                    ).toByteArray(StandardCharsets.UTF_8)
                    repeat(2) {
                        socket.send(DatagramPacket(bytes, bytes.size, group, SSDP_PORT))
                        Thread.sleep(200L)
                    }
                    val deadline = System.currentTimeMillis() + 4000L
                    val buffer = ByteArray(8192)
                    while (System.currentTimeMillis() < deadline) {
                        try {
                            val packet = DatagramPacket(buffer, buffer.size)
                            socket.receive(packet)
                            val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                            val location = parseHeaders(response)["location"] ?: continue
                            val parsed = parsePullDescription(location, Engine.NEKOVIDEO)
                            if (!results.containsKey(parsed.id)) results[parsed.id] = parsed
                        } catch (_: SocketTimeoutException) {
                            // Keep receiving for the whole four-second window.
                        }
                    }
                    runCatching { socket.leaveGroup(group) }
                }
            }.onFailure { Log.d(TAG, "NekoVideo discovery on ${networkInterface.name} failed: ${it.message}") }
        }
        results.values.sortedBy { it.name.lowercase(Locale.US) }
    }

    /*
     * YAACC is built around a UPnP control point. This adapter implements its renderer-focused
     * control-point route without importing YAACC's entire app/Cling fork into SE's UI module.
     */
    private fun discoverYaacc(context: Context): List<Device> = withMulticastLock(context, "YAACC_CONTROL_POINT") {
        val found = linkedMapOf<String, String>()
        val wifiInterface = findWifiInterface()
        MulticastSocket(null).use { socket ->
            socket.reuseAddress = true
            socket.soTimeout = 550
            if (wifiInterface != null) runCatching { socket.networkInterface = wifiInterface }
            socket.bind(InetSocketAddress(0))
            val group = InetAddress.getByName(SSDP_ADDRESS)
            val targets = listOf(
                "urn:schemas-upnp-org:service:AVTransport:1",
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                "upnp:rootdevice",
                "ssdp:all"
            )
            targets.forEach { st ->
                val bytes = searchPacket(st, 4, "Linux/Android UPnP/1.0 YAACC-compatible")
                    .toByteArray(StandardCharsets.UTF_8)
                runCatching { socket.send(DatagramPacket(bytes, bytes.size, group, SSDP_PORT)) }
            }
            val deadline = System.currentTimeMillis() + 5600L
            val buffer = ByteArray(8192)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val headers = parseHeaders(response)
                    val location = headers["location"]
                    if (!location.isNullOrBlank() && location.startsWith("http", true)) {
                        if (!found.containsKey(location)) found[location] = headers["st"].orEmpty()
                    }
                } catch (_: SocketTimeoutException) {
                    // Continue until YAACC-style control point discovery finishes.
                }
            }
        }
        found.keys.mapNotNull { location ->
            runCatching { parsePullDescription(location, Engine.YAACC) }.getOrNull()
        }.distinctBy { it.id }.sortedBy { it.name.lowercase(Locale.US) }
    }

    private fun castLab(device: Device, mediaUrl: String, title: String, isLive: Boolean) {
        tryMediaProfiles(device, mediaUrl, title, isLive, listOf("video/mp4", "video/mpeg", "video/mp2t", "application/vnd.apple.mpegurl")) { d, action, args ->
            soapUrlConnection(d, action, args, "CastLab/1.6 UPnP/1.0", includeConnectionClose = false)
        }
    }

    private fun castVega(device: Device, mediaUrl: String, title: String, isLive: Boolean) {
        val urls = candidateUrls(mediaUrl, isLive)
        var failure: Throwable? = null
        for (url in urls) {
            for (mime in mimeCandidates(url, isLive, vegaOrder = true)) {
                try {
                    val didl = buildDidl(title, url, mime)
                    vegaSoap(device, "Stop", "<InstanceID>0</InstanceID>")
                    vegaSoap(device, "SetAVTransportURI",
                        "<InstanceID>0</InstanceID><CurrentURI>${xmlEscape(url)}</CurrentURI>" +
                            "<CurrentURIMetaData>${xmlEscape(didl)}</CurrentURIMetaData>")
                    Thread.sleep(500L)
                    vegaSoap(device, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
                    Log.i(TAG, "Vega DLNA sent Play to ${device.name} using $mime")
                    return
                } catch (t: Throwable) {
                    failure = t
                    Log.w(TAG, "Vega DLNA attempt failed (${device.name}, $mime): ${t.message}")
                }
            }
        }
        throw failure ?: IllegalStateException("VEGA DLNA FAILED")
    }

    private fun castNekoVideo(device: Device, mediaUrl: String, title: String, isLive: Boolean) {
        tryMediaProfiles(device, mediaUrl, title, isLive, listOf("video/mp4", "video/*", "application/octet-stream", "video/mp2t")) { d, action, args ->
            nekoSoap(d, action, args)
        }
    }

    private fun castYaacc(device: Device, mediaUrl: String, title: String, isLive: Boolean) {
        val urls = candidateUrls(mediaUrl, isLive)
        var lastError: Throwable? = null
        for (url in urls) {
            for (mime in mimeCandidates(url, isLive, vegaOrder = false)) {
                try {
                    val didl = buildDidl(title, url, mime)
                    yaaccSoap(device, "SetAVTransportURI",
                        "<InstanceID>0</InstanceID><CurrentURI>${xmlEscape(url)}</CurrentURI>" +
                            "<CurrentURIMetaData>${xmlEscape(didl)}</CurrentURIMetaData>")
                    yaaccSoap(device, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
                    Thread.sleep(900L)
                    // YAACC-style follow-up action: confirm the receiver exposes transport status.
                    yaaccSoap(device, "GetTransportInfo", "<InstanceID>0</InstanceID>")
                    Log.i(TAG, "YAACC-compatible AVTransport commands accepted by ${device.name}")
                    return
                } catch (t: Throwable) {
                    lastError = t
                    Log.w(TAG, "YAACC-compatible attempt failed (${device.name}, $mime): ${t.message}")
                }
            }
        }
        throw lastError ?: IllegalStateException("YAACC DLNA FAILED")
    }

    private fun tryMediaProfiles(
        device: Device,
        mediaUrl: String,
        title: String,
        isLive: Boolean,
        preferredMimes: List<String>,
        send: (Device, String, String) -> String
    ) {
        var lastError: Throwable? = null
        for (url in candidateUrls(mediaUrl, isLive)) {
            val mimes = (preferredMimes + mimeCandidates(url, isLive)).distinct()
            for (mime in mimes) {
                try {
                    runCatching { send(device, "Stop", "<InstanceID>0</InstanceID>") }
                    val didl = buildDidl(title, url, mime)
                    send(device, "SetAVTransportURI",
                        "<InstanceID>0</InstanceID><CurrentURI>${xmlEscape(url)}</CurrentURI>" +
                            "<CurrentURIMetaData>${xmlEscape(didl)}</CurrentURIMetaData>")
                    Thread.sleep(650L)
                    send(device, "Play", "<InstanceID>0</InstanceID><Speed>1</Speed>")
                    Log.i(TAG, "${device.engine.label} sent Play to ${device.name} using $mime")
                    return
                } catch (t: Throwable) {
                    lastError = t
                    Log.w(TAG, "${device.engine.label} attempt failed (${device.name}, $mime): ${t.message}")
                }
            }
        }
        throw lastError ?: IllegalStateException("${device.engine.label} CAST FAILED")
    }

    private fun vegaSoap(device: Device, action: String, args: String): String {
        val serviceType = device.serviceType
        val envelope = soapEnvelope(serviceType, action, args)
        val request = Request.Builder()
            .url(device.controlUrl)
            .header("SOAPAction", "$serviceType#$action")
            .header("User-Agent", "SE-Vega-DLNA/1.0 UPnP/1.0")
            .header("Connection", "close")
            .post(envelope.toRequestBody("text/xml; charset=utf-8".toMediaType()))
            .build()
        okHttp.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw IllegalStateException("HTTP ${response.code} ${action}: ${parseUpnpError(body)}")
            }
            return body
        }
    }

    private fun nekoSoap(device: Device, action: String, args: String): String =
        soapUrlConnection(device, action, args, "NekoVideo/1.x UPnP/1.0", includeConnectionClose = true)

    private fun yaaccSoap(device: Device, action: String, args: String): String =
        soapUrlConnection(device, action, args, "Linux/Android UPnP/1.0 YAACC-compatible", includeConnectionClose = true)

    private fun soapUrlConnection(
        device: Device,
        action: String,
        args: String,
        userAgent: String,
        includeConnectionClose: Boolean
    ): String {
        val envelope = soapEnvelope(device.serviceType, action, args)
        val connection = (URL(device.controlUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 7000
            readTimeout = 10000
            requestMethod = "POST"
            doOutput = true
            instanceFollowRedirects = true
            setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
            setRequestProperty("SOAPAction", "\" ${device.serviceType}#$action\"".replace("\" ", "\""))
            setRequestProperty("User-Agent", userAgent)
            if (includeConnectionClose) setRequestProperty("Connection", "close")
            setRequestProperty("Accept", "text/xml, */*")
        }
        try {
            connection.outputStream.use { it.write(envelope.toByteArray(StandardCharsets.UTF_8)) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                throw IllegalStateException("HTTP $code $action: ${parseUpnpError(body)}")
            }
            return body
        } finally {
            connection.disconnect()
        }
    }

    private fun parsePullDescription(location: String, engine: Engine): Device {
        val connection = (URL(location).openConnection() as HttpURLConnection).apply {
            connectTimeout = 5000
            readTimeout = 6500
            instanceFollowRedirects = true
            requestMethod = "GET"
            setRequestProperty("User-Agent", "${engine.name}/1.0 UPnP/1.0")
            setRequestProperty("Accept", "text/xml, application/xml, */*")
        }
        val xml = try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            require(code in 200..299) { "DEVICE DESCRIPTION HTTP $code" }
            requireNotNull(stream) { "DEVICE DESCRIPTION EMPTY" }.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }

        val parser = XmlPullParserFactory.newInstance().newPullParser()
        parser.setInput(xml.reader())
        var friendlyName = ""
        var deviceType = ""
        var urlBase: String? = null
        var currentTag = ""
        var inService = false
        var serviceType = ""
        var controlUrl = ""
        val services = mutableListOf<ServiceInfo>()
        while (parser.next() != XmlPullParser.END_DOCUMENT) {
            when (parser.eventType) {
                XmlPullParser.START_TAG -> {
                    currentTag = parser.name.substringAfter(':')
                    if (currentTag.equals("service", true)) {
                        inService = true
                        serviceType = ""
                        controlUrl = ""
                    }
                }
                XmlPullParser.TEXT -> {
                    val value = parser.text?.trim().orEmpty()
                    if (value.isBlank()) continue
                    when {
                        inService && currentTag.equals("serviceType", true) -> serviceType = value
                        inService && currentTag.equals("controlURL", true) -> controlUrl = value
                        !inService && currentTag.equals("friendlyName", true) -> if (friendlyName.isBlank()) friendlyName = value
                        !inService && currentTag.equals("deviceType", true) -> if (deviceType.isBlank()) deviceType = value
                        currentTag.equals("URLBase", true) -> urlBase = value
                    }
                }
                XmlPullParser.END_TAG -> if (parser.name.substringAfter(':').equals("service", true)) {
                    inService = false
                    if (serviceType.isNotBlank() && controlUrl.isNotBlank()) services += ServiceInfo(serviceType, controlUrl)
                }
            }
        }
        return buildDevice(location, engine, friendlyName, deviceType, urlBase, services)
    }

    private fun parseDomDescription(location: String, engine: Engine): Device {
        val xml = readDescription(location, "${engine.name}/1.0 UPnP/1.0")
        val factory = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
            runCatching { setFeature("http://apache.org/xml/features/disallow-doctype-decl", true) }
            runCatching { setFeature("http://xml.org/sax/features/external-general-entities", false) }
            runCatching { setFeature("http://xml.org/sax/features/external-parameter-entities", false) }
        }
        val doc = factory.newDocumentBuilder().parse(ByteArrayInputStream(xml.toByteArray(StandardCharsets.UTF_8)))
        fun tag(name: String): String {
            val nodes = doc.getElementsByTagName(name)
            if (nodes.length > 0) return nodes.item(0)?.textContent?.trim().orEmpty()
            val namespaced = doc.getElementsByTagNameNS("*", name)
            return if (namespaced.length > 0) namespaced.item(0)?.textContent?.trim().orEmpty() else ""
        }
        val serviceNodes = doc.getElementsByTagName("service")
        val services = mutableListOf<ServiceInfo>()
        for (i in 0 until serviceNodes.length) {
            val element = serviceNodes.item(i) as? Element ?: continue
            fun child(name: String): String {
                val direct = element.getElementsByTagName(name)
                if (direct.length > 0) return direct.item(0)?.textContent?.trim().orEmpty()
                val ns = element.getElementsByTagNameNS("*", name)
                return if (ns.length > 0) ns.item(0)?.textContent?.trim().orEmpty() else ""
            }
            val serviceType = child("serviceType")
            val control = child("controlURL")
            if (serviceType.isNotBlank() && control.isNotBlank()) services += ServiceInfo(serviceType, control)
        }
        return buildDevice(location, engine, tag("friendlyName"), tag("deviceType"), tag("URLBase").ifBlank { null }, services)
    }

    private fun readDescription(location: String, userAgent: String): String {
        val connection = (URL(location).openConnection() as HttpURLConnection).apply {
            connectTimeout = 5000
            readTimeout = 6500
            requestMethod = "GET"
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", userAgent)
            setRequestProperty("Accept", "text/xml, application/xml, */*")
        }
        try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            require(code in 200..299) { "DEVICE DESCRIPTION HTTP $code" }
            return requireNotNull(stream) { "DEVICE DESCRIPTION EMPTY" }
                .bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun buildDevice(
        location: String,
        engine: Engine,
        name: String,
        deviceType: String,
        urlBase: String?,
        services: List<ServiceInfo>
    ): Device {
        val renderer = deviceType.contains("MediaRenderer", true) ||
            services.any { it.type.contains("AVTransport", true) }
        require(renderer) { "UPNP DEVICE IS NOT A MEDIA RENDERER" }
        val av = services.firstOrNull { it.type == AVTRANSPORT_V1 }
            ?: services.firstOrNull { it.type.contains("AVTransport", true) }
            ?: throw IllegalStateException("NO AVTRANSPORT SERVICE")
        val resolved = URL(URL(urlBase?.takeIf { it.isNotBlank() } ?: location), av.control).toString()
        val host = URL(location).host
        require(host.isNotBlank()) { "DEVICE HOST MISSING" }
        return Device(
            id = "${engine.name.lowercase(Locale.US)}:$host:${resolved.lowercase(Locale.US)}",
            name = name.ifBlank { "DLNA TV ($host)" },
            host = host,
            location = location,
            controlUrl = resolved,
            serviceType = av.type,
            engine = engine
        )
    }

    private fun withMulticastLock(context: Context, tag: String, block: () -> List<Device>): List<Device> {
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = wifi?.createMulticastLock(tag)?.apply {
            setReferenceCounted(false)
            acquire()
        }
        return try {
            block()
        } finally {
            runCatching { lock?.release() }
        }
    }

    private fun findWifiInterface(): NetworkInterface? = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
            .sortedBy {
                when {
                    it.name.lowercase(Locale.US).startsWith("wlan") -> 0
                    it.name.lowercase(Locale.US).startsWith("wifi") -> 1
                    it.name.lowercase(Locale.US).startsWith("eth") -> 2
                    else -> 3
                }
            }.firstOrNull()
    }.getOrNull()

    private fun activeIpv4Interfaces(): List<Pair<NetworkInterface, Inet4Address>> = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
            .flatMap { iface ->
                iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                    .filterNot { it.isLoopbackAddress || it.isLinkLocalAddress }
                    .map { iface to it }
            }
    }.getOrDefault(emptyList())

    private fun searchPacket(target: String, mx: Int, userAgent: String): String =
        "M-SEARCH * HTTP/1.1\r\n" +
            "HOST: $SSDP_ADDRESS:$SSDP_PORT\r\n" +
            "MAN: \"ssdp:discover\"\r\n" +
            "MX: $mx\r\n" +
            "ST: $target\r\n" +
            "USER-AGENT: $userAgent\r\n\r\n"

    private fun parseHeaders(response: String): Map<String, String> = response
        .split("\r\n", "\n")
        .drop(1)
        .mapNotNull { line ->
            val colon = line.indexOf(':')
            if (colon <= 0) null
            else line.substring(0, colon).trim().lowercase(Locale.US) to line.substring(colon + 1).trim()
        }.toMap()

    private fun soapEnvelope(serviceType: String, action: String, args: String): String =
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>" +
            "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" " +
            "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
            "<u:$action xmlns:u=\"$serviceType\">$args</u:$action>" +
            "</s:Body></s:Envelope>"

    private fun buildDidl(title: String, url: String, mime: String): String =
        "<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" " +
            "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" " +
            "xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\">" +
            "<item id=\"0\" parentID=\"-1\" restricted=\"1\">" +
            "<dc:title>${xmlEscape(title.ifBlank { "SE IPTV PLAYER" })}</dc:title>" +
            "<upnp:class>object.item.videoItem</upnp:class>" +
            "<res protocolInfo=\"http-get:*:$mime:*\">${xmlEscape(url)}</res>" +
            "</item></DIDL-Lite>"

    private fun candidateUrls(url: String, isLive: Boolean): List<String> = buildList {
        add(url)
        if (isLive) {
            runCatching { GencMediaPlayer.swapLiveFormat(url, "ts") }
                .getOrNull()?.takeIf { it != url }?.let(::add)
            runCatching { GencMediaPlayer.swapLiveFormat(url, "m3u8") }
                .getOrNull()?.takeIf { it != url }?.let(::add)
        }
    }.distinct()

    private fun mimeCandidates(url: String, isLive: Boolean, vegaOrder: Boolean = false): List<String> {
        val lowerPath = runCatching { URL(url).path.lowercase(Locale.US) }.getOrDefault(url.lowercase(Locale.US))
        val likely = when {
            lowerPath.endsWith(".m3u8") -> listOf("application/vnd.apple.mpegurl", "application/x-mpegURL", "audio/mpegurl", "video/mp2t")
            lowerPath.endsWith(".ts") -> listOf("video/mp2t", "video/mpeg", "application/octet-stream")
            lowerPath.endsWith(".mp4") -> listOf("video/mp4", "video/*", "application/octet-stream")
            lowerPath.endsWith(".mkv") -> listOf("video/x-matroska", "video/*", "application/octet-stream")
            lowerPath.endsWith(".avi") -> listOf("video/avi", "video/x-msvideo", "video/*")
            else -> listOf("video/mp4", "video/*", "application/octet-stream")
        }
        val live = if (isLive) listOf("video/mp2t", "application/vnd.apple.mpegurl", "application/x-mpegURL", "video/mpeg") else emptyList()
        return (if (vegaOrder) live + likely else likely + live).distinct()
    }

    private fun xmlEscape(value: String): String = value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")

    private fun parseUpnpError(body: String): String {
        val code = Regex("<errorCode>(.*?)</errorCode>", RegexOption.IGNORE_CASE).find(body)?.groupValues?.getOrNull(1)
        val desc = Regex("<errorDescription>(.*?)</errorDescription>", RegexOption.IGNORE_CASE).find(body)?.groupValues?.getOrNull(1)
        return listOfNotNull(code, desc).joinToString(" ").ifBlank { body.take(220).ifBlank { "NO RESPONSE BODY" } }
    }
}
