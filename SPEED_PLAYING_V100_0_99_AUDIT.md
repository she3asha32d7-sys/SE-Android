# SE-Android V100.0.99 — Speed Playing Long-Press Audit

Speed Playing has exactly two prerequisites:
1. A non-1x SPEED PLAYING value is explicitly selected from the Media Player control.
2. A long press is held on the left or right side of the video.

At 1x, long press does nothing.
At any non-1x value, right-side long press starts forward Speed Playing; left-side long press starts reverse Speed Playing.
Releasing the finger stops Speed Playing and restores normal playback.
Single tap remains controls-only, and V98 double-tap seek remains separate.

The implementation uses Android ViewConfiguration.getLongPressTimeout() for the long-press threshold. Android documents ACTION_DOWN as gesture start and ACTION_UP/ACTION_CANCEL as gesture termination.

Version: 100.0.99