from pathlib import Path
import re
R=Path('.')
java=R/'app/src/main/java'
for p in java.rglob('*.kt'):
    s=p.read_text(encoding='utf-8')
    s=s.replace('import com.orbital.iptv.utils.SEKeyboardController\\n','')
    s=s.replace('import com.orbital.iptv.utils.SEKeyboardController\\r\\n','')
    s=s.replace('com.orbital.iptv.utils.SEKeyboardController.prepare(', '')
    s=s.replace('SEKeyboardController.prepare(', '')
    s=s.replace('SEKeyboardController.install(this)', '')
    s=re.sub(r'\\s*com\\.orbital\\.iptv\\.utils\\.SEKeyboardController\\.showFocused\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.showFocused\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*com\\.orbital\\.iptv\\.utils\\.SEKeyboardController\\.showFor\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.showFor\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.install\\([^\\n]*\\)', '', s)
    s=s.replace('et.showSoftInputOnFocus = false','et.showSoftInputOnFocus = true')
    s='\n'.join(line for line in s.splitlines() if 'SEKeyboardController' not in line)
    s=s.replace('com.orbital.iptv.utils.SEKeyboardController.showFocused','')
    s=s.replace('SEKeyboardController.showFocused','')
    s=s.replace('com.orbital.iptv.utils.SEKeyboardController.showFor','')
    s=s.replace('SEKeyboardController.showFor','')
    p.write_text(s,encoding='utf-8')
ctl=java/'com/orbital/iptv/utils/SEKeyboardController.kt'
if ctl.exists(): ctl.unlink()
for p in [R/'scripts/apply_keyboard_v24.py', *R.glob('scripts/keyboard_v24_payload_*.b64'), *R.glob('scripts/v25_keyboard_part_*.b64')]:
    if p.exists(): p.unlink()
p=R/'app/build.gradle'
lines=p.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if line.strip().startswith('versionCode '):
        lines[i]='        versionCode 1000026'
    if line.strip().startswith('versionName '):
        lines[i]='        versionName "100.0.26"'
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
remaining=[]
for p in java.rglob('*.kt'):
    for i,line in enumerate(p.read_text(encoding='utf-8',errors='ignore').splitlines(),1):
        if 'SEKeyboardController' in line:
            remaining.append(f"{p}:{i}:{line}")
if remaining:
    print("\n".join(remaining))
    raise SystemExit("custom keyboard references remain")
print('FINAL_PATCH_OK')

# Live mini-player and lifecycle fixes
p=java/'com/orbital/iptv/ui/home/HomeActivity.kt'
s=p.read_text(encoding='utf-8')
old='''    override fun onPause() {
        super.onPause()
        ReminderBus.unregister()
    }'''
new='''    override fun onPause() {
        super.onPause()
        ReminderBus.unregister()
        miniPlayer?.let { p ->
            p.playWhenReady = false
            p.pause()
            p.stop()
            p.clearMediaItems()
        }
        binding.miniPlayer.player = miniPlayer
        lastPreviewStreamId = -1
    }

    override fun onDestroy() {
        binding.miniPlayer.player = null
        miniPlayer?.release()
        miniPlayer = null
        super.onDestroy()
    }'''
if old in s: s=s.replace(old,new,1)
old2='''        val url=viewModel.buildStreamUrl(stream.streamId)
        if (binding.miniPlayer.player==null) return
        binding.miniPlayer.player?.setMediaItem(MediaItem.fromUri(url)); binding.miniPlayer.player?.prepare(); binding.miniPlayer.player?.play()'''
new2='''        val url=viewModel.buildStreamUrl(stream.streamId)
        val preview = binding.miniPlayer.player ?: miniPlayer ?: return
        binding.miniPlayer.player = preview
        binding.miniPlayer.useController = false
        preview.playWhenReady = true
        preview.setMediaItem(MediaItem.fromUri(url))
        preview.prepare()
        preview.play()'''
if old2 in s: s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8')

p=R/'app/src/main/res/layout/activity_home.xml'
s=p.read_text(encoding='utf-8')
if 'xmlns:app=' not in s.split('\n',1)[0]:
    s=s.replace('xmlns:android="http://schemas.android.com/apk/res/android"','xmlns:android="http://schemas.android.com/apk/res/android" xmlns:app="http://schemas.android.com/apk/res-auto"',1)
s=s.replace('android:background="#000000" />\n                    <TextView android:text="PREVIEW"',
'''android:background="#000000"
                        app:use_controller="false"
                        app:show_buffering="when_playing" />
                    <TextView android:text="PREVIEW"''',1)
