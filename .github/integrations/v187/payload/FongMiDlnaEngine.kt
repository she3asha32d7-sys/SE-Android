package com.orbital.iptv.utils.originaldlna.fongmi

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import android.net.wifi.WifiManager
import android.util.Log
import com.orbital.iptv.utils.originaldlna.DlnaReceiver
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.jupnp.android.AndroidUpnpService
import org.jupnp.controlpoint.ControlPoint
import org.jupnp.model.message.header.STAllHeader
import org.jupnp.model.meta.RemoteDevice
import org.jupnp.model.meta.RemoteService
import org.jupnp.model.types.UDADeviceType
import org.jupnp.model.types.UDAServiceType
import org.jupnp.support.contentdirectory.DIDLParser
import org.jupnp.support.model.DIDLContent
import org.jupnp.support.model.ProtocolInfo
import org.jupnp.support.model.Res
import org.jupnp.support.model.item.VideoItem
import java.net.URL
import java.util.concurrent.CompletableFuture
import java.util.Locale
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Independent jUPnP sender modeled on FongMi/TV's mobile DLNACastManager and DLNACast sequence.
 * It does not route through SE's Cling, Vega, YAACC, TDM, NekoVideo, or CastLab engines.
 * Upstream: https://github.com/FongMi/TV (GPL-3.0); see THIRD_PARTY_NOTICES.md.
 */
object FongMiDlnaEngine {
    private const val TAG = "SE-FongMi-DLNA"
    private val rendererType = UDADeviceType("MediaRenderer", 1)
    private val avTransportType = UDAServiceType("AVTransport", 1)
    private val lock = Any()

