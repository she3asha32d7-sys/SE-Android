from pathlib import Path

PLAYER = Path("app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt")
OVERLAY = Path("app/src/main/res/layout/layout_genc_player_overlay.xml")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"pattern not found: {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


# PlayerActivity: use the exact URL already being played.
replace_once(
    PLAYER,
    "import com.orbital.iptv.utils.GencMediaPlayer\n",
    "import com.orbital.iptv.utils.GencMediaPlayer\n"
    "import com.orbital.iptv.utils.DownloadStore\n",
)

replace_once(
    PLAYER,
    """        b.btnGencNext.setOnClickListener { playNextEpisodeNow() }
        b.btnGencOpenWith.setOnClickListener { launchExternalPlayer() }
""",
    """        b.btnGencNext.setOnClickListener { playNextEpisodeNow() }
        b.btnGencDownload.visibility = if (!isLive && streamUrl.isNotBlank()) View.VISIBLE else View.GONE
        b.btnGencDownload.setOnClickListener {
            if (isLive || streamUrl.isBlank()) {
                Toast.makeText(this, "DOWNLOAD IS NOT AVAILABLE", Toast.LENGTH_SHORT).show()
            } else {
                DownloadStore.start(this, streamUrl, channelName.ifBlank { "video" })
                Toast.makeText(this, "DOWNLOAD STARTED", Toast.LENGTH_SHORT).show()
                showGencOverlay()
            }
        }
        b.btnGencOpenWith.setOnClickListener { launchExternalPlayer() }
""",
)

# Genç-style player action row: place DOWNLOAD immediately before OPEN WITH.
replace_once(
    OVERLAY,
    """                <TextView
                    android:id="@+id/btn_genc_open_with"
""",
    """                <TextView
                    android:id="@+id/btn_genc_download"
                    android:layout_width="wrap_content"
                    android:layout_height="38dp"
                    android:layout_marginEnd="6dp"
                    android:background="@drawable/bg_genc_pill"
                    android:clickable="true"
                    android:focusable="true"
                    android:gravity="center"
                    android:minWidth="104dp"
                    android:paddingStart="14dp"
                    android:paddingEnd="14dp"
                    android:text="DOWNLOAD"
                    android:textColor="#FFFFFFFF"
                    android:textSize="11sp"
                    android:textStyle="bold" />

                <TextView
                    android:id="@+id/btn_genc_open_with"
""",
)

print("SE player download controls applied")
