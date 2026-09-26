#!/usr/bin/env python3
import base64, hashlib, lzma
from pathlib import Path

TARGET = Path("app/src/main/java/com/orbital/iptv/utils/SEKeyboardController.kt")
parts = [
    Path("scripts/keyboard_v24_payload_1.b64"),
    Path("scripts/keyboard_v24_payload_2.b64"),
    Path("scripts/keyboard_v24_payload_3.b64"),
    Path("scripts/keyboard_v24_payload_4.b64"),
]
payload = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
expected_payload_sha256 = "a32acc59bcfc8b79d2440d7b9d6378a8b27b71c3a25c1c8f68d05ebe5909aa54"
actual_payload_sha256 = hashlib.sha256(payload.encode()).hexdigest()
if actual_payload_sha256 != expected_payload_sha256:
    raise SystemExit(
        f"SE Keyboard v24 payload integrity mismatch: {actual_payload_sha256}"
    )

content = lzma.decompress(base64.b64decode(payload)).decode("utf-8")

# Compile fixes for the controller's context overloads.
needle = '    private fun currentLanguage(context: Context): LanguageSpec {'
overload = '''    private fun currentLanguage(): LanguageSpec {
        val context = activeTarget?.get()?.context
        return if (context != null) currentLanguage(context) else languages.first()
    }

'''
if needle not in content:
    raise SystemExit("SE Keyboard v24 expected currentLanguage(Context) declaration not found")
content = content.replace(needle, overload + needle, 1)

content = content.replace(
    '        val current = currentLanguageId ?: currentLanguage(context).id',
    '        val current = currentLanguageId ?: context?.let { currentLanguage(it).id } ?: available.first().id',
    1,
)

TARGET.write_text(content, encoding="utf-8")
print(f"Wrote {TARGET} ({len(content.splitlines())} lines, {len(content)} chars)")
