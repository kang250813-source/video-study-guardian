package io.github.videostudyguardian

import android.content.Context
import android.content.SharedPreferences
import java.util.Calendar

/** 所有设置都保存在本机 SharedPreferences 中，不联网、不上传。 */
class Prefs(context: Context) {
    val sp: SharedPreferences = context.applicationContext.getSharedPreferences("guardian", Context.MODE_PRIVATE)

    companion object {
        val SUBJECTS = listOf("语文", "数学", "英语")
        val MODES = listOf("全部", "背古诗", "背单词")
        const val MIN_MINUTES = 1
        const val MAX_MINUTES = 60

        val DEFAULT_VIDEO_APPS: Map<String, String> = linkedMapOf(
            "com.ss.android.ugc.aweme" to "抖音",
            "com.ss.android.ugc.aweme.lite" to "抖音极速版",
            "com.smile.gifmaker" to "快手",
            "com.kuaishou.nebula" to "快手极速版",
            "tv.danmaku.bili" to "哔哩哔哩",
            "com.ss.android.article.video" to "西瓜视频",
            "com.tencent.qqlive" to "腾讯视频",
            "com.qiyi.video" to "爱奇艺",
            "com.youku.phone" to "优酷",
            "com.hunantv.imgo.activity" to "芒果TV",
            "com.google.android.youtube" to "YouTube",
            "com.ss.android.ugc.live" to "抖音火山版",
            "com.xingin.xhs" to "小红书",
            "com.tencent.weishi" to "微视",
            "com.baidu.haokan" to "好看视频",
            "com.heytap.yoli" to "OPPO 视频",
        )

        /** 默认列表版本；升级时把新加入的默认 App 合并进已保存的列表。 */
        const val DEFAULT_APPS_VERSION = 2

        /** 计时范围 */
        const val SCOPE_SELECTED = "selected"
        const val SCOPE_ALL = "all"
        val SCOPES = listOf(SCOPE_SELECTED, SCOPE_ALL)
        val SCOPE_LABELS = listOf("仅选中的视频 App", "除桌面和本应用外的所有 App")

        /** 和电脑版一样：8 月到次年 1 月默认上册，其余默认下册。 */
        fun defaultTerm(): String {
            val month = Calendar.getInstance().get(Calendar.MONTH) + 1
            return if (month >= 8 || month == 1) "上" else "下"
        }
    }

    var setupDone: Boolean
        get() = sp.getBoolean("setup_done", false)
        set(v) = sp.edit().putBoolean("setup_done", v).apply()

    var passwordSalt: String
        get() = sp.getString("password_salt", "") ?: ""
        set(v) = sp.edit().putString("password_salt", v).apply()

    var passwordHash: String
        get() = sp.getString("password_hash", "") ?: ""
        set(v) = sp.edit().putString("password_hash", v).apply()

    var passwordIterations: Int
        get() = sp.getInt("password_iterations", Password.ITERATIONS)
        set(v) = sp.edit().putInt("password_iterations", v).apply()

    var minutes: Int
        get() = sp.getInt("minutes", 10).coerceIn(MIN_MINUTES, MAX_MINUTES)
        set(v) = sp.edit().putInt("minutes", v.coerceIn(MIN_MINUTES, MAX_MINUTES)).apply()

    var grade: Int
        get() = sp.getInt("grade", 6).coerceIn(1, 6)
        set(v) = sp.edit().putInt("grade", v.coerceIn(1, 6)).apply()

    var term: String
        get() = sp.getString("term", "上").takeIf { it == "上" || it == "下" } ?: "上"
        set(v) = sp.edit().putString("term", v).apply()

    var mode: String
        get() = sp.getString("mode", "全部").takeIf { it in MODES } ?: "全部"
        set(v) = sp.edit().putString("mode", v).apply()

    var subjects: List<String>
        get() {
            val raw = sp.getString("subjects", null) ?: return SUBJECTS
            return raw.split(',').map { it.trim() }.filter { it.isNotEmpty() }
        }
        set(v) = sp.edit().putString("subjects", v.joinToString(",")).apply()

    /** 英语教材版本："new" 新教材 / "old" 旧教材 */
    var englishEdition: String
        get() = sp.getString("english_edition", "new").takeIf { it == "new" || it == "old" } ?: "new"
        set(v) = sp.edit().putString("english_edition", v).apply()

