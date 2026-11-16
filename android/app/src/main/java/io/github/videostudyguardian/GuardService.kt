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

/**
 * 前台服务：每 2 秒查看一次前台应用；视频 App 在前台且屏幕亮着时累计时间，
 * 用完后在所有应用上方显示全屏答题层。
 */
class GuardService : Service() {

    companion object {
        private const val CHANNEL_ID = "guardian"
        private const val NOTIFICATION_ID = 1
        private const val TICK_MS = 2000L
        private const val MAX_STEP_SECONDS = 5f  // 防止休眠唤醒后一次扣掉太多时间
        const val ACTION_LOCK_NOW = "io.github.videostudyguardian.LOCK_NOW"

        @Volatile
        var running = false
            private set

        fun start(context: Context, action: String? = null) {
            val intent = Intent(context, GuardService::class.java)
            if (action != null) intent.action = action
            try {
                context.startForegroundService(intent)
            } catch (e: Exception) {
                // Android 12+ 某些后台场景不允许启动前台服务；下次打开 App 或开机时会再启动
            }
        }
    }

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var prefs: Prefs
    private lateinit var overlay: QuizOverlay
    private var lastTick = 0L
    private var lastEventQuery = 0L
    private var foregroundPackage: String? = null
    private var lastNotificationText = ""
    private var focusRequest: AudioFocusRequest? = null

    private val tickRunnable = object : Runnable {
        override fun run() {
            try {
                tick()
            } catch (e: Exception) {
                // 不让单次异常终止守护循环
            }
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
        lastTick = SystemClock.elapsedRealtime()
        handler.post(tickRunnable)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startInForeground(buildNotification(lastNotificationText.ifEmpty { "守护已开启" }))
        if (intent?.action == ACTION_LOCK_NOW) prefs.lockRequested = true
        handler.removeCallbacks(tickRunnable)
        handler.post(tickRunnable)
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
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
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    // ───────────────────────── 计时循环 ─────────────────────────

    private fun tick() {
        val now = SystemClock.elapsedRealtime()
        val elapsed = ((now - lastTick) / 1000f).coerceIn(0f, MAX_STEP_SECONDS)
        lastTick = now

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

        if (prefs.paused) {
            if (prefs.locked) unlock()
            prefs.lockRequested = false
            updateNotification("守护已暂停")
            return
        }

        if (prefs.lockRequested) {
            prefs.lockRequested = false
            lock()
        }

        if (prefs.locked) {
            // 被关掉或被系统移除时重新显示
            if (!overlay.isShowing) overlay.show()
            updateNotification(if (Permissions.canDrawOverlays(this)) "答题中：答对后可继续观看" else "需要“悬浮窗/显示在其他应用上层”权限才能出题")
            return
        }

        val pkg = currentForegroundPackage()
        val watching = pkg != null && pkg in prefs.videoApps && screenOnAndUnlocked()
        if (watching) {
            remaining = (remaining - elapsed).coerceAtLeast(0f)
            prefs.remainingSeconds = remaining
            if (remaining <= 0f) {
                lock()
                return
            }
        }
        val left = kotlin.math.ceil(remaining / 60f).toInt()
        val text = when {
            !Permissions.hasUsageAccess(this) -> "缺少“使用情况访问”权限，无法计时"
            watching -> "正在看视频，本轮还剩约 $left 分钟"
            else -> "守护中，本轮还剩约 $left 分钟视频时间"
        }
        updateNotification(text)
    }

    private fun screenOnAndUnlocked(): Boolean {
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val km = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        return pm.isInteractive && !km.isKeyguardLocked
    }

    /** 通过 UsageStatsManager 的事件流找出最近一次切到前台的应用。 */
    private fun currentForegroundPackage(): String? {
        if (!Permissions.hasUsageAccess(this)) return null
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val end = System.currentTimeMillis()
        val begin = if (lastEventQuery == 0L || end < lastEventQuery) end - 10 * 60_000L else lastEventQuery - 1000L
        val events = usm.queryEvents(begin, end)
        val e = UsageEvents.Event()
        var latestTime = 0L
        var latest: String? = null
        while (events.hasNextEvent()) {
            events.getNextEvent(e)
            @Suppress("DEPRECATION")
            if (e.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND && e.timeStamp >= latestTime) {
                latestTime = e.timeStamp
                latest = e.packageName
            }
        }
        lastEventQuery = end
        if (latest != null) foregroundPackage = latest
        return foregroundPackage
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
