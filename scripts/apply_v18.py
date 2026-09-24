from pathlib import Path
import re

def rep(path, old, new):
    p=Path(path)
    s=p.read_text()
    if old not in s:
        raise SystemExit(f"missing pattern: {path}: {old[:80]}")
    p.write_text(s.replace(old,new,1))

rep("app/build.gradle","versionCode 1000017","versionCode 1000018")
rep("app/build.gradle",'versionName "100.0.17"','versionName "100.0.18"')
rep("settings.gradle",'SEAndroid_v100.0.17','SEAndroid_v100.0.18')

p=Path("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt")
s=p.read_text()
if 'b.tvBuiltinPlayerValue.text = "SE PLAYER"' not in s:
    s=s.replace('b.tvBuiltinPlayerValue.text = "SE"','b.tvBuiltinPlayerValue.text = "SE PLAYER"',1)
p.write_text(s)

p=Path("app/src/main/res/layout/activity_settings.xml")
s=p.read_text()
s=s.replace('android:id="@+id/tv_builtin_player_value" android:text="SE"', 'android:id="@+id/tv_builtin_player_value" android:text="SE PLAYER"',1)
start=s.find('<TextView android:id="@+id/about_text"')
if start<0:
    raise SystemExit("about_text not found")
end=s.find('/>',start)
if end<0:
    raise SystemExit("about_text end not found")
table='''<TableLayout
    android:id="@+id/about_table"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:layout_marginTop="10dp"
    android:stretchColumns="1">
    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
        <TextView android:text="NAME" android:textColor="@color/sky_cyan" android:textStyle="bold" android:padding="10dp" android:background="@color/se_panel_alt" android:layout_width="150dp" android:layout_height="wrap_content"/>
        <TextView android:text="SE IPTV PLAYER" android:textColor="@color/sky_white" android:padding="10dp" android:background="@color/orbital_dark_blue" android:layout_width="0dp" android:layout_weight="1" android:layout_height="wrap_content"/>
    </TableRow>
    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
        <TextView android:text="VERSION" android:textColor="@color/sky_cyan" android:textStyle="bold" android:padding="10dp" android:background="@color/se_panel_alt" android:layout_width="150dp" android:layout_height="wrap_content"/>
        <TextView android:text="V100.0.18" android:textColor="@color/sky_white" android:padding="10dp" android:background="@color/orbital_dark_blue" android:layout_width="0dp" android:layout_weight="1" android:layout_height="wrap_content"/>
    </TableRow>
    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
        <TextView android:text="APPLICATION ID" android:textColor="@color/sky_cyan" android:textStyle="bold" android:padding="10dp" android:background="@color/se_panel_alt" android:layout_width="150dp" android:layout_height="wrap_content"/>
        <TextView android:text="com.se.iptv.player" android:textColor="@color/sky_white" android:padding="10dp" android:background="@color/orbital_dark_blue" android:layout_width="0dp" android:layout_weight="1" android:layout_height="wrap_content"/>
    </TableRow>
    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
        <TextView android:text="PLATFORM" android:textColor="@color/sky_cyan" android:textStyle="bold" android:padding="10dp" android:background="@color/se_panel_alt" android:layout_width="150dp" android:layout_height="wrap_content"/>
        <TextView android:text="Android" android:textColor="@color/sky_white" android:padding="10dp" android:background="@color/orbital_dark_blue" android:layout_width="0dp" android:layout_weight="1" android:layout_height="wrap_content"/>
    </TableRow>
    <TableRow android:layout_width="match_parent" android:layout_height="wrap_content">
        <TextView android:text="LICENSE" android:textColor="@color/sky_cyan" android:textStyle="bold" android:padding="10dp" android:background="@color/se_panel_alt" android:layout_width="150dp" android:layout_height="wrap_content"/>
        <TextView android:text="Open Source" android:textColor="@color/sky_white" android:padding="10dp" android:background="@color/orbital_dark_blue" android:layout_width="0dp" android:layout_weight="1" android:layout_height="wrap_content"/>
    </TableRow>
</TableLayout>'''
p.write_text(s[:start]+table+s[end+2:])

rep("app/src/main/res/layout/activity_login.xml",'android:layout_width="192dp"\n            android:layout_height="192dp"','android:layout_width="384dp"\n            android:layout_height="384dp"')

# Remove obsolete About TextView binding; About is now a TableLayout.
rep("app/src/main/java/com/orbital/iptv/ui/settings/SettingsActivity.kt", "listOf(b.tvBuiltinPlayerValue, b.aboutText).forEach", "listOf(b.tvBuiltinPlayerValue).forEach")

