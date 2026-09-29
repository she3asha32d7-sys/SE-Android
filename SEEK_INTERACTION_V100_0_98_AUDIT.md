# SE-Android V100.0.98 — Seek Interaction Audit

## Requested behavior
1. One ordinary touch anywhere on the video only reveals the media-player UI. It does not hide it and does not seek.
2. The first ordinary double tap on the left or right side of a VOD video opens the SEEK value picker.
3. After a value is selected, that value remains active for the rest of the current video.
4. Later double taps on the right side seek forward by the selected value.
5. Later double taps on the left side seek backward by the selected value.
6. The SEEK buttons beside PLAY always open the value picker again, even when a value is already selected.
7. After choosing a new value, the two side button labels become -<value> and +<value>.
8. Vertical side swipes retain the existing brightness/volume gestures.
9. Horizontal swipes are not treated as seek actions, preventing gesture/tap conflicts.

## V100.0.98 implementation
- Added per-video `seekPickerArmedForSideDoubleTap`, reset when a new PlayerActivity/video starts.
- First double tap opens the picker; selecting a value disables the first-double-tap picker for that video.
- Subsequent double taps call the same `seekBy(±seekStepMs)` path used by the player seek controls.
- `btnGencSeekBack` and `btnGencSeekForward` continue to call `showSeekStepPicker()` directly, so they always reopen the picker.
- A single tap on the video now always calls `showGencOverlay()`; it never toggles/hides the controls.
- The previous side single-tap seek and side long-press/speed-playing paths were removed from touch handling because they conflicted with the specified tap state machine.
- `updateSeekStepButton()` is called when player controls initialize, and again after each picker selection, keeping -SEEK/+SEEK labels synchronized.
- Version is 100.0.98.

## Android event model
The implementation distinguishes ACTION_DOWN/ACTION_UP and uses the event timing window for the second tap. Android documents ACTION_DOWN as the start of a touch sequence and ACTION_UP as the end; the event stream can therefore be used to distinguish a completed tap sequence. The touch behavior is kept in PlayerActivity so it does not interfere with the inner player view's normal rendering.
