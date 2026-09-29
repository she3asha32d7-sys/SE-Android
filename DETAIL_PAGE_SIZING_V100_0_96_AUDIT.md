# SE-Android V100.0.96 — Movie/Series Detail Sizing Audit

Movie detail had an artificial minimum height of 900dp and a child using match_parent inside that card. That forces a large empty vertical area and can push lower actions such as DOWNLOAD far below the actual information.

Series detail had a fixed 520dp RecyclerView for episodes even when the selected season contained few episodes. That creates a large unused area and makes the page unnecessarily long.

V100.0.96 changes:
- Movie detail card no longer has the 900dp minimum.
- Movie detail content uses wrap_content vertically.
- Movie poster is reduced from 286x429dp to 260x390dp while preserving the 2:3 ratio.
- Movie and Series detail ScrollViews no longer stretch short content with fillViewport.
- Series hero card is reduced from 360dp to 330dp.
- Series season tabs are reduced from 52dp to 46dp.
- Series episode list height is calculated from the selected season: two episodes per row, six visible rows maximum (336dp); longer seasons can scroll inside the RecyclerView.
- Version is 100.0.96.

Expected result: the detail pages are shorter, the empty scroll tail is removed, and the lower action controls are within the actual measured content instead of being separated by artificial vertical space.