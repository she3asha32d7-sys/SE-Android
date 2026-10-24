package com.orbital.iptv.utils.originalcast

import android.content.Context
import android.net.Uri
import androidx.mediarouter.media.MediaRouteSelector
import androidx.mediarouter.media.MediaRouter
import com.google.android.gms.cast.CastMediaControlIntent
import com.google.android.gms.cast.MediaInfo
import com.google.android.gms.cast.MediaLoadRequestData
import com.google.android.gms.cast.MediaMetadata
import com.google.android.gms.cast.framework.CastContext
import com.google.android.gms.cast.framework.CastSession
import com.google.android.gms.cast.framework.media.RemoteMediaClient
import com.google.android.gms.common.images.WebImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.util.Locale
import kotlin.coroutines.resume

/**
 * OpenIPTV-inspired native Google Cast compatibility route. It owns a separate route picker,
 * default-receiver load request, MIME map, and Xtream live HLS-before-TS retry policy.
 * Upstream: https://github.com/Hunter-Clipper/OpenIPTV (GPL-3.0); see THIRD_PARTY_NOTICES.md.
 */
object OpenIptvCastCompatibility {
    data class Target internal constructor(
        val name: String,
        internal val route: MediaRouter.RouteInfo,
        internal val router: MediaRouter,
        internal val castContext: CastContext
    )

    suspend fun discover(context: Context): List<Target> = withContext(Dispatchers.Main.immediate) {
        val app = context.applicationContext
        val castContext = CastContext.getSharedInstance(app)
        val router = MediaRouter.getInstance(app)
        val selector = castContext.mergedSelector ?: MediaRouteSelector.Builder()
            .addControlCategory(
                CastMediaControlIntent.categoryForCast(
                    CastMediaControlIntent.DEFAULT_MEDIA_RECEIVER_APPLICATION_ID
                )
            ).build()
        val callback = object : MediaRouter.Callback() {}
        router.addCallback(selector, callback, MediaRouter.CALLBACK_FLAG_REQUEST_DISCOVERY)
        try {
            delay(4_000L)
            router.routes
                .filter { !it.isDefaultOrBluetooth && it.isEnabled && it.matchesSelector(selector) }
                .distinctBy { it.id }
                .sortedBy { it.name.lowercase(Locale.US) }
                .map { Target(it.name, it, router, castContext) }
        } finally {
            router.removeCallback(callback)
        }
    }

    suspend fun cast(
        target: Target,
        mediaUrl: String,
        title: String,
        isLive: Boolean,
        imageUrl: String?,
        startPositionMs: Long
    ): String = withContext(Dispatchers.Main.immediate) {
        target.router.selectRoute(target.route)
        val session = withTimeout(20_000L) {
            var connected: CastSession? = null
            while (connected == null) {
                val current = target.castContext.sessionManager.currentCastSession
                if (current?.isConnected == true && current.remoteMediaClient != null) {
                    connected = current
                } else {
                    delay(200L)
                }
            }
            connected!!
        }
        val client = session.remoteMediaClient
            ?: throw IllegalStateException("Cast connected, but the receiver media client is unavailable.")
        var lastError: String? = null
        for (candidate in castCandidates(mediaUrl, isLive)) {
            if (loadCandidate(client, candidate, title, isLive, imageUrl, startPositionMs)) {
                return@withContext candidate
            }
            lastError = "Receiver rejected ${contentType(candidate)} for ${Uri.parse(candidate).lastPathSegment ?: candidate}"
        }
        throw IllegalStateException(lastError ?: "The Cast receiver did not accept the media.")
    }

    private suspend fun loadCandidate(
        client: RemoteMediaClient,
        url: String,
        title: String,
        isLive: Boolean,
        imageUrl: String?,
        startPositionMs: Long
    ): Boolean = withTimeout(15_000L) {
        val metadata = MediaMetadata(
            if (isLive) MediaMetadata.MEDIA_TYPE_GENERIC else MediaMetadata.MEDIA_TYPE_MOVIE
        ).apply {
            putString(MediaMetadata.KEY_TITLE, title)
            imageUrl?.takeIf { it.startsWith("http://", true) || it.startsWith("https://", true) }?.let {
                runCatching { addImage(WebImage(Uri.parse(it))) }
            }
        }
        val info = MediaInfo.Builder(url)
            .setStreamType(if (isLive) MediaInfo.STREAM_TYPE_LIVE else MediaInfo.STREAM_TYPE_BUFFERED)
            .setContentType(contentType(url))
            .setMetadata(metadata)
            .build()
        val request = MediaLoadRequestData.Builder()
            .setMediaInfo(info)
            .setAutoplay(true)
            .setCurrentTime(startPositionMs.coerceAtLeast(0L))
            .build()
        suspendCancellableCoroutine<Boolean> { continuation ->
            client.load(request).setResultCallback { result ->
                if (continuation.isActive) continuation.resume(result.status.isSuccess)
            }
        }
    }

    /** Matches OpenIPTV's candidate policy: try the Xtream HLS form before the original live TS URL. */
    fun castCandidates(url: String, live: Boolean): List<String> {
        if (!live) return listOf(url)
        val uri = Uri.parse(url)
        val path = uri.path.orEmpty()
        if (!Regex("""/live/[^/]+/[^/]+/[^/]+\.ts$""").containsMatchIn(path)) return listOf(url)
        val hls = uri.buildUpon().path(path.dropLast(3) + ".m3u8").build().toString()
        return listOf(hls, url).distinct()
    }

    fun contentType(url: String): String {
        val path = (Uri.parse(url).path ?: url).lowercase(Locale.US)
        return when {
            path.endsWith(".m3u8") || path.endsWith(".m3u") -> "application/x-mpegURL"
            path.endsWith(".ts") -> "video/mp2t"
            path.endsWith(".mkv") -> "video/x-matroska"
            path.endsWith(".webm") -> "video/webm"
            path.endsWith(".mp3") -> "audio/mpeg"
            path.endsWith(".aac") -> "audio/aac"
            else -> "video/mp4"
        }
    }
}
