#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
repo=Path(__file__).resolve().parents[3]
up=Path(os.environ.get("UPSTREAM_ROOT","/tmp/upstream"))
java=root/"app/src/main/java"
player=java/"com/orbital/iptv/ui/player/PlayerActivity.kt"
gradle=root/"app/build.gradle"
settings=root/"settings.gradle"
assert player.is_file() and gradle.is_file() and settings.is_file()
for n in ("CastLab","Vega","NekoVideo","YAACC"): assert (up/n).is_dir(), n
dst=java/"com/orbital/iptv/utils/originaldlna"
dst.mkdir(parents=True,exist_ok=True)
for n in ("DlnaReceiver.kt","CastLabDlnaEngine.kt","VegaDlnaEngine.kt","NekoVideoDlnaEngine.kt","YaaccDlnaEngine.kt"):
    shutil.copy2(repo/".github/integrations/v178"/n,dst/n)

# Keep source snapshots; generated caches/build output are excluded.
tp=root/"third_party_sources"; tp.mkdir(exist_ok=True)
def ignore(_dir,names):
    denied={".git",".gradle",".idea","node_modules","build",".expo","Pods","coverage","DerivedData","screenshots",".yarn"}
    return [n for n in names if n in denied or n.endswith((".apk",".aab",".jks",".keystore"))]
for n in ("CastLab","Vega","NekoVideo","YAACC"):
    target=tp/n
    if target.exists(): shutil.rmtree(target)
    shutil.copytree(up/n,target,ignore=ignore)

# Compile YAACC's original Cling model/binders and ActionCallback SOAP pipeline in the native SE app.
y=up/"YAACC/yaacc/src/main/java"
for sub in ("org/fourthline/cling/model","org/fourthline/cling/binding","org/fourthline/cling/support","org/seamless"):
    assert (y/sub).is_dir(),sub
    target=java/sub
    if target.exists(): shutil.rmtree(target)
    shutil.copytree(y/sub,target)
for rel in ("org/fourthline/cling/transport/impl/SOAPActionProcessorImpl.java",
            "org/fourthline/cling/transport/spi/SOAPActionProcessor.java",
            "de/yaacc/upnp/callback/ActionCallback.java",
            "de/yaacc/upnp/callback/avtransport/SetAVTransportURI.java",
            "de/yaacc/upnp/callback/avtransport/Play.java",
            "de/yaacc/upnp/callback/avtransport/GetTransportInfo.java",
            "de/yaacc/upnp/protocol/SendingAsync.java",
            "de/yaacc/upnp/protocol/SendingSync.java",
            "de/yaacc/upnp/protocol/sync/SendingAction.java",
            "de/yaacc/upnp/server/http/HttpRequestSender.java",
            "de/yaacc/upnp/model/message/header/ContentLengthHeader.java",
            "de/yaacc/util/YaaccLogger.java"):
    src=y/rel
    assert src.is_file(),str(src)
    target=java/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,target)

g=gradle.read_text()
assert 'versionCode 1000176' in g and 'versionName "100.0.176"' in g
if "org.apache.httpcomponents.client5:httpclient5:5.2.1" not in g:
    at=g.rfind("\n}")
    assert at>=0
    g=g[:at]+"\n    // YAACC original HTTP sender. Keep pinned to Android-compatible 5.2.x.\n    implementation 'org.apache.httpcomponents.client5:httpclient5:5.2.1'\n    implementation 'org.apache.httpcomponents.core5:httpcore5:5.2'\n"+g[at:]
g=g.replace("versionCode 1000176","versionCode 1000178",1).replace('versionName "100.0.176"','versionName "100.0.178"',1)
pack_old="packagingOptions {\\n        pickFirst '**/libc++_shared.so'\\n    }"
pack_new="packagingOptions {\\n        pickFirst '**/libc++_shared.so'\\n        exclude 'META-INF/DEPENDENCIES'\\n        exclude 'META-INF/LICENSE'\\n        exclude 'META-INF/LICENSE.txt'\\n        exclude 'META-INF/NOTICE'\\n        exclude 'META-INF/NOTICE.txt'\\n    }"
assert pack_old in g, "Could not locate packagingOptions block"
g=g.replace(pack_old,pack_new,1)
gradle.write_text(g)
s=settings.read_text()
assert 'rootProject.name = "SEAndroid_v100.0.176"' in s
settings.write_text(s.replace('rootProject.name = "SEAndroid_v100.0.176"','rootProject.name = "SEAndroid_v100.0.178"',1))

