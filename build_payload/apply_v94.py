from pathlib import Path
import os
import re

ROOT = Path(os.environ.get("ROOT", ".")).resolve()

def fail(msg):
    raise SystemExit(msg)

def replace_once(path, old, new):
    p = ROOT / path
    s = p.read_text()
    if old not in s:
        fail(f"Missing expected text in {path}: {old!r}")
    p.write_text(s.replace(old, new, 1))

def append_ime_flags_to_layout(path):
    p = ROOT / path
    s = p.read_text()

    def repl(m):
        block = m.group(0)
        if "android:imeOptions=" in block:
            bm = re.search(r'android:imeOptions="([^"]*)"', block)
            if not bm:
                return block
            value = bm.group(1)
            flags = []
            if "flagNoFullscreen" not in value:
                flags.append("flagNoFullscreen")
            if "flagNoExtractUi" not in value:
                flags.append("flagNoExtractUi")
            if not flags:
                return block
            new_value = value + "|" + "|".join(flags)
            return block[:bm.start(1)] + new_value + block[bm.end(1):]
        return block.replace(">", ' android:imeOptions="flagNoFullscreen|flagNoExtractUi">', 1)

    new = re.sub(r'<EditText\b[^>]*>', repl, s)
    if new != s:
        p.write_text(new)

# 1) Preserve the single inline Search architecture.
sidebar = ROOT / "app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt"
if sidebar.exists():
    s = sidebar.read_text()
    s = s.replace("import com.orbital.iptv.ui.search.SearchActivity\n", "")
    s = s.replace(
        """                    Section.SEARCH -> {
                        InlineSearchController.clear(activity)
                        go(activity, SearchActivity::class.java)
                    }""",
        """                    Section.SEARCH -> {
                        InlineSearchController.open(activity, root)
                    }"""
    )
    s = s.replace("        Section.SEARCH -> SearchActivity::class.java", "        Section.SEARCH -> Activity::class.java")
    sidebar.write_text(s)

# A dedicated SearchActivity is explicitly not part of this design.
for rel in [
    "app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt",
    "app/src/main/res/layout/activity_search.xml",
]:
    p = ROOT / rel
    if p.exists():
        p.unlink()

manifest = ROOT / "app/src/main/AndroidManifest.xml"
if manifest.exists():
    s = manifest.read_text()
    s = re.sub(
        r'\n\s*<activity\n\s*android:name="\.ui\.search\.SearchActivity"\n\s*android:exported="false"\n\s*android:windowSoftInputMode="adjustResize"\s*/>\n',
        "\n",
        s,
        count=1,
    )
    manifest.write_text(s)

# 2) Fix Xtream password visibility from V91 while keeping the requested icon UI.
login = ROOT / "app/src/main/java/com/orbital/iptv/ui/login/LoginActivity.kt"
s = login.read_text()
s = s.replace("import android.text.method.HideReturnsTransformationMethod\n", "")
if "private var isPasswordVisible = false" not in s:
    s = s.replace(
        "    private lateinit var binding: ActivityLoginBinding\n",
        "    private lateinit var binding: ActivityLoginBinding\n    private var isPasswordVisible = false\n",
        1,
    )
listener = """        binding.btnShowPassword.setOnClickListener {
            val editText = binding.etPassword
            val selection = editText.selectionStart.coerceIn(0, editText.text.length)
            isPasswordVisible = !isPasswordVisible

            editText.transformationMethod = if (isPasswordVisible) {
                null
            } else {
                PasswordTransformationMethod.getInstance()
            }
            editText.setSelection(selection)

            binding.btnShowPassword.setImageResource(
                if (isPasswordVisible) R.drawable.ic_visibility_off
                else R.drawable.ic_visibility
            )
            binding.btnShowPassword.contentDescription = getString(
                if (isPasswordVisible) R.string.hide_password
                else R.string.show_password
            )
        }

"""
if "binding.btnShowPassword.setOnClickListener" not in s:
    anchor = "        binding.btnConnect.setOnFocusChangeListener { _, hasFocus ->"
    if anchor not in s:
        fail("LoginActivity connect listener anchor not found")
    s = s.replace(anchor, listener + anchor, 1)
