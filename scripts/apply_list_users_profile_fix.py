from pathlib import Path

PREFS = Path("app/src/main/java/com/orbital/iptv/utils/PrefsManager.kt")
LOGIN = Path("app/src/main/java/com/orbital/iptv/ui/login/LoginActivity.kt")

def replace_once(path, old, new):
    s = path.read_text()
    if new in s:
        return
    if old not in s:
        raise SystemExit(f"Pattern not found in {path}: {old[:100]!r}")
    path.write_text(s.replace(old, new, 1))

# Keep saved profiles visible independently from the current active connection.
replace_once(
    PREFS,
    '''    fun getProfiles(context: Context): List<ServerProfile> {
        val json = prefs(context).getString(KEY_PROFILES, null)
        if (json != null) {
            return try {
                Gson().fromJson(json, object : TypeToken<List<ServerProfile>>() {}.type)
            } catch (_: Exception) { emptyList() }
        }
        // Migrate old single-server data on first run
        return migrateLegacy(context)
    }
''',
    '''    fun getProfiles(context: Context): List<ServerProfile> {
        val json = prefs(context).getString(KEY_PROFILES, null)
        if (!json.isNullOrBlank()) {
            try {
                val parsed: List<ServerProfile>? = Gson().fromJson(
                    json,
                    object : TypeToken<List<ServerProfile>>() {}.type
                )
                if (!parsed.isNullOrEmpty()) return parsed
            } catch (_: Exception) {
                // Fall through to legacy migration below.
            }
        }
        // Migrate old single-server data on first run, or recover if the multi-profile
        // list was empty/corrupted but legacy credentials still exist.
        return migrateLegacy(context)
    }
''',
)

replace_once(
    PREFS,
    '''    fun deleteProfile(context: Context, id: String) {
        saveProfileList(context, getProfiles(context).filter { it.id != id })
    }

    fun getActiveProfileId(context: Context): String? =
        prefs(context).getString(KEY_ACTIVE_PROFILE_ID, null)

    fun setActiveProfile(context: Context, id: String) {
''',
    '''    fun deleteProfile(context: Context, id: String) {
        val activeId = getActiveProfileId(context)
        saveProfileList(context, getProfiles(context).filter { it.id != id })
        if (id == activeId) {
            prefs(context).edit()
                .remove(KEY_ACTIVE_PROFILE_ID)
                .remove(KEY_SERVER_URL)
                .remove(KEY_USERNAME)
                .remove(KEY_PASSWORD)
                .apply()
        }
    }

    fun disconnectProfile(context: Context, id: String) {
        if (getActiveProfileId(context) != id) return
        prefs(context).edit()
            .remove(KEY_ACTIVE_PROFILE_ID)
            .remove(KEY_SERVER_URL)
            .remove(KEY_USERNAME)
            .remove(KEY_PASSWORD)
            .apply()
    }

    fun isProfileActive(context: Context, id: String): Boolean =
        getActiveProfileId(context) == id

    fun getActiveProfileId(context: Context): String? =
        prefs(context).getString(KEY_ACTIVE_PROFILE_ID, null)?.takeIf { it.isNotBlank() }

    fun setActiveProfile(context: Context, id: String) {
''',
)

replace_once(
    PREFS,
    '''    fun getActiveProfile(context: Context): ServerProfile? {
        val profiles = getProfiles(context)
        if (profiles.isEmpty()) return null
        val activeId = getActiveProfileId(context)
        return (profiles.find { it.id == activeId } ?: profiles.first()).also {
            if (it.id != activeId) setActiveProfile(context, it.id)
        }
    }
''',
    '''    fun getActiveProfile(context: Context): ServerProfile? {
        val activeId = getActiveProfileId(context) ?: return null
        return getProfiles(context).firstOrNull { it.id == activeId }
    }
''',
)

# Adding a user must not silently make it active. Editing preserves the old active state.
replace_once(
    LOGIN,
    'import com.orbital.iptv.ui.tv.TvModeActivity\\n',
    'import com.orbital.iptv.ui.tv.TvModeActivity\\nimport com.orbital.iptv.ui.users.ListUsersActivity\\n',
)

old_auth = '''                onSuccess = {
                    val editId = intent.getStringExtra("edit_profile_id")
            val old = editId?.let { id -> PrefsManager.getProfiles(this@LoginActivity).firstOrNull { it.id == id } }
            val profile = (old ?: ServerProfile(name = name, serverUrl = url, username = username, password = password)).copy(name = name, serverUrl = url, username = username, password = password)
                    PrefsManager.saveProfile(this@LoginActivity, profile)
                    PrefsManager.setActiveProfile(this@LoginActivity, profile.id)
                    binding.tvStatus.text = "AUTHENTICATION SUCCESSFUL"
                    startHomeActivity()
                },
'''
new_auth = '''                onSuccess = {
                    val editId = intent.getStringExtra("edit_profile_id")
                    val addingUser = intent.getBooleanExtra("add_user", false)
                    val old = editId?.let { id ->
                        PrefsManager.getProfiles(this@LoginActivity)
                            .firstOrNull { it.id == id }
                    }
                    val wasActive = old?.id == PrefsManager.getActiveProfileId(this@LoginActivity)

                    val profile = (old ?: ServerProfile(
                        name = name,
                        serverUrl = url,
                        username = username,
                        password = password
                    )).copy(
                        name = name,
                        serverUrl = url,
                        username = username,
                        password = password
                    )

                    PrefsManager.saveProfile(this@LoginActivity, profile)

                    when {
                        addingUser -> {
                            binding.tvStatus.text = "USER SAVED"
                            startActivity(
                                Intent(this@LoginActivity, ListUsersActivity::class.java)
                                    .addFlags(
                                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                        Intent.FLAG_ACTIVITY_SINGLE_TOP
                                    )
                            )
                            finish()
                        }
                        editId != null -> {
                            if (wasActive) {
                                // Preserve the active connection while updating its credentials.
                                PrefsManager.setActiveProfile(this@LoginActivity, profile.id)
                            }
                            binding.tvStatus.text = "USER UPDATED"
                            startActivity(
                                Intent(this@LoginActivity, ListUsersActivity::class.java)
                                    .addFlags(
                                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                                        Intent.FLAG_ACTIVITY_SINGLE_TOP
                                    )
                            )
                            finish()
                        }
                        else -> {
                            PrefsManager.setActiveProfile(this@LoginActivity, profile.id)
                            binding.tvStatus.text = "AUTHENTICATION SUCCESSFUL"
                            startHomeActivity()
                        }
                    }
                },
'''
replace_once(LOGIN, old_auth, new_auth)

print("List Users profile management fixes applied.")
