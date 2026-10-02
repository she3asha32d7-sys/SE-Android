package com.orbital.iptv.utils

import android.content.Context
import android.net.wifi.WifiManager
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import org.xmlpull.v1.XmlPullParserFactory
import java.net.DatagramPacket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.net.URL
import java.nio.charset.StandardCharsets
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.LinkedHashMap
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/**
 * SE universal remote playback backend.
 *
 * DLNA/UPnP is used for standards-based MediaRenderers from multiple brands.
 * LG webOS uses the native SSAP media viewer over WebSocket when the renderer
 * identifies itself as an LG webOS TV. Google Cast stays in Media3.
 */
object LgDlnaCastManager {

    data class Device(
        val friendlyName: String,
        val location: String,
        val controlUrl: String,
        val serviceType: String
    )

    private data class SsdpHit(val location: String, val server: String)
    private data class Service(val type: String, val control: String)
    private data class Renderer(
        val friendly: String,
        val manufacturer: String,
        val model: String,
        val description: String,
        val deviceType: String,
        val base: String?,
        val services: List<Service>
    )

    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val DISCOVERY_MS = 5000L
    private const val HTTP_MS = 3500
    private const val SOAP_MS = 7000
    private const val PLAY_DELAY_MS = 900L
    private const val WS_CONNECT_MS = 6500L
    private const val WS_REGISTER_MS = 20000L
    private const val WS_REQUEST_MS = 20000L
    private const val UA = "SE IPTV PLAYER/1.0 UniversalCast"
    private const val PREFS = "se_universal_cast"
    private const val KEY_PREFIX = "webos_client_key_"

