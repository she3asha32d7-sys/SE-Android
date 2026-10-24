package com.orbital.iptv.utils.originaldlna

import android.content.ContentResolver
import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.net.BindException
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID
import java.util.concurrent.Executors
import android.net.wifi.WifiManager

/**
 * CastLab-compatible HTTP media handoff for local files.
 *
 * CastLab copies a selected phone file to its webroot and announces an HTTP URL to the TV.
 * This native implementation does the same inside SE: it copies content:// and file:// sources
 * into a private cache file first, then serves that stable file with byte ranges and the DLNA
 * response headers used by CastLab. It does not expose arbitrary app files: only the active
 * random-token URL is served.
 */
object CastLabMediaServer {
    private const val PREFERRED_PORT = 9125
    private const val ROUTE = "/"
    private const val COPY_BUFFER_SIZE = 128 * 1024
    private const val DLNA_FLAGS = "01700000000000000000000000000000"

    private data class ActiveMedia(
        val token: String,
        val file: File,
        val displayName: String,
        val mimeType: String
    )

    @Volatile private var activeMedia: ActiveMedia? = null
    @Volatile private var serverSocket: ServerSocket? = null
    private val serverLock = Any()
    private val clients = Executors.newCachedThreadPool { task ->
        Thread(task, "SE-CastLab-HTTP-Client").apply { isDaemon = true }
    }

    /**
     * Return the original URL for network media, or copy local media and return a phone-LAN URL.
     */
    suspend fun prepare(context: Context, sourceText: String, titleHint: String): String =
        withContext(Dispatchers.IO) {
            val source = sourceText.trim()
            require(source.isNotBlank()) { "No media URL or local file was provided." }
            if (source.startsWith("http://", true) || source.startsWith("https://", true)) {
                return@withContext source
            }

            val app = context.applicationContext
            val uri = toLocalUri(source)
            val displayName = queryDisplayName(app.contentResolver, uri)
                .ifBlank { uri.lastPathSegment.orEmpty() }
                .ifBlank { titleHint.ifBlank { "video.mp4" } }
            val extension = displayName.substringAfterLast('.', "").lowercase(Locale.US)
                .takeIf { it.matches(Regex("[a-z0-9]{1,10}")) }
            val safeBase = displayName.substringBeforeLast('.', displayName)
                .replace(Regex("[^A-Za-z0-9_]+"), "_")
                .trim('_')
                .take(90)
                .ifBlank { "media" }
            val safeExt = extension?.let { ".$it" } ?: ".mp4"
            val digest = sha256(uri.toString()).take(16)
            val webroot = File(app.cacheDir, "castlab-webroot")
            check(webroot.exists() || webroot.mkdirs()) { "Could not create CastLab media cache." }
            val target = File(webroot, "${safeBase}_${digest}$safeExt")

            if (!target.isFile || target.length() == 0L) {
                val temp = File(webroot, ".${target.name}.${UUID.randomUUID()}.tmp")
                try {
                    openLocalInput(app.contentResolver, uri).use { input ->
                        FileOutputStream(temp).use { output ->
                            val buffer = ByteArray(COPY_BUFFER_SIZE)
                            while (true) {
                                val count = input.read(buffer)
                                if (count < 0) break
                                if (count > 0) output.write(buffer, 0, count)
                            }
                            output.fd.sync()
                        }
                    }
                    check(temp.isFile && temp.length() > 0L) { "The local media file is empty or unreadable." }
                    if (target.exists() && !target.delete()) {
                        throw IllegalStateException("Could not replace the cached media file.")
                    }
                    check(temp.renameTo(target)) { "Could not finalize the CastLab media file." }
                } finally {
                    runCatching { if (temp.exists()) temp.delete() }
                }
            }

            val mimeType = resolveMime(app.contentResolver, uri, displayName)
            val token = UUID.randomUUID().toString().replace("-", "")
            activeMedia = ActiveMedia(target.name, target, displayName, mimeType)
            ensureServerRunning()

            val localIp = findLanIpv4(app)
            val mediaUrl = "http://$localIp:${serverSocket?.localPort ?: error("CastLab media server is not running")}/${Uri.encode(target.name)}"
            verifyServerUrl(mediaUrl, target.length())
            mediaUrl
        }

