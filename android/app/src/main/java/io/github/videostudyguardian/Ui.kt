package io.github.videostudyguardian

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** 纯代码构建界面用的小工具（不依赖 AndroidX）。 */
object Ui {
    const val PURPLE = 0xFF7A5CFF.toInt()
    const val INK = 0xFF1F1B3D.toInt()
    const val MUTED = 0xFF8A83B0.toInt()
    const val GREEN = 0xFF2F9E72.toInt()
    const val RED = 0xFFC43C3C.toInt()
    const val YELLOW = 0xFFFFD23F.toInt()
    const val OPTION_BG = 0xFFF2EFFF.toInt()
    const val OPTION_BORDER = 0xFFDDD5FF.toInt()

    fun dp(context: Context, value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), context.resources.displayMetrics).toInt()

    fun rounded(context: Context, fill: Int, radiusDp: Int, stroke: Int = 0, strokeColor: Int = Color.TRANSPARENT) =
        GradientDrawable().apply {
            setColor(fill)
            cornerRadius = dp(context, radiusDp).toFloat()
            if (stroke > 0) setStroke(dp(context, stroke), strokeColor)
        }

    fun text(context: Context, value: String, sp: Float, color: Int = INK, bold: Boolean = false, center: Boolean = false) =
        TextView(context).apply {
            text = value
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
            if (center) gravity = Gravity.CENTER_HORIZONTAL
        }

    fun button(context: Context, label: String, sp: Float = 18f, fill: Int = YELLOW, color: Int = INK) =
        Button(context).apply {
            text = label
            isAllCaps = false
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sp)
            setTextColor(color)
            setTypeface(typeface, Typeface.BOLD)
            background = rounded(context, fill, 14)
            val p = dp(context, 12)
            setPadding(p * 2, p, p * 2, p)
        }

    fun ghost(context: Context, label: String) = Button(context, null, android.R.attr.borderlessButtonStyle).apply {
        text = label
        isAllCaps = false
        setTextColor(MUTED)
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
    }

    fun vertical(context: Context, spacingDp: Int = 0) = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        if (spacingDp > 0) {
            showDividers = LinearLayout.SHOW_DIVIDER_MIDDLE
            dividerDrawable = GradientDrawable().apply { setSize(1, dp(context, spacingDp)); setColor(Color.TRANSPARENT) }
        }
    }

    fun matchWidth(topMarginDp: Int = 0, context: Context? = null): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            if (context != null) topMargin = dp(context, topMarginDp)
        }

    fun wrapCenter(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            gravity = Gravity.CENTER_HORIZONTAL
        }

    fun View.visible(show: Boolean) {
        visibility = if (show) View.VISIBLE else View.GONE
    }
}