p=player.read_text()
anchor="import com.orbital.iptv.utils.TdmCompatibleDlnaManager"
assert anchor in p
for imp in (
"import com.orbital.iptv.utils.originaldlna.CastLabDlnaEngine",
"import com.orbital.iptv.utils.originaldlna.DlnaReceiver",
"import com.orbital.iptv.utils.originaldlna.NekoVideoDlnaEngine",
"import com.orbital.iptv.utils.originaldlna.VegaDlnaEngine",
"import com.orbital.iptv.utils.originaldlna.YaaccDlnaEngine"):
    if imp not in p: p=p.replace(anchor,anchor+"\n"+imp,1); anchor=imp
old='arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast")'
new='arrayOf("TV", "DLNA", "DLNA 2", "Screen Mirror / Wireless Display", "Web Video Caster", "Google Cast", "DLNA 3 (CastLab)", "DLNA 4 (Vega)", "DLNA 5 (NekoVideo)", "DLNA 6 (YAACC)")'
assert old in p
p=p.replace(old,new,1)
old_dispatch='''                    5 -> binding.btnCast.performClick()
                }'''
new_dispatch='''                    5 -> binding.btnCast.performClick()
                    6 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.CASTLAB)
                    7 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.VEGA)
                    8 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.NEKOVIDEO)
                    9 -> showOriginalDlnaChooser(mediaUri, OriginalDlnaEngine.YAACC)
                }'''
assert old_dispatch in p
p=p.replace(old_dispatch,new_dispatch,1)
marker="    private fun showCastDeviceChooser(mediaUri: String, dlnaOnly: Boolean) {"
assert marker in p
helper='''    private enum class OriginalDlnaEngine(val label: String) {
        CASTLAB("DLNA 3 (CastLab)"),
        VEGA("DLNA 4 (Vega)"),
        NEKOVIDEO("DLNA 5 (NekoVideo)"),
        YAACC("DLNA 6 (YAACC)")
    }

    private fun showOriginalDlnaChooser(mediaUri: String, engine: OriginalDlnaEngine) {
        val searching = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle(engine.label).setMessage("SEARCHING FOR DLNA TVs...")
            .setNegativeButton("CANCEL", null).create()
        searching.show()
        lifecycleScope.launch {
            val devices: List<DlnaReceiver> = try {
                when (engine) {
                    OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.discover(this@PlayerActivity)
                    OriginalDlnaEngine.VEGA -> VegaDlnaEngine.discover(this@PlayerActivity)
                    OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.discover(this@PlayerActivity)
                    OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.discover(this@PlayerActivity)
                }
            } catch (error: Exception) {
                android.util.Log.w("SEOriginalDLNA", "DOLLAR{engine.label} discovery failed", error)
                emptyList()
            }
            if (isFinishing || isDestroyed) { searching.dismiss(); return@launch }
            searching.dismiss()
            if (devices.isEmpty()) {
                AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                    .setTitle(engine.label)
                    .setMessage("NO DLNA TVs FOUND. Make sure the phone and TV share the same Wi-Fi network and retry.")
                    .setPositiveButton("OK", null).show()
                return@launch
            }
            AlertDialog.Builder(this@PlayerActivity, ThemeManager.dialogStyle())
                .setTitle("DOLLAR{engine.label} — SELECT TV")
                .setItems(devices.map { "DOLLAR{it.name}  (DOLLAR{it.host})" }.toTypedArray()) { _, selected ->
                    val device = devices[selected]
                    lifecycleScope.launch {
                        val result = when (engine) {
                            OriginalDlnaEngine.CASTLAB -> CastLabDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.VEGA -> VegaDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.NEKOVIDEO -> NekoVideoDlnaEngine.cast(device, mediaUri, channelName, isLive)
                            OriginalDlnaEngine.YAACC -> YaaccDlnaEngine.cast(device, mediaUri, channelName, isLive)
                        }
                        if (result.isSuccess) {
                            if (::localPlayer.isInitialized) localPlayer.pause()
                            Toast.makeText(this@PlayerActivity, "DOLLAR{engine.label} CASTING TO DOLLAR{device.name}", Toast.LENGTH_SHORT).show()
                            showGencOverlay()
                        } else {
                            Toast.makeText(this@PlayerActivity, engine.label + " FAILED: " + (result.exceptionOrNull()?.message ?: "UNKNOWN ERROR"), Toast.LENGTH_LONG).show()
                        }
                    }
                }.setNegativeButton("CANCEL", null).show()
        }
    }

'''
helper=helper.replace("DOLLAR{","$")
p=p.replace(marker,helper+marker,1)
player.write_text(p)

