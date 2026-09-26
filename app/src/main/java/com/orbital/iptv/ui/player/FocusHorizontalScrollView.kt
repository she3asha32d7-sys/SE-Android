package com.orbital.iptv.ui.player

import android.content.Context
import android.util.AttributeSet
import android.view.KeyEvent
import android.view.View
import android.widget.HorizontalScrollView

/**
 * TV-friendly horizontal action bar.
 *
 * Keeps the focused action visible and allows the D-pad LEFT/RIGHT keys
 * to scroll the action strip when more controls exist than fit on screen.
 */
class FocusHorizontalScrollView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : HorizontalScrollView(context, attrs, defStyleAttr) {

    init {
        isSmoothScrollingEnabled = true
        isHorizontalScrollBarEnabled = false
        overScrollMode = View.OVER_SCROLL_NEVER
    }

    override fun requestChildFocus(child: View, focused: View) {
        super.requestChildFocus(child, focused)

        post {
            if (!focused.isShown) return@post

            val rect = android.graphics.Rect()
            focused.getDrawingRect(rect)
            offsetDescendantRectToMyCoords(focused, rect)

            val leftEdge = paddingLeft
            val rightEdge = width - paddingRight

            when {
                rect.left < leftEdge -> {
                    smoothScrollBy(rect.left - leftEdge, 0)
                }
                rect.right > rightEdge -> {
                    smoothScrollBy(rect.right - rightEdge, 0)
                }
            }
        }
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN) {
            when (event.keyCode) {
                KeyEvent.KEYCODE_DPAD_LEFT -> {
                    if (canScrollHorizontally(-1)) {
                        val handled = arrowScroll(View.FOCUS_LEFT)
                        if (handled) return true
                    }
                }
                KeyEvent.KEYCODE_DPAD_RIGHT -> {
                    if (canScrollHorizontally(1)) {
                        val handled = arrowScroll(View.FOCUS_RIGHT)
                        if (handled) return true
                    }
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }
}
