from pathlib import Path
import os, re, shutil

ROOT = Path(os.environ.get("ROOT", ".")).resolve()
PAYLOAD = Path(os.environ["GITHUB_WORKSPACE"]) / "build_payload" / "v95_search_src"

def fail(msg):
    raise SystemExit(msg)

def copy_payload(src_name, dst_rel):
    src = PAYLOAD / src_name
    dst = ROOT / dst_rel
    if not src.exists():
        fail(f"Missing Search payload: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# Reintroduce the dedicated Search page.
copy_payload("SearchActivity.kt", "app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt")
copy_payload("SearchAdapter.kt", "app/src/main/java/com/orbital/iptv/ui/search/SearchAdapter.kt")
copy_payload("activity_search.xml", "app/src/main/res/layout/activity_search.xml")

# Make the dedicated SearchActivity use the system/mobile IME without landscape
# fullscreen/extract UI, preserving the current Activity UI during typing.
search = ROOT / "app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt"
s = search.read_text()
needle = """    private fun setupSearchBar() {
        SEKeyboardController.prepare(binding.etSearch)
"""
replacement = """    private fun setupSearchBar() {
        SEKeyboardController.prepare(binding.etSearch)
        binding.etSearch.showSoftInputOnFocus = true
        binding.etSearch.imeOptions = binding.etSearch.imeOptions or
            EditorInfo.IME_FLAG_NO_FULLSCREEN or
            EditorInfo.IME_FLAG_NO_EXTRACT_UI
        window.setSoftInputMode(
            android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING
        )
"""
if needle not in s:
    fail("SearchActivity setupSearchBar anchor not found")
search.write_text(s.replace(needle, replacement, 1))

# Route Main Sidebar SEARCH to the dedicated SearchActivity.
sidebar = ROOT / "app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt"
s = sidebar.read_text()
if "import com.orbital.iptv.ui.search.SearchActivity" not in s:
    anchor = "import com.orbital.iptv.ui.home.HomeActivity\n"
    if anchor not in s:
        fail("HomeActivity import anchor not found")
    s = s.replace(anchor, anchor + "import com.orbital.iptv.ui.search.SearchActivity\n", 1)

# Ensure Search participates in pending-focus routing.
old_cond = """                if (section != Section.SEARCH) {
                    pendingFocus[targetActivityFor(section)] = section
                }"""
if old_cond in s:
    s = s.replace(old_cond, "                pendingFocus[targetActivityFor(section)] = section", 1)

old_inline = """                    }                    Section.SEARCH -> {
                        InlineSearchController.open(activity, root)
                    }"""
new_search = """                    }                    Section.SEARCH -> {
                        InlineSearchController.clear(activity)
                        go(activity, SearchActivity::class.java)
                    }"""
if old_inline not in s:
    fail("V94 inline Search branch not found")
s = s.replace(old_inline, new_search, 1)

if "Section.SEARCH -> SearchActivity::class.java" not in s:
    old_target = "        Section.SEARCH -> Activity::class.java"
    if old_target not in s:
        fail("SEARCH target mapping not found")
    s = s.replace(old_target, "        Section.SEARCH -> SearchActivity::class.java", 1)
sidebar.write_text(s)

# Register the dedicated SearchActivity.
manifest = ROOT / "app/src/main/AndroidManifest.xml"
s = manifest.read_text()
if '.ui.search.SearchActivity' not in s:
    anchor = '        <activity android:name=".ui.settings.SettingsActivity" android:exported="false" />'
    if anchor not in s:
        fail("Manifest settings activity anchor not found")
    entry = '''        <activity
            android:name=".ui.search.SearchActivity"
            android:exported="false"
            android:windowSoftInputMode="adjustNothing" />

'''
    s = s.replace(anchor, anchor + "

" + entry.rstrip(), 1)
manifest.write_text(s)

# Version.
build = ROOT / "app/build.gradle"
s = build.read_text()
s = re.sub(r'versionCode\s+\d+', 'versionCode 1000095', s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.95"', s, count=1)
build.write_text(s)

settings = ROOT / "settings.gradle"
s = settings.read_text()
s = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.95"', s, count=1)
settings.write_text(s)

# Hard assertions.
assert "go(activity, SearchActivity::class.java)" in sidebar.read_text()
assert "Section.SEARCH -> SearchActivity::class.java" in sidebar.read_text()
assert "InlineSearchController.open(activity, root)" not in sidebar.read_text()
assert '.ui.search.SearchActivity' in manifest.read_text()
assert (ROOT / "app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt").exists()
assert (ROOT / "app/src/main/res/layout/activity_search.xml").exists()
assert (ROOT / "app/src/main/java/com/orbital/iptv/ui/search/SearchAdapter.kt").exists()
assert "IME_FLAG_NO_FULLSCREEN" in search.read_text()
assert "IME_FLAG_NO_EXTRACT_UI" in search.read_text()
assert "SOFT_INPUT_ADJUST_NOTHING" in search.read_text()
assert 'versionName "100.0.95"' in build.read_text()

print("V100.0.95 dedicated Search page transformation: OK")
