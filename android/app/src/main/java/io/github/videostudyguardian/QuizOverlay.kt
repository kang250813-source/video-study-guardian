package io.github.videostudyguardian

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import io.github.videostudyguardian.Ui.visible

/**
 * 盖在所有应用上方的全屏答题层（TYPE_APPLICATION_OVERLAY）。
 * 窗口拦截全部触摸；返回键无效；答对一题解锁，答错多加一题并等待 3 秒；家长密码可直接解锁。
 */
class QuizOverlay(
    private val context: Context,
    private val prefs: Prefs,
    private val onPassed: () -> Unit,
) {
    companion object {
        const val WRONG_WAIT = 3  // 答错后需等待的秒数，防止乱点
    }

    private val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val handler = Handler(Looper.getMainLooper())
    private val bank = QuestionBank(context.assets)

    private var root: View? = null
    private var question: QuestionBank.Question? = null
    private var need = 1          // 还需答对的题数；答错一题 +1
    private var waiting = false
    private var sessionActive = false

    private lateinit var quizPage: LinearLayout
    private lateinit var adminPage: LinearLayout
    private lateinit var progress: TextView
    private lateinit var subject: TextView
    private lateinit var prompt: TextView
    private lateinit var optionsBox: LinearLayout
    private val optionButtons = ArrayList<Button>()
    private lateinit var fillBox: LinearLayout
    private lateinit var answer: EditText
    private lateinit var feedback: TextView
    private lateinit var password: EditText
    private lateinit var adminMsg: TextView
    private lateinit var adminOk: Button

    val isShowing: Boolean get() = root?.isAttachedToWindow == true

    fun show() {
        if (isShowing) return
        if (!Permissions.canDrawOverlays(context)) return
        root?.let { old -> try { wm.removeViewImmediate(old) } catch (e: Exception) { } }
        val view = buildView()
        try {
            wm.addView(view, layoutParams())
        } catch (e: Exception) {
            root = null
            return
        }
        root = view
        if (!sessionActive) {
            sessionActive = true
            need = 1
            waiting = false
        }
        showQuiz()
        if (question == null || !waiting) nextQuestion() else renderQuestion()
        updateProgress()
    }

    fun hide() {
        handler.removeCallbacksAndMessages(null)
        sessionActive = false
        waiting = false
        question = null
        val view = root ?: return
        root = null
        try { wm.removeViewImmediate(view) } catch (e: Exception) { }
    }

    private fun layoutParams() = WindowManager.LayoutParams(
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.MATCH_PARENT,
        WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED or
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
        PixelFormat.OPAQUE,
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
        if (Build.VERSION.SDK_INT >= 28) {
            layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        title = "视频学习守护"
    }

    // ───────────────────────── 界面 ─────────────────────────

    /** 根布局：吞掉返回键，也吞掉所有触摸（不会传给下面的应用）。 */
    private inner class BlockingFrame(ctx: Context) : FrameLayout(ctx) {
        override fun dispatchKeyEvent(event: KeyEvent): Boolean {
            if (event.keyCode == KeyEvent.KEYCODE_BACK) {
                if (event.action == KeyEvent.ACTION_UP && adminPage.visibility == View.VISIBLE) showQuiz()
                return true
            }
            return super.dispatchKeyEvent(event)
        }

        override fun onTouchEvent(event: android.view.MotionEvent?): Boolean {
            if (event?.action == android.view.MotionEvent.ACTION_UP) performClick()
            return true
        }

        override fun performClick(): Boolean {
            super.performClick()
            return true
        }
    }

    private fun buildView(): View {
        val c = context
        val frame = BlockingFrame(c)
        frame.isFocusable = true
        frame.isFocusableInTouchMode = true
        frame.background = GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            intArrayOf(0xFF1B1840.toInt(), 0xFF2C2266.toInt(), 0xFF3D2A7A.toInt()),
        )

        val scroll = ScrollView(c).apply { isFillViewport = true }
        frame.addView(scroll, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))

        val outer = FrameLayout(c)
        val pad = Ui.dp(c, 18)
        outer.setPadding(pad, pad * 2, pad, pad * 2)
        scroll.addView(outer, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT))

        val card = Ui.vertical(c)
        card.background = Ui.rounded(c, 0xF7FFFFFF.toInt(), 28)
        val cp = Ui.dp(c, 22)
        card.setPadding(cp, cp, cp, cp)
        outer.addView(card, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.CENTER))

        // 答题页
        quizPage = Ui.vertical(c, 12)
        quizPage.addView(Ui.text(c, "✦ 视频时间到了 ✦", 15f, Ui.PURPLE, bold = true, center = true), Ui.matchWidth())
        quizPage.addView(Ui.text(c, "认真答题，答对就能继续观看", 24f, 0xFF24204A.toInt(), bold = true, center = true), Ui.matchWidth())
        progress = Ui.text(c, "", 17f, Ui.PURPLE, bold = true, center = true)
        quizPage.addView(progress, Ui.matchWidth())
        subject = Ui.text(c, "", 15f, android.graphics.Color.WHITE, bold = true, center = true).apply {
            val p = Ui.dp(c, 4)
            setPadding(p * 4, p, p * 4, p)
        }
        quizPage.addView(subject, Ui.wrapCenter())
        prompt = Ui.text(c, "", 26f, Ui.INK, bold = true, center = true).apply { setLineSpacing(0f, 1.15f) }
        quizPage.addView(prompt, Ui.matchWidth())

        optionsBox = Ui.vertical(c, 12)
        optionButtons.clear()
        for (i in 0 until 4) {
            val b = Button(c).apply {
                isAllCaps = false
                gravity = Gravity.START or Gravity.CENTER_VERTICAL
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 22f)
                setTextColor(0xFF2A2357.toInt())
                val p = Ui.dp(c, 16)
                setPadding(p, p, p, p)
                minHeight = Ui.dp(c, 64)
                setOnClickListener { onOption(i) }
            }
            optionButtons.add(b)
            optionsBox.addView(b, Ui.matchWidth())
        }
        quizPage.addView(optionsBox, Ui.matchWidth())

        fillBox = Ui.vertical(c, 12)
        answer = EditText(c).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 26f)
            gravity = Gravity.CENTER
            isSingleLine = true
            hint = "在这里输入答案"
            // 不用 VISIBLE_PASSWORD：部分填空题答案是汉字，需要能切换中文输入法
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            imeOptions = EditorInfo.IME_ACTION_DONE
            setOnEditorActionListener { _, actionId, _ ->
                if (actionId == EditorInfo.IME_ACTION_DONE) { onFill(); true } else false
            }
        }
        fillBox.addView(answer, Ui.matchWidth())
        fillBox.addView(Ui.button(c, "提交答案", 22f).apply { setOnClickListener { onFill() } }, Ui.wrapCenter())
        quizPage.addView(fillBox, Ui.matchWidth())

        feedback = Ui.text(c, "", 19f, Ui.RED, bold = true, center = true)
        quizPage.addView(feedback, Ui.matchWidth())
        quizPage.addView(Ui.ghost(c, "家长解锁").apply { setOnClickListener { showAdmin() } }, Ui.wrapCenter())
        card.addView(quizPage, Ui.matchWidth())

        // 家长页（同一窗口内）
        adminPage = Ui.vertical(c, 16)
        adminPage.addView(Ui.text(c, "家长解锁", 26f, 0xFF24204A.toInt(), bold = true, center = true), Ui.matchWidth())
        adminPage.addView(Ui.text(c, "输入家长密码", 15f, Ui.MUTED, center = true), Ui.matchWidth())
        password = EditText(c).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 24f)
            gravity = Gravity.CENTER
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            imeOptions = EditorInfo.IME_ACTION_DONE
            setOnEditorActionListener { _, actionId, _ ->
                if (actionId == EditorInfo.IME_ACTION_DONE) { onPassword(); true } else false
            }
        }
        adminPage.addView(password, Ui.matchWidth())
        adminMsg = Ui.text(c, "", 17f, Ui.RED, bold = true, center = true)
        adminPage.addView(adminMsg, Ui.matchWidth())
        adminOk = Ui.button(c, "解锁", 20f).apply { setOnClickListener { onPassword() } }
        adminPage.addView(adminOk, Ui.wrapCenter())
        adminPage.addView(Ui.ghost(c, "返回答题").apply { setOnClickListener { showQuiz() } }, Ui.wrapCenter())
        card.addView(adminPage, Ui.matchWidth())

        return frame
    }

    // ───────────────────────── 题目 ─────────────────────────

    private fun nextQuestion() {
        question = bank.next(prefs.quizConfig())
        renderQuestion()
    }

    private fun renderQuestion() {
        val q = question ?: return
        val color = when (q.subject) { "英语" -> Ui.GREEN; "数学" -> 0xFF3A7BD5.toInt(); else -> 0xFFE0703A.toInt() }
        subject.text = q.subject
        subject.background = Ui.rounded(context, color, 999)
        prompt.text = q.prompt
        if (q.type == "choice") {
            optionsBox.visible(true)
            fillBox.visible(false)
            for ((i, b) in optionButtons.withIndex()) {
                if (i < q.options.size) {
                    b.visible(true)
                    b.text = "${"ABCD"[i]}.  ${q.options[i]}"
                    styleOption(b, Ui.OPTION_BG, Ui.OPTION_BORDER)
                    b.isEnabled = true
                } else {
                    b.visible(false)
                }
            }
        } else {
            optionsBox.visible(false)
            fillBox.visible(true)
            answer.setText("")
            answer.isEnabled = true
            answer.requestFocus()
            handler.postDelayed({ showKeyboard(answer) }, 250)
        }
    }

    private fun styleOption(b: Button, fill: Int, border: Int) {
        b.background = Ui.rounded(context, fill, 16, 2, border)
    }

    private fun onOption(index: Int) {
        val q = question ?: return
        if (waiting || q.type != "choice") return
        optionButtons.forEach { it.isEnabled = false }
        styleOption(optionButtons[q.right], 0xFFD9F7E8.toInt(), Ui.GREEN)
        if (index == q.right) {
            correct()
        } else {
            styleOption(optionButtons[index], 0xFFFFE1E1.toInt(), 0xFFD94A4A.toInt())
            wrong("")
        }
    }

    private fun onFill() {
        val q = question ?: return
        if (waiting || q.type != "fill") return
        answer.isEnabled = false
        if (bank.isCorrectFill(q, answer.text.toString())) correct() else wrong("正确答案：${q.answers.first()}")
    }

    private fun updateProgress() {
        progress.text = "还需答对 $need 题" + if (need == 1) "（答错一题会多加一题）" else ""
    }

    private fun correct() {
        feedback.setTextColor(Ui.GREEN)
        need -= 1
        waiting = true
        if (need <= 0) {
            feedback.text = "答对了！马上解锁～"
            handler.postDelayed({ onPassed() }, 900)
            return
        }
        feedback.text = "答对了！还要再答对 $need 题"
        handler.postDelayed({
            waiting = false
            feedback.text = ""
            updateProgress()
            nextQuestion()
        }, 1200)
    }

    private fun wrong(extra: String) {
        feedback.setTextColor(Ui.RED)
        need += 1
        updateProgress()
        waiting = true
        var left = WRONG_WAIT
        val tick = object : Runnable {
            override fun run() {
                if (left <= 0) {
                    waiting = false
                    feedback.text = ""
                    nextQuestion()
                    return
                }
                val msg = if (extra.isEmpty()) "答错了，多加一题。看看正确答案，" else "答错了，多加一题。$extra，"
                feedback.text = "$msg$left 秒后换一道题"
                left -= 1
                handler.postDelayed(this, 1000)
            }
        }
        tick.run()
    }

    // ───────────────────────── 家长解锁 ─────────────────────────

    private fun showAdmin() {
        password.setText("")
        adminMsg.text = ""
        adminOk.isEnabled = true
        quizPage.visible(false)
        adminPage.visible(true)
        password.requestFocus()
        handler.postDelayed({ showKeyboard(password) }, 250)
    }

    private fun showQuiz() {
        if (!::adminPage.isInitialized) return
        adminPage.visible(false)
        quizPage.visible(true)
        hideKeyboard(password)
    }

    private fun onPassword() {
        val input = password.text.toString()
        if (input.isEmpty()) return
        adminOk.isEnabled = false
        adminMsg.setTextColor(Ui.MUTED)
        adminMsg.text = "正在验证…"
        Thread {
            val ok = try { Password.check(prefs, input) } catch (e: Exception) { false }
            handler.post {
                if (!isShowing) return@post
                if (ok) {
                    hideKeyboard(password)
                    onPassed()
                } else {
                    adminOk.isEnabled = true
                    adminMsg.setTextColor(Ui.RED)
                    adminMsg.text = "密码不正确"
                    password.setText("")
                }
            }
        }.start()
    }

    private fun showKeyboard(view: View) {
        if (!isShowing) return
        val imm = context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        imm.showSoftInput(view, InputMethodManager.SHOW_IMPLICIT)
    }

    private fun hideKeyboard(view: View) {
        val imm = context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(view.windowToken, 0)
    }
}
