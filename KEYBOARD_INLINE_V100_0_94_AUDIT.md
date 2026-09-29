# SE-Android V100.0.94 — Keyboard + Inline Search Fix Audit

## Root cause
Two independent behaviors were interacting:
1. Search had been changed to a dedicated SearchActivity, which created the unwanted separate search page.
2. The application runs in landscape. Android documents that software IMEs may enter fullscreen mode in landscape on smaller displays. That fullscreen IME can show an extracted editor UI instead of leaving the application UI visible.

## V100.0.94 design
- Source basis: the successfully built V100.0.91 source artifact.
- Re-applies the V100.0.92 password visibility fix.
- SEARCH uses the existing InlineSearchController on the current Activity.
- No dedicated SearchActivity is included.
- Search input stays over the current page; Home/Movies/Series/Downloads UI remains the underlying Activity.
- The inline search uses the Android system IME only.
- Inline search requests `IME_FLAG_NO_FULLSCREEN` and `IME_FLAG_NO_EXTRACT_UI`.
- All XML EditTexts are given the same IME flags.
- Activity-created and dynamically present EditTexts also receive the same flags from the application lifecycle.
- Inline search uses `SOFT_INPUT_ADJUST_NOTHING` so the keyboard overlays the lower part of the current page rather than replacing it with a new editor screen.
- Version is 100.0.94.

## Android documentation basis
Android's EditorInfo documentation states that `IME_FLAG_NO_FULLSCREEN` requests that the IME never enter fullscreen mode; fullscreen is especially relevant on small screens in landscape. The `IME_FLAG_NO_EXTRACT_UI` flag requests that the IME not show its extracted-text UI. `InputMethodManager.showSoftInput(view, ...)` operates on the currently focused editor.

## Validation
The GitHub workflow builds from the verified V100.0.91 source artifact, applies the V100.0.94 transformation, assembles the debug APK, validates the ZIP, and packages both APK and source ZIP as Actions artifacts.
