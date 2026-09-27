package me.snhgn.schedule.reminder

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.network.Course
import java.util.Calendar

/**
 * 系统闹钟封装助手 (AlarmManager)
 * 适配 Android 12+ 精确闹钟权限与 Doze 模式
 */
object AlarmManagerHelper {
    private const val TAG = "AlarmManagerHelper"

    const val ACTION_COURSE_START = "me.snhgn.schedule.ACTION_COURSE_START"
    const val ACTION_COURSE_END = "me.snhgn.schedule.ACTION_COURSE_END"
    const val ACTION_COURSE_REMINDER = ACTION_COURSE_START // 保持向后兼容
    const val ACTION_DAILY_SYNC = "me.snhgn.schedule.ACTION_DAILY_SYNC"

    const val EXTRA_COURSE_ID = "extra_course_id"
    const val EXTRA_COURSE_NAME = "extra_course_name"
    const val EXTRA_CLASSROOM = "extra_classroom"
    const val EXTRA_START_TIME = "extra_start_time"
    const val EXTRA_END_TIME = "extra_end_time"
    const val EXTRA_UNIQUE_KEY = "extra_unique_key"

    /**
     * 生成稳定唯一的 RequestCode
     */
    fun getRequestCode(uniqueKey: String): Int {
        return uniqueKey.hashCode() and 0x7FFFFFFF
    }

    /**
     * 为单节课程注册成对的系统闹钟：
     * 1. 开始 Alarm (课前 5 分钟触发)
     * 2. 结束 Alarm (下课时间触发，用于强制关闭悬浮窗并彻底释放 Service)
     */
    fun registerCourseAlarms(context: Context, course: Course): Pair<Boolean, Boolean> {
        val startSuccess = scheduleAlarm(
            context = context,
            action = ACTION_COURSE_START,
            triggerAtMillis = course.reminderMillis,
            uniqueKey = course.startKey,
            course = course
        )

        val endSuccess = scheduleAlarm(
            context = context,
            action = ACTION_COURSE_END,
            triggerAtMillis = course.endMillis,
            uniqueKey = course.endKey,
            course = course
        )

        return Pair(startSuccess, endSuccess)
    }

    /**
     * 保持向后兼容的单节闹钟注册方法
     */
    fun registerCourseAlarm(context: Context, course: Course): Boolean {
        return registerCourseAlarms(context, course).first
    }

    /**
     * 底层注册闹钟方法
     */
    private fun scheduleAlarm(
        context: Context,
        action: String,
        triggerAtMillis: Long,
        uniqueKey: String,
        course: Course
    ): Boolean {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return false
        val currentTime = System.currentTimeMillis()

        if (triggerAtMillis <= currentTime) {
            Log.d(TAG, "闹钟触发时间已过，跳过: action=$action, key=$uniqueKey")
            return false
        }

        val intent = Intent(context, AlarmBroadcastReceiver::class.java).apply {
            this.action = action
            putExtra(EXTRA_COURSE_ID, course.id)
            putExtra(EXTRA_COURSE_NAME, course.courseName)
            putExtra(EXTRA_CLASSROOM, course.classRoom)
            putExtra(EXTRA_START_TIME, course.startTime)
            putExtra(EXTRA_END_TIME, course.endTime)
            putExtra(EXTRA_UNIQUE_KEY, uniqueKey)
        }

        val requestCode = getRequestCode(uniqueKey)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val pendingIntent = PendingIntent.getBroadcast(context, requestCode, intent, flags)

        try {
            val canScheduleExact = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                alarmManager.canScheduleExactAlarms()
            } else {
                true
            }

            if (canScheduleExact) {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAtMillis,
                    pendingIntent
                )
                Log.d(TAG, "已注册精确闹钟: action=$action, key=$uniqueKey, code=$requestCode, time=$triggerAtMillis")
            } else {
                alarmManager.setAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAtMillis,
                    pendingIntent
                )
                Log.w(TAG, "精确闹钟权限未开启，降级注册非精确闹钟: action=$action, key=$uniqueKey")
            }
            return true
        } catch (e: SecurityException) {
            Log.e(TAG, "注册闹钟权限异常: ${e.message}", e)
            return try {
                alarmManager.setAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    triggerAtMillis,
                    pendingIntent
                )
                true
            } catch (ex: Exception) {
                Log.e(TAG, "降级注册闹钟仍失败: ${ex.message}", ex)
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "注册闹钟发生未知错误: ${e.message}", e)
            return false
        }
    }

    /**
     * 成对取消单节课程的开始 Alarm 和结束 Alarm
     */
    fun cancelCourseAlarms(context: Context, startKey: String, endKey: String) {
        cancelAlarmByKey(context, ACTION_COURSE_START, startKey)
        cancelAlarmByKey(context, ACTION_COURSE_END, endKey)
    }

    /**
     * 取消指定 Action 和 Key 的闹钟
     */
    fun cancelAlarmByKey(context: Context, action: String, uniqueKey: String) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
        val intent = Intent(context, AlarmBroadcastReceiver::class.java).apply {
            this.action = action
        }
        val requestCode = getRequestCode(uniqueKey)
        val flags = PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
        val pendingIntent = PendingIntent.getBroadcast(context, requestCode, intent, flags)

        if (pendingIntent != null) {
            alarmManager.cancel(pendingIntent)
            pendingIntent.cancel()
            Log.d(TAG, "已取消闹钟: action=$action, key=$uniqueKey, code=$requestCode")
        }
    }

    /**
     * 保持向后兼容的单闹钟取消接口
     */
    fun cancelCourseAlarm(context: Context, uniqueKey: String) {
        cancelAlarmByKey(context, ACTION_COURSE_START, uniqueKey)
        cancelAlarmByKey(context, ACTION_COURSE_END, uniqueKey)
    }

    /**
     * 注册每日固定时间 (如凌晨 03:00) 自动同步课表的系统闹钟
     */
    fun scheduleDailySync(context: Context) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return

        val calendar = Calendar.getInstance().apply {
            timeInMillis = System.currentTimeMillis()
            set(Calendar.HOUR_OF_DAY, AppConfig.DAILY_SYNC_HOUR)
            set(Calendar.MINUTE, AppConfig.DAILY_SYNC_MINUTE)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            // 如果今天的同步时间已经过去，则排在明天同一时间
            if (timeInMillis <= System.currentTimeMillis()) {
                add(Calendar.DAY_OF_YEAR, 1)
            }
        }

        val intent = Intent(context, AlarmBroadcastReceiver::class.java).apply {
            action = ACTION_DAILY_SYNC
        }
        val requestCode = 999901
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val pendingIntent = PendingIntent.getBroadcast(context, requestCode, intent, flags)

        try {
            alarmManager.setAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                calendar.timeInMillis,
                pendingIntent
            )
            Log.d(TAG, "已安排下一次每日同步闹钟: ${calendar.time}")
        } catch (e: Exception) {
            Log.e(TAG, "注册每日同步闹钟失败: ${e.message}", e)
        }
    }
}
