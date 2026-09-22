from pathlib import Path
import re

ROOT = Path(".")
APP = ROOT / "app"

def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8")

def write(rel, s):
    (ROOT / rel).write_text(s, encoding="utf-8")

# Lock app build version to the requested release number.
p = APP / "build.gradle"
s = p.read_text(encoding="utf-8")
s = re.sub(r'versionCode\s+\d+', 'versionCode 201', s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "2.0.1"', s, count=1)
p.write_text(s, encoding="utf-8")

# Persist the VOD seek step between player launches.
p = APP / "src/main/java/com/orbital/iptv/utils/PrefsManager.kt"
s = p.read_text(encoding="utf-8")
if 'KEY_SEEK_STEP_MS' not in s:
    s = s.replace(
        '    private const val KEY_PLAYER_TYPE             = "player_type"\n',
        '    private const val KEY_PLAYER_TYPE             = "player_type"\n    private const val KEY_SEEK_STEP_MS              = "seek_step_ms"\n',
        1
    )
if 'fun getSeekStepMs' not in s:
    marker = '''    fun setPlaybackSpeed(context: Context, speed: Float) =
        prefs(context).edit().putFloat("playback_speed", speed).apply()
'''
    add = marker + '''
    fun getSeekStepMs(context: Context): Long =
        prefs(context).getLong(KEY_SEEK_STEP_MS, 30_000L)

    fun setSeekStepMs(context: Context, stepMs: Long) =
        prefs(context).edit().putLong(KEY_SEEK_STEP_MS, stepMs.coerceIn(5_000L, 600_000L)).apply()
'''
    if marker in s:
        s = s.replace(marker, add, 1)
p.write_text(s, encoding="utf-8")

# PlayerActivity: load and save the persistent seek step.
p = APP / "src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt"
s = p.read_text(encoding="utf-8")
s = s.replace(
    '    private var seekStepMs = DEFAULT_SEEK_STEP_MS',
    '    private var seekStepMs = DEFAULT_SEEK_STEP_MS',
    1
)
load_anchor = '        setContentView(binding.root)\n'
if 'seekStepMs = PrefsManager.getSeekStepMs(this)' not in s and load_anchor in s:
    s = s.replace(load_anchor, load_anchor + '        seekStepMs = PrefsManager.getSeekStepMs(this)\n', 1)
s = s.replace(
    '                seekStepMs = values[which]\n                updateSeekStepButton()',
    '                seekStepMs = values[which]\n                PrefsManager.setSeekStepMs(this, seekStepMs)\n                updateSeekStepButton()',
    1
)
# Make the obsolete player buttons non-interactive and invisible while preserving bindings
# used by legacy code paths.
anchor = '        binding.btnScores.visibility=View.GONE; binding.btnNews.visibility=View.GONE; binding.btnGoalFlash.visibility=View.GONE;'
if anchor not in s:
    # Preserve the same behavior if the source uses multiline formatting.
    s = s.replace(
        '        binding.btnGoalFlash.setOnClickListener { toggleGoalFlash() }\n',
        '        binding.btnGoalFlash.setOnClickListener { toggleGoalFlash() }\n' + anchor + '\n',
        1
    )
p.write_text(s, encoding="utf-8")

# Live TV: keep legacy sports/news/goal-flash bindings available for compilation,
# but remove them from the user-facing HUD completely.
p = APP / "src/main/java/com/orbital/iptv/ui/tv/TvModeActivity.kt"
s = p.read_text(encoding="utf-8")
anchor = '        binding = ActivityTvModeBinding.inflate(layoutInflater)\n        setContentView(binding.root)\n'
if 'binding.btnHudScores.visibility = View.GONE' not in s and anchor in s:
    s = s.replace(
        anchor,
        anchor + '''        binding.btnHudScores.visibility = View.GONE
        binding.btnHudNews.visibility = View.GONE
        binding.btnHudGoalFlash.visibility = View.GONE
        binding.tickerRow.visibility = View.GONE
        binding.newsTickerRow.visibility = View.GONE
        binding.goalFlashOverlay.visibility = View.GONE
''',
        1
    )
p.write_text(s, encoding="utf-8")

# Remove stale "Box Office" wording from user-facing/internal TV menu comments and make
# the legacy menu control itself invisible while retaining its binding.
p = APP / "src/main/res/layout/activity_tv_mode.xml"
s = p.read_text(encoding="utf-8")
s = s.replace('MAIN_MENU  – Live TV / Box Office / Radio / Interactive / Settings',
              'MAIN_MENU  – Live TV / Content / Radio / Interactive / Settings')
s = s.replace('MAIN_MENU – top-level navigation', 'MAIN_MENU – top-level navigation')
s = re.sub(
    r'(<TextView\s+android:id="@\+id/btn_hud_scores"\b[\s\S]*?)(/>)',
    lambda m: m.group(1) if 'android:visibility=' in m.group(1) else m.group(1).replace('\n', '\n            android:visibility="gone"\n', 1),
    s, count=1
)
# Simpler targeted replacements for the compact legacy HUD buttons if they are present.
for ident in ('btn_hud_scores', 'btn_hud_news', 'btn_hud_goal_flash'):
    s = re.sub(
        rf'(<TextView\s+android:id="@\+id/{ident}"[\s\S]*?)(?=<TextView\s+android:id="@\+id/|</LinearLayout>|</FrameLayout>)',
        lambda m: m.group(1) if 'android:visibility="gone"' in m.group(1) else m.group(1).replace('android:layout_height="wrap_content"', 'android:layout_height="wrap_content"\n            android:visibility="gone"', 1),
        s, count=1
    )
# Player legacy controls are already gone; clear their hidden labels to avoid accidental UI reuse.
pp = APP / "src/main/res/layout/activity_player.xml"
ps = pp.read_text(encoding="utf-8")
ps = re.sub(r'(android:id="@\+id/btn_scores"[^>]*android:text=")[^"]*(")', r'\1\2', ps)
ps = re.sub(r'(android:id="@\+id/btn_news"[^>]*android:text=")[^"]*(")', r'\1\2', ps)
ps = re.sub(r'(android:id="@\+id/btn_goal_flash"[^>]*android:text=")[^"]*(")', r'\1\2', ps)
pp.write_text(ps, encoding="utf-8")

print("FINALIZE_V201_OK")