    @Volatile private var service: AndroidUpnpService? = null
    private var pendingService: CompletableDeferred<AndroidUpnpService>? = null
    private var bound = false
    @Volatile private var appContext: Context? = null

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            val connected = binder as? AndroidUpnpService
            if (connected == null) {
                synchronized(lock) {
                    pendingService?.completeExceptionally(
                        IllegalStateException("FongMi jUPnP service returned an invalid binder")
                    )
                    pendingService = null
                }
                return
            }
            service = connected
            synchronized(lock) {
                pendingService?.complete(connected)
                pendingService = null
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            Log.w(TAG, "jUPnP service disconnected")
            service = null
            synchronized(lock) {
                // Android retains a live binding after a temporary disconnection and may reconnect
                // this same ServiceConnection. Do not bind a duplicate connection here.
                if (pendingService == null || pendingService?.isCompleted == true) {
                    pendingService = CompletableDeferred()
                }
            }
        }
    }

    private fun requestService(context: Context): Deferred<AndroidUpnpService> {
        val app = context.applicationContext
        synchronized(lock) {
            appContext = app
            service?.let { return CompletableDeferred(it) }
            val waiting = pendingService?.takeIf { !it.isCompleted }
                ?: CompletableDeferred<AndroidUpnpService>().also { pendingService = it }
            if (!bound) {
                bound = app.bindService(
                    Intent(app, FongMiDlnaService::class.java),
                    connection,
                    Context.BIND_AUTO_CREATE
                )
                if (!bound) {
                    waiting.completeExceptionally(
                        IllegalStateException("Could not bind the FongMi DLNA service")
                    )
                    pendingService = null
                }
            }
            return waiting
        }
    }

    private suspend fun upnp(context: Context): AndroidUpnpService {
        try {
            return withTimeout(18_000L) { requestService(context).await() }
        } catch (error: Exception) {
            Log.e(TAG, "Timed out or failed while connecting to the jUPnP service", error)
            resetFailedBinding(context)
            throw error
        }
    }

    private fun resetFailedBinding(context: Context) {
        synchronized(lock) {
            val app = appContext ?: context.applicationContext
            if (bound) {
                runCatching { app.unbindService(connection) }
                    .onFailure { Log.d(TAG, "Service unbind after failed bind is harmless: ${it.message}") }
            }
            bound = false
            service = null
            pendingService?.cancel()
            pendingService = null
        }
    }

    suspend fun discover(context: Context): List<DlnaReceiver> = withContext(Dispatchers.IO) {
        val upnp = upnp(context)
        val control = upnp.controlPoint ?: throw IllegalStateException("jUPnP control point is unavailable.")
        val app = context.applicationContext
        val wifi = app.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val multicastLock = runCatching { wifi?.createMulticastLock("se_fongmi_dlna_discovery") }.getOrNull()
        try {
            multicastLock?.setReferenceCounted(false)
            if (multicastLock != null && !multicastLock.isHeld) multicastLock.acquire()
            Log.d(TAG, "Sending SSDP discovery request")
            control.search(STAllHeader())
            // Samsung renderers can answer slowly while their device/service descriptors are hydrated.
            delay(4_500L)
            val receivers = upnp.registry.getDevices(rendererType)
                .mapNotNull { raw ->
                    val device = raw as? RemoteDevice ?: return@mapNotNull null
                    val av = device.findService(avTransportType) ?: return@mapNotNull null
                    val description = device.identity.descriptorURL?.toString().orEmpty()
                    val host = runCatching { URL(description).host }.getOrDefault("")
                    val name = device.details?.friendlyName.orEmpty().ifBlank {
                        host.ifBlank { "DLNA TV" }
                    }
                    // controlURI is often relative to the renderer description; normalize it before use.
                    val controlUrl = runCatching {
                        device.normalizeURI(av.controlURI).toURL().toString()
                    }.getOrDefault("")
                    if (host.isBlank() || controlUrl.isBlank()) {
                        Log.w(TAG, "Skipping incomplete renderer descriptor: ${device.displayString}")
                        return@mapNotNull null
                    }
                    DlnaReceiver(
                        id = device.identity.udn.identifierString,
                        name = name,
                        host = host,
                        descriptionUrl = description,
                        controlUrl = controlUrl,
                        serviceType = av.serviceType.toString()
                    )
                }
                .distinctBy { it.id }
                .sortedBy { it.name.lowercase(Locale.US) }
            Log.i(TAG, "Discovery returned ${receivers.size} DLNA renderer(s)")
            receivers
        } finally {
            runCatching { if (multicastLock?.isHeld == true) multicastLock.release() }
                .onFailure { Log.d(TAG, "Multicast lock release failed", it) }
        }
    }

    suspend fun cast(
        context: Context,
        receiver: DlnaReceiver,
        mediaUrl: String,
        title: String,
        isLive: Boolean,
        positionMs: Long = 0L
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            require(mediaUrl.startsWith("http://", true) || mediaUrl.startsWith("https://", true)) {
                "FongMi DLNA requires an HTTP/HTTPS media URL reachable by the TV."
            }
            val upnp = upnp(context)
            val device = upnp.registry.getDevices(rendererType)
                .filterIsInstance<RemoteDevice>()
                .firstOrNull { it.identity.udn.identifierString == receiver.id }
                ?: throw IllegalStateException(
                    "FongMi could not resolve the selected TV again. Rediscover and retry."
                )
            val av = device.findService(avTransportType)
                ?: throw IllegalStateException("The selected TV does not expose AVTransport:1.")
            val control = upnp.controlPoint
                ?: throw IllegalStateException("FongMi jUPnP control point is unavailable.")
            val metadata = buildMetadata(title, mediaUrl)
            setUri(control, av, mediaUrl, metadata)
            play(control, av)
            if (!isLive && positionMs > 2_000L) seek(control, av, positionMs)
        }
    }

    private fun buildMetadata(title: String, mediaUrl: String): String {
        val content = DIDLContent()
        content.addItem(
            VideoItem(
                "0", "-1", title, "",
                Res(ProtocolInfo("http-get:*:video/*:*"), 0L, mediaUrl)
            )
        )
        return runCatching { DIDLParser().generate(content) }.getOrElse { "" }
    }

    private suspend fun awaitAction(future: CompletableFuture<Void>) {
        withTimeout(18_000L) {
            suspendCancellableCoroutine<Unit> { continuation ->
                future.whenComplete { _, error ->
                    if (continuation.isActive) {
                        val cause = error?.cause ?: error
                        if (cause == null) continuation.resume(Unit)
                        else continuation.resumeWithException(cause)
                    }
                }
            }
        }
    }

    private suspend fun setUri(
        control: ControlPoint,
        service: RemoteService,
        url: String,
        metadata: String
    ) = awaitAction(FongMiActionExecutor.setUri(control, service, url, metadata))

    private suspend fun play(control: ControlPoint, service: RemoteService) =
        awaitAction(FongMiActionExecutor.play(control, service))

    private suspend fun seek(control: ControlPoint, service: RemoteService, positionMs: Long) =
        awaitAction(FongMiActionExecutor.seek(control, service, formatMs(positionMs)))

    private fun formatMs(ms: Long): String {
        val total = (ms / 1000L).coerceAtLeast(0L)
        return String.format(
            Locale.US,
            "%02d:%02d:%02d",
            total / 3600L,
            (total % 3600L) / 60L,
            total % 60L
        )
    }
}
