SE IPTV Player V100.0.177 — Third-party notices
=================================================

This release keeps all pre-existing SE cast options and adds five additional menu paths.

1) TDM-compatible DLNA (DLNA 1)
   The TDM application supplied by the user is proprietary. No TDM source or decompiled
   application code is copied into SE. The adapter in TdmCompatibleDlnaManager.kt is an
   independent implementation based on the observed SSDP/UPnP wire behavior.

2) CastLab (DLNA 2)
   Upstream: https://codeberg.org/tom79/CastLab
   CastLab is distributed under GNU GPL v3 only. The SE adapter provides its own integration
   with SE's Activity and media URL flow; it is not a copy of the CastLab application UI.

3) Vega (DLNA 3)
   Upstream: https://github.com/vega-org/vega-app/tree/9ccc0c8
   Portions of the native DLNA discovery/control approach were adapted from Vega revision
   9ccc0c8, which was licensed under Apache License 2.0. See VEGA-APACHE-2.0.txt.
   The repository's current Vega license has since changed; this release uses the earlier
   Apache-2.0 revision identified above, not the current main-branch code.

4) NekoVideo (DLNA 4)
   Upstream: https://github.com/FellipitoPV/NekoVideo
   Selected multi-interface SSDP discovery patterns were adapted from DLNACastManager.kt.
   Copyright and licensing remain subject to GNU GPL v3.0. This SE integration is modified
   and is not the complete NekoVideo application.

5) YAACC (DLNA 5)
   Upstream: https://github.com/tobexyz/yaacc-code
   This is an SE-native UPnP/AVTransport control-point adapter. YAACC's complete application
   and bundled Cling fork have NOT been embedded; the adapter follows standard UPnP AVTransport
   action semantics and performs a post-Play GetTransportInfo request.

CastLab and YAACC names are used to identify the implementation target/reference, not to imply
endorsement or affiliation. The TV receiver must support a media renderer/AVTransport service.
Successful compilation does not guarantee playback on every television, codec, or IPTV provider.