    private val trustManager = object : X509TrustManager {
        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) = Unit
        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) = Unit
        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }

    private val sslSocketFactory: SSLSocketFactory by lazy {
        SSLContext.getInstance("TLS").apply {
            init(null, arrayOf<TrustManager>(trustManager), SecureRandom())
        }.socketFactory
    }

    private val hostnameVerifier = HostnameVerifier { _, _ -> true }

    suspend fun discover(context: Context): List<Device> =
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val lock = wifi?.createMulticastLock("SE_IPTV_UNIVERSAL_DISCOVERY")?.apply {
                setReferenceCounted(false)
                acquire()
            }

            try {
                val hits = discoverSsdp()
                val devices = mutableListOf<Device>()

                for (hit in hits.take(80)) {
                    val renderer = runCatching { readRenderer(hit.location) }.getOrNull() ?: continue
                    val u = runCatching { URL(hit.location) }.getOrNull() ?: continue
                    val host = u.host
                    if (host.isBlank()) continue

                    val fingerprint = listOf(
                        renderer.friendly,
                        renderer.manufacturer,
                        renderer.model,
                        renderer.description,
                        hit.server
                    ).joinToString(" ").lowercase(Locale.US)

                    val isLg = fingerprint.contains("webos") ||
                        fingerprint.contains("lg electronics") ||
                        fingerprint.contains("lge electronics") ||
                        fingerprint.contains("lg ")

                    if (isLg) {
                        devices += Device(
                            friendlyName = renderer.friendly.ifBlank { "LG webOS TV" } + " — LG webOS",
                            location = "webos://" + host,
                            controlUrl = "webos://" + host,
                            serviceType = "WEBOS"
                        )
                    }

                    val av = renderer.services.firstOrNull { it.type.contains("AVTransport", true) }
                    if (av != null) {
                        val base = renderer.base ?: hit.location
                        val control = runCatching {
                            URL(URL(base), av.control).toString()
                        }.getOrNull()

                        if (!control.isNullOrBlank()) {
                            devices += Device(
                                friendlyName = renderer.friendly.ifBlank {
                                    renderer.manufacturer.ifBlank { "TV / Media Renderer" }
                                } + " — DLNA",
                                location = hit.location,
                                controlUrl = control,
                                serviceType = av.type
                            )
                        }
                    }
                }

                devices.distinctBy { it.serviceType + "|" + it.location + "|" + it.controlUrl }
                    .sortedWith(
                        compareBy<Device> { !it.serviceType.equals("WEBOS", true) }
                            .thenBy { it.friendlyName.lowercase(Locale.US) }
                    )
            } finally {
                runCatching { lock?.release() }
            }
        }

    suspend fun cast(
        device: Device,
        mediaUrl: String,
        title: String,
        isLive: Boolean
    ): Result<Unit> =
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "CAST REQUIRES A NETWORK-REACHABLE HTTP/HTTPS MEDIA URL"
                }

                if (device.serviceType.equals("WEBOS", true)) {
                    castWebOs(device.location.removePrefix("webos://"), mediaUrl, title)
                } else {
                    castDlna(device, mediaUrl, title, isLive)
                }
            }
        }

    private fun discoverSsdp(): List<SsdpHit> {
        val found = LinkedHashMap<String, SsdpHit>()
        val targets = listOf(
            "urn:schemas-upnp-org:service:AVTransport:1",
            "urn:schemas-upnp-org:device:MediaRenderer:1",
            "urn:lge-com:service:webos-second-screen:1",
            "upnp:rootdevice",
            "ssdp:all"
        )

        MulticastSocket(null).use { socket ->
            socket.reuseAddress = true
            socket.bind(InetSocketAddress(0))
            socket.soTimeout = 400
            chooseInterface()?.let { runCatching { socket.networkInterface = it } }

            val group = InetAddress.getByName(GROUP)
            for (target in targets) {
                val bytes = mSearch(target).toByteArray(StandardCharsets.US_ASCII)
                repeat(2) {
                    socket.send(DatagramPacket(bytes, bytes.size, group, PORT))
                    Thread.sleep(60L)
                }
            }

            val end = System.currentTimeMillis() + DISCOVERY_MS
            val buffer = ByteArray(16384)
            while (System.currentTimeMillis() < end) {
                try {
                    val packet = DatagramPacket(buffer, buffer.size)
                    socket.receive(packet)
                    val raw = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                    val h = parseHeaders(raw)
                    val location = h["location"].orEmpty()
                    if (location.startsWith("http://", true) || location.startsWith("https://", true)) {
                        found.putIfAbsent(location, SsdpHit(location, h["server"].orEmpty()))
                    }
                } catch (_: SocketTimeoutException) {
                }
            }
        }
        return found.values.toList()
    }

    private fun chooseInterface(): NetworkInterface? {
        val e = NetworkInterface.getNetworkInterfaces() ?: return null
        var fallback: NetworkInterface? = null
        while (e.hasMoreElements()) {
            val n = e.nextElement()
            val good = runCatching {
                n.isUp && !n.isLoopback && n.supportsMulticast()
            }.getOrDefault(false)
            if (!good) continue
            if (n.name.equals("wlan0", true) ||
                n.name.contains("wlan", true) ||
                n.name.contains("wifi", true)
            ) return n
            if (fallback == null) fallback = n
        }
        return fallback
    }

    private fun mSearch(st: String): String =
        "M-SEARCH * HTTP/1.1\r\n" +
            "HOST: " + GROUP + ":" + PORT + "\r\n" +
            "MAN: \"ssdp:discover\"\r\n" +
            "MX: 2\r\n" +
            "ST: " + st + "\r\n\r\n"

    private fun parseHeaders(raw: String): Map<String, String> {
        val map = HashMap<String, String>()
        raw.split("\r\n", "\n").forEach { line ->
            val i = line.indexOf(':')
            if (i > 0) {
                map[
                    line.substring(0, i).trim().lowercase(Locale.US)
                ] = line.substring(i + 1).trim()
            }
        }
        return map
    }

    private fun readRenderer(location: String): Renderer {
        val c = URL(location).openConnection() as java.net.HttpURLConnection
        c.connectTimeout = HTTP_MS
        c.readTimeout = HTTP_MS
        c.requestMethod = "GET"
        c.setRequestProperty("User-Agent", UA)

        val xml = c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        c.disconnect()

        val p = XmlPullParserFactory.newInstance().newPullParser()
        p.setInput(xml.reader())

        var friendly = ""
        var manufacturer = ""
        var model = ""
        var description = ""
        var deviceType = ""
        var base: String? = null
        var tag = ""
        var inService = false
        var serviceType = ""
        var control = ""
        val services = mutableListOf<Service>()

        fun assign(name: String, value: String) {
            when (name.substringAfter(':').lowercase(Locale.US)) {
                "friendlyname" -> friendly = value
                "manufacturer" -> manufacturer = value
                "modelname" -> model = value
                "modeldescription" -> description = value
                "devicetype" -> deviceType = value
                "urlbase" -> base = value
                "servicetype" -> if (inService) serviceType = value
                "controlurl" -> if (inService) control = value
            }
        }

        var event = p.eventType
        while (event != XmlPullParser.END_DOCUMENT) {
            when (event) {
                XmlPullParser.START_TAG -> {
                    tag = p.name
                    if (p.name.substringAfter(':').equals("service", true)) inService = true
                }
                XmlPullParser.TEXT -> {
                    val value = p.text.trim()
                    if (value.isNotBlank()) assign(tag, value)
                }
                XmlPullParser.END_TAG -> {
                    if (p.name.substringAfter(':').equals("service", true)) {
                        if (serviceType.isNotBlank() && control.isNotBlank()) {
                            services += Service(serviceType, control)
                        }
                        serviceType = ""
                        control = ""
                        inService = false
                    }
                    tag = ""
                }
            }
            event = p.next()
        }

        return Renderer(friendly, manufacturer, model, description, deviceType, base, services)
    }

    private fun castDlna(device: Device, url: String, title: String, isLive: Boolean) {
        val mediaMime = mime(url, isLive)

        // A failed Stop must never prevent loading the new URI.
        runCatching {
            soap(device.controlUrl, device.serviceType, "Stop", "<InstanceID>0</InstanceID>")
        }

        val metadata = didl(title, url, mediaMime)
        val set = runCatching {
            soap(
                device.controlUrl,
                device.serviceType,
                "SetAVTransportURI",
                "<InstanceID>0</InstanceID>" +
                    "<CurrentURI>" + xml(url) + "</CurrentURI>" +
                    "<CurrentURIMetaData>" + xml(metadata) + "</CurrentURIMetaData>"
            )
        }

        // Retry without DIDL when a renderer rejects the metadata profile.
        if (set.isFailure) {
            soap(
                device.controlUrl,
                device.serviceType,
                "SetAVTransportURI",
                "<InstanceID>0</InstanceID>" +
                    "<CurrentURI>" + xml(url) + "</CurrentURI>" +
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

    private fun soap(controlUrl: String, serviceType: String, action: String, body: String) {
        val envelope =
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>" +
                "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" " +
                "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\">" +
                "<s:Body><u:" + action + " xmlns:u=\"" + xml(serviceType) +
                "\">" + body + "</u:" + action + "></s:Body></s:Envelope>"

        val c = URL(controlUrl).openConnection() as java.net.HttpURLConnection
        c.connectTimeout = SOAP_MS
        c.readTimeout = SOAP_MS
        c.requestMethod = "POST"
        c.doOutput = true
        c.setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
        c.setRequestProperty("SOAPACTION", "\"" + serviceType + "#" + action + "\"")
        c.setRequestProperty("User-Agent", UA)
        c.outputStream.use { it.write(envelope.toByteArray(StandardCharsets.UTF_8)) }

        val code = c.responseCode
        val response = (if (code in 200..299) c.inputStream else c.errorStream)
            ?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        c.disconnect()

        if (code !in 200..299) {
            throw IllegalStateException(
                "DLNA " + action + " HTTP " + code + " " + response.take(240)
            )
        }
    }

    private fun castWebOs(context: Context, host: String, mediaUrl: String, title: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val cachedKey = prefs.getString(KEY_PREFIX + host, null)

        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .pingInterval(15, TimeUnit.SECONDS)
            .sslSocketFactory(sslSocketFactory, trustManager)
            .hostnameVerifier(hostnameVerifier)
            .build()

        var lastError: Throwable? = null

        for (endpoint in listOf("wss://" + host + ":3001/", "ws://" + host + ":3000/")) {
            val opened = CountDownLatch(1)
            val registered = CountDownLatch(1)
            val done = CountDownLatch(1)
            val error = AtomicReference<Throwable?>(null)
            val sequence = AtomicInteger(0)
            val openId = AtomicReference<String?>(null)
            val socketRef = AtomicReference<WebSocket?>()

            val listener = object : WebSocketListener() {
                override fun onOpen(ws: WebSocket, response: okhttp3.Response) {
                    socketRef.set(ws)
                    opened.countDown()

                    val permissions = JSONArray()
                    permissions.put("LAUNCH")
                    permissions.put("CONTROL_AUDIO")
                    permissions.put("CONTROL_INPUT_MEDIA_PLAYBACK")
                    permissions.put("READ_CURRENT_CHANNEL")

                    val manifest = JSONObject()
                        .put("manifestVersion", 1)
                        .put("appVersion", "1.0")
                        .put("signed", JSONObject())
                        .put("permissions", permissions)

                    val registration = JSONObject()
                        .put("pairingType", "PROMPT")
                        .put("manifest", manifest)

                    if (!cachedKey.isNullOrBlank()) {
                        registration.put("client-key", cachedKey)
                    }

                    ws.send(
                        JSONObject()
                            .put("type", "register")
                            .put("id", "register_0")
                            .put("payload", registration)
                            .toString()
                    )
                }

                override fun onMessage(ws: WebSocket, text: String) {
                    runCatching {
                        val obj = JSONObject(text)
                        when (obj.optString("type").lowercase(Locale.US)) {
                            "registered" -> {
                                val payload = obj.optJSONObject("payload")
                                val key = payload?.optString("client-key").orEmpty()
                                if (key.isNotBlank()) {
                                    prefs.edit().putString(KEY_PREFIX + host, key).apply()
                                }

                                registered.countDown()

                                val id = "open_" + sequence.incrementAndGet()
                                openId.set(id)

                                val media = JSONObject()
                                    .put("target", mediaUrl)
                                    .put("title", title.ifBlank { "SE IPTV PLAYER" })
                                    .put("description", "")
                                    .put("mimeType", mime(mediaUrl, false))
                                    .put("loop", false)

                                ws.send(
                                    JSONObject()
                                        .put("type", "request")
                                        .put("id", id)
                                        .put("uri", "ssap://media.viewer/open")
                                        .put("payload", media)
                                        .toString()
                                )
                            }

                            "response" -> {
                                if (obj.optString("id") == openId.get()) {
                                    if (obj.optBoolean("returnValue", true)) {
                                        done.countDown()
                                    } else {
                                        val payload = obj.optJSONObject("payload")
                                        error.set(
                                            IllegalStateException(
                                                payload?.optString("errorText")
                                                    ?: payload?.optString("error")
                                                    ?: "LG webOS rejected the media URL"
                                            )
                                        )
                                        done.countDown()
                                    }
                                }
                            }

                            "error" -> {
                                error.set(
                                    IllegalStateException(
                                        obj.optString("errorText").ifBlank { "LG webOS cast error" }
                                    )
                                )
                                registered.countDown()
                                done.countDown()
                            }
                        }
                    }.onFailure {
                        error.set(it)
                        registered.countDown()
                        done.countDown()
                    }
                }

                override fun onFailure(ws: WebSocket, t: Throwable, response: okhttp3.Response?) {
                    error.set(t)
                    registered.countDown()
                    done.countDown()
                }
            }

            socketRef.set(
                client.newWebSocket(
                    Request.Builder().url(endpoint).header("User-Agent", UA).build(),
                    listener
                )
            )

            if (!opened.await(WS_CONNECT_MS, TimeUnit.MILLISECONDS)) {
                lastError = error.get() ?: IllegalStateException("WEBOS CONNECTION FAILED")
                socketRef.get()?.cancel()
                continue
            }

            if (!registered.await(WS_REGISTER_MS, TimeUnit.MILLISECONDS)) {
                lastError = error.get()
                    ?: IllegalStateException("WEBOS PAIRING TIMEOUT — ACCEPT THE CONNECTION PROMPT ON THE TV")
                socketRef.get()?.cancel()
                continue
            }

            if (!done.await(WS_REQUEST_MS, TimeUnit.MILLISECONDS)) {
                lastError = error.get()
                    ?: IllegalStateException("WEBOS MEDIA REQUEST TIMEOUT")
                socketRef.get()?.cancel()
                continue
            }

            error.get()?.let {
                lastError = it
                socketRef.get()?.cancel()
                continue
            }

            socketRef.get()?.close(1000, "done")
            client.dispatcher.executorService.shutdown()
            return
        }

        client.dispatcher.executorService.shutdown()
        throw (lastError ?: IllegalStateException("LG WEBOS CAST FAILED"))
    }

    private fun mime(url: String, isLive: Boolean): String {
        val x = url.substringBefore('?').lowercase(Locale.US)
        return when {
            x.endsWith(".m3u8") || x.endsWith(".m3u") -> "application/vnd.apple.mpegurl"
            x.endsWith(".ts") || (isLive && x.contains("mpegts")) -> "video/mp2t"
            x.endsWith(".mkv") -> "video/x-matroska"
            x.endsWith(".avi") -> "video/x-msvideo"
            x.endsWith(".mov") -> "video/quicktime"
            x.endsWith(".webm") -> "video/webm"
            else -> "video/mp4"
        }
    }

    private fun didl(title: String, url: String, mime: String): String =
        "<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" " +
            "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" " +
            "xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\">" +
            "<item id=\"0\" parentID=\"-1\" restricted=\"1\">" +
            "<dc:title>" + xml(title.ifBlank { "SE IPTV PLAYER" }) + "</dc:title>" +
            "<upnp:class>object.item.videoItem</upnp:class>" +
            "<res protocolInfo=\"http-get:*:" + mime + ":\"'>" + xml(url) + "</res>" +
            "</item></DIDL-Lite>"

    private fun xml(v: String): String =
        v.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
}
