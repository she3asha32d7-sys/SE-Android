package com.orbital.iptv.utils

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.util.Log
import androidx.mediarouter.media.MediaRouter
import com.google.android.gms.cast.framework.CastContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/** Tracks the last SE-owned cast target and stops the matching receiver/session. */
object CastDisconnectManager {
    private const val TAG = "SECastDisconnect"
    private enum class Kind { DLNA_SOAP, UNIVERSAL, GOOGLE_CAST, EXTERNAL }
    private data class Active(val label: String, val kind: Kind, val controlUrl: String? = null, val serviceType: String? = null)

    @Volatile private var active: Active? = null

    fun registerDlna(label: String, controlUrl: String, serviceType: String) {
        active = Active(label, Kind.DLNA_SOAP, controlUrl, serviceType)
        Log.i(TAG, "Registered active DLNA cast route: " + label)
    }

    fun registerUniversal(label: String = "TV / DLNA") {
        active = Active(label, Kind.UNIVERSAL)
        Log.i(TAG, "Registered active SE TV route: " + label)
    }

    fun registerGoogleCast(label: String = "Google Cast") {
        active = Active(label, Kind.GOOGLE_CAST)
        Log.i(TAG, "Registered active Google Cast route: " + label)
    }

    fun registerExternal(label: String) {
        active = Active(label, Kind.EXTERNAL)
        Log.i(TAG, "Registered externally owned cast route: " + label)
    }

    fun clear() { active = null }

    suspend fun disconnect(context: Context): Result<String> {
        val snapshot = active
        val castStopped = stopGoogleCastIfConnected(context)
        if (castStopped != null) {
            active = null
            return castStopped
        }

        if (snapshot != null) {
            val attempt: Result<Unit> = when (snapshot.kind) {
                Kind.DLNA_SOAP -> stopDlna(snapshot.controlUrl.orEmpty(), snapshot.serviceType.orEmpty())
                Kind.UNIVERSAL -> UniversalCastManager.disconnectActiveCast()
                Kind.GOOGLE_CAST -> Result.failure(IllegalStateException("NO ACTIVE GOOGLE CAST SESSION WAS FOUND."))
                Kind.EXTERNAL -> stopExternalOrExplain(context, snapshot.label)
            }
            if (attempt.isSuccess) {
                if (active == snapshot) active = null
                return Result.success(snapshot.label)
            }
            return Result.failure(attempt.exceptionOrNull() ?: IllegalStateException("DISCONNECT FAILED"))
        }

        val routeStopped = stopSelectedMediaRoute(context)
        if (routeStopped != null) return routeStopped

        if (UniversalCastManager.getActiveCastDevice() != null) {
            val result = UniversalCastManager.disconnectActiveCast()
            if (result.isSuccess) return Result.success("TV / DLNA")
            return Result.failure(result.exceptionOrNull() ?: IllegalStateException("TV / DLNA DISCONNECT FAILED"))
        }
        return Result.failure(IllegalStateException("NO ACTIVE CAST SESSION WAS FOUND."))
    }

    private suspend fun stopGoogleCastIfConnected(context: Context): Result<String>? =
        withContext(Dispatchers.Main.immediate) {
            val castContext = runCatching { CastContext.getSharedInstance(context.applicationContext) }.getOrNull()
                ?: return@withContext null
            val sessions = castContext.sessionManager
            val session = sessions.currentCastSession?.takeIf { it.isConnected }
                ?: return@withContext null
            runCatching {
                runCatching { session.remoteMediaClient?.stop() }
                sessions.endCurrentSession(true)
            }.fold(
                onSuccess = { Result.success("GOOGLE CAST") },
                onFailure = { Result.failure(it) }
            )
        }

    private suspend fun stopSelectedMediaRoute(context: Context): Result<String>? =
        withContext(Dispatchers.Main.immediate) {
            val disconnected = runCatching {
                val router = MediaRouter.getInstance(context.applicationContext)
                val route = router.selectedRoute
                if (route.isDefault) false else {
                    router.unselect(MediaRouter.UNSELECT_REASON_STOPPED)
                    true
                }
            }.onFailure { Log.d(TAG, "No selectable app-owned route found", it) }.getOrDefault(false)
            if (disconnected) Result.success("MEDIA ROUTE") else null
        }

    private suspend fun stopDlna(controlUrl: String, serviceType: String): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            require(controlUrl.startsWith("http://", true) || controlUrl.startsWith("https://", true)) {
                "THE ACTIVE TV CONTROL URL IS INVALID."
            }
            require(serviceType.contains("AVTransport", ignoreCase = true)) {
                "THE ACTIVE TV AVTRANSPORT SERVICE IS INVALID."
            }
            val envelope = """<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:Stop xmlns:u="$serviceType"><InstanceID>0</InstanceID></u:Stop></s:Body></s:Envelope>"""
            val connection = (URL(controlUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = 4500
                readTimeout = 6500
                requestMethod = "POST"
                doOutput = true
                useCaches = false
                setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
                setRequestProperty("SOAPAction", "\"$serviceType#Stop\"")
                setRequestProperty("Connection", "close")
            }
            try {
                connection.outputStream.use { it.write(envelope.toByteArray(StandardCharsets.UTF_8)) }
                val code = connection.responseCode
                val response = runCatching {
                    val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                    stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }.orEmpty()
                }.getOrDefault("")
                require(code in 200..299) {
                    "TV DISCONNECT FAILED (HTTP " + code + "): " + response.take(700)
                }
            } finally {
                connection.disconnect()
            }
        }
    }

    private suspend fun stopExternalOrExplain(context: Context, label: String): Result<Unit> =
        when {
            label.contains("WEB VIDEO CASTER", true) -> Result.failure(
                IllegalStateException("WEB VIDEO CASTER OWNS THIS CAST SESSION AND DOES NOT EXPOSE A PUBLIC DISCONNECT COMMAND TO SE IPTV PLAYER. OPEN WEB VIDEO CASTER AND PRESS ITS STOP CASTING / DISCONNECT CONTROL.")
            )
            label.contains("WIRELESS DISPLAY", true) || label.contains("SCREEN MIRROR", true) -> {
                val opened = withContext(Dispatchers.Main.immediate) {
                    runCatching {
                        context.startActivity(Intent(Settings.ACTION_CAST_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }.isSuccess
                }
                Result.failure(IllegalStateException(if (opened) {
                    "ANDROID OWNS THIS SYSTEM MIRRORING SESSION. THE SYSTEM CAST SETTINGS WERE OPENED; DISCONNECT THE ACTIVE DISPLAY THERE."
                } else {
                    "ANDROID OWNS THIS SYSTEM MIRRORING SESSION. DISCONNECT IT FROM THE PHONE'S SYSTEM CAST / SMART VIEW PANEL."
                }))
            }
            else -> Result.failure(IllegalStateException("THIS CAST SESSION IS CONTROLLED BY AN EXTERNAL APP. DISCONNECT IT FROM THAT APP."))
        }
}
