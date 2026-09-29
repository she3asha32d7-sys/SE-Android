# SE-Android V100.0.97 — Home Touch Scroll / Scrollbar Fix

## Finding
HomeActivity creates its dashboard ScrollView in code. The XML already requested no scrollbars, but the programmatic ScrollView explicitly set `isVerticalScrollBarEnabled = true`. That programmatic setting wins for the actual dashboard view and produces the visible scrollbar at the far-right edge.

## Fix
- Set `isVerticalScrollBarEnabled = false` on the Home dashboard ScrollView.
- Set `isHorizontalScrollBarEnabled = false` for consistency.
- Keep `overScrollMode` and the ScrollView itself unchanged so touch scrolling remains enabled.
- Keep the XML Home ScrollView configured with `android:scrollbars="none"`.
- Version is 100.0.97.

## Expected behavior
The right-edge scrollbar thumb disappears. Swiping up/down with a finger continues to scroll the Home page normally.

Android's ScrollView/NestedScrollView APIs distinguish scrollbar visibility from scrolling behavior; `scrollbars="none"` / `setVerticalScrollBarEnabled(false)` hides scrollbar rendering without disabling scrolling. citeturn901792search0turn901792search2