login.write_text(s)

login_xml = ROOT / "app/src/main/res/layout/activity_login.xml"
s = login_xml.read_text()
old = """                    <TextView
                        android:id="@+id/btn_show_password"
                        android:layout_width="118dp"
                        android:layout_height="match_parent"
                        android:layout_marginStart="6dp"
                        android:gravity="center"
                        android:text="SHOW PASSWORD"
                        android:textColor="@color/sky_cyan"
                        android:textSize="10sp"
                        android:textStyle="bold"
                        android:fontFamily="sans-serif-condensed"
                        android:background="@color/sky_mid_blue"
                        android:focusable="true"
                        android:clickable="true" />"""
new = """                    <ImageButton
                        android:id="@+id/btn_show_password"
                        android:layout_width="118dp"
                        android:layout_height="match_parent"
                        android:layout_marginStart="6dp"
                        android:background="@color/sky_mid_blue"
                        android:src="@drawable/ic_visibility"
                        android:scaleType="centerInside"
                        android:padding="8dp"
                        android:tint="@color/sky_cyan"
                        android:contentDescription="@string/show_password"
                        android:focusable="true"
                        android:clickable="true" />"""
if old in s:
    s = s.replace(old, new, 1)
login_xml.write_text(s)

strings = ROOT / "app/src/main/res/values/strings.xml"
s = strings.read_text()
if 'name="show_password"' not in s:
    s = s.replace("</resources>", '    <string name="show_password">Show password</string>\n    <string name="hide_password">Hide password</string>\n</resources>')
strings.write_text(s)

drawable = ROOT / "app/src/main/res/drawable"
drawable.mkdir(parents=True, exist_ok=True)
(drawable / "ic_visibility.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M12,4.5C7,4.5 2.73,7.61 1,12c1.73,4.39 6,7.5 11,7.5s9.27,-3.11 11,-7.5C21.27,7.61 17,4.5 12,4.5zM12,17c-2.76,0 -5,-2.24 -5,-5s2.24,-5 5,-5 5,2.24 5,5 -2.24,5 -5,5zM12,9c-1.66,0 -3,1.34 -3,3s1.34,3 3,3 3,-1.34 3,-3 -1.34,-3 -3,-3z"/>
</vector>
""")
(drawable / "ic_visibility_off.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M2.8,2.81L1.39,4.22l3.25,3.25C3.06,8.7 1.73,10.29 1,12c1.73,4.39 6,7.5 11,7.5 1.75,0 3.41,-0.36 4.91,-1.01l3.87,3.87 1.41,-1.41L2.8,2.81zM12,17c-2.76,0 -5,-2.24 -5,-5 0,-0.64 0.12,-1.24 0.34,-1.81l1.53,1.53C8.95,11.81 9,11.9 9,12c0,1.66 1.34,3 3,3 0.1,0 0.19,-0.05 0.28,-0.13l1.53,1.53C13.24,16.88 12.64,17 12,17zM12,7c2.76,0 5,2.24 5,5 0,0.64 -0.12,1.24 -0.34,1.81l1.51,1.51C19.95,14.36 21.15,13.06 22,12c-1.73,-4.39 -6,-7.5 -10,-7.5 -1.16,0 -2.29,0.18 -3.35,0.5l1.64,1.64C10.77,6.14 11.37,7 12,7zM12,9c1.66,0 3,1.34 3,3 0,0.1 -0.01,0.2 -0.03,0.3l-3.27,-3.27C11.8,9.01 11.9,9 12,9z"/>
</vector>
""")

# 3) Request native mobile/system keyboard, not fullscreen/extracted editor UI.
for p in (ROOT / "app/src/main/res/layout").glob("*.xml"):
    append_ime_flags_to_layout(str(p.relative_to(ROOT)))

# The inline search panel is dynamically inflated after Activity creation.
inline = ROOT / "app/src/main/java/com/orbital/iptv/utils/InlineSearchController.kt"
s = inline.read_text()
s = s.replace(
    'import android.view.inputmethod.InputMethodManager\n',
    'import android.view.inputmethod.InputMethodManager\n'
)
old_show = """    private fun showKeyboard(activity: AppCompatActivity, edit: EditText) {
        activity.window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        val imm = activity.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        imm.showSoftInput(edit, InputMethodManager.SHOW_IMPLICIT)
    }"""
