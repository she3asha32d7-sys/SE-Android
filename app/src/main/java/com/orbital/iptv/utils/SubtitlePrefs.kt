package com.orbital.iptv.utils

import android.content.Context
import android.graphics.Typeface
import androidx.media3.ui.CaptionStyleCompat
import androidx.media3.ui.SubtitleView

/** Applies the Genç-style Subtitle Appearance preferences to Media3 subtitle rendering. */
object SubtitlePrefs {
    fun apply(context: Context, view: SubtitleView?) {
        if (view == null) return

        val family = PrefsManager.getSubtitleFontFamily(context)
        val style = PrefsManager.getSubtitleFontStyle(context)

        val familyName = when (family) {
            PrefsManager.SubtitleFontFamily.SYSTEM,
            PrefsManager.SubtitleFontFamily.SANS_SERIF -> "sans-serif"
            PrefsManager.SubtitleFontFamily.SERIF -> "serif"
            PrefsManager.SubtitleFontFamily.MONOSPACE -> "monospace"
            PrefsManager.SubtitleFontFamily.CASUAL,
            PrefsManager.SubtitleFontFamily.CURSIVE -> "cursive"
        }
        val typefaceStyle = when (style) {
            PrefsManager.SubtitleFontStyle.NORMAL -> Typeface.NORMAL
            PrefsManager.SubtitleFontStyle.BOLD -> Typeface.BOLD
            PrefsManager.SubtitleFontStyle.ITALIC -> Typeface.ITALIC
            PrefsManager.SubtitleFontStyle.BOLD_ITALIC -> Typeface.BOLD_ITALIC
        }
        val typeface = Typeface.create(familyName, typefaceStyle)

        fun alpha(color: Int, opacity: Int): Int =
            ((opacity.coerceIn(0, 100) * 255 / 100) shl 24) or (color and 0x00FFFFFF)

        val textColor = alpha(
            PrefsManager.getSubtitleTextColor(context),
            PrefsManager.getSubtitleTextOpacity(context)
        )
        val backgroundColor = alpha(
            PrefsManager.getSubtitleBackgroundColor(context),
            PrefsManager.getSubtitleBackgroundOpacity(context)
        )
        val windowColor = alpha(
            PrefsManager.getSubtitleWindowColor(context),
            PrefsManager.getSubtitleWindowOpacity(context)
        )

        val edgeType = when (PrefsManager.getSubtitleEdgeType(context)) {
            PrefsManager.SubtitleEdgeType.NONE -> CaptionStyleCompat.EDGE_TYPE_NONE
            PrefsManager.SubtitleEdgeType.OUTLINE -> CaptionStyleCompat.EDGE_TYPE_OUTLINE
            PrefsManager.SubtitleEdgeType.DROP_SHADOW -> CaptionStyleCompat.EDGE_TYPE_DROP_SHADOW
            PrefsManager.SubtitleEdgeType.RAISED -> CaptionStyleCompat.EDGE_TYPE_RAISED
            PrefsManager.SubtitleEdgeType.DEPRESSED -> CaptionStyleCompat.EDGE_TYPE_DEPRESSED
        }

        view.setApplyEmbeddedStyles(true)
        view.setApplyEmbeddedFontSizes(false)
        view.setStyle(
            CaptionStyleCompat(
                edgeType,
                textColor,
                backgroundColor,
                windowColor,
                PrefsManager.getSubtitleEdgeColor(context),
                typeface
            )
        )

        val size = 0.053f * (PrefsManager.getSubtitleTextSize(context) / 100f)
        view.setFractionalTextSize(size)

        val bottomPadding = when (PrefsManager.getSubtitleVerticalPosition(context)) {
            PrefsManager.SubtitleVerticalPosition.BOTTOM -> 0.08f
            PrefsManager.SubtitleVerticalPosition.CENTER -> 0.42f
            PrefsManager.SubtitleVerticalPosition.TOP -> 0.72f
        }
        view.setBottomPaddingFraction(bottomPadding)
    }
}
