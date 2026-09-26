from pathlib import Path
import re

ROOT = Path(".")

# Make the engine host a real VLCVideoLayout from XML instead of creating/attaching
# a new VLCVideoLayout immediately after adding it to the hierarchy.
layout = ROOT / "app/src/main/res/layout/activity_engine_player.xml"
s = layout.read_text()
old = '''    <FrameLayout
        android:id="@+id/engine_player_container"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
'''
new = '''    <org.videolan.libvlc.util.VLCVideoLayout
        android:id="@+id/engine_player_container"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:background="#000000" />
'''
assert old in s
s = s.replace(old, new, 1)
layout.write_text(s)

# Replace the V30 VLC engine with a surface-safe implementation.
vlc = ROOT / "app/src/main/java/com/orbital/iptv/ui/player/VlcPlaybackEngine.kt"
s = vlc.read_text()

s = s.replace("import android.widget.FrameLayout\n", "", 1)
s = s.replace("    private var currentContainer: ViewGroup? = null\n", "    private var currentContainer: ViewGroup? = null\n    private var viewsAttached = false\n", 1)

start = s.find("    override fun attach(container: ViewGroup) {")
end = s.find("    override fun prepare(url: String, startPositionMs: Long) {", start)
assert start >= 0 and end > start
attach_block = '''    override fun attach(container: ViewGroup) {
        currentContainer = container
        val layout = container as? VLCVideoLayout
            ?: throw IllegalArgumentException("Engine container must be VLCVideoLayout")
        videoLayout = layout
        attachWhenReady(layout, 0)
    }

    private fun attachWhenReady(layout: VLCVideoLayout, retry: Int) {
        if (released || mediaPlayer == null) return
        if (viewsAttached) return

        val ready = layout.isShown && layout.width > 0 && layout.height > 0
        if (!ready) {
            if (retry >= 40) {
                val error = IllegalStateException("VLCVideoLayout was not ready")
                log("attachViews timeout: width=" + layout.width + ", height=" + layout.height)
                errorCallback?.invoke(error)
                return
            }
            handler.postDelayed({ attachWhenReady(layout, retry + 1) }, 50L)
            return
        }

        try {
            // TextureView avoids the independent SurfaceView compositor path that was
            // producing the visible on/off flicker on the target device.
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
        if (mediaPlayer != null && viewsAttached) {
            try { mediaPlayer?.detachViews() } catch (t: Throwable) { log("detachViews: " + t.message) }
        }
        viewsAttached = false
        videoLayout = null
    }

'''
s = s[:start] + attach_block + s[end:]

# Ensure release resets view state and does not try to detach twice through the old path.
s = s.replace("        try { mediaPlayer?.detachViews() } catch (_: Throwable) {}\n", "", 1)
marker = "        try { mediaPlayer?.release() } catch (_: Throwable) {}\n"
assert marker in s
s = s.replace(marker, "        detachViews()\n" + marker, 1)
s = s.replace("        detachViews()\n        currentContainer = null\n", "        currentContainer = null\n", 1)

# The final release currently calls detachViews after mediaPlayer is nulled in the old code.
# Normalize that section explicitly.
old_tail = '''        try { mediaPlayer?.release() } catch (_: Throwable) {}
        try { libVlc?.release() } catch (_: Throwable) {}
        mediaPlayer = null
        libVlc = null
        detachViews()
        currentContainer = null
'''
new_tail = '''        detachViews()
        try { mediaPlayer?.release() } catch (_: Throwable) {}
        try { libVlc?.release() } catch (_: Throwable) {}
        mediaPlayer = null
        libVlc = null
        currentContainer = null
'''
assert old_tail in s
s = s.replace(old_tail, new_tail, 1)

vlc.write_text(s)

# Bump app version.
g = ROOT / "app/build.gradle"
gs = g.read_text()
gs = re.sub(r'versionCode\s+\d+', 'versionCode 1000031', gs, count=1)
gs = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.31"', gs, count=1)
g.write_text(gs)

print("V100.0.31 VLC surface lifecycle fix applied")
