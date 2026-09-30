package me.snhgn.schedule.reminder

import android.content.Context
import android.os.Build
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.permission.PermissionHelper
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 灵动岛提醒自检数据源
 *
 * 背景：课前提醒有两条完全独立的唤醒路径 ——
 *  1) 前台路径：打开 App 时 scheduleFutureCourses 内联唤起胶囊（一定能成）
 *  2) 后台路径：AlarmManager -> AlarmBroadcastReceiver -> FloatingWindowService（曾长期静默失败）
 *
 * 失败时既没有崩溃也没有界面反馈，用户只看到"没弹出来"，无法区分是
 * 闹钟压根没注册、广播没收到、还是前台服务被系统拒绝。这里把每一步的
 * 结论都落盘，供 App 内"灵动岛自检"面板直接读取，不用连 adb 猜。
 */
object ReminderDiagnostics {

    private const val KEY_ALARM_COUNT = "key_diag_alarm_count"
    private const val KEY_NEXT_ALARM = "key_diag_next_alarm"
    private const val KEY_LAST_AT = "key_diag_last_at"
    private const val KEY_LAST_ACTION = "key_diag_last_action"
    private const val KEY_LAST_OUTCOME = "key_diag_last_outcome"
    private const val KEY_LAST_DETAIL = "key_diag_last_detail"
    private const val KEY_LAST_SYNC_AT = "key_diag_last_sync_at"
    private const val KEY_LAST_SYNC_COUNT = "key_diag_last_sync_count"

    // ---- 上次结果取值 ----
    const val OUTCOME_NONE = "none"                 // 从未尝试过
    const val OUTCOME_OK = "ok"                     // 前台服务已成功启动
    const val OUTCOME_FGS_REFUSED = "fgs_refused"   // 系统拒绝后台启动前台服务
    const val OUTCOME_NO_COURSE = "no_course"       // 闹钟到了但没匹配到有效课程
    const val OUTCOME_COURSE_PASSED = "course_passed" // 闹钟到了但课程已结束
    const val OUTCOME_NO_OVERLAY = "no_overlay"     // 服务起来了但没有悬浮窗权限
    const val OUTCOME_EMPTY_CACHE = "empty_cache"   // 无本地课表，无法注册任何闹钟

    private fun prefs(context: Context) =
        context.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)

    /**
     * 记录一次闹钟调度结果（由 ScheduleSyncManager 在批量注册后调用）
     */
    fun recordScheduling(context: Context, alarmCount: Int, nextAlarmAt: Long) {
        prefs(context).edit()
            .putInt(KEY_ALARM_COUNT, alarmCount)
            .putLong(KEY_NEXT_ALARM, nextAlarmAt)
            .putLong(KEY_LAST_SYNC_AT, System.currentTimeMillis())
            .putInt(KEY_LAST_SYNC_COUNT, alarmCount)
            .apply()
    }

    /**
     * 记录一次唤醒尝试的结论
     */
    fun recordAttempt(context: Context, action: String, outcome: String, detail: String) {
        prefs(context).edit()
            .putLong(KEY_LAST_AT, System.currentTimeMillis())
            .putString(KEY_LAST_ACTION, action)
            .putString(KEY_LAST_OUTCOME, outcome)
            .putString(KEY_LAST_DETAIL, detail)
            .apply()
    }

    /**
     * 汇总为 JSON 交给网页侧渲染
     */
    fun toJson(context: Context): JSONObject {
        val sp = prefs(context)
        val cached = ScheduleSyncManager.getCachedCourses(context).size
        val lastAt = sp.getLong(KEY_LAST_AT, 0L)
        val nextAlarm = sp.getLong(KEY_NEXT_ALARM, 0L)

        return JSONObject().apply {
            put("cachedCourses", cached)
            put("alarmCount", sp.getInt(KEY_ALARM_COUNT, 0))
            put("nextAlarmAt", nextAlarm)
            put("nextAlarmText", if (nextAlarm > 0) formatTime(nextAlarm) else "未注册")
            put("lastSyncAt", sp.getLong(KEY_LAST_SYNC_AT, 0L))
            put("lastSyncText", sp.getLong(KEY_LAST_SYNC_AT, 0L).let {
                if (it > 0) formatTime(it) else "从未同步"
            })
            put("lastSyncCount", sp.getInt(KEY_LAST_SYNC_COUNT, 0))
            put("lastAt", lastAt)
            put("lastAtText", if (lastAt > 0) formatTime(lastAt) else "从未尝试")
            put("lastAction", sp.getString(KEY_LAST_ACTION, "") ?: "")
            put("lastOutcome", sp.getString(KEY_LAST_OUTCOME, OUTCOME_NONE) ?: OUTCOME_NONE)
            put("lastDetail", sp.getString(KEY_LAST_DETAIL, "") ?: "")

            put("exactAlarm", PermissionHelper.hasExactAlarmPermission(context))
            put("overlay", PermissionHelper.hasOverlayPermission(context))
            put("batteryExempt", PermissionHelper.isIgnoringBatteryOptimizations(context))
            put("notification", PermissionHelper.hasNotificationPermission(context))
            put("sdkInt", Build.VERSION.SDK_INT)
            put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
        }
    }

    private fun formatTime(millis: Long): String =
        SimpleDateFormat("MM-dd HH:mm:ss", Locale.getDefault()).format(Date(millis))
}
