#!/usr/bin/env python3
"""V100.0.187: stabilize the independent FongMi jUPnP sender and keep cast failures non-fatal."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_v187.py <SE-source-root>")

root = Path(sys.argv[1]).resolve()
payload = Path(__file__).resolve().parent / "payload"
gradle = root / "app/build.gradle"
settings = root / "settings.gradle"
player = root / "app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
manifest = root / "app/src/main/AndroidManifest.xml"
assert all(path.is_file() for path in (gradle, settings, player, manifest))

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(old, new, 1)

g = gradle.read_text(encoding="utf-8")
s = settings.read_text(encoding="utf-8")
p = player.read_text(encoding="utf-8")
m = manifest.read_text(encoding="utf-8")

assert 'versionCode 1000186' in g and 'versionName "100.0.186"' in g
assert 'rootProject.name = "SEAndroid_v100.0.186"' in s
assert "implementation 'org.jupnp:org.jupnp:3.0.5'" in g

fongmi_dir = root / "app/src/main/java/com/orbital/iptv/utils/originaldlna/fongmi"
fongmi_dir.mkdir(parents=True, exist_ok=True)
for name, target_name in (
    ("FongMiDLNAServiceConfiguration.java", "DLNAServiceConfiguration.java"),
    ("FongMiOkHttpStreamClient.java", "OkHttpStreamClient.java"),
    ("FongMiSocketHttpStreamServer.java", "SocketHttpStreamServer.java"),
):
    source = (payload / name).read_text(encoding="utf-8")
    source = source.replace(
        "package com.fongmi.android.tv.dlna;",
        "package com.orbital.iptv.utils.originaldlna.fongmi;",
        1,
    )
    if "package com.orbital.iptv.utils.originaldlna.fongmi;" not in source:
        raise SystemExit(f"Failed to rewrite package name in {name}")
    (fongmi_dir / target_name).write_text(source, encoding="utf-8")

shutil.copyfile(payload / "FongMiDlnaService.kt", fongmi_dir / "FongMiDlnaService.kt")
shutil.copyfile(payload / "FongMiDlnaEngine.kt", fongmi_dir / "FongMiDlnaEngine.kt")
shutil.copyfile(payload / "FongMiActionExecutor.java", fongmi_dir / "FongMiActionExecutor.java")

if 'android:name="android.permission.WAKE_LOCK"' not in m:
    m = replace_once(
        m,
        '    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />\n',
        '    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />\n'
        '    <uses-permission android:name="android.permission.WAKE_LOCK" />\n',
        "WAKE_LOCK permission insertion",
    )

old_result = '''                        val result = when (engine) {
                            OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.VEGA -> VegaDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, castUri, channelName, isLive)
                            OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(
                                this@PlayerActivity,
                                device,
                                castUri,
                                channelName,
                                isLive,
                                if (isLive || !::player.isInitialized) 0L else player.currentPosition.coerceAtLeast(0L)
                            )
                        }'''
new_result = '''                        val result: Result<Unit> = try {
                            when (engine) {
                                OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, castUri, channelName, isLive)
                                OriginalDlnaEngine.VEGA -> VegaDlnaEngine.cast(device, castUri, channelName, isLive)
                                OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.cast(device, castUri, channelName, isLive)
                                OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, castUri, channelName, isLive)
                                OriginalDlnaEngine.FONGMI -> FongMiDlnaEngine.cast(
                                    this@PlayerActivity,
                                    device,
                                    castUri,
                                    channelName,
                                    isLive,
                                    if (isLive || !::player.isInitialized) 0L else player.currentPosition.coerceAtLeast(0L)
                                )
                            }
                        } catch (error: Exception) {
                            android.util.Log.e("SEOriginalDLNA", "${engine.label} cast failed unexpectedly", error)
                            Result.failure(error)
                        }'''
p = replace_once(p, old_result, new_result, "safe cast operation wrapper")

old_error = '''                            if (engine == OriginalDlnaEngine.CASTLAB) {
                                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                                    .setTitle("CASTLAB DIAGNOSTICS — FAILED")'''
new_error = '''                            if (engine == OriginalDlnaEngine.CASTLAB || engine == OriginalDlnaEngine.FONGMI) {
                                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                                    .setTitle(if (engine == OriginalDlnaEngine.FONGMI) "FONGMI DLNA — FAILED" else "CASTLAB DIAGNOSTICS — FAILED")'''
p = replace_once(p, old_error, new_error, "FongMi diagnostics dialog")
p = replace_once(
    p,
    'clipboard.setPrimaryClip(android.content.ClipData.newPlainText("SE CastLab failure", errorMessage))',
    'clipboard.setPrimaryClip(android.content.ClipData.newPlainText("${engine.label} failure", errorMessage))',
    "diagnostic clipboard label",
)

g = g.replace("versionCode 1000186", "versionCode 1000187", 1)
g = g.replace('versionName "100.0.186"', 'versionName "100.0.187"', 1)
s = s.replace('rootProject.name = "SEAndroid_v100.0.186"', 'rootProject.name = "SEAndroid_v100.0.187"', 1)
gradle.write_text(g, encoding="utf-8")
settings.write_text(s, encoding="utf-8")
player.write_text(p, encoding="utf-8")
manifest.write_text(m, encoding="utf-8")

audit = root / "DLNA7_FONGMI_CRASH_FIX_V100_0_187_AUDIT.md"
audit.write_text("""# DLNA 7 (FongMi) stability fix — V100.0.187

