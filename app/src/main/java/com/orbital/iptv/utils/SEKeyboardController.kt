package com.orbital.iptv.utils

import android.app.Activity
import android.app.Dialog
import android.content.Context
import android.graphics.Color
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.text.Editable
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewTreeObserver
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.orbital.iptv.R
import java.lang.ref.WeakReference
import java.util.WeakHashMap

/**
 * SE's in-app keyboard.
 *
 * It is deliberately not an Android IME: the keyboard is rendered inside the SAME application
 * window and writes directly to the focused EditText. Keeping it in-window is important for
 * Android/TV devices where a separate PopupWindow may be composited or positioned differently
 * from the activity/dialog content.
 */
object SEKeyboardController {
    private const val KEY_HEIGHT_DP = 42
    private const val KEY_GAP_DP = 4
    private const val PANEL_PADDING_DP = 8

    private val installedRoots = WeakHashMap<View, Boolean>()
    private val boundFields = WeakHashMap<EditText, Boolean>()
    private var activeTarget: WeakReference<EditText>? = null
    private var activeOverlay: FrameLayout? = null
    private var shift = false
    private var symbols = false

    fun install(activity: Activity) {
        activity.window.setSoftInputMode(
            android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN
        )
        val root = activity.window.decorView

        // Application ActivityLifecycleCallbacks can run before Activity.onCreate()/setContentView().
        // Post the scan so fields inflated by the Activity are also bound.
        root.post { installRoot(root) }
    }

    fun installDialog(dialog: Dialog) {
        dialog.setOnShowListener {
            dialog.window?.decorView?.let { root ->
                installRoot(root)
                root.post { bindEditTexts(root) }
            }
        }
    }

    fun prepare(editText: EditText): EditText {
        bindEditText(editText)
        return editText
    }

    fun showFor(editText: EditText) {
        bindEditText(editText)
        editText.showSoftInputOnFocus = false
        hideSystemIme(editText)
        // Multiple focus/touch/lifecycle callbacks can arrive for the same field.
        // If this field already owns a visible keyboard overlay, keep it instead of rebuilding it.
        if (activeTarget?.get() === editText && activeOverlay?.parent != null) {
            activeOverlay?.bringToFront()
            return
        }

        activeTarget = WeakReference(editText)

        val root = editText.rootView
        if (!root.isAttachedToWindow || root.width <= 0 || root.height <= 0) {
            editText.post { showFor(editText) }
            return
        }

        shift = false
        symbols = isNumericField(editText)
        showKeyboardOverlay(editText, root)
    }

    fun hide() {
        activeOverlay?.let { overlay ->
            (overlay.parent as? ViewGroup)?.removeView(overlay)
        }
        activeOverlay = null
        activeTarget = null
    }

    fun showFocused(root: View) {
        val focused = root.findFocus()
        if (focused is EditText) showFor(focused)
    }

    private fun installRoot(root: View) {
        if (installedRoots.put(root, true) == null) {
            root.viewTreeObserver.addOnGlobalFocusChangeListener(
                object : ViewTreeObserver.OnGlobalFocusChangeListener {
                    override fun onGlobalFocusChanged(oldFocus: View?, newFocus: View?) {
                        if (newFocus is EditText) {
                            bindEditText(newFocus)
                            newFocus.showSoftInputOnFocus = false
                            newFocus.post { showFor(newFocus) }
                        } else if (oldFocus is EditText && activeTarget?.get() === oldFocus) {
                            hide()
                        }
                    }
                }
            )
        }

        // Always scan, even if the root was registered earlier. This is what fixes Activities
        // whose decorView existed before setContentView() inflated their EditTexts.
        bindEditTexts(root)
    }

    private fun bindEditTexts(root: View) {
        fun walk(view: View) {
            if (view is EditText) bindEditText(view)
            if (view is ViewGroup) {
                for (i in 0 until view.childCount) walk(view.getChildAt(i))
            }
        }
        walk(root)
    }

    private fun bindEditText(editText: EditText) {
        if (boundFields.put(editText, true) != null) return

        editText.showSoftInputOnFocus = false
        editText.setOnTouchListener { v, _ ->
            (v as? EditText)?.let { target ->
                target.requestFocus()
                showFor(target)
            }
            false
        }
        editText.setOnFocusChangeListener { v, hasFocus ->
            if (hasFocus) {
                (v as? EditText)?.let { target ->
                    target.post { showFor(target) }
                }
            } else if (activeTarget?.get() === v) {
                hide()
            }
        }
    }

