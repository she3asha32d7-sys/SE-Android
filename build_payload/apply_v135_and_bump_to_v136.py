from pathlib import Path

root = Path(__import__('os').environ['ROOT'])
ua = root/'app/src/main/java/com/orbital/iptv/utils/UniversalCastManager.kt'
pa = root/'app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt'

def repl(path, old, new):
    s = path.read_text()
    if old not in s:
        raise SystemExit(f'pattern not found: {path}')
    path.write_text(s.replace(old, new, 1))

repl(ua,
'''import java.util.concurrent.TimeUnit\nimport java.util.concurrent.atomic.AtomicReference''',
'''import java.util.concurrent.TimeUnit\nimport java.util.concurrent.atomic.AtomicBoolean\nimport java.util.concurrent.atomic.AtomicReference''')
repl(ua,
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        pin: String? = null\n''',
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean\n''')
repl(ua,
'''                Protocol.DLNA -> castDlna(device, mediaUrl, title, isLive)\n                Protocol.WEBOS -> castWebOs(context, device, mediaUrl, title, isLive, pin)''',
'''                Protocol.DLNA -> castDlna(device, mediaUrl, title, isLive)\n                Protocol.WEBOS -> castWebOs(context, device, mediaUrl, title, isLive)''')
repl(ua,
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        pin: String?\n''',
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean\n''')
repl(ua,
'''                mediaUrl = mediaUrl,\n                title = title,\n                isLive = isLive,\n                pin = pin,\n                clientKey = clientKey''',
'''                mediaUrl = mediaUrl,\n                title = title,\n                isLive = isLive,\n                clientKey = clientKey''')
repl(ua,
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        pin: String?,\n        clientKey: String?\n''',
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        clientKey: String?\n''')
repl(ua,
'''                    mediaUrl = mediaUrl,\n                    title = title,\n                    isLive = isLive,\n                    pin = pin,\n                    clientKey = clientKey,\n                    endpoint = endpoint''',
'''                    mediaUrl = mediaUrl,\n                    title = title,\n                    isLive = isLive,\n                    clientKey = clientKey,\n                    endpoint = endpoint''')
repl(ua,
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        pin: String?,\n        clientKey: String?,\n        endpoint: String\n''',
'''        mediaUrl: String,\n        title: String,\n        isLive: Boolean,\n        clientKey: String?,\n        endpoint: String\n''')
repl(ua,
'''        val pairingType = AtomicReference<String?>(null)\n        val registeredKey = AtomicReference<String?>(clientKey)\n        val socketError = AtomicReference<String?>(null)\n        val pending = ConcurrentHashMap<String, PendingResponse>''',
'''        val pairingType = AtomicReference<String?>(null)\n        val registeredKey = AtomicReference<String?>(clientKey)\n        val socketError = AtomicReference<String?>(null)\n        val socketClosed = AtomicBoolean(false)\n        val pending = ConcurrentHashMap<String, PendingResponse>''')
repl(ua,
'''                        type.equals("pairing", true) -> {\n                            val state = payload?.optString("pairingType").orEmpty()\n                            if (state.isNotBlank()) pairingType.set(state)\n                            registered.countDown()\n                        }''',
'''                        type.equals("pairing", true) -> {\n                            val state = payload?.optString("pairingType").orEmpty()\n                            if (state.isNotBlank()) pairingType.set(state)\n                            // The TV prompt is only an authorization notification.\n                            // Do NOT treat it as registration; wait for the separate\n                            // `registered` message and client-key after the user presses Yes.\n                            // No PIN/code is requested or entered by this app.\n                        }''')
repl(ua,
'''            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {\n                socketError.compareAndSet(''',
'''            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {\n                socketClosed.set(true)\n                socketError.compareAndSet(''')
repl(ua,
'''            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {\n                val detail =''',
'''            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {\n                socketClosed.set(true)\n                val detail =''')
const oldPair='''            val deadline = System.currentTimeMillis() + WEBOS_PROMPT_TIMEOUT_MS\n            while (!registered.await(300L, TimeUnit.MILLISECONDS)) {\n                val pair = pairingType.get()\n                if (pair?.equals("PIN", true) == true && pin.isNullOrBlank()) {\n                    throw IllegalStateException("PAIRING_PIN_REQUIRED: ENTER THE PIN SHOWN ON THE LG TV")\n                }\n                if (System.currentTimeMillis() >= deadline) {\n                    throw IllegalStateException("PAIRING_REQUIRED: ACCEPT THE CONNECTION REQUEST ON THE LG TV")\n                }\n                val failure = socketError.get()\n                if (!failure.isNullOrBlank() && failure.contains("REGISTER", true)) {\n                    throw IllegalStateException("WEBOS REGISTER FAILED: $failure")\n                }\n                if (socketRef.get()?.send("") == false) {\n                    throw IllegalStateException("WEBOS CONNECTION CLOSED DURING PAIRING")\n                }\n            }\n\n            if (pairingType.get()?.equals("PIN", true) == true && !pin.isNullOrBlank()) {\n                sendRequest(\n                    ws,\n                    "ssap://pairing/setPin",\n                    JSONObject().put("pin", pin),\n                    7000L\n                )\n                // Wait briefly for the final registered event when the PIN flow is used.\n                registered.await(1500L, TimeUnit.MILLISECONDS)\n            }'''
const newPair='''            val deadline = System.currentTimeMillis() + WEBOS_PROMPT_TIMEOUT_MS\n            while (!registered.await(300L, TimeUnit.MILLISECONDS)) {\n                // The only user interaction used by SE IPTV PLAYER is the Yes/No\n                // confirmation displayed by the LG TV. No PIN/code is requested or entered.\n                if (System.currentTimeMillis() >= deadline) {\n                    throw IllegalStateException("PAIRING_REQUIRED: ACCEPT THE CONNECTION REQUEST ON THE LG TV")\n                }\n                if (socketClosed.get()) {\n                    throw IllegalStateException("WEBOS CONNECTION CLOSED AFTER TV PAIRING PROMPT")\n                }\n                val failure = socketError.get()\n                if (!failure.isNullOrBlank() && failure.contains("REGISTER", true)) {\n                    throw IllegalStateException("WEBOS REGISTER FAILED: $failure")\n                }\n            }'''
repl(ua, oldPair, newPair)
repl(pa,
'''            if (result.exceptionOrNull()?.message?.startsWith("PAIRING_PIN_REQUIRED:") == true) {\n                val pinInput = android.widget.EditText(this@PlayerActivity).apply {\n                    hint = "PIN FROM TV"\n                    inputType = android.text.InputType.TYPE_CLASS_NUMBER\n                    isSingleLine = true\n                }\n                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())\n                    .setTitle("LG TV PAIRING")\n                    .setMessage("Enter the PIN shown on the LG TV.")\n                    .setView(pinInput)\n                    .setPositiveButton("PAIR") { _, _ ->\n                        lifecycleScope.launch {\n                            val retry = UniversalCastManager.cast(\n                                context = this@PlayerActivity,\n                                device = device,\n                                mediaUrl = mediaUri,\n                                title = channelName,\n                                isLive = isLive,\n                                pin = pinInput.text.toString().trim()\n                            )\n                            finishCastResult(device, retry)\n                        }\n                    }\n                    .setNegativeButton("CANCEL", null)\n                    .show()\n                return@launch\n            }\n\n''', '')
repl(pa, '        lifecycleScope.launch {\n            var result = UniversalCastManager.cast(', '        lifecycleScope.launch {\n            val result = UniversalCastManager.cast(')
repl(root/'app/build.gradle','versionCode 1000134','versionCode 1000136')
repl(root/'app/build.gradle','versionName "100.0.134"','versionName "100.0.136"')
repl(root/'settings.gradle','SEAndroid_v100.0.134','SEAndroid_v100.0.136')