This patch responds to the report that selecting DLNA 7 exits the player and leaves the app hung.
No Android crash log was available, so the exact runtime exception is not claimed as proven.
The inspected implementation did have several risks that are addressed here:

1. The sender was using jUPnP's generic Android stream transports, not FongMi's own Android
   transport configuration. It now uses the upstream FongMi DLNAServiceConfiguration, OkHttp
   control stream client and bounded socket HTTP stream server.
2. jUPnP device controlURI may be relative to the device description. Discovery now resolves it
   through RemoteDevice.normalizeURI(...) before exposing a TV to the cast picker.
3. Discovery holds the Android Wi-Fi multicast lock while sending SSDP search and releases it in a
   finally path. It logs whether the registry returned any renderers.
4. Binder failures/timeouts reset the failed binding, and unexpected action exceptions become a
   failure result. The player is not paused unless the cast sequence reports success.
5. The FongMi error path offers a copyable diagnostic dialog. A failure should leave the current
   video open rather than silently escaping the player coroutine.

The menu name stays DLNA 7 (FongMi); existing other cast selections are unchanged.

The build can establish compile/package integrity, not whether a Samsung TV decodes a particular URL.
After installation, verify: (a) clicking the option leaves the player open while discovery runs,
(b) the TV appears, and (c) selecting it initiates playback. If any step fails, the FongMi diagnostic
message/log should identify the failing boundary for a targeted follow-up.
""", encoding="utf-8")

notices = root / "THIRD_PARTY_NOTICES.md"
notice_text = notices.read_text(encoding="utf-8")
notice_text += """

V100.0.187 — DLNA 7 (FongMi) stability patch
--------------------------------------------
The FongMi-derived DLNA sender now also includes the upstream Android-side jUPnP transport
configuration files (DLNAServiceConfiguration, OkHttpStreamClient, SocketHttpStreamServer) from
https://github.com/FongMi/TV, inspected revision ef58e5551f9a9d8679821b38422c06373185a04e.
The project is GPL-3.0; see THIRD_PARTY_LICENSES/FONGMI-TV-GPL-3.0.txt.
"""
notices.write_text(notice_text, encoding="utf-8")

assert 'versionCode 1000187' in g and 'versionName "100.0.187"' in g
assert 'android:name="android.permission.WAKE_LOCK"' in m
assert 'device.normalizeURI(av.controlURI)' in (fongmi_dir / "FongMiDlnaEngine.kt").read_text(encoding="utf-8")
assert 'new SetAVTransportURI(service, url, metadata)' in (fongmi_dir / "FongMiActionExecutor.java").read_text(encoding="utf-8")
assert 'Result.failure(error)' in p and 'FONGMI DLNA — FAILED' in p
assert (fongmi_dir / "DLNAServiceConfiguration.java").is_file()
assert (fongmi_dir / "OkHttpStreamClient.java").is_file()
assert (fongmi_dir / "SocketHttpStreamServer.java").is_file()
assert audit.is_file()
print("V100.0.187 FongMi stability patch applied and static checks passed.")
