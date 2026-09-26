from pathlib import Path
import re

ROOT = Path(".")

# 1) Put the VLCVideoLayout in the Activity XML from the start.
layout = ROOT / "app/src/main/res/layout/activity_engine_player.xml"
s = layout.read_text()
old_layout = '''    <FrameLayout
        android:id="@+id/engine_player_container"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
'''
new_layout = '''    <org.videolan.libvlc.util.VLCVideoLayout
        android:id="@+id/engine_player_container"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:background="#000000" />
'''
if old_layout in s:
    s = s.replace(old_layout, new_layout, 1)
elif "org.videolan.libvlc.util.VLCVideoLayout" not in s:
    raise SystemExit("engine_player_container layout anchor not found")
layout.write_text(s)

# 2) Make VLC attach only after the layout is measured and use TextureView.
vlc = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/VlcPlaybackEngine.kt"
s = vlc.read_text()
if "private var viewsAttached = false" not in s:
    s = s.replace(
        "    private var currentContainer: ViewGroup? = null\n",
        "    private var currentContainer: ViewGroup? = null\n    private var viewsAttached = false\n",
        1
    )

start = s.find("    override fun attach(container: ViewGroup) {")
end = s.find("    override fun prepare(url: String, startPositionMs: Long) {", start)
if start < 0 or end < 0:
    raise SystemExit("attach/prepare anchors not found")

attach_block = '''    override fun attach(container: ViewGroup) {
        currentContainer = container
        val layout = container as? VLCVideoLayout
            ?: throw IllegalArgumentException("Engine container must be VLCVideoLayout")
        videoLayout = layout
        attachWhenReady(layout, 0)
    }

    private fun attachWhenReady(layout: VLCVideoLayout, retry: Int) {
        if (released || mediaPlayer == null || viewsAttached) return

        val ready = layout.isShown && layout.width > 0 && layout.height > 0
        if (!ready) {
            if (retry >= 40) {
                val error = IllegalStateException(
                    "VLCVideoLayout was not ready: " + layout.width + "x" + layout.height
                )
                log("attachViews timeout: " + layout.width + "x" + layout.height)
                errorCallback?.invoke(error)
                return
            }
            handler.postDelayed({ attachWhenReady(layout, retry + 1) }, 50L)
            return
        }

        try {
            // TextureView avoids the independent SurfaceView compositor path that
            // was producing visible on/off flicker on the target device.
            mediaPlayer?.attachViews(layout, null, false, true)
            mediaPlayer?.setVideoScale(MediaPlayer.ScaleType.SURFACE_BEST_FIT)
            viewsAttached = true
            log("attachViews success after layout ready: " + layout.width + "x" + layout.height)
        } catch (t: Throwable) {
            log("attachViews failed: " + t)
            if (retry < 40) {
                handler.postDelayed({ attachWhenReady(layout, retry + 1) }, 100L)
            } else {
                errorCallback?.invoke(t)
            }
        }
    }

    private fun detachViews() {
        if (viewsAttached) {
            try { mediaPlayer?.detachViews() } catch (t: Throwable) {
                log("detachViews: " + t.message)
            }
        }
        viewsAttached = false
        videoLayout = null
    }

'''
s = s[:start] + attach_block + s[end:]

# 3) Replace release() completely and keep cleanup ordering safe.
start = s.find("    override fun release() {")
if start < 0:
    raise SystemExit("release anchor not found")
end = s.rfind("\n}")
assert end > start
release_block = '''    override fun release() {
        released = true
        handler.removeCallbacksAndMessages(null)
        detachViews()
        try { mediaPlayer?.stop() } catch (_: Throwable) {}
        try { mediaPlayer?.setEventListener(null) } catch (_: Throwable) {}
        try { mediaPlayer?.release() } catch (_: Throwable) {}
        try { libVlc?.release() } catch (_: Throwable) {}
        mediaPlayer = null
        libVlc = null
        currentContainer = null
        currentUrl = null
        pendingStartPosition = -1L
    }
'''
s = s[:start] + release_block + s[end:]
vlc.write_text(s)

# 4) Version bump.
g = ROOT / "app/build.gradle"
gs = g.read_text()
gs = re.sub(r'versionCode\s+\d+', 'versionCode 1000031', gs, count=1)
gs = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.31"', gs, count=1)
g.write_text(gs)

print("V100.0.31 VLC surface lifecycle fix applied")
