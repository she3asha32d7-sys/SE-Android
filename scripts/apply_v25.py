#!/usr/bin/env python3
import base64
import hashlib
import lzma
from pathlib import Path
import re

ROOT = Path(".")
KEYBOARD = ROOT / "app/src/main/java/com/orbital/iptv/utils/SEKeyboardController.kt"
PARTS = [ROOT / f"scripts/v25_keyboard_part_{i}.b64" for i in range(1, 5)]

payload = "".join(p.read_text(encoding="utf-8").strip() for p in PARTS)
expected = "19041eb1c34f5eea9b6b55c926a2a1881878d6ce686e55ec28afdcd079fc4c39"
actual = hashlib.sha256(payload.encode("utf-8")).hexdigest()
if actual != expected:
    raise SystemExit(f"V25 keyboard payload integrity failure: {actual}")

content = lzma.decompress(base64.b64decode(payload)).decode("utf-8")

# Keep Android window behavior compatible with both SE's custom keyboard and the system IME.
content = content.replace(
    "activity.window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN)",
    "activity.window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE or WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN)"
)
content = content.replace(
    "private fun isUrlField(): Boolean = (activeTarget?.get()?.inputType ?: 0 and InputType.TYPE_TEXT_VARIATION_URI) != 0",
    "private fun isUrlField(): Boolean = ((activeTarget?.get()?.inputType ?: 0) and InputType.TYPE_TEXT_VARIATION_URI) != 0"
)

KEYBOARD.write_text(content, encoding="utf-8")

# 1) List Users: remove the cyan active-card fill; active status text remains readable.
p = ROOT / "app/src/main/java/com/orbital/iptv/ui/users/ListUsersActivity.kt"
s = p.read_text(encoding="utf-8")
s2 = s.replace("if (active) palette.highlight else palette.bgMid", "palette.bgMid")
if s2 == s:
    raise SystemExit("ListUsers active-card background pattern not found")
p.write_text(s2, encoding="utf-8")

# 2) Exit dialog typography: identical sizes to Settings confirmation dialogs (20sp title, 18sp buttons).
p = ROOT / "app/src/main/java/com/orbital/iptv/utils/MainSidebarController.kt"
s = p.read_text(encoding="utf-8")
pattern = re.compile(r'    private fun confirmExit\(activity: Activity\) \{.*?\n    \}', re.S)
replacement = '''    private fun confirmExit(activity: Activity) {
        val dialog = AlertDialog.Builder(activity, ThemeManager.dialogStyle())
            .setTitle("Do You Want To Exit The App")
            .setPositiveButton("Yes") { _, _ -> activity.finishAffinity() }
            .setNegativeButton("No", null)
            .create()
        dialog.setOnShowListener {
            dialog.window?.decorView?.findViewsWithText(
                mutableListOf(),
                "Do You Want To Exit The App",
                View.FIND_VIEWS_WITH_TEXT
            )?.firstOrNull { it is TextView }
                ?.let { (it as TextView).textSize = 20f }
            dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.textSize = 18f
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE)?.textSize = 18f
        }
        dialog.show()
    }'''
s2, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit("MainSidebar confirmExit block not found")
p.write_text(s2, encoding="utf-8")

# 3) Settings > About: replace run-on text with an actual 2-column table.
p = ROOT / "app/src/main/res/layout/activity_settings.xml"
s = p.read_text(encoding="utf-8")
old = '<TextView android:id="@+id/about_text" android:text="Name: SE IPTV PLAYER&#10;Version: V100.0.24&#10;Application id: com.se.iptv.player&#10;Platform: Android&#10;License: Open Source" android:textColor="@color/sky_white" android:textSize="14sp" android:lineSpacingExtra="5dp" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="10dp"/>'
new = '''<TextView
                    android:id="@+id/about_text"
                    android:visibility="gone"
                    android:layout_width="0dp"
                    android:layout_height="0dp" />

                <TableLayout
                    android:id="@+id/about_table"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="10dp"
                    android:stretchColumns="1"
                    android:shrinkColumns="1">

                    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
                        <TextView android:text="Name" android:textColor="@color/sky_cyan" android:textStyle="bold" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                        <TextView android:text="SE IPTV PLAYER" android:textColor="@color/sky_white" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                    </TableRow>
                    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
                        <TextView android:text="Version" android:textColor="@color/sky_cyan" android:textStyle="bold" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                        <TextView android:text="V100.0.25" android:textColor="@color/sky_white" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                    </TableRow>
                    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
                        <TextView android:text="Application ID" android:textColor="@color/sky_cyan" android:textStyle="bold" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                        <TextView android:text="com.se.iptv.player" android:textColor="@color/sky_white" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                    </TableRow>
                    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
                        <TextView android:text="Platform" android:textColor="@color/sky_cyan" android:textStyle="bold" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                        <TextView android:text="Android" android:textColor="@color/sky_white" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                    </TableRow>
                    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
                        <TextView android:text="License" android:textColor="@color/sky_cyan" android:textStyle="bold" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                        <TextView android:text="Open Source" android:textColor="@color/sky_white" android:textSize="13sp" android:padding="10dp" android:background="@drawable/bg_table_cell" />
                    </TableRow>
                </TableLayout>'''
if old not in s:
    raise SystemExit("Settings About text block not found")
p.write_text(s.replace(old, new), encoding="utf-8")

d = ROOT / "app/src/main/res/drawable/bg_table_cell.xml"
d.write_text('''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/se_panel_alt" />
    <stroke android:width="1dp" android:color="@color/sky_cyan" />
</shape>
''', encoding="utf-8")

# 4) Version metadata.
p = ROOT / "app/build.gradle"
s = p.read_text(encoding="utf-8").replace("versionCode 1000024", "versionCode 1000025").replace('versionName "100.0.24"', 'versionName "100.0.25"')
p.write_text(s, encoding="utf-8")

p = ROOT / "settings.gradle"
s = p.read_text(encoding="utf-8").replace("SEAndroid_v100.0.24", "SEAndroid_v100.0.25")
p.write_text(s, encoding="utf-8")

print("V100.0.25 patch applied successfully.")
print("Keyboard:", KEYBOARD)
print("List Users: cyan active-card highlight removed")
print("About: 2-column table added")
print("Exit: Settings-matched typography applied")
print("Version: 100.0.25 / 1000025")