    private fun buildKeyboard(context: Context): View {
        val panel = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(
                dp(context, PANEL_PADDING_DP),
                dp(context, PANEL_PADDING_DP),
                dp(context, PANEL_PADDING_DP),
                dp(context, PANEL_PADDING_DP)
            )
            background = GradientDrawable().apply {
                cornerRadius = dp(context, 14).toFloat()
                setColor(ContextCompat.getColor(context, R.color.se_panel))
                setStroke(dp(context, 1), ContextCompat.getColor(context, R.color.sky_cyan))
            }
        }

        if (symbols || isUrlField()) {
            addRow(
                panel,
                if (symbols) listOf("1","2","3","4","5","6","7","8","9","0")
                else listOf("@",".","/",":","-","_","+","=","#","&")
            )
            if (symbols) {
                addRow(panel, listOf("@","#","$","%","&","*","-","_","+","="))
                addRow(panel, listOf("(",")","[","]","{","}",";",",","?","!"))
            } else {
                addLetterRows(panel)
            }
        } else {
            addRow(panel, listOf("1","2","3","4","5","6","7","8","9","0"))
            addLetterRows(panel)
        }

        addBottomRow(panel)
        return panel
    }

    private fun addLetterRows(panel: LinearLayout) {
        val rows = listOf(
            listOf("q","w","e","r","t","y","u","i","o","p"),
            listOf("a","s","d","f","g","h","j","k","l"),
            listOf("⇧","z","x","c","v","b","n","m","⌫")
        )
        rows.forEach { row -> addRow(panel, row) }
    }

    private fun addBottomRow(panel: LinearLayout) {
        val row = LinearLayout(panel.context).apply { orientation = LinearLayout.HORIZONTAL }
        addKey(row, if (symbols) "ABC" else "123#", 1.0f) {
            symbols = !symbols
            refreshKeyboard()
        }
        addKey(row, "SPACE", 2.5f) { insertText(" ") }
        addKey(row, "PASTE", 1.3f) { paste() }
        addKey(row, "CLEAR", 1.2f) { activeTarget?.get()?.setText("") }
        val target = activeTarget?.get()
        val action = if (target != null && (target.imeOptions and EditorActionMask.ACTION_DONE) != 0) "DONE" else "NEXT"
        addKey(row, action, 1.4f) { performAction() }
        panel.addView(row)
    }

    private fun addRow(panel: LinearLayout, keys: List<String>) {
        val row = LinearLayout(panel.context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        keys.forEach { key ->
            val weight = when (key) {
                "⇧", "⌫" -> 1.3f
                else -> 1f
            }
            addKey(row, displayKey(key), weight) {
                when (key) {
                    "⇧" -> {
                        shift = !shift
                        refreshKeyboard()
                    }
                    "⌫" -> backspace()
                    else -> insertText(key)
                }
            }
        }
        panel.addView(
            row,
            LinearLayout.LayoutParams(-1, dp(panel.context, KEY_HEIGHT_DP)).apply {
                topMargin = dp(panel.context, KEY_GAP_DP)
            }
        )
    }

    private fun addKey(row: LinearLayout, label: String, weight: Float, onClick: () -> Unit) {
        val context = row.context
        val tv = TextView(context).apply {
            text = label
            gravity = Gravity.CENTER
            setTextColor(ContextCompat.getColor(context, R.color.sky_white))
            textSize = if (label.length > 5) 10f else 13f
            isClickable = true
            isFocusable = false
            background = GradientDrawable().apply {
                cornerRadius = dp(context, 8).toFloat()
                setColor(ContextCompat.getColor(context, R.color.se_panel_alt))
                setStroke(dp(context, 1), ContextCompat.getColor(context, R.color.sky_light_blue))
            }
            setOnClickListener { onClick() }
        }
        row.addView(
            tv,
            LinearLayout.LayoutParams(0, -1, weight).apply {
                leftMargin = dp(context, KEY_GAP_DP / 2)
                rightMargin = dp(context, KEY_GAP_DP / 2)
            }
        )
    }

    private fun refreshKeyboard() {
        val target = activeTarget?.get() ?: return
        val root = target.rootView
        if (!root.isAttachedToWindow || root.width <= 0 || root.height <= 0) return
        showKeyboardOverlay(target, root)
    }

    private fun showKeyboardOverlay(editText: EditText, root: View) {
        val content = root.findViewById<ViewGroup>(android.R.id.content)
            ?: (root as? ViewGroup)
            ?: return

        activeOverlay?.let { old ->
            (old.parent as? ViewGroup)?.removeView(old)
        }

        val overlay = FrameLayout(editText.context).apply {
            clipChildren = false
            clipToPadding = false
            elevation = dp(editText.context, 20).toFloat()
            setBackgroundColor(Color.TRANSPARENT)
            isClickable = false
            isFocusable = false
        }

        val keyboard = buildKeyboard(editText.context)
        keyboard.elevation = dp(editText.context, 20).toFloat()
        overlay.addView(
            keyboard,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.BOTTOM
            }
        )

        content.addView(
            overlay,
            ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )

        // Force a real layout pass after insertion. This is important on Android TV where
        // the content hierarchy may be attached before its final window dimensions exist.
        overlay.visibility = View.VISIBLE
        keyboard.visibility = View.VISIBLE
        activeOverlay = overlay
        overlay.bringToFront()
        overlay.requestLayout()

        content.post {
            if (activeOverlay === overlay && overlay.parent != null) {
                overlay.visibility = View.VISIBLE
                overlay.bringToFront()
                overlay.requestLayout()
                keyboard.requestLayout()
                bringFocusedFieldIntoView(editText)
            }
        }
    }

    private fun displayKey(key: String): String {
        if (key.length != 1 || !key[0].isLetter()) return key
        return if (shift) key.uppercase() else key.lowercase()
    }

    private fun insertText(text: String) {
        val target = activeTarget?.get() ?: return
        val start = maxOf(0, target.selectionStart)
        val end = maxOf(start, target.selectionEnd)
        val editable: Editable = target.text ?: return
        editable.replace(start, end, text)
        val newPos = (start + text.length).coerceAtMost(editable.length)
        target.setSelection(newPos)
        target.post { hideSystemIme(target) }
    }

    private fun backspace() {
        val target = activeTarget?.get() ?: return
        val editable = target.text ?: return
        val start = target.selectionStart
        val end = target.selectionEnd
        if (start != end) {
            editable.delete(start, end)
            target.setSelection(start)
        } else if (start > 0) {
            editable.delete(start - 1, start)
            target.setSelection(start - 1)
        }
        target.post { hideSystemIme(target) }
    }

    private fun paste() {
        val target = activeTarget?.get() ?: return
        val clipboard = target.context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
        val clip = clipboard?.primaryClip
            ?.takeIf { it.itemCount > 0 }
            ?.getItemAt(0)
            ?.coerceToText(target.context)
            ?.toString()
            ?: return
        insertText(clip)
    }

    private fun performAction() {
        val target = activeTarget?.get() ?: return
        hideSystemIme(target)
        val isDone =
            (target.imeOptions and EditorActionMask.ACTION_DONE) != 0 || target.imeOptions == 0
        if (isDone) {
            target.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_DONE)
            hide()
        } else {
            target.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_NEXT)
            val next = target.focusSearch(View.FOCUS_FORWARD)
            if (next != null) next.requestFocus() else hide()
        }
    }

    private fun hideSystemIme(view: View) {
        val imm = view.context.getSystemService(Context.INPUT_METHOD_SERVICE)
            as? InputMethodManager ?: return
        imm.hideSoftInputFromWindow(view.windowToken, 0)
    }

    private fun bringFocusedFieldIntoView(editText: EditText) {
        editText.post {
            val r = Rect()
            editText.getDrawingRect(r)
            editText.requestRectangleOnScreen(r, true)
        }
    }

    private fun isNumericField(editText: EditText): Boolean {
        val type = editText.inputType and InputType.TYPE_MASK_CLASS
        return type == InputType.TYPE_CLASS_NUMBER || type == InputType.TYPE_CLASS_PHONE
    }

    private fun isUrlField(): Boolean {
        val input = activeTarget?.get()?.inputType ?: return false
        return (input and InputType.TYPE_TEXT_VARIATION_URI) != 0
    }

    private fun dp(context: Context, value: Int): Int =
        (value * context.resources.displayMetrics.density).toInt().coerceAtLeast(1)

    private object EditorActionMask {
        const val ACTION_DONE = android.view.inputmethod.EditorInfo.IME_ACTION_DONE
    }
}
