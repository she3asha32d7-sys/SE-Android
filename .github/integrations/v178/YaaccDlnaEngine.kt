package com.orbital.iptv.utils.originaldlna

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import de.yaacc.upnp.callback.ActionCallback
import de.yaacc.upnp.callback.avtransport.GetTransportInfo
import de.yaacc.upnp.callback.avtransport.Play
import de.yaacc.upnp.callback.avtransport.SetAVTransportURI
import de.yaacc.upnp.server.http.HttpRequestSender
import de.yaacc.util.YaaccLogger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.fourthline.cling.binding.xml.UDA10DeviceDescriptorBinderSAXImpl
import org.fourthline.cling.binding.xml.UDA10ServiceDescriptorBinderSAXImpl
import org.fourthline.cling.model.meta.RemoteDevice
import org.fourthline.cling.model.meta.RemoteDeviceIdentity
import org.fourthline.cling.model.meta.RemoteService
import org.fourthline.cling.model.types.UDAServiceId
import org.fourthline.cling.model.types.UDN
import org.fourthline.cling.support.model.TransportInfo
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
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request

/**
 * YAACC original UPnP model and AVTransport callback integration.
 *
 * This engine uses YAACC's GPL-3.0 ActionCallback, SetAVTransportURI, Play, GetTransportInfo,
 * HttpRequestSender and YAACC's own Cling descriptor/model fork. The small SSDP collector is the
 * SE-side bridge that delivers a discovered renderer description into those original YAACC
 * objects; it is not the shared SOAP adapter used by the four modes in V100.0.177.
 */
object YaaccDlnaEngine {
    private const val TAG = "SE-YAACC-DLNA"
    private const val GROUP = "239.255.255.250"
    private const val PORT = 1900
    private const val MX = 3
    private const val AV_SERVICE = "AVTransport"

