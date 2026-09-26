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
    s=re.sub(r'\\s*com\\.orbital\\.iptv\\.utils\\.SEKeyboardController\\.showFocused\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.showFocused\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*com\\.orbital\\.iptv\\.utils\\.SEKeyboardController\\.showFor\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.showFor\\([^\\n]*\\)', '', s)
    s=re.sub(r'\\s*SEKeyboardController\\.install\\([^\\n]*\\)', '', s)
    s=s.replace('et.showSoftInputOnFocus = false','et.showSoftInputOnFocus = true')
    p.write_text(s,encoding='utf-8')
ctl=java/'com/orbital/iptv/utils/SEKeyboardController.kt'
if ctl.exists(): ctl.unlink()
for p in [R/'scripts/apply_keyboard_v24.py', *R.glob('scripts/keyboard_v24_payload_*.b64'), *R.glob('scripts/v25_keyboard_part_*.b64')]:
    if p.exists(): p.unlink()
p=R/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\\s+\\d+', 'versionCode 1000026', s, count=1)
s=re.sub(r'versionName\\s+"[^"]+"', 'versionName "100.0.26"', s, count=1)
p.write_text(s,encoding='utf-8')
assert not any('SEKeyboardController' in p.read_text(encoding='utf-8',errors='ignore') for p in java.rglob('*.kt'))
print('FINAL_PATCH_OK')
