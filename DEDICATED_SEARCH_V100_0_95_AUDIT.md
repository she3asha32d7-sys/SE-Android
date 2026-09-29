# SE-Android V100.0.95 — Dedicated Search Page Fix

## Requested behavior
Pressing SEARCH from the Main Sidebar must open one dedicated Search page. Search input and results must belong to that page, never to Downloads or another section.

## Root cause addressed
The V100.0.94 branch intentionally routed SEARCH back to InlineSearchController. That matched an earlier requirement but is the opposite of the current requirement. V100.0.95 reverses that routing and restores the existing dedicated SearchActivity implementation.

## Fix
- Restore SearchActivity, SearchAdapter, and activity_search.xml.
- Route Section.SEARCH in MainSidebarController to SearchActivity.
- Map pending focus for Section.SEARCH to SearchActivity.
- Clear any inline search overlay before starting SearchActivity.
- Register SearchActivity in AndroidManifest.xml.
- Use the Android system/mobile IME in SearchActivity.
- Set IME_FLAG_NO_FULLSCREEN and IME_FLAG_NO_EXTRACT_UI to prevent landscape fullscreen/extracted editor UI.
- Use SOFT_INPUT_ADJUST_NOTHING so the Search page remains visible when the keyboard is shown.
- Version is 100.0.95.

## Expected flow
Downloads -> press SEARCH -> SearchActivity becomes the foreground Activity -> Main Sidebar SEARCH is the active section -> Search bar and results are rendered by SearchActivity only.

Android's task/back-stack model puts a started Activity on top of the current Activity, while REORDER_TO_FRONT can bring an existing target Activity forward in its task. This project already uses that navigation pattern.