    private val http = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(12, TimeUnit.SECONDS)
        .build()
    private val requestSender by lazy { HttpRequestSender() }
    private val remoteServices = ConcurrentHashMap<String, RemoteService>()

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        remoteServices.clear()
        val app = context.applicationContext
        val wifiManager = app.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = wifiManager?.createMulticastLock("yaacc_upnp_client")
        val found = ConcurrentHashMap<String, DlnaReceiver>()
        try {
            lock?.setReferenceCounted(false)
            if (lock != null && !lock.isHeld) lock.acquire()
            val interfaces = activeInterfaces()
            for ((networkInterface, localAddress) in interfaces) {
                discoverOnInterface(networkInterface, localAddress, found)
            }
            found.values.toList().sortedBy { it.name.lowercase(Locale.US) }
        } finally {
            runCatching { if (lock?.isHeld == true) lock.release() }
        }
    }

    suspend fun cast(receiver: DlnaReceiver, mediaUrl: String, title: String, isLive: Boolean): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                    "YAACC DLNA needs an HTTP/HTTPS media URL reachable by the TV."
                }
                val service = remoteServices[receiver.controlUrl]
                    ?: throw IllegalStateException("YAACC renderer metadata expired; rediscover the TV and retry.")
                val serviceType = service.serviceType.toString()
                val mime = dlnaMimeFor(mediaUrl, isLive)
                val didl = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="0" parentID="-1" restricted="1"><dc:title>${dlnaXmlEscape(title)}</dc:title><upnp:class>object.item.videoItem</upnp:class><res protocolInfo="http-get:*:$mime:DLNA.ORG_OP=01;DLNA.ORG_CI=0">${dlnaXmlEscape(mediaUrl)}</res></item></DIDL-Lite>"""

                val setUri = object : SetAVTransportURI(service, mediaUrl, didl, requestSender) {
                    override fun failure(
                        invocation: org.fourthline.cling.model.action.ActionInvocation<*>,
                        operation: org.fourthline.cling.model.message.UpnpResponse?,
                        defaultMsg: String?
                    ) {
                        Log.e(TAG, "YAACC SetAVTransportURI failed: ${defaultMsg ?: invocation.failure?.message}")
                    }
                }
                runCallback(setUri, "SetAVTransportURI")

                // YAACC's original Play callback sets InstanceID=0 and Speed=1, then delegates
                // SOAP marshalling, response parsing and HTTP compatibility to its Cling stack.
                val play = object : Play(service, requestSender) {
                    override fun failure(
                        invocation: org.fourthline.cling.model.action.ActionInvocation<*>,
                        operation: org.fourthline.cling.model.message.UpnpResponse?,
                        defaultMsg: String?
                    ) {
                        Log.e(TAG, "YAACC Play failed: ${defaultMsg ?: invocation.failure?.message}")
                    }
                }
                runCallback(play, "Play")

                // YAACC's GetTransportInfo callback is retained as a best-effort receiver check.
                runCatching {
                    val check = object : GetTransportInfo(service, requestSender) {
                        override fun received(
                            invocation: org.fourthline.cling.model.action.ActionInvocation<*>,
                            transportInfo: TransportInfo
                        ) {
                            Log.d(TAG, "YAACC transport state: ${transportInfo.currentTransportState}")
                        }

                        override fun failure(
                            invocation: org.fourthline.cling.model.action.ActionInvocation<*>,
                            operation: org.fourthline.cling.model.message.UpnpResponse?,
                            defaultMsg: String?
                        ) {
                            Log.d(TAG, "YAACC GetTransportInfo not available: ${defaultMsg.orEmpty()}")
                        }
                    }
                    check.run()
                }.onFailure { Log.d(TAG, "YAACC post-Play state check failed", it) }
                @Suppress("UNUSED_VARIABLE") val serviceName = serviceType
            }
        }

    private fun runCallback(callback: ActionCallback, actionName: String) {
        callback.run()
        val failure = callback.actionInvocation.failure
        if (failure != null) {
            throw IllegalStateException("$actionName failed: ${failure.message}")
        }
    }

    private fun activeInterfaces(): List<Pair<NetworkInterface, Inet4Address>> =
        runCatching {
            NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
                .filter { runCatching { it.isUp && !it.isLoopback }.getOrDefault(false) }
                .flatMap { iface ->
                    iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                        .filterNot { it.isLoopbackAddress || it.isLinkLocalAddress }
                        .map { iface to it }
                }.take(8)
        }.getOrDefault(emptyList())

    private fun discoverOnInterface(
        networkInterface: NetworkInterface,
        localAddress: Inet4Address,
        found: ConcurrentHashMap<String, DlnaReceiver>
    ) {
        val multicast = InetAddress.getByName(GROUP)
        val search = "M-SEARCH * HTTP/1.1\r\nHOST: $GROUP:$PORT\r\nMAN: \"ssdp:discover\"\r\nMX: $MX\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n"
            .toByteArray(StandardCharsets.UTF_8)
        try {
            MulticastSocket(null).use { socket ->
                socket.reuseAddress = true
                socket.bind(InetSocketAddress(localAddress, 0))
                socket.soTimeout = 500
                socket.networkInterface = networkInterface
                runCatching { socket.joinGroup(InetSocketAddress(multicast, PORT), networkInterface) }
                repeat(5) {
                    socket.send(DatagramPacket(search, search.size, multicast, PORT))
                    Thread.sleep(500L)
                }
                val deadline = System.currentTimeMillis() + 5000L
                val buffer = ByteArray(8192)
                while (System.currentTimeMillis() < deadline) {
                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        val response = String(packet.data, packet.offset, packet.length, StandardCharsets.UTF_8)
                        val headers = response.lineSequence().mapNotNull { line ->
                            val index = line.indexOf(':')
                            if (index <= 0) null else line.substring(0, index).trim().lowercase(Locale.US) to line.substring(index + 1).trim()
                        }.toMap()
                        val location = headers["location"] ?: continue
                        val usn = headers["usn"]?.substringBefore("::") ?: continue
                        val receiver = runCatching { parseWithYaacc(location, usn, localAddress) }
                            .onFailure { Log.w(TAG, "YAACC rejected renderer descriptor: $location", it) }
                            .getOrNull() ?: continue
                        found.putIfAbsent(receiver.id, receiver)
                    } catch (_: SocketTimeoutException) {
                        // A socket timeout is normal while devices reply asynchronously.
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "YAACC SSDP failed on ${networkInterface.name}", e)
        }
    }

    /**
     * Use YAACC's original descriptor binders to hydrate RemoteDevice -> RemoteService -> Action
     * model; no bespoke action name/service URL parser is used for AVTransport dispatch.
     */
    private fun parseWithYaacc(
        location: String,
        usn: String,
        localAddress: InetAddress
    ): DlnaReceiver? {
        val descriptionXml = fetchText(location) ?: return null
        val udn = UDN.valueOf(usn)
        val identity = RemoteDeviceIdentity(udn, 1800, URL(location), null, localAddress)
        val undescribed = RemoteDevice(identity)
        val device = UDA10DeviceDescriptorBinderSAXImpl().describe(undescribed, descriptionXml)
        val service = device.findServices().firstOrNull {
            it.serviceType.type.equals(AV_SERVICE, ignoreCase = true) ||
                it.serviceType.toString().contains(":AVTransport:", ignoreCase = true)
        } as? RemoteService ?: return null

        val serviceDescriptorUrl = device.normalizeURI(service.descriptorURI)
        val serviceXml = fetchText(serviceDescriptorUrl.toString()) ?: return null
        val hydrated = UDA10ServiceDescriptorBinderSAXImpl().describe(service, serviceXml) as RemoteService
        val controlUrl = device.normalizeURI(hydrated.controlURI).toString()
        val host = URL(location).host
        remoteServices[controlUrl] = hydrated
        return DlnaReceiver(
            id = udn.identifierString,
            name = device.details?.friendlyName?.takeIf { it.isNotBlank() } ?: host,
            host = host,
            descriptionUrl = location,
            controlUrl = controlUrl,
            serviceType = hydrated.serviceType.toString()
        )
    }

    private fun fetchText(url: String): String? {
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", "Android ${android.os.Build.VERSION.RELEASE} UPnP/1.0 YAACC")
            .get()
            .build()
        return http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) null else response.body?.string()
        }
    }
}
