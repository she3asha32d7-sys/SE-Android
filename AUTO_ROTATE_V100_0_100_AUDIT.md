# SE-Android V100.0.100 — Auto Rotate OFF Hard Lock Audit

## Problem found
The earlier implementation stored only the boolean Auto Rotate preference and used `SCREEN_ORIENTATION_LOCKED` per Activity. Android defines LOCKED as locking the current rotation, but applying that independently during every Activity transition allowed the system to reconsider orientation before the new Activity received its lock.

## V100.0.100 fix
- When Auto Rotate is switched OFF, capture the exact current display rotation first.
- Convert it to a concrete ActivityInfo orientation:
  - ROTATION_90 -> LANDSCAPE
  - ROTATION_270 -> REVERSE_LANDSCAPE
  - ROTATION_180 -> REVERSE_PORTRAIT
  - ROTATION_0 -> PORTRAIT
- Persist that concrete lock orientation.
- When Auto Rotate is OFF, every Activity uses that same persisted concrete orientation.
- Apply the policy in `onActivityPreCreated` on Android 10/API 29+ so the lock is requested before the Activity's normal creation work.
- Re-apply the same concrete value in `onActivityCreated` and `onActivityResumed`.
- No Activity in the project contains a separate sensor/portrait request; the application-wide lifecycle policy owns orientation.
- When Auto Rotate is ON, the policy returns to `SCREEN_ORIENTATION_SENSOR_LANDSCAPE`.
- Version is 100.0.100.

## Expected behavior
OFF freezes the screen to the exact side that is visible when OFF is pressed. Opening Home, Movies, Series, Search, Downloads, Settings, Player, or any other Activity does not switch orientation. Turning ON restores automatic landscape sensor rotation.

Android documents `SCREEN_ORIENTATION_LOCKED` as locking the display to its current rotation, while concrete LANDSCAPE/REVERSE_LANDSCAPE values specify the exact requested orientation. citeturn145906search0turn145906search2
