from pathlib import Path

FILES = [
    'app/src/main/java/com/orbital/iptv/OrbitalApp.kt',
    'app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt',
    'app/src/main/java/com/orbital/iptv/ui/login/LoginActivity.kt',
    'app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt',
    'app/src/main/java/com/orbital/iptv/ui/series/SeriesActivity.kt',
    'app/src/main/java/com/orbital/iptv/ui/tv/TvModeActivity.kt',
    'app/src/main/java/com/orbital/iptv/ui/vod/VodActivity.kt',
]

def unwrap_prepare(s: str) -> str:
    needle = 'com.orbital.iptv.utils.SEKeyboardController.prepare('
    while True:
        i = s.find(needle)
        if i < 0:
            return s
        start = i + len(needle)
        depth = 1
        j = start
        in_str = False
        esc = False
        while j < len(s) and depth:
            ch = s[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
            j += 1
        if depth != 0:
            raise RuntimeError(f'unclosed prepare() near {s[max(0,i-80):i+100]}')
        inner = s[start:j-1]
        s = s[:i] + inner + s[j:]

for rel in FILES:
    p = Path(rel)
    s = p.read_text()
    s = s.replace('import com.orbital.iptv.utils.SEKeyboardController\n', '')
    s = s.replace('SEKeyboardController.install(this)\n', '')
    s = s.replace('SEKeyboardController.install(a)\n', '')
    s = ''.join(line for line in s.splitlines(True) if 'SEKeyboardController.showFocused' not in line)
    s = unwrap_prepare(s)
    p.write_text(s)

p = Path('app/src/main/java/com/orbital/iptv/ui/search/SearchActivity.kt')
s = p.read_text().replace('SEKeyboardController.prepare(binding.etSearch)', 'binding.etSearch.showSoftInputOnFocus = true')
p.write_text(s)

p = Path('app/src/main/java/com/orbital/iptv/ui/login/LoginActivity.kt')
s = p.read_text()
s = s.replace('import android.view.inputmethod.EditorInfo\n', 'import android.view.inputmethod.EditorInfo\nimport android.view.inputmethod.InputMethodManager\n')
s = s.replace('''        // Bind every Xtream field directly to the in-app keyboard. Do not rely only on
        // the application-level focus observer because OrbitalApp installs the observer before
        // this Activity inflates its layout.
        listOf(binding.etProfileName, binding.etServerUrl, binding.etUsername, binding.etPassword)
            .forEach { SEKeyboardController.prepare(it) }

        // The original screen opened the Android/TV IME. SE keeps text entry completely inside
        // the app with the custom keyboard, so the system IME stays disabled.
''', '''        listOf(binding.etProfileName, binding.etServerUrl, binding.etUsername, binding.etPassword)
            .forEach { it.showSoftInputOnFocus = true }
''')
s = s.replace('''            binding.etPassword.requestFocus()
        }
''', '''            binding.etPassword.requestFocus()
            showSystemKeyboard(binding.etPassword)
        }
''', 1)
s = s.replace('''    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
''', '''    private fun showSystemKeyboard(view: View) {
        view.requestFocus()
        view.post {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager
            imm?.showSoftInput(view, 0)
        }
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
''')
s = s.replace('if (focused is EditText) SEKeyboardController.showFor(focused)', 'if (focused is EditText) showSystemKeyboard(focused)')
p.write_text(s)

Path('app/src/main/java/com/orbital/iptv/utils/SEKeyboardController.kt').unlink(missing_ok=True)