Path("app/src/main/res/drawable/se_launcher_scaled.xml").write_text('''<scale xmlns:android="http://schemas.android.com/apk/res/android"
    android:drawable="@drawable/se_launcher"
    android:scaleWidth="200%"
    android:scaleHeight="200%"
    android:scaleGravity="center" />
''')

p=Path("app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt")
s=p.read_text()
s=s.replace('''    fun getProfiles(context: Context): List<ServerProfile> {
        val json = prefs(context).getString(KEY_PROFILES, null)
        if (json != null) {
            return try {
                Gson().fromJson(json, object : TypeToken<List<ServerProfile>>() {}.type)
            } catch (_: Exception) { emptyList() }
        }
        // Migrate old single-server data on first run
        return migrateLegacy(context)
    }''','''    fun getProfiles(context: Context): List<ServerProfile> {
        val p = prefs(context)
        val json = p.getString(KEY_PROFILES, null)
        if (!json.isNullOrBlank()) {
            try {
                val parsed: List<ServerProfile>? = Gson().fromJson(
                    json, object : TypeToken<List<ServerProfile>>() {}.type
                )
                if (!parsed.isNullOrEmpty()) return parsed
            } catch (_: Exception) {
                try {
                    val single = Gson().fromJson(json, ServerProfile::class.java)
                    if (single != null && single.serverUrl.isNotBlank() && single.username.isNotBlank()) {
                        val repaired = listOf(single)
                        saveProfileList(context, repaired)
                        p.edit().putString(KEY_ACTIVE_PROFILE_ID, single.id).apply()
                        return repaired
                    }
                } catch (_: Exception) {}
            }
        }
        return migrateLegacy(context)
    }''',1)
s=s.replace('''    fun saveProfile(context: Context, profile: ServerProfile) {
        val list = getProfiles(context).toMutableList()
        val idx = list.indexOfFirst { it.id == profile.id }
        if (idx >= 0) list[idx] = profile else list.add(profile)
        saveProfileList(context, list)
    }

    fun deleteProfile(context: Context, id: String) {
        saveProfileList(context, getProfiles(context).filter { it.id != id })
    }''','''    fun saveProfile(context: Context, profile: ServerProfile) {
        val list = getProfiles(context).toMutableList()
        val idx = list.indexOfFirst { it.id == profile.id }
        if (idx >= 0) list[idx] = profile else list.add(profile)
        saveProfileList(context, list)
        if (getActiveProfileId(context) == null || list.size == 1) {
            setActiveProfile(context, profile.id)
        }
    }

    fun deleteProfile(context: Context, id: String) {
        val remaining = getProfiles(context).filter { it.id != id }
        saveProfileList(context, remaining)
        when {
            remaining.isEmpty() -> prefs(context).edit()
                .remove(KEY_ACTIVE_PROFILE_ID)
                .remove(KEY_SERVER_URL)
                .remove(KEY_USERNAME)
                .remove(KEY_PASSWORD)
                .apply()
            id == getActiveProfileId(context) -> setActiveProfile(context, remaining.first().id)
        }
    }''',1)
s=s.replace('''    fun saveCredentials(context: Context, credentials: XtreamCredentials) {
        // Called only from old paths; new path uses saveProfile directly
        prefs(context).edit()
            .putString(KEY_SERVER_URL, credentials.serverUrl)
            .putString(KEY_USERNAME,   credentials.username)
            .putString(KEY_PASSWORD,   credentials.password)
            .apply()
    }''','''    fun saveCredentials(context: Context, credentials: XtreamCredentials) {
        val profiles = getProfiles(context)
        val existing = profiles.firstOrNull {
            it.serverUrl == credentials.serverUrl && it.username == credentials.username
        }
        val profile = (existing ?: ServerProfile(
            name = "Server " + (profiles.size + 1),
            serverUrl = credentials.serverUrl,
            username = credentials.username,
            password = credentials.password
        )).copy(
            serverUrl = credentials.serverUrl,
            username = credentials.username,
            password = credentials.password
        )
        saveProfile(context, profile)
    }''',1)
p.write_text(s)

p=Path("app/src/main/java/com/orbital/iptv/ui/users/ListUsersActivity.kt")
s=p.read_text().replace('if (profiles.isEmpty()) "NO SAVED USERS" else ""',
                        'if (profiles.isEmpty()) "NO SAVED USERS — PRESS ADD USER" else ""',1)
p.write_text(s)

p=Path("SE_BUILD_MANIFEST.txt")
if p.exists():
    p.write_text(p.read_text().replace("100.0.17","100.0.18"))

print("v100.0.18 source changes applied")
