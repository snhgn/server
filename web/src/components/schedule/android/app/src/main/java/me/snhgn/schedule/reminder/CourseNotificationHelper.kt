package me.snhgn.schedule.reminder

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import me.snhgn.schedule.R
import me.snhgn.schedule.network.Course
import me.snhgn.schedule.ui.CourseReminderActivity
import me.snhgn.schedule.ui.MainActivity

/**
 * 课程强提醒与 FullScreenIntent 调度助手
 *
 * 遵循 Android 官方高优先级闹钟标准：
 * 1. 息屏/锁屏状态：通过 setFullScreenIntent 结合唤醒锁点亮屏幕，直接居中拉起 CourseReminderActivity 弹窗
 * 2. 亮屏/使用其他应用状态：以最高优先级 Heads-up Notification (顶部悬浮横幅) 强提醒弹出，伴随震动与提示音
 */
object CourseNotificationHelper {

    private const val TAG = "CourseNotifHelper"
    private const val CHANNEL_ID = "channel_course_alarm"
    private const val NOTIFICATION_ID = 2026

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
        val existing = nm.getNotificationChannel(CHANNEL_ID)
        if (existing != null) return

        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)

        val audioAttributes = AudioAttributes.Builder()
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .setUsage(AudioAttributes.USAGE_ALARM)
            .build()

        val channel = NotificationChannel(
            CHANNEL_ID,
            "课程上课强提醒 (含锁屏弹窗)",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "在课程即将开始时提供全屏/横幅强提醒及锁屏弹窗"
            setShowBadge(true)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 250, 150, 250)
            setSound(soundUri, audioAttributes)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                setAllowBubbles(true)
            }
        }

        nm.createNotificationChannel(channel)
        Log.i(TAG, "已创建高优先级强提醒通知渠道: $CHANNEL_ID")
    }

    /**
     * 发出课程强提醒通知与全屏弹窗 Intent
     */
    fun showCourseAlarm(context: Context, course: Course) {
        Log.i(TAG, "正在触发课程强提醒: ${course.courseName} @ ${course.classRoom}")
        ensureChannel(context)

        // 1. 点亮屏幕短时唤醒锁 (保证息屏状态下手机唤醒并点亮屏幕)
        acquireBriefWakeLock(context)

        // 2. 构造 FullScreenIntent (锁屏/息屏下直达 CourseReminderActivity 弹窗)
        val fullScreenIntent = CourseReminderActivity.createIntent(context, course)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val fullScreenPendingIntent = PendingIntent.getActivity(
            context,
            (course.id and 0x7FFFFFFF).toInt(),
            fullScreenIntent,
            flags
        )

        // 3. 构造点击通知主体的 PendingIntent
        val contentPendingIntent = PendingIntent.getActivity(
            context,
            (course.id and 0x7FFFFFFF).toInt() + 1,
            fullScreenIntent,
            flags
        )

        // 4. 构造直接查看完整课表的 Action
        val openScheduleIntent = Intent(context, MainActivity::class.java).apply {
            this.flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val openSchedulePendingIntent = PendingIntent.getActivity(
            context,
            (course.id and 0x7FFFFFFF).toInt() + 2,
            openScheduleIntent,
            flags
        )

        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)

        val minutes = ((course.startMillis - System.currentTimeMillis()) / 60000L).coerceAtLeast(0L)
        val bodyText = if (minutes > 0) {
            "${course.classRoom} · 还有 $minutes 分钟上课"
        } else {
            "${course.classRoom} · 正在上课中"
        }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle(course.courseName)
            .setContentText(bodyText)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(contentPendingIntent)
            .setFullScreenIntent(fullScreenPendingIntent, true) // 核心：高优先级锁屏全屏弹窗
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setAutoCancel(true)
            .setOngoing(false)
            .setSound(soundUri)
            .setVibrate(longArrayOf(0, 250, 150, 250))
            .addAction(R.drawable.ic_launcher_foreground, "打开课表", openSchedulePendingIntent)
            .build()

        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        nm?.notify(NOTIFICATION_ID, notification)

        ReminderDiagnostics.recordAttempt(
            context,
            "弹窗提醒",
            ReminderDiagnostics.OUTCOME_OK,
            "已发出 FullScreenIntent 强提醒通知: ${course.courseName}"
        )
        Log.i(TAG, "已成功发送 FullScreenIntent 强提醒通知！")
    }

    /**
     * 取消强提醒通知
     */
    fun cancelCourseAlarm(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        nm?.cancel(NOTIFICATION_ID)
    }

    /**
     * 点亮屏幕的短时唤醒锁
     */
    private fun acquireBriefWakeLock(context: Context) {
        try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return
            @Suppress("DEPRECATION")
            val flags = PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP
            val wakeLock = pm.newWakeLock(flags, "me.snhgn.schedule:CourseAlarmWakeLock")
            wakeLock.acquire(3000L) // 3 秒后自动释放，不留后台耗电
            Log.d(TAG, "已获取短时屏幕点亮 WakeLock")
        } catch (e: Exception) {
            Log.w(TAG, "获取屏幕点亮 WakeLock 异常: ${e.message}")
        }
    }
}
