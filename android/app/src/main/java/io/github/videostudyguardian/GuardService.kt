package io.github.videostudyguardian

import android.app.KeyguardManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.widget.Toast

/**
 * 前台服务：每 2 秒查看一次前台应用；要计时的 App 在前台且屏幕亮着时累计时间，
 * 用完后在所有应用上方显示全屏答题层。
 */
class GuardService : Service() {

    companion object {
        private const val CHANNEL_ID = "guardian"
        private const val NOTIFICATION_ID = 1
        private const val TICK_MS = 2000L
        private const val MAX_STEP_SECONDS = 5f  // 防止休眠唤醒后一次扣掉太多时间
        private const val EVENT_WINDOW_MS = 60_000L      // 每次都查最近 60 秒的事件（滑动窗口）
        private const val FIRST_EVENT_WINDOW_MS = 10 * 60_000L  // 服务刚启动、还没缓存时多看一点
        const val ACTION_LOCK_NOW = "io.github.videostudyguardian.LOCK_NOW"
        const val ACTION_RESET = "io.github.videostudyguardian.RESET"

        // UsageEvents 事件类型（Android 10+ 的 ACTIVITY_RESUMED/PAUSED 与旧的 MOVE_TO_FOREGROUND/BACKGROUND 数值相同）
        private const val EVENT_RESUMED = 1
        private const val EVENT_PAUSED = 2

        @Volatile
        var running = false
            private set

        /**
         * 启动（或唤醒）守护服务。失败时记录到 Prefs.lastError 并弹出 Toast，不再静默吞掉。
         * 返回 null 表示成功，否则返回错误说明。
         */
        fun start(context: Context, action: String? = null): String? {
            val intent = Intent(context, GuardService::class.java)
            if (action != null) intent.action = action
            return try {
                context.startForegroundService(intent)
                null
            } catch (e: Exception) {
                // Android 12+ 某些后台场景不允许启动前台服务；ColorOS 也可能拦截
                val msg = "守护服务启动失败：${e.javaClass.simpleName}: ${e.message ?: ""}".trim()
                try { Prefs(context).lastError = msg } catch (_: Exception) { }
                Handler(Looper.getMainLooper()).post {
                    try { Toast.makeText(context.applicationContext, msg, Toast.LENGTH_LONG).show() } catch (_: Exception) { }
                }
                msg
            }
        }

        /** 家长保存设置后：停止并重新启动服务，把本轮时间重置为新的分钟数。 */
        fun restart(context: Context): String? {
            Prefs(context).resetRound()
            try { context.stopService(Intent(context, GuardService::class.java)) } catch (_: Exception) { }
            return start(context, ACTION_RESET)
        }

        /** 计时时永远不算的包：本应用、系统界面、桌面。 */
        fun ignoredPackages(context: Context): Set<String> {
            val set = hashSetOf(
                context.packageName,
                "com.android.systemui",
                "com.oppo.launcher", "com.android.launcher", "com.android.launcher3",
                "com.coloros.recents", "com.oplus.launcher", "com.google.android.apps.nexuslauncher",
            )
            try {
                val home = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
                context.packageManager.queryIntentActivities(home, 0).forEach { set += it.activityInfo.packageName }
            } catch (_: Exception) { }
            return set
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var prefs: Prefs
    private lateinit var overlay: QuizOverlay
    private var lastTick = 0L
    private var foregroundPackage: String? = null
    private var foregroundSource = "none"
    private var ignored: Set<String> = emptySet()
    private var ignoredRefreshedAt = 0L
    private var lastNotificationText = ""
    private var focusRequest: AudioFocusRequest? = null

    private val tickRunnable = object : Runnable {
        override fun run() {
            try {
                tick()
            } catch (e: Throwable) {
                // 不让单次异常终止守护循环，但记录下来给家长页诊断
                try { prefs.lastError = "计时循环异常：${e.javaClass.simpleName}: ${e.message ?: ""}" } catch (_: Throwable) { }
            }
            handler.removeCallbacks(this)
            handler.postDelayed(this, TICK_MS)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        overlay = QuizOverlay(this, prefs) { onQuizPassed() }
        createChannel()
        startInForeground(buildNotification("守护已开启"))
        running = true
        prefs.lastError = ""
        lastTick = SystemClock.elapsedRealtime()
        handler.post(tickRunnable)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startInForeground(buildNotification(lastNotificationText.ifEmpty { "守护已开启" }))
        when (intent?.action) {
            ACTION_LOCK_NOW -> prefs.lockRequested = true
            ACTION_RESET -> {
                prefs.resetRound()
                lastTick = SystemClock.elapsedRealtime()
                lastNotificationText = ""
            }
        }
        handler.removeCallbacks(tickRunnable)
        handler.post(tickRunnable)
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        try { prefs.watching = false } catch (_: Throwable) { }
        handler.removeCallbacksAndMessages(null)
        overlay.hide()
        abandonAudioFocus()
        super.onDestroy()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // 从最近任务划掉后尽量保持运行（前台服务一般不受影响）
        super.onTaskRemoved(rootIntent)
    }

    private fun startInForeground(notification: Notification) {
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            val msg = "无法进入前台服务：${e.javaClass.simpleName}: ${e.message ?: ""}"
            prefs.lastError = msg
            handler.post { try { Toast.makeText(applicationContext, msg, Toast.LENGTH_LONG).show() } catch (_: Exception) { } }
        }
    }

    // ───────────────────────── 计时循环 ─────────────────────────

    private fun tick() {
        val now = SystemClock.elapsedRealtime()
        val elapsed = ((now - lastTick) / 1000f).coerceIn(0f, MAX_STEP_SECONDS)
        lastTick = now
        prefs.lastTickAt = System.currentTimeMillis()

        if (!prefs.setupDone) {
            stopSelf()
            return
        }

        val roundSeconds = prefs.minutes * 60f
        if (prefs.appliedMinutes != prefs.minutes) {
            prefs.appliedMinutes = prefs.minutes
            prefs.remainingSeconds = roundSeconds
        }
        var remaining = prefs.remainingSeconds.coerceAtMost(roundSeconds)

        // 不论是否计时都检测前台 App，供家长页诊断
        val pkg = currentForegroundPackage()
        prefs.lastForegroundPackage = pkg ?: ""
        prefs.lastForegroundSource = foregroundSource

        if (prefs.paused) {
            if (prefs.locked) unlock()
            prefs.lockRequested = false
            prefs.watching = false
            updateNotification("守护已暂停")
            return
        }

        if (prefs.lockRequested) {
            prefs.lockRequested = false
            lock()
        }

        if (prefs.locked) {
            prefs.watching = false
            // 被关掉或被系统移除时重新显示
            if (!overlay.isShowing) overlay.show()
            updateNotification(if (Permissions.canDrawOverlays(this)) "答题中：答对后可继续观看" else "需要“悬浮窗/显示在其他应用上层”权限才能出题")
            return
        }

        val counted = pkg != null && isCounted(pkg)
        val watching = counted && screenOnAndUnlocked()
        prefs.watching = watching
        if (watching) {
            remaining = (remaining - elapsed).coerceAtLeast(0f)
            prefs.remainingSeconds = remaining
            if (remaining <= 0f) {
                prefs.watching = false
                lock()
                return
            }
        }
        val leftText = if (prefs.minutes <= 2) {
            "${kotlin.math.ceil(remaining).toInt()} 秒"
        } else {
            "约 ${kotlin.math.ceil(remaining / 60f).toInt()} 分钟"
        }
        val fgText = if (pkg == null) "未识别" else appLabel(pkg)
        val text = when {
            !Permissions.hasUsageAccess(this) -> "缺少“使用情况访问”权限，无法计时"
            watching -> "正在计时（$fgText），本轮还剩 $leftText"
            else -> "守护中，本轮还剩 $leftText · 前台：$fgText（不计时）"
        }
        updateNotification(text)
    }

    private fun refreshIgnored() {
        val now = SystemClock.elapsedRealtime()
        if (ignored.isEmpty() || now - ignoredRefreshedAt > 10 * 60_000L) {
            ignored = ignoredPackages(this)
            ignoredRefreshedAt = now
        }
    }

    /** 这个前台 App 是否要计时（取决于“计时范围”设置）。 */
    private fun isCounted(pkg: String): Boolean {
        refreshIgnored()
        if (pkg in ignored) return false
        return when (prefs.scope) {
            Prefs.SCOPE_ALL -> true
            else -> pkg in prefs.videoApps
        }
    }

    private val labelCache = HashMap<String, String>()

    private fun appLabel(pkg: String): String = labelCache.getOrPut(pkg) {
        try {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(pkg, 0)).toString()
        } catch (e: Exception) {
            Prefs.DEFAULT_VIDEO_APPS[pkg] ?: pkg
        }
    }

    private fun screenOnAndUnlocked(): Boolean {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val km = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        return pm.isInteractive && !km.isKeyguardLocked
    }

    /**
     * 找出当前前台应用。
     * 1) 每次都查最近 60 秒的 UsageEvents（滑动窗口），按时间顺序重放 RESUMED(1)/PAUSED(2)：
     *    最后一个 RESUMED 的包就是前台；如果它之后又 PAUSED 且没有新的 RESUMED，就认为没有前台 App。
     * 2) 窗口内没有任何事件（例如一直在看同一个视频）时，沿用上次识别的结果。
     * 3) 还没有缓存时，用 queryUsageStats(INTERVAL_DAILY) 取 lastTimeUsed 最大的包。
     * 返回值可能是桌面/本应用，计时与否由 isCounted() 决定。
     */
    private fun currentForegroundPackage(): String? {
        if (!Permissions.hasUsageAccess(this)) {
            foregroundSource = "no_permission"
            return null
        }
        refreshIgnored()
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val end = System.currentTimeMillis()
        val window = if (foregroundPackage == null) FIRST_EVENT_WINDOW_MS else EVENT_WINDOW_MS
        var sawEvent = false
        var fg: String? = null
        try {
            val events = usm.queryEvents(end - window, end + 1000L)
            val e = UsageEvents.Event()
            while (events.hasNextEvent()) {
                events.getNextEvent(e)
                val p = e.packageName ?: continue
                when (e.eventType) {
                    EVENT_RESUMED -> {
                        if (p == "com.android.systemui") continue  // 系统界面不改变“前台 App”
                        fg = p
                        sawEvent = true
                    }
                    EVENT_PAUSED -> {
                        sawEvent = true
                        if (p == fg) fg = null
                    }
                }
            }
        } catch (e: Exception) {
            prefs.lastError = "读取使用事件失败：${e.javaClass.simpleName}: ${e.message ?: ""}"
        }
        if (sawEvent) {
            if (fg != null) {
                foregroundPackage = fg
                foregroundSource = "events"
                return fg
            }
            // 最后的事件是暂停（例如锁屏或切换中）——试试使用统计
            val fromStats = fromUsageStats(usm, end)
            foregroundPackage = fromStats
            foregroundSource = if (fromStats != null) "usage_stats" else "none"
            return fromStats
        }
        if (foregroundPackage != null) {
            foregroundSource = "cache"
            return foregroundPackage
        }
        val fromStats = fromUsageStats(usm, end)
        foregroundPackage = fromStats
        foregroundSource = if (fromStats != null) "usage_stats" else "none"
        return fromStats
    }

    /** 兜底：最近 60 秒（以及当天）里 lastTimeUsed 最大的包，跳过本应用和系统界面/桌面。 */
    private fun fromUsageStats(usm: UsageStatsManager, end: Long): String? {
        return try {
            var stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, end - EVENT_WINDOW_MS, end)
            if (stats.isNullOrEmpty()) stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, end - 24 * 3600_000L, end)
            stats?.filter { it.packageName !in ignored && it.lastTimeUsed > 0 }
                ?.maxByOrNull { it.lastTimeUsed }
                ?.packageName
        } catch (e: Exception) {
            null
        }
    }

    // ───────────────────────── 锁定 / 解锁 ─────────────────────────

    private fun lock() {
        prefs.locked = true
        prefs.remainingSeconds = 0f
        requestAudioFocus()  // 让正在播放的视频暂停
        overlay.show()
        updateNotification("视频时间到了，答对题目才能继续")
    }

    private fun unlock() {
        prefs.locked = false
        prefs.remainingSeconds = prefs.minutes * 60f
        overlay.hide()
        abandonAudioFocus()
    }

    private fun onQuizPassed() {
        unlock()
        lastTick = SystemClock.elapsedRealtime()
        tick()
    }

    private fun requestAudioFocus() {
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION).build())
            .setOnAudioFocusChangeListener { }
            .build()
        focusRequest = request
        try { am.requestAudioFocus(request) } catch (e: Exception) { }
    }

    private fun abandonAudioFocus() {
        val request = focusRequest ?: return
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        try { am.abandonAudioFocusRequest(request) } catch (e: Exception) { }
        focusRequest = null
    }

    // ───────────────────────── 通知 ─────────────────────────

    private fun createChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(CHANNEL_ID, "视频学习守护", NotificationManager.IMPORTANCE_LOW)
        channel.description = "显示本轮剩余的视频时间"
        channel.setShowBadge(false)
        nm.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("视频学习守护")
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build()
    }

    private fun updateNotification(text: String) {
        if (text == lastNotificationText) return
        lastNotificationText = text
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, buildNotification(text))
    }
}
