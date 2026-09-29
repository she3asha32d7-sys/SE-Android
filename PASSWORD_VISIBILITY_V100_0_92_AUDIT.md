# SE-Android V100.0.92 — Password Visibility Audit

## Root cause
The Xtream login layout contained `btn_show_password`, but `LoginActivity.setupClickListeners()` did not attach any click handler to that view. The password field therefore remained in `textPassword` mode and the control was non-functional.

## Changes
- Added a stateful click handler in `LoginActivity.kt`.
- Hidden state uses `PasswordTransformationMethod`.
- Visible state removes the transformation so the entered password is shown.
- Caret position is preserved across toggles.
- Replaced the visible `SHOW PASSWORD` text control with an `ImageButton`.
- Added vector icons for visibility and visibility-off states.
- Updated the button accessibility description when the state changes.
- Added `show_password` and `hide_password` string resources.
- Bumped the project version to `100.0.92`.

## Validation
- XML resources parse successfully.
- The v92 patch applies cleanly to the V100.0.91 source package.
- The existing 118dp control area and focusability are preserved for remote navigation.
