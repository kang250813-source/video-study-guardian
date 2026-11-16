package io.github.videostudyguardian

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast

/** 家长页：首次设置、密码登录、全部设置和权限引导。 */
class MainActivity : Activity() {

    private lateinit var prefs: Prefs
    private val handler = Handler(Looper.getMainLooper())
    private var authed = false
    private var leavingForSettings = false
    private var statusView: TextView? = null
    private var diagView: TextView? = null
    private val refreshStatus = object : Runnable {
        override fun run() {
            statusView?.text = statusText()
            diagView?.text = diagnosticsText()
            handler.removeCallbacks(this)
            handler.postDelayed(this, 2000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        // 家长页不允许截屏/出现在最近任务缩略图里，避免泄露设置
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }

    override fun onResume() {
        super.onResume()
        leavingForSettings = false
        // 服务没在跑（或计时循环超过 10 秒没动）就重新拉起；失败时 start() 会弹 Toast 并记录错误
        if (prefs.setupDone && (!GuardService.running || System.currentTimeMillis() - prefs.lastTickAt > 10_000L)) {
            GuardService.start(this)
        }
        render()
        handler.post(refreshStatus)
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(refreshStatus)
    }

    override fun onStop() {
        super.onStop()
        // 离开家长页后需重新输入密码（去系统设置授权时除外）
        if (!leavingForSettings) authed = false
    }

    private fun render() {
        when {
            !prefs.setupDone -> showSetup()
            !authed -> showLogin()
            else -> showSettings()
        }
    }

    // ───────────────────────── 通用布局 ─────────────────────────

    private fun page(build: LinearLayout.() -> Unit) {
        statusView = null
        diagView = null
        val scroll = ScrollView(this)
        val box = Ui.vertical(this, 10)
        val p = Ui.dp(this, 20)
        box.setPadding(p, p, p, p * 2)
        box.build()
        scroll.addView(box)
        setContentView(scroll)
    }

    private fun LinearLayout.title(text: String) =
        addView(Ui.text(context, text, 24f, Ui.INK, bold = true), Ui.matchWidth())

    private fun LinearLayout.section(text: String) =
        addView(Ui.text(context, text, 18f, Ui.PURPLE, bold = true).apply { setPadding(0, Ui.dp(context, 14), 0, 0) }, Ui.matchWidth())

    private fun LinearLayout.note(text: String, color: Int = Ui.MUTED) =
        addView(Ui.text(context, text, 14f, color).apply { setLineSpacing(0f, 1.2f) }, Ui.matchWidth())

    private fun LinearLayout.label(text: String) =
        addView(Ui.text(context, text, 16f, Ui.INK), Ui.matchWidth())

    private fun passwordField(hint: String) = EditText(this).apply {
        this.hint = hint
        isSingleLine = true
        inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
    }

    private fun numberField(value: Int) = EditText(this).apply {
        setText(value.toString())
        isSingleLine = true
        inputType = InputType.TYPE_CLASS_NUMBER
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
    }

    private fun spinner(items: List<String>, selected: Int) = Spinner(this).apply {
        adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, items)
        setSelection(selected.coerceIn(0, items.size - 1))
    }

    private fun termGroup(selected: String): RadioGroup = RadioGroup(this).apply {
        orientation = RadioGroup.HORIZONTAL
        for ((i, t) in listOf("上", "下").withIndex()) {
            addView(RadioButton(this@MainActivity).apply {
                id = View.generateViewId()
                text = "${t}册"
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
                tag = t
                if (t == selected) isChecked = true
            })
            if (i == 0) addView(View(this@MainActivity), LinearLayout.LayoutParams(Ui.dp(this@MainActivity, 24), 1))
        }
    }

    private fun RadioGroup.selectedTerm(): String =
        (findViewById<RadioButton>(checkedRadioButtonId)?.tag as? String) ?: "上"

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()

    private fun background(work: () -> Boolean, done: (Boolean) -> Unit) {
        Thread {
            val r = try { work() } catch (e: Exception) { false }
            handler.post { if (!isFinishing) done(r) }
        }.start()
    }

    // ───────────────────────── 首次设置 ─────────────────────────

    private fun showSetup() = page {
        title("视频学习守护 · 首次设置")
        note("孩子在抖音、快手、B站等视频 App 里累计观看满设定的分钟数后，屏幕会被答题界面盖住：答对一题继续看，答错多加一题。家长密码可直接解锁。")
        section("家长密码（至少 ${Password.MIN_LENGTH} 位）")
        val pw1 = passwordField("设置家长密码")
        val pw2 = passwordField("再次输入家长密码")
        addView(pw1, Ui.matchWidth()); addView(pw2, Ui.matchWidth())
        section("每轮观看分钟数（${Prefs.MIN_MINUTES}–${Prefs.MAX_MINUTES}）")
        val minutes = numberField(10)
        addView(minutes, Ui.matchWidth())
        section("孩子的年级")
        val grade = spinner((1..6).map { "${it} 年级" }, 5)
        addView(grade, Ui.matchWidth())
        val term = termGroup(Prefs.defaultTerm())
        addView(term, Ui.matchWidth())
        val msg = Ui.text(context, "", 15f, Ui.RED)
        addView(msg, Ui.matchWidth())
        val save = Ui.button(context, "保存并开始")
        addView(save, Ui.matchWidth(12, context))
        save.setOnClickListener {
            val p1 = pw1.text.toString()
            val m = minutes.text.toString().toIntOrNull()
            when {
                p1.length < Password.MIN_LENGTH -> { msg.text = "密码至少需要 ${Password.MIN_LENGTH} 位"; return@setOnClickListener }
                p1 != pw2.text.toString() -> { msg.text = "两次密码不一致"; return@setOnClickListener }
                m == null || m < Prefs.MIN_MINUTES || m > Prefs.MAX_MINUTES -> {
                    msg.text = "分钟数必须是 ${Prefs.MIN_MINUTES} 到 ${Prefs.MAX_MINUTES} 的整数"; return@setOnClickListener
                }
            }
            save.isEnabled = false
            msg.setTextColor(Ui.MUTED); msg.text = "正在保存…"
            val g = grade.selectedItemPosition + 1
            val t = term.selectedTerm()
            background({ Password.set(prefs, p1); true }) {
                prefs.minutes = m!!
                prefs.grade = g
                prefs.term = t
                prefs.mode = "全部"
                prefs.subjects = Prefs.SUBJECTS
                prefs.videoApps = Prefs.DEFAULT_VIDEO_APPS.keys
                prefs.appliedMinutes = -1
                prefs.locked = false
                prefs.setupDone = true
                authed = true
                toast("设置完成：每轮 $m 分钟，$g 年级${t}册。请继续授予下面的权限。")
                GuardService.start(this@MainActivity)
                render()
            }
        }
    }

    // ───────────────────────── 登录 ─────────────────────────

    private fun showLogin() = page {
        title("视频学习守护")
        note("家长设置需要输入密码。")
        val pw = passwordField("家长密码")
        addView(pw, Ui.matchWidth())
        val msg = Ui.text(context, "", 15f, Ui.RED)
        addView(msg, Ui.matchWidth())
        val ok = Ui.button(context, "进入家长设置")
        addView(ok, Ui.matchWidth(8, context))
        statusView = Ui.text(context, statusText(), 15f, Ui.MUTED)
        addView(statusView, Ui.matchWidth(16, context))
        diagnosticsCard(this)
        ok.setOnClickListener {
            val input = pw.text.toString()
            if (input.isEmpty()) return@setOnClickListener
            ok.isEnabled = false
            msg.setTextColor(Ui.MUTED); msg.text = "正在验证…"
            background({ Password.check(prefs, input) }) { good ->
                if (good) {
                    authed = true
                    render()
                } else {
                    ok.isEnabled = true
                    msg.setTextColor(Ui.RED); msg.text = "密码不正确"
                    pw.setText("")
                }
            }
        }
    }

    private fun statusText(): String {
        if (!prefs.setupDone) return ""
        val left = kotlin.math.ceil(prefs.remainingSeconds.coerceAtMost(prefs.minutes * 60f) / 60f).toInt().coerceAtLeast(0)
        val state = when {
            prefs.paused -> "已暂停"
            prefs.locked -> "答题中"
            GuardService.running -> "守护中"
            else -> "服务未运行"
        }
        val missing = mutableListOf<String>()
        if (!Permissions.hasUsageAccess(this)) missing += "使用情况访问"
        if (!Permissions.canDrawOverlays(this)) missing += "悬浮窗"
        return "状态：$state · 本轮剩余约 $left 分钟" + if (missing.isEmpty()) "" else "\n缺少权限：${missing.joinToString("、")}"
    }

    // ───────────────────────── 诊断 ─────────────────────────

    private fun diagnosticsCard(parent: LinearLayout) {
        val card = Ui.vertical(this, 4)
        val p = Ui.dp(this, 14)
        card.setPadding(p, p, p, p)
        card.background = Ui.rounded(this, Ui.OPTION_BG, 14, 1, Ui.OPTION_BORDER)
        card.addView(Ui.text(this, "运行诊断（每 2 秒刷新）", 16f, Ui.PURPLE, bold = true), Ui.matchWidth())
        val tv = Ui.text(this, diagnosticsText(), 14f, Ui.INK).apply { setLineSpacing(0f, 1.25f) }
        card.addView(tv, Ui.matchWidth())
        diagView = tv
        parent.addView(card, Ui.matchWidth(8, this))
    }

    private fun yesNo(b: Boolean) = if (b) "✅ 是" else "❌ 否"

    private fun diagnosticsText(): String {
        if (!prefs.setupDone) return ""
        val now = System.currentTimeMillis()
        val lastTick = prefs.lastTickAt
        val tickAge = if (lastTick > 0) (now - lastTick) / 1000 else -1
        val serviceOk = GuardService.running && tickAge in 0..10
        val serviceLine = when {
            serviceOk -> "✅ 运行中（${tickAge} 秒前计时循环）"
            GuardService.running -> "⚠️ 服务在但计时循环 ${if (tickAge < 0) "从未运行" else "已 $tickAge 秒没动"}"
            else -> "❌ 未运行"
        }
        val pkg = prefs.lastForegroundPackage
        val source = when (prefs.lastForegroundSource) {
            "events" -> "使用事件"
            "cache" -> "沿用上次"
            "usage_stats" -> "使用统计兜底"
            "no_permission" -> "无权限"
            else -> "未识别"
        }
        val fgLine = if (pkg.isEmpty()) "（未检测到）· $source" else "${appLabel(pkg)}（$pkg）· $source"
        val ignored = GuardService.ignoredPackages(this)
        val inScope = pkg.isNotEmpty() && pkg !in ignored &&
            (prefs.scope == Prefs.SCOPE_ALL || pkg in prefs.videoApps)
        val scopeLabel = Prefs.SCOPE_LABELS[Prefs.SCOPES.indexOf(prefs.scope).coerceAtLeast(0)]
        val remaining = kotlin.math.ceil(prefs.remainingSeconds.coerceIn(0f, prefs.minutes * 60f)).toInt()
        val sb = StringBuilder()
        sb.append("服务：").append(serviceLine).append('\n')
        sb.append("使用情况访问：").append(yesNo(Permissions.hasUsageAccess(this))).append('\n')
        sb.append("悬浮窗：").append(yesNo(Permissions.canDrawOverlays(this))).append('\n')
        sb.append("通知：").append(yesNo(Permissions.hasNotifications(this))).append('\n')
        sb.append("计时范围：").append(scopeLabel).append('\n')
        sb.append("当前前台 App：").append(fgLine).append('\n')
        if (pkg.isNotEmpty()) sb.append("该 App 是否计入：").append(yesNo(inScope)).append('\n')
        sb.append("正在计时：").append(yesNo(serviceOk && prefs.watching))
        if (prefs.paused) sb.append("（已暂停守护）")
        if (prefs.locked) sb.append("（答题中）")
        sb.append('\n')
        sb.append("本轮剩余：").append(remaining).append(" 秒（每轮 ").append(prefs.minutes).append(" 分钟）")
        val err = prefs.lastError
        if (err.isNotEmpty()) sb.append("\n最近错误：").append(err)
        return sb.toString()
    }

    // ───────────────────────── 设置 ─────────────────────────

    private fun showSettings() = page {
        title("家长设置")
        statusView = Ui.text(context, statusText(), 15f, Ui.INK)
        addView(statusView, Ui.matchWidth())
        diagnosticsCard(this)

        // 权限放在最前面，第一次进来最需要
        section("权限（全部打勾才能正常工作）")
        permissionRow(this, "使用情况访问（识别正在用的 App）", Permissions.hasUsageAccess(context)) {
            openSettings(listOf(Permissions.usageAccessIntent(context), Intent(android.provider.Settings.ACTION_USAGE_ACCESS_SETTINGS)))
        }
        permissionRow(this, "显示在其他应用上层（答题界面）", Permissions.canDrawOverlays(context)) {
            openSettings(listOf(Permissions.overlayIntent(context), Permissions.appDetailsIntent(context)))
        }
        permissionRow(this, "通知（显示剩余时间，保持后台运行）", Permissions.hasNotifications(context)) {
            if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
                shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS).not() && !askedNotifications
            ) {
                askedNotifications = true
                leavingForSettings = true
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
            } else {
                openSettings(listOf(Permissions.notificationSettingsIntent(context), Permissions.appDetailsIntent(context)))
            }
        }
        permissionRow(this, "忽略电池优化（防止被系统杀掉）", Permissions.ignoresBatteryOptimizations(context)) {
            openSettings(listOf(Permissions.batteryIntent(context), Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)))
        }

        section("OPPO / 一加 / realme（ColorOS）用户请注意")
        note(
            "ColorOS 会主动清理后台应用，请额外设置：\n" +
                "① 设置 → 应用 → 自启动管理（或“手机管家 → 权限隐私 → 自启动管理”）：打开“视频学习守护”。\n" +
                "② 设置 → 电池 → 应用耗电管理 → 视频学习守护：允许“后台运行”“自启动”“关联启动”，关闭“智能限制”。\n" +
                "③ 在最近任务里下拉本应用卡片加锁，避免一键清理时被关掉。",
            Ui.INK,
        )
        val oppoRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        oppoRow.addView(Ui.button(context, "自启动管理", 15f, Ui.OPTION_BG).apply {
            setOnClickListener {
                leavingForSettings = true
                if (!Permissions.tryStart(this@MainActivity, Permissions.oppoAutoStartIntents() + Permissions.appDetailsIntent(context))) {
                    leavingForSettings = false
                    toast("没找到自启动页面，请在系统设置里手动查找")
                }
            }
        })
        oppoRow.addView(View(context), LinearLayout.LayoutParams(Ui.dp(context, 12), 1))
        oppoRow.addView(Ui.button(context, "应用详情 / 耗电", 15f, Ui.OPTION_BG).apply {
            setOnClickListener { openSettings(listOf(Permissions.appDetailsIntent(context))) }
        })
        addView(oppoRow, Ui.matchWidth())

        section("计时")
        label("每轮观看分钟数（${Prefs.MIN_MINUTES}–${Prefs.MAX_MINUTES}）")
        val minutes = numberField(prefs.minutes)
        addView(minutes, Ui.matchWidth())
        label("计时范围")
        val scopeGroup = RadioGroup(context).apply {
            orientation = RadioGroup.VERTICAL
            for ((i, key) in Prefs.SCOPES.withIndex()) {
                addView(RadioButton(this@MainActivity).apply {
                    id = View.generateViewId()
                    text = Prefs.SCOPE_LABELS[i]
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
                    tag = key
                    if (key == prefs.scope) isChecked = true
                })
            }
        }
        addView(scopeGroup, Ui.matchWidth())
        note("“所有 App”模式下，除了桌面、系统界面和本应用，用任何 App 都会计时。修改后点下方“保存设置”生效。")
        val pause = Switch(context).apply {
            text = "暂停守护（不计时、不出题）"
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            isChecked = prefs.paused
            setOnCheckedChangeListener { _, checked ->
                prefs.paused = checked
                toast(if (checked) "守护已暂停" else "守护已恢复")
            }
        }
        addView(pause, Ui.matchWidth())

        section("题目")
        label("年级")
        val grade = spinner((1..6).map { "${it} 年级" }, prefs.grade - 1)
        addView(grade, Ui.matchWidth())
        val term = termGroup(prefs.term)
        addView(term, Ui.matchWidth())
        label("科目")
        val current = prefs.subjects
        val boxes = Prefs.SUBJECTS.map { s ->
            CheckBox(context).apply { text = s; isChecked = s in current; setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f) }
        }
        val subjRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        boxes.forEach { subjRow.addView(it) }
        addView(subjRow, Ui.matchWidth())
        label("专题模式")
        val mode = spinner(Prefs.MODES, Prefs.MODES.indexOf(prefs.mode))
        addView(mode, Ui.matchWidth())
        label("英语教材版本")
        val editions = listOf("new", "old")
        val edition = spinner(listOf("新教材（找不到时自动用旧教材）", "旧教材"), editions.indexOf(prefs.englishEdition))
        addView(edition, Ui.matchWidth())
        note("一二年级没有英语，会自动改用其他科目；背古诗只出语文，背单词只出英语。")

        val save = Ui.button(context, "保存设置")
        addView(save, Ui.matchWidth(10, context))
        save.setOnClickListener {
            val m = minutes.text.toString().toIntOrNull()
            if (m == null || m < Prefs.MIN_MINUTES || m > Prefs.MAX_MINUTES) {
                toast("分钟数必须是 ${Prefs.MIN_MINUTES} 到 ${Prefs.MAX_MINUTES} 的整数"); return@setOnClickListener
            }
            prefs.minutes = m
            prefs.scope = (scopeGroup.findViewById<RadioButton>(scopeGroup.checkedRadioButtonId)?.tag as? String) ?: Prefs.SCOPE_SELECTED
            prefs.grade = grade.selectedItemPosition + 1
            prefs.term = term.selectedTerm()
            prefs.subjects = Prefs.SUBJECTS.filterIndexed { i, _ -> boxes[i].isChecked }.ifEmpty { Prefs.SUBJECTS }
            prefs.mode = Prefs.MODES[mode.selectedItemPosition.coerceIn(0, Prefs.MODES.size - 1)]
            prefs.englishEdition = editions[edition.selectedItemPosition.coerceIn(0, 1)]
            val n = QuestionBank(assets).count(prefs.quizConfig())
            // 重启服务并把本轮剩余时间重置为新的分钟数
            val err = GuardService.restart(this@MainActivity)
            if (err == null) toast("已保存：每轮 ${prefs.minutes} 分钟，${prefs.grade} 年级${prefs.term}册，当前题库 $n 题；已重新开始计时")
            render()
        }

        section("视频 App")
        val appsInfo = Ui.text(context, videoAppsSummary(), 15f, Ui.INK)
        addView(appsInfo, Ui.matchWidth())
        val appsRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        appsRow.addView(Ui.button(context, "选择视频 App", 15f, Ui.OPTION_BG).apply {
            setOnClickListener { pickVideoApps { appsInfo.text = videoAppsSummary() } }
        })
        appsRow.addView(View(context), LinearLayout.LayoutParams(Ui.dp(context, 12), 1))
        appsRow.addView(Ui.button(context, "恢复默认", 15f, Ui.OPTION_BG).apply {
            setOnClickListener {
                prefs.videoApps = Prefs.DEFAULT_VIDEO_APPS.keys
                appsInfo.text = videoAppsSummary()
                toast("已恢复默认视频 App 列表")
            }
        })
        addView(appsRow, Ui.matchWidth())

        section("其他")
        addView(Ui.button(context, "立即测试答题界面", 16f, Ui.OPTION_BG).apply {
            setOnClickListener {
                if (!Permissions.canDrawOverlays(context)) { toast("请先允许“显示在其他应用上层”"); return@setOnClickListener }
                if (prefs.paused) { toast("请先关闭“暂停守护”"); return@setOnClickListener }
                GuardService.start(context, GuardService.ACTION_LOCK_NOW)
            }
        }, Ui.matchWidth())
        addView(Ui.button(context, "修改家长密码", 16f, Ui.OPTION_BG).apply { setOnClickListener { changePassword() } }, Ui.matchWidth())
        addView(Ui.button(context, "退出家长设置", 16f).apply {
            setOnClickListener { authed = false; render() }
        }, Ui.matchWidth())
        note("提示：孩子仍可能在系统设置里卸载本应用或关闭权限。建议同时开启系统自带的“家长守护 / 儿童空间 / 应用锁”，锁住“设置”和“应用商店”。")
    }

    private var askedNotifications = false

    private fun permissionRow(parent: LinearLayout, label: String, granted: Boolean, open: () -> Unit) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val t = Ui.text(this, (if (granted) "✅ " else "❌ ") + label, 15f, if (granted) Ui.GREEN else Ui.RED)
        row.addView(t, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        val b = Ui.button(this, if (granted) "查看" else "去开启", 14f, if (granted) Ui.OPTION_BG else Ui.YELLOW)
        b.setOnClickListener { open() }
        row.addView(b)
        parent.addView(row, Ui.matchWidth())
    }

    private fun openSettings(intents: List<Intent>) {
        leavingForSettings = true
        if (!Permissions.tryStart(this, intents)) {
            leavingForSettings = false
            toast("无法打开系统设置页面，请手动前往系统设置")
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        leavingForSettings = false
        render()
    }

    // ───────────────────────── 视频 App 列表 ─────────────────────────

    private fun appLabel(pkg: String): String = try {
        packageManager.getApplicationLabel(packageManager.getApplicationInfo(pkg, 0)).toString()
    } catch (e: Exception) {
        Prefs.DEFAULT_VIDEO_APPS[pkg] ?: pkg
    }

    private fun isInstalled(pkg: String): Boolean = try {
        packageManager.getApplicationInfo(pkg, 0); true
    } catch (e: Exception) { false }

    private fun videoAppsSummary(): String {
        val apps = prefs.videoApps
        val installed = apps.filter { isInstalled(it) }.map { appLabel(it) }.sorted()
        return "已选 ${apps.size} 个，其中本机已安装：" + if (installed.isEmpty()) "无" else installed.joinToString("、")
    }

    private fun pickVideoApps(done: () -> Unit) {
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val launchable = packageManager.queryIntentActivities(launcher, 0)
            .map { it.activityInfo.packageName }
            .filter { it != packageName }
            .toSet()
        val selected = prefs.videoApps
        val all = (launchable + selected + Prefs.DEFAULT_VIDEO_APPS.keys).toList()
            .map { pkg -> pkg to appLabel(pkg) }
            .sortedWith(compareBy<Pair<String, String>>({ it.first !in selected }, { it.first !in launchable }, { it.second }))
        val labels = all.map { (pkg, label) ->
            val tag = if (pkg in launchable) "" else "（未安装）"
            "$label$tag\n$pkg"
        }.toTypedArray()
        val checked = BooleanArray(all.size) { all[it].first in selected }
        AlertDialog.Builder(this)
            .setTitle("勾选要计时的视频 App")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked -> checked[which] = isChecked }
            .setPositiveButton("保存") { _, _ ->
                prefs.videoApps = all.filterIndexed { i, _ -> checked[i] }.map { it.first }.toSet()
                GuardService.start(this)
                done()
                toast("已保存视频 App 列表")
            }
            .setNegativeButton("取消", null)
            .show()
    }

    // ───────────────────────── 修改密码 ─────────────────────────

    private fun changePassword() {
        val box = Ui.vertical(this, 8)
        val p = Ui.dp(this, 20)
        box.setPadding(p, p / 2, p, 0)
        val old = passwordField("当前密码")
        val new1 = passwordField("新密码（至少 ${Password.MIN_LENGTH} 位）")
        val new2 = passwordField("再次输入新密码")
        listOf(old, new1, new2).forEach { box.addView(it, Ui.matchWidth()) }
        val dialog = AlertDialog.Builder(this)
            .setTitle("修改家长密码")
            .setView(box)
            .setPositiveButton("保存", null)
            .setNegativeButton("取消", null)
            .create()
        dialog.setOnShowListener {
            val ok: Button = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            ok.setOnClickListener {
                val n1 = new1.text.toString()
                if (n1.length < Password.MIN_LENGTH) { toast("新密码至少需要 ${Password.MIN_LENGTH} 位"); return@setOnClickListener }
                if (n1 != new2.text.toString()) { toast("两次新密码不一致"); return@setOnClickListener }
                ok.isEnabled = false
                val oldText = old.text.toString()
                background({
                    if (Password.check(prefs, oldText)) { Password.set(prefs, n1); true } else false
                }) { good ->
                    ok.isEnabled = true
                    if (good) { toast("密码已修改"); dialog.dismiss() } else toast("当前密码不正确")
                }
            }
        }
        dialog.show()
    }
}