p.write_text(s,encoding='utf-8')

p=java/'com/orbital/iptv/ui/player/PlayerActivity.kt'
s=p.read_text(encoding='utf-8')
if 'private var playbackStoppedForLifecycle' not in s:
    s=s.replace('    private val repository = XtreamRepository()','    private val repository = XtreamRepository()\n    private var playbackStoppedForLifecycle = false\n    private var lifecycleResumePositionMs = 0L',1)
s=s.replace('b.btnGencBack.setOnClickListener { finish() }','b.btnGencBack.setOnClickListener { stopPlaybackBeforeExit(); finish() }')
s=s.replace('binding.btnBack.setOnClickListener { finish() }','binding.btnBack.setOnClickListener { stopPlaybackBeforeExit(); finish() }')
marker='    // ── Lifecycle ─────────────────────────────────────────────────────────────'
if 'private fun stopPlaybackForLifecycle()' not in s:
    s=s.replace(marker,'''    private fun stopPlaybackBeforeExit() {
        if (!::player.isInitialized) return
        try { player.playWhenReady=false; player.pause(); player.stop(); player.clearMediaItems() } catch (_: Exception) {}
    }
    private fun stopPlaybackForLifecycle() {
        if (!::player.isInitialized) return
        try {
            if (!isLive) lifecycleResumePositionMs=player.currentPosition.coerceAtLeast(0L)
            player.playWhenReady=false; player.pause(); player.stop(); player.clearMediaItems()
        } catch (_: Exception) {}
        playbackStoppedForLifecycle=true
    }

'''+marker,1)
s=s.replace('''        if (plexRatingKey.isNotEmpty() && !episodeCompleted) reportPlexStop()
        if (isLive) {''','''        if (plexRatingKey.isNotEmpty() && !episodeCompleted) reportPlexStop()
        if (!isInPictureInPictureMode && !enteringPip) stopPlaybackForLifecycle()
        if (isLive) {''',1)
s=s.replace('''        if (::player.isInitialized && !hasError) player.playWhenReady = true''','''        if (playbackStoppedForLifecycle && !isFinishing && !isInPictureInPictureMode) {
            if (!isLive && lifecycleResumePositionMs > 0L) resumeMs=lifecycleResumePositionMs
            playbackStoppedForLifecycle=false
            playMedia()
        } else if (::player.isInitialized && !hasError && !isInPictureInPictureMode) player.playWhenReady=true''',1)
s=s.replace('''        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        if (isInPictureInPictureMode) {''','''        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        if (!isInPictureInPictureMode && !isFinishing && ::player.isInitialized) { player.playWhenReady=false; player.pause() }
        if (isInPictureInPictureMode) {''',1)
p.write_text(s,encoding='utf-8')

p=java/'com/orbital/iptv/ui/tv/TvModeActivity.kt'
s=p.read_text(encoding='utf-8')
marker='    // ── Lifecycle ─────────────────────────────────────────────────────────────'
if 'private fun stopPlaybackBeforeExit()' not in s:
    s=s.replace(marker,'''    private fun stopPlaybackBeforeExit() {
        try {
            player?.playWhenReady=false; player?.pause(); player?.stop(); player?.clearMediaItems()
            localPlayer?.let { it.playWhenReady=false; it.pause(); it.stop(); it.clearMediaItems() }
        } catch (_: Exception) {}
    }

'''+marker,1)
s=s.replace('if (hudVisible) { hideHudOverlay(); return true }\n                    showExitDialog(); return true','if (hudVisible) { hideHudOverlay(); return true }\n                    stopPlaybackBeforeExit()\n                    showExitDialog(); return true',1)
s=s.replace('.setPositiveButton("EXIT") { _, _ -> finishAffinity() }','.setPositiveButton("EXIT") { _, _ -> stopPlaybackBeforeExit(); finishAffinity() }',1)
s=s.replace('''    override fun onPause() {
        super.onPause()
        if (!enteringPip && !isInPictureInPictureMode) player?.pause()
        GoalFlashManager.onGoal = null''','''    override fun onPause() {
        super.onPause()
        if (!enteringPip && !isInPictureInPictureMode) stopPlaybackBeforeExit()
        GoalFlashManager.onGoal = null''',1)
s=s.replace('''        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        if (isInPictureInPictureMode) {''','''        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        if (!isInPictureInPictureMode && !isFinishing) stopPlaybackBeforeExit()
        if (isInPictureInPictureMode) {''',1)
p.write_text(s,encoding='utf-8')
print('LIVE_PATCH_APPLIED')
