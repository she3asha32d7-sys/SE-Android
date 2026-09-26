from pathlib import Path

def replace_once(path: str, old: str, new: str):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise SystemExit(f"Pattern not found in {path}: {old[:120]!r}")
    p.write_text(s.replace(old, new, 1))

settings = Path("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt")
s = settings.read_text()
old = '''    private fun confirm(title: String, yes: () -> Unit) {
        AlertDialog.Builder(this, ThemeManager.dialogStyle()).setTitle(title).setPositiveButton("Yes") { _, _ -> yes() }.setNegativeButton("No", null).show()
    }
'''
new = '''    private fun confirm(title: String, yes: () -> Unit) {
        val dialog = AlertDialog.Builder(this, ThemeManager.dialogStyle())
            .setTitle(title)
            .setPositiveButton("Yes") { _, _ -> yes() }
            .setNegativeButton("No", null)
            .create()

        dialog.setOnShowListener {
            dialog.findViewById<TextView>(androidx.appcompat.R.id.alertTitle)?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 20f)
            dialog.findViewById<TextView>(android.R.id.message)?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18f)
            dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18f)
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE)?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18f)
        }
        dialog.show()
    }
'''
replace_once(str(settings), old, new)

home = Path("app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt")
s = home.read_text()
old = '''    private fun confirmExitApp() {
        androidx.appcompat.app.AlertDialog.Builder(this, com.orbital.iptv.utils.ThemeManager.dialogStyle())
            .setTitle("Do You Want To Exit The App")
            .setPositiveButton("Yes") { _, _ -> finishAffinity() }
            .setNegativeButton("No", null)
            .show()
    }
'''
new = '''    private fun confirmExitApp() {
        val dialog = androidx.appcompat.app.AlertDialog.Builder(
            this,
            com.orbital.iptv.utils.ThemeManager.dialogStyle()
        )
            .setTitle("Do You Want To Exit The App")
            .setPositiveButton("Yes") { _, _ -> finishAffinity() }
            .setNegativeButton("No", null)
            .create()

        dialog.setOnShowListener {
            val title = dialog.findViewById<TextView>(androidx.appcompat.R.id.alertTitle)
            if (title != null) {
                title.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 20f)
            } else {
                fun applyTitle(view: View) {
                    if (view is TextView && view.text?.toString() == "Do You Want To Exit The App") {
                        view.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 20f)
                    }
                    if (view is ViewGroup) {
                        for (i in 0 until view.childCount) applyTitle(view.getChildAt(i))
                    }
                }
                dialog.window?.decorView?.let { applyTitle(it) }
            }
            dialog.getButton(androidx.appcompat.app.AlertDialog.BUTTON_POSITIVE)
                ?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18f)
            dialog.getButton(androidx.appcompat.app.AlertDialog.BUTTON_NEGATIVE)
                ?.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 18f)
        }
        dialog.show()
    }
'''
replace_once(str(home), old, new)

print("Large confirm-dialog typography applied")
