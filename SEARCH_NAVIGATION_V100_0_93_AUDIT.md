# SE-Android V100.0.93 — Search Navigation Audit

## Root cause
The Main Sidebar SEARCH item was not navigating to SearchActivity. It called InlineSearchController.open(activity, root), which intentionally creates a search overlay inside the current Activity. When the current Activity was DownloadsActivity, the search bar and search results therefore appeared on top of DownloadsActivity and focus remained in that Activity.

## Fix
- SEARCH now targets SearchActivity.
- The pending-focus map now recognizes SearchActivity as the target for Section.SEARCH.
- SEARCH navigation clears any inline search overlay on the current screen, then starts/reorders SearchActivity.
- SearchActivity is explicitly declared in AndroidManifest.xml.
- Version is bumped to 100.0.93.

## Expected behavior
From Downloads, Movies, Series, Home, Favourites, or another main section, pressing SEARCH opens the dedicated Search page. The main sidebar focus moves to SEARCH, and all search input/results are handled by SearchActivity.

## Android reference
Android requires Activity subclasses to be declared in the application manifest before the system can start them. FLAG_ACTIVITY_REORDER_TO_FRONT brings an already-running target Activity to the front of the task.