    /** 暂停守护（相当于电脑版的工作模式） */
    var paused: Boolean
        get() = sp.getBoolean("paused", false)
        set(v) = sp.edit().putBoolean("paused", v).apply()

    var videoApps: Set<String>
        get() {
            val saved = sp.getStringSet("video_apps", null) ?: return HashSet(DEFAULT_VIDEO_APPS.keys)
            val result = HashSet(saved)
            if (sp.getInt("default_apps_version", 1) < DEFAULT_APPS_VERSION) {
                // 老版本升级：补上新加入的默认 App（家长之前取消勾选的旧默认项不会被加回）
                val v1 = setOf(
                    "com.ss.android.ugc.aweme", "com.ss.android.ugc.aweme.lite", "com.smile.gifmaker", "com.kuaishou.nebula",
                    "tv.danmaku.bili", "com.ss.android.article.video", "com.tencent.qqlive", "com.qiyi.video",
                    "com.youku.phone", "com.hunantv.imgo.activity", "com.google.android.youtube",
                )
                result.addAll(DEFAULT_VIDEO_APPS.keys - v1)
                sp.edit().putStringSet("video_apps", HashSet(result)).putInt("default_apps_version", DEFAULT_APPS_VERSION).apply()
            }
            return result
        }
        set(v) = sp.edit().putStringSet("video_apps", HashSet(v)).putInt("default_apps_version", DEFAULT_APPS_VERSION).apply()

    /** 计时范围：SCOPE_SELECTED（默认）或 SCOPE_ALL */
    var scope: String
        get() = sp.getString("scope", SCOPE_SELECTED).takeIf { it in SCOPES } ?: SCOPE_SELECTED
        set(v) = sp.edit().putString("scope", if (v in SCOPES) v else SCOPE_SELECTED).apply()

    // ── 运行状态（服务写入，界面读取）──
    var remainingSeconds: Float
        get() = sp.getFloat("remaining_seconds", minutes * 60f)
        set(v) = sp.edit().putFloat("remaining_seconds", v).apply()

    /** 计算剩余时间时所用的分钟数；家长改了分钟数后据此重置计时。 */
    var appliedMinutes: Int
        get() = sp.getInt("applied_minutes", -1)
        set(v) = sp.edit().putInt("applied_minutes", v).apply()

    var locked: Boolean
        get() = sp.getBoolean("locked", false)
        set(v) = sp.edit().putBoolean("locked", v).apply()

    /** 家长点了“立即测试答题” */
    var lockRequested: Boolean
        get() = sp.getBoolean("lock_requested", false)
        set(v) = sp.edit().putBoolean("lock_requested", v).apply()

    // ── 诊断信息（服务写入，家长页读取）──
    /** 服务最近一次检测到的前台 App 包名（空 = 未检测到） */
    var lastForegroundPackage: String
        get() = sp.getString("diag_fg_pkg", "") ?: ""
        set(v) = sp.edit().putString("diag_fg_pkg", v).apply()

    /** 前台 App 是怎么判断出来的：events / cache / usage_stats / none */
    var lastForegroundSource: String
        get() = sp.getString("diag_fg_source", "") ?: ""
        set(v) = sp.edit().putString("diag_fg_source", v).apply()

    /** 最近一次计时循环时是否正在计时 */
    var watching: Boolean
        get() = sp.getBoolean("diag_watching", false)
        set(v) = sp.edit().putBoolean("diag_watching", v).apply()

    /** 计时循环最近一次运行的时间（System.currentTimeMillis） */
    var lastTickAt: Long
        get() = sp.getLong("diag_last_tick", 0L)
        set(v) = sp.edit().putLong("diag_last_tick", v).apply()

    /** 最近一次服务错误（启动失败、循环异常等），空 = 无 */
    var lastError: String
        get() = sp.getString("diag_last_error", "") ?: ""
        set(v) = sp.edit().putString("diag_last_error", v).apply()

    /** 把剩余时间重置为一整轮（家长保存设置后调用） */
    fun resetRound() {
        sp.edit()
            .putFloat("remaining_seconds", minutes * 60f)
            .putInt("applied_minutes", minutes)
            .apply()
    }

    fun quizConfig() = QuestionBank.Config(grade, term, mode, subjects, englishEdition)
}