lic_src=repo/"LICENSE"
lic=lic_src.read_text(errors="replace")
assert "GNU GENERAL PUBLIC LICENSE" in lic
shutil.copy2(lic_src,root/"LICENSE")
lp=root/"THIRD_PARTY_LICENSES"; lp.mkdir(exist_ok=True)
for n in ("CASTLAB-GPL-3.0.txt","NEKOVIDEO-GPL-3.0.txt","YAACC-GPL-3.0.txt"): shutil.copy2(lic_src,lp/n)
vega_lic=repo/".github/integrations/v177/VEGA-APACHE-2.0.txt"
assert vega_lic.is_file(); shutil.copy2(vega_lic,lp/"VEGA-APACHE-2.0.txt")
(root/"THIRD_PARTY_NOTICES.md").write_text("""SE IPTV PLAYER V100.0.178 — Open-source DLNA integrations
==========================================================

The original six cast choices remain unchanged and in their original order: TV, DLNA, DLNA 2,
Screen Mirror / Wireless Display, Web Video Caster and Google Cast. Four distinct routes are added:
CastLab, Vega, NekoVideo and YAACC. They are not routed through V100.0.177's OpenSourceDlnaAdapters.

CastLab: https://codeberg.org/tom79/CastLab; pinned d9afa0d47bc899886e25cc9332da5e41b4cbee71;
GNU GPL v3-only. Source snapshot is third_party_sources/CastLab.
Vega: https://github.com/vega-org/vega-app; pinned 9ccc0c8fc9f92702fd021f1b6f67e26e30988362;
Apache-2.0 at that revision. Integration derives from native-src/android/com/vega/DlnaModule.kt
and src/lib/remote/dlnaService.ts. Wi-Fi-bound SSDP, search targets, DOM description parsing and
AVTransport route are implemented in its own engine; its React Native bridge is replaced for SE.
NekoVideo: https://github.com/FellipitoPV/NekoVideo; pinned a0bfd5f36d44d4ce761fa19652f54eed18c911bb;
GNU GPL v3. Engine has its own per-IPv4-interface SSDP flow and NekoVideo-style AVTransport/DIDL
path. DLNACastManager.kt, LocalVideoServer.kt and DLNACastService.kt are included under source
snapshots. SE's current player casts HTTP/HTTPS IPTV URLs directly; local-file serving is not used.
YAACC: https://github.com/tobexyz/yaacc-code; pinned 247e0eee72811b074d2adda30482e9f3c7b567e6;
GNU GPL v3 application code. Runtime uses YAACC's original Cling model/descriptor binders,
ActionCallback, SetAVTransportURI, Play, GetTransportInfo, SendingAction and HttpRequestSender.
YAACC's app UI/service shell is omitted; the original action stack and model code are included.
Cling file headers have their own LGPL-2.1-or-later or CDDL terms.

Full useful source snapshots, attribution and license texts are preserved in this source export.
Successful CI compilation does not guarantee playback on every TV/provider/codec; a target-TV test
is still required.
""")
f=gradle.read_text()
assert 'versionCode 1000178' in f and 'versionName "100.0.178"' in f
assert new in player.read_text()
for t in ("0 -> showTvCastChooser(mediaUri)","1 -> showDlnaCastChooser(mediaUri)","2 -> showDlna2Chooser(mediaUri)","3 -> openWirelessDisplaySettings()","4 -> launchWebVideoCaster(mediaUri)","5 -> binding.btnCast.performClick()"):
    assert t in player.read_text(),t
print("V178 preflight passed.")