    private fun toLocalUri(source: String): Uri {
        val parsed = Uri.parse(source)
        if (!parsed.scheme.isNullOrBlank()) {
            require(parsed.scheme.equals("file", true) || parsed.scheme.equals("content", true) ||
                parsed.scheme.equals(ContentResolver.SCHEME_ANDROID_RESOURCE, true)) {
                "CastLab can serve local file/content URLs; unsupported URI scheme: ${parsed.scheme}"
            }
            return parsed
        }
        val file = File(source)
        require(file.isFile) { "The selected local file cannot be found: $source" }
        return Uri.fromFile(file)
    }

    private fun queryDisplayName(resolver: ContentResolver, uri: Uri): String {
        if (uri.scheme.equals("file", true)) return runCatching { File(uri.path.orEmpty()).name }.getOrDefault("")
        var cursor: Cursor? = null
        return try {
            cursor = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            if (cursor != null && cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index).orEmpty() else ""
            } else ""
        } catch (_: Exception) {
            ""
        } finally {
            runCatching { cursor?.close() }
        }
    }

    private fun openLocalInput(resolver: ContentResolver, uri: Uri): InputStream {
        return if (uri.scheme.equals("file", true)) {
            val path = uri.path ?: throw IllegalArgumentException("The local file URI has no path.")
            FileInputStream(File(path))
        } else {
            resolver.openInputStream(uri)
                ?: throw IllegalStateException("Android could not open the selected local media.")
        }
    }

    private fun resolveMime(resolver: ContentResolver, uri: Uri, name: String): String {
        val extension = name.substringAfterLast('.', "").lowercase(Locale.US)
        val fromExtension = when (extension) {
            "mp4", "m4v" -> "video/mp4"
            "mkv" -> "video/x-matroska"
            "avi" -> "video/x-msvideo"
            "mov" -> "video/quicktime"
            "webm" -> "video/webm"
            "ts", "mts", "m2ts" -> "video/mp2t"
            "m3u8" -> "application/vnd.apple.mpegurl"
            "mp3" -> "audio/mpeg"
            "m4a" -> "audio/mp4"
            "aac" -> "audio/aac"
            "wav" -> "audio/wav"
            else -> MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension)
        }
        val providerMime = runCatching { resolver.getType(uri) }.getOrNull()
        return fromExtension ?: providerMime ?: "application/octet-stream"
    }

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(StandardCharsets.UTF_8))
        .joinToString("") { "%02x".format(it) }

    private fun ensureServerRunning() {
        if (serverSocket?.isClosed == false) return
        synchronized(serverLock) {
            if (serverSocket?.isClosed == false) return
            val socket = ServerSocket()
            socket.reuseAddress = true
            try {
                socket.bind(InetSocketAddress(InetAddress.getByName("0.0.0.0"), PREFERRED_PORT), 32)
            } catch (_: BindException) {
                socket.bind(InetSocketAddress(InetAddress.getByName("0.0.0.0"), 0), 32)
            }
            serverSocket = socket
            Thread({ acceptLoop(socket) }, "SE-CastLab-HTTP-Server").apply {
                isDaemon = true
                start()
            }
        }
    }

    private fun acceptLoop(socket: ServerSocket) {
        while (!socket.isClosed) {
            try {
                val client = socket.accept()
                clients.execute { handleClient(client) }
            } catch (_: SocketException) {
                if (!socket.isClosed) continue else break
            } catch (_: Exception) {
                if (socket.isClosed) break
            }
        }
    }

    private fun handleClient(client: Socket) {
        client.use { socket ->
            try {
                socket.soTimeout = 15000
                val input = BufferedInputStream(socket.getInputStream())
                val output = BufferedOutputStream(socket.getOutputStream())
                val requestLine = readLine(input) ?: return
                val parts = requestLine.trim().split(Regex("\\s+"))
                if (parts.size < 2) {
                    writeError(output, 400, "Bad Request")
                    return
                }
                val method = parts[0].uppercase(Locale.US)
                val path = parts[1].substringBefore('?')
                val headers = linkedMapOf<String, String>()
                var totalHeaderBytes = 0
                while (true) {
                    val line = readLine(input) ?: break
                    totalHeaderBytes += line.length
                    if (totalHeaderBytes > 64 * 1024) {
                        writeError(output, 431, "Request Header Fields Too Large")
                        return
                    }
                    if (line.isEmpty()) break
                    val colon = line.indexOf(':')
                    if (colon > 0) headers[line.substring(0, colon).trim().lowercase(Locale.US)] =
                        line.substring(colon + 1).trim()
                }
                if (method != "GET" && method != "HEAD") {
                    output.write("HTTP/1.1 405 Method Not Allowed\r\nAllow: GET, HEAD\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".toByteArray(StandardCharsets.US_ASCII))
                    output.flush()
                    return
                }

                val current = activeMedia
                val requestedName = Uri.decode(path).removePrefix("/")
                if (current == null || requestedName != current.file.name ||
                    !current.file.isFile || current.file.length() <= 0L) {
                    writeError(output, 404, "Not Found")
                    return
                }

                val total = current.file.length()
                val rangeHeader = headers["range"]
                val range = if (rangeHeader.isNullOrBlank()) ByteRange(0L, total - 1L, false)
                    else parseRange(rangeHeader, total)
                if (range == null) {
                    val response = "HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */$total\r\nAccept-Ranges: bytes\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
                    output.write(response.toByteArray(StandardCharsets.US_ASCII))
                    output.flush()
                    return
                }

                val length = range.end - range.start + 1L
                val status = if (range.partial) "206 Partial Content" else "200 OK"
                val responseHeaders = buildString {
                    append("HTTP/1.1 $status\r\n")
                    append("Content-Type: ${current.mimeType}\r\n")
                    append("Content-Length: $length\r\n")
                    append("Accept-Ranges: bytes\r\n")
                    append("transferMode.dlna.org: Streaming\r\n")
                    append("contentFeatures.dlna.org: DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=$DLNA_FLAGS\r\n")
                    append("Access-Control-Allow-Origin: *\r\n")
                    append("Access-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n")
                    append("Connection: close\r\n")
                    if (range.partial) append("Content-Range: bytes ${range.start}-${range.end}/$total\r\n")
                    append("Content-Disposition: inline; filename=\"${current.displayName.replace(Regex("[^A-Za-z0-9_. -]"), "_").take(120)}\"\r\n")
                    append("Server: SE-CastLab/1.5 UPnP/1.0\r\n")
                    append("\r\n")
                }
                output.write(responseHeaders.toByteArray(StandardCharsets.UTF_8))
                output.flush()
                if (method == "HEAD") return

                FileInputStream(current.file).use { fileInput ->
                    val channel = fileInput.channel
                    channel.position(range.start)
                    val buffer = ByteArray(64 * 1024)
                    var remaining = length
                    while (remaining > 0) {
                        val requestSize = minOf(buffer.size.toLong(), remaining).toInt()
                        val count = fileInput.read(buffer, 0, requestSize)
                        if (count < 0) break
                        if (count > 0) {
                            output.write(buffer, 0, count)
                            remaining -= count
                        }
                    }
                    output.flush()
                }
            } catch (_: Exception) {
                // The receiver may disconnect, seek or cancel a transfer while reading.
                runCatching { socket.close() }
            }
        }
    }

    private data class ByteRange(val start: Long, val end: Long, val partial: Boolean)

    private fun parseRange(header: String, total: Long): ByteRange? {
        if (total <= 0L || !header.startsWith("bytes=", true)) return null
        val value = header.substringAfter('=').trim()
        if (value.contains(',')) return null // CastLab serves one requested byte range per response.
        val startEnd = value.split('-', limit = 2)
        if (startEnd.size != 2) return null
        val startText = startEnd[0].trim()
        val endText = startEnd[1].trim()
        return try {
            if (startText.isEmpty()) {
                val suffixLength = endText.toLong()
                if (suffixLength <= 0L) return null
                val start = (total - suffixLength).coerceAtLeast(0L)
                ByteRange(start, total - 1L, true)
            } else {
                val start = startText.toLong()
                if (start < 0L || start >= total) return null
                val requestedEnd = if (endText.isEmpty()) total - 1L else endText.toLong()
                if (requestedEnd < start) return null
                ByteRange(start, requestedEnd.coerceAtMost(total - 1L), true)
            }
        } catch (_: NumberFormatException) {
            null
        }
    }

    private fun writeError(output: BufferedOutputStream, code: Int, text: String) {
        val body = "$code $text\n".toByteArray(StandardCharsets.UTF_8)
        output.write("HTTP/1.1 $code $text\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray(StandardCharsets.US_ASCII))
        output.write(body)
        output.flush()
    }

    private fun readLine(input: BufferedInputStream): String? {
        val bytes = java.io.ByteArrayOutputStream()
        while (bytes.size() <= 16384) {
            val value = input.read()
            if (value < 0) return if (bytes.size() == 0) null else bytes.toString("US-ASCII")
            if (value == 10) break
            if (value != 13) bytes.write(value)
        }
        return bytes.toString("US-ASCII")
    }

    /**
     * Fail early with a useful message if the HTTP URL cannot be opened by the phone itself.
     * Requiring a valid byte-range response catches broken listener binding/headers before the
     * renderer is asked to play media.
     */
    private fun verifyServerUrl(mediaUrl: String, expectedLength: Long) {
        val connection = java.net.URL(mediaUrl).openConnection() as java.net.HttpURLConnection
        try {
            connection.connectTimeout = 3000
            connection.readTimeout = 3000
            connection.requestMethod = "GET"
            connection.setRequestProperty("Range", "bytes=0-0")
            connection.setRequestProperty("Connection", "close")
            val status = connection.responseCode
            val contentRange = connection.getHeaderField("Content-Range").orEmpty()
            require(status == 206 && contentRange.startsWith("bytes 0-0/$expectedLength")) {
                "CastLab local server self-test failed: HTTP $status, Content-Range='$contentRange', URL=$mediaUrl"
            }
            connection.inputStream.use { input ->
                require(input.read() >= 0) { "CastLab local server returned an empty byte-range response." }
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun findLanIpv4(context: Context): String {
        val interfaces = runCatching { NetworkInterface.getNetworkInterfaces()?.toList().orEmpty() }
            .getOrDefault(emptyList())
            .filter { iface -> runCatching { iface.isUp && !iface.isLoopback }.getOrDefault(false) }
        val preferred = interfaces.sortedBy { iface ->
            when {
                iface.name.startsWith("wlan", true) || iface.name.startsWith("wifi", true) -> 0
                iface.name.startsWith("ap", true) -> 1
                else -> 2
            }
        }
        for (iface in preferred) {
            val address = runCatching {
                iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                    .firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress && it.hostAddress?.startsWith("169.254.") != true }
            }.getOrNull()
            if (address != null) return address.hostAddress!!
        }
        val wifi = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val ip = runCatching { wifi?.connectionInfo?.ipAddress ?: 0 }.getOrDefault(0)
        if (ip != 0) {
            val address = listOf(ip and 0xff, ip shr 8 and 0xff, ip shr 16 and 0xff, ip shr 24 and 0xff)
                .joinToString(".")
            if (address != "0.0.0.0") return address
        }
        throw IllegalStateException("Could not determine the phone's Wi-Fi IP address. Connect to the same Wi-Fi as the TV and retry.")
    }
}