new_show = """    private fun showKeyboard(activity: AppCompatActivity, edit: EditText) {
        edit.showSoftInputOnFocus = true
        edit.imeOptions = edit.imeOptions or
            android.view.inputmethod.EditorInfo.IME_FLAG_NO_FULLSCREEN or
            android.view.inputmethod.EditorInfo.IME_FLAG_NO_EXTRACT_UI
        activity.window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING)
        edit.post {
            val imm = activity.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showSoftInput(edit, 0)
        }
    }"""
if old_show not in s:
    fail("InlineSearchController showKeyboard implementation not found")
s = s.replace(old_show, new_show, 1)
inline.write_text(s)

# 4) Dynamically created EditTexts receive the same system-IME policy.
orbital = ROOT / "app/src/main/java/com/orbital/iptv/OrbitalApp.kt"
s = orbital.read_text()
if "android.widget.EditText" not in s:
    s = s.replace("import android.view.WindowManager\n", "import android.view.WindowManager\nimport android.view.View\nimport android.view.ViewGroup\nimport android.view.inputmethod.EditorInfo\nimport android.widget.EditText\n", 1)
if "private fun applyImePolicy" not in s:
    anchor = """    private fun applyOrientationPolicy(a: Activity) {"""
    helper = """    private fun applyImePolicy(view: View) {
        if (view is EditText) {
            view.showSoftInputOnFocus = true
            view.imeOptions = view.imeOptions or
                EditorInfo.IME_FLAG_NO_FULLSCREEN or
                EditorInfo.IME_FLAG_NO_EXTRACT_UI
        }
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) applyImePolicy(view.getChildAt(i))
        }
    }

"""
    s = s.replace(anchor, helper + anchor, 1)
s = s.replace(
    """                a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                applyOrientationPolicy(a)
                
""",
    """                a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                applyOrientationPolicy(a)
                a.window.decorView.post { applyImePolicy(a.window.decorView) }

"""
)
s = s.replace(
    """            override fun onActivityResumed(a: Activity) {
                // Re-apply sensor rotation when ON.""",
    """            override fun onActivityResumed(a: Activity) {
                a.window.decorView.post { applyImePolicy(a.window.decorView) }
                // Re-apply sensor rotation when ON."""
)
orbital.write_text(s)

# Keep explicit inline behavior documented and make sure dynamic search EditText is flagged.
flag = inline.read_text()
if "IME_FLAG_NO_FULLSCREEN" not in flag or "SOFT_INPUT_ADJUST_NOTHING" not in flag:
    fail("Inline IME policy was not installed")

# 5) Version 100.0.94.
gradle = ROOT / "app/build.gradle"
s = gradle.read_text()
s = re.sub(r'versionCode\s+\d+', 'versionCode 1000094', s, count=1)
s = re.sub(r'versionName\s+"[^"]+"', 'versionName "100.0.94"', s, count=1)
gradle.write_text(s)
settings = ROOT / "settings.gradle"
s = settings.read_text()
s = re.sub(r'rootProject\.name\s*=\s*"[^"]+"', 'rootProject.name = "SEAndroid_v100.0.94"', s, count=1)
settings.write_text(s)

# Final assertions.
assert 'Section.SEARCH -> SearchActivity::class.java' not in sidebar.read_text()
assert 'InlineSearchController.open(activity, root)' in sidebar.read_text()
assert 'Section.SEARCH -> Activity::class.java' in sidebar.read_text()
assert 'versionName "100.0.94"' in gradle.read_text()
assert 'versionCode 1000094' in gradle.read_text()
assert 'IME_FLAG_NO_FULLSCREEN' in inline.read_text()
assert 'SOFT_INPUT_ADJUST_NOTHING' in inline.read_text()
assert 'binding.btnShowPassword.setOnClickListener' in login.read_text()

print("V100.0.94 source transformation completed successfully.")
