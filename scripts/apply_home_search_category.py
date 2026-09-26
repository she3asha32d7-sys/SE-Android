from pathlib import Path

path = Path("app/src/main/java/com/orbital/iptv/ui/home/HomeActivity.kt")
s = path.read_text()

old = '''    companion object {
        const val EXTRA_SECTION = "section"
    }
'''
new = '''    companion object {
        const val EXTRA_SECTION = "section"
        const val EXTRA_LIVE_CATEGORY_ID = "live_category_id"
    }
'''
if "EXTRA_LIVE_CATEGORY_ID" not in s:
    if old not in s: raise SystemExit("Home companion block not found")
    s = s.replace(old, new, 1)

old = '''        setIntent(intent)
        when (intent.getStringExtra(EXTRA_SECTION)?.uppercase(Locale.ROOT)) {
            "LIVE" -> showSection("LIVE")
            "HOME" -> showSection("HOME")
            else -> showSection("HOME")
        }
'''
new = '''        pendingLiveCategoryId = intent.getStringExtra(EXTRA_LIVE_CATEGORY_ID)
        setIntent(intent)
        when (intent.getStringExtra(EXTRA_SECTION)?.uppercase(Locale.ROOT)) {
            "LIVE" -> showSection("LIVE")
            "HOME" -> showSection("HOME")
            else -> showSection("HOME")
        }
'''
if "pendingLiveCategoryId = intent.getStringExtra(EXTRA_LIVE_CATEGORY_ID)" not in s:
    if old not in s: raise SystemExit("Home onNewIntent block not found")
    s = s.replace(old, new, 1)

old = '''    private lateinit var liveAdapter: LiveChannelAdapter
    private var epgLoadingJob: Job? = null
    private var miniPlayer: ExoPlayer? = null
    private var liveSearchActive = false
    private var currentSection: Section = Section.HOME
'''
new = '''    private lateinit var liveAdapter: LiveChannelAdapter
    private var epgLoadingJob: Job? = null
    private var miniPlayer: ExoPlayer? = null
    private var liveSearchActive = false
    private var currentSection: Section = Section.HOME
    private var pendingLiveCategoryId: String? = null
'''
if "private var pendingLiveCategoryId: String? = null" not in s:
    if old not in s: raise SystemExit("Home fields block not found")
    s = s.replace(old, new, 1)

old = '''        setupLiveChannels()
        showSection(intent.getStringExtra(EXTRA_SECTION) ?: "HOME")
'''
new = '''        setupLiveChannels()
        pendingLiveCategoryId = intent.getStringExtra(EXTRA_LIVE_CATEGORY_ID)
        showSection(intent.getStringExtra(EXTRA_SECTION) ?: "HOME")
'''
if "pendingLiveCategoryId = intent.getStringExtra(EXTRA_LIVE_CATEGORY_ID)" not in s.split("override fun onNewIntent")[0]:
    if old not in s: raise SystemExit("Home onCreate section setup not found")
    s = s.replace(old, new, 1)

old = '''            showLiveChannels(state.channels)
            binding.tvChannelCount?.text = "${state.channels.size} CHANNELS"

            setupCategoryMenu(state.xtreamCategories, state.selectedXtreamCategory)
'''
new = '''            showLiveChannels(state.channels)
            binding.tvChannelCount?.text = "${state.channels.size} CHANNELS"

            pendingLiveCategoryId?.let { requestedId ->
                state.xtreamCategories.firstOrNull { it.categoryId == requestedId }?.let { requestedCategory ->
                    pendingLiveCategoryId = null
                    viewModel.selectXtreamCategory(requestedCategory)
                }
            }
            setupCategoryMenu(state.xtreamCategories, state.selectedXtreamCategory)
'''
if "pendingLiveCategoryId?.let { requestedId ->" not in s:
    if old not in s: raise SystemExit("Home observer block not found")
    s = s.replace(old, new, 1)

path.write_text(s)
print("Home Live category deep-link support added")
