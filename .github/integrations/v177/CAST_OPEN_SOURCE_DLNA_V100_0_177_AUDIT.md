# Open-source DLNA adapters — V100.0.177

## Cast menu
The six original choices remain in the same order: TV, DLNA, DLNA 2 (the previous TDM-compatible path), Screen Mirror / Wireless Display, Web Video Caster, and Google Cast. Five additional choices are appended:
- DLNA 1 (TDM): calls the already-present independent TDM-compatible manager.
- DLNA 2 (CastLab): its own SSDP search and UPnP description parser.
- DLNA 3 (Vega): Wi-Fi-bound SSDP discovery, multicast plus broadcast search, and OkHttp SOAP control.
- DLNA 4 (NekoVideo): per-IPv4-interface discovery with SSDP group join and separate AVTransport actions.
- DLNA 5 (YAACC): renderer-focused UPnP control-point discovery and a post-Play GetTransportInfo request.

## Sources and licensing
See THIRD_PARTY_NOTICES.md and THIRD_PARTY_LICENSES/VEGA-APACHE-2.0.txt. The NekoVideo discovery pattern adapted into the new adapter is GPL-3.0-only, so this derived release and its corresponding source are distributed under GPLv3. Vega code is based on Apache-2.0 revision 9ccc0c8, prior to its current-branch license change. No TDM source or decompiled TDM code is included. YAACC's application and Cling fork are not embedded; the YAACC-labelled adapter remains an SE-native control-point implementation.

## Verification
The GitHub workflow checks version metadata, all eleven menu choices/routes, the original cast entries, existence of all five adapter paths, and the protected release-signing fingerprint. A successful CI build is not proof that a particular Samsung/LG television accepts a specific stream URL or codec. Testing on the target TV is still required.
