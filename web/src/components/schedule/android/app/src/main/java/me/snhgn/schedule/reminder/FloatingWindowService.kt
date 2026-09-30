package me.snhgn.schedule.reminder

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.TextView
import androidx.core.app.NotificationCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import me.snhgn.schedule.R
import me.snhgn.schedule.network.Course
import me.snhgn.schedule.ui.MainActivity
import java.util.Locale

/**
 * 顶部“流体云 / 灵动岛”悬浮胶囊前台服务
 * 在课前及课中精准展示倒计时与课程信息，下课时自动退出且不留后台常驻
 */
class FloatingWindowService : Service() {

    companion object {
        private const val TAG = "FloatingService"
        private const val CHANNEL_ID = "channel_course_pill"
        private const val NOTIFICATION_ID = 2001

        const val ACTION_START_REMINDER = "me.snhgn.schedule.ACTION_START_REMINDER"
        const val ACTION_STOP_REMINDER = "me.snhgn.schedule.ACTION_STOP_REMINDER"

        private const val EXTRA_COURSE_NAME = "course_name"
        private const val EXTRA_CLASSROOM = "classroom"
        private const val EXTRA_START_MILLIS = "start_millis"
        private const val EXTRA_END_MILLIS = "end_millis"

        fun startService(context: Context, course: Course) {
            val intent = Intent(context, FloatingWindowService::class.java).apply {
                action = ACTION_START_REMINDER
                putExtra(EXTRA_COURSE_NAME, course.courseName)
                putExtra(EXTRA_CLASSROOM, course.classRoom)
                putExtra(EXTRA_START_MILLIS, course.startMillis)
                putExtra(EXTRA_END_MILLIS, course.endMillis)
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
                ReminderDiagnostics.recordAttempt(
                    context, "胶囊", ReminderDiagnostics.OUTCOME_OK,
                    "已启动前台服务，悬浮窗权限=${Settings.canDrawOverlays(context)}"
                )
            } catch (e: Exception) {
                // Android 12+ 禁止后台启动前台服务，ColorOS 限制更严。
                // 这里原本只有一个 Log.e，用户侧表现为"到点什么都不弹"，
                // 完全没有反馈、也无法排查。改为：记录原因 + 降级发普通通知。
                // 普通通知不受后台启动前台服务的限制，是保证提醒不丢的底线。
                Log.e(TAG, "启动前台服务被拒绝: ${e.message}", e)
                ReminderDiagnostics.recordAttempt(
                    context, "胶囊", ReminderDiagnostics.OUTCOME_FGS_REFUSED,
                    "${e.javaClass.simpleName}: ${e.message ?: "无详细信息"}"
                )
                postFallbackNotification(context, course)
            }
        }

        /**
         * 降级提醒：不启动前台服务，只发一条高优先级通知。
         *
         * 这条路径在"App 处于后台"这一唯一场景下有意义 —— 前台打开 App 时
         * 走的是内联唤起分支，本来就能成功，不该被这条降级路径影响。
         */
        private fun postFallbackNotification(context: Context, course: Course) {
            try {
                ensureChannel(context)

                val minutes = ((course.startMillis - System.currentTimeMillis()) / 60000L)
                    .coerceAtLeast(0L)
                val body = if (course.startMillis > System.currentTimeMillis()) {
                    "${course.classRoom} · $minutes 分钟后上课"
                } else {
                    "${course.classRoom} · 正在上课"
                }

                val pendingIntent = PendingIntent.getActivity(
                    context, 0,
                    Intent(context, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )

                val notification: Notification = NotificationCompat.Builder(context, CHANNEL_ID)
                    .setContentTitle(course.courseName)
                    .setContentText(body)
                    .setSmallIcon(R.mipmap.ic_launcher)
                    .setContentIntent(pendingIntent)
                    .setAutoCancel(true)
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    .setCategory(NotificationCompat.CATEGORY_EVENT)
                    .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                    .build()

                val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
                nm?.notify(NOTIFICATION_ID, notification)
                Log.i(TAG, "已降级为普通通知提醒: ${course.courseName}")
            } catch (e: Exception) {
                Log.e(TAG, "降级通知发送失败: ${e.message}", e)
            }
        }

        private fun ensureChannel(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val channel = NotificationChannel(
                CHANNEL_ID, "课程流体云提醒", NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "在课程即将开始及上课期间展示轻量提醒"
                setShowBadge(true)
                enableVibration(false)
                setSound(null, null)
            }
            (context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager)
                ?.createNotificationChannel(channel)
        }

        fun stopService(context: Context) {
            try {
                val intent = Intent(context, FloatingWindowService::class.java)
                context.stopService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "停止 FloatingWindowService 异常: ${e.message}", e)
            }
        }
    }

    private var windowManager: WindowManager? = null
    private var capsuleView: View? = null
    private val handler = Handler(Looper.getMainLooper())

    private var courseName: String = ""
    private var classroom: String = ""
    private var startMillis: Long = 0L
    private var endMillis: Long = 0L

    private var tvCourseName: TextView? = null
    private var tvClassroom: TextView? = null
    private var tvStatus: TextView? = null
    private var ivClose: ImageView? = null

    // 每秒倒计时刷新任务 (纯本地系统时间计算，无网络请求)
    private val tickerRunnable = object : Runnable {
        override fun run() {
            updateCapsuleContent()
            val now = System.currentTimeMillis()
            // 兜底保护：若由于系统时间跃变导致结束 Alarm 异常，Service 在下课后也安全退出
            if (now >= endMillis && endMillis > 0) {
                Log.d(TAG, "课程到达下课时间点，安全退出流体云提醒任务")
                stopSelf()
            } else {
                handler.postDelayed(this, 1000L)
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as? WindowManager
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        val action = intent.action
        if (ACTION_STOP_REMINDER == action) {
            Log.d(TAG, "收到明确关闭指令 (ACTION_STOP_REMINDER)，立即结束短生命周期任务并销毁浮窗")
            stopSelf()
            return START_NOT_STICKY
        }

        courseName = intent.getStringExtra(EXTRA_COURSE_NAME) ?: "课程提醒"
        classroom = intent.getStringExtra(EXTRA_CLASSROOM) ?: "待定教室"
        startMillis = intent.getLongExtra(EXTRA_START_MILLIS, 0L)
        endMillis = intent.getLongExtra(EXTRA_END_MILLIS, 0L)

        // 1. 启动临时前台服务并关联静音通知 (适配 Android 14+ specialUse)
        startForegroundNotification()

        // 2. 检查是否有悬浮窗权限，若有则显示顶部流体云胶囊
        if (Settings.canDrawOverlays(this)) {
            showOrUpdateFloatingCapsule()
        } else {
            // 服务起来了但画不出胶囊 —— 通知还在，但用户想要的灵动岛不会出现。
            // 这个状态必须显式记录，否则自检面板会误报"成功"。
            Log.w(TAG, "未授予悬浮窗权限，仅保留前台通知提醒")
            ReminderDiagnostics.recordAttempt(
                this, "胶囊", ReminderDiagnostics.OUTCOME_NO_OVERLAY,
                "前台服务已启动，但 SYSTEM_ALERT_WINDOW 未授予，顶部胶囊无法显示"
            )
        }

        return START_NOT_STICKY
    }

    private fun startForegroundNotification() {
        val notificationIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            notificationIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(courseName)
            .setContentText("教室: $classroom")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_EVENT)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                // Android 14+ (API 34) 必须显式声明前台服务类型
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (e: Exception) {
            Log.e(TAG, "startForeground 异常: ${e.message}", e)
        }
    }

    @SuppressLint("InflateParams")
    private fun showOrUpdateFloatingCapsule() {
        if (capsuleView != null) {
            updateCapsuleContent()
            return
        }

        val inflater = LayoutInflater.from(this)
        val view = inflater.inflate(R.layout.layout_floating_capsule, null)
        capsuleView = view

        tvCourseName = view.findViewById(R.id.tv_capsule_course_name)
        tvClassroom = view.findViewById(R.id.tv_capsule_classroom)
        tvStatus = view.findViewById(R.id.tv_capsule_status)
        ivClose = view.findViewById(R.id.iv_capsule_close)

        // 点击胶囊直接唤起主 App WebView 查看完整课程
        view.setOnClickListener {
            val appIntent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(appIntent)
        }

        // 点击关闭图标手动隐藏当前胶囊
        ivClose?.setOnClickListener {
            stopSelf()
        }

        val defaultStatusBarHeight = getStatusBarHeight()
        val defaultExtra = (resources.displayMetrics.density * 8).toInt()

        val layoutParams = WindowManager.LayoutParams().apply {
            type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            }
            format = PixelFormat.TRANSLUCENT
            // 不抢占输入焦点，允许穿透点击外部区域
            flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS

            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            x = 0
            y = defaultStatusBarHeight + defaultExtra // 默认在状态栏/挖孔屏正下方预留间距
            width = WindowManager.LayoutParams.WRAP_CONTENT
            height = WindowManager.LayoutParams.WRAP_CONTENT

            // Android 9+ 适配刘海/挖孔屏，允许绘制到顶部安全区域
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            }
        }

        // 动态监听 WindowInsets，获取状态栏与刘海屏真实高度，完美避开遮挡
        ViewCompat.setOnApplyWindowInsetsListener(view) { _, insets ->
            val statusBarHeight = insets.getInsets(WindowInsetsCompat.Type.statusBars()).top
            val cutoutHeight = insets.displayCutout?.safeInsetTop ?: 0
            val topMargin = maxOf(defaultStatusBarHeight, maxOf(statusBarHeight, cutoutHeight)) + defaultExtra
            if (layoutParams.y != topMargin) {
                layoutParams.y = topMargin
                try {
                    if (capsuleView?.isAttachedToWindow == true) {
                        windowManager?.updateViewLayout(capsuleView, layoutParams)
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "更新窗口 Insets 坐标异常: ${e.message}")
                }
            }
            insets
        }

        try {
            windowManager?.addView(view, layoutParams)
            Log.d(TAG, "流体云胶囊悬浮窗添加成功")
            handler.post(tickerRunnable)
        } catch (e: Exception) {
            Log.e(TAG, "添加悬浮窗失败: ${e.message}", e)
        }
    }

    private fun getStatusBarHeight(): Int {
        var result = 0
        val resourceId = resources.getIdentifier("status_bar_height", "dimen", "android")
        if (resourceId > 0) {
            result = resources.getDimensionPixelSize(resourceId)
        }
        if (result <= 0) {
            result = (resources.displayMetrics.density * 36).toInt()
        }
        return result
    }

    /**
     * 刷新流体云内容与倒计时状态
     */
    private fun updateCapsuleContent() {
        tvCourseName?.text = courseName
        tvClassroom?.text = classroom

        val now = System.currentTimeMillis()
        val diffToStart = startMillis - now
        val statusStr: String

        if (diffToStart > 0) {
            // 上课前：倒计时
            val totalSeconds = diffToStart / 1000
            val minutes = totalSeconds / 60
            val seconds = totalSeconds % 60
            statusStr = String.format(Locale.getDefault(), "还有 %02d:%02d", minutes, seconds)
            tvStatus?.text = statusStr
        } else if (now < endMillis) {
            // 正在上课中
            statusStr = "正在上课"
            tvStatus?.text = statusStr
        } else {
            statusStr = "课程已结束"
            tvStatus?.text = statusStr
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "课程流体云提醒",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "在课程即将开始及上课期间展示轻量提醒"
                setShowBadge(true)
                enableVibration(false)
                setSound(null, null)
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            nm?.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(tickerRunnable)
        if (capsuleView != null) {
            try {
                windowManager?.removeView(capsuleView)
            } catch (e: Exception) {
                Log.w(TAG, "移除悬浮窗异常: ${e.message}")
            }
            capsuleView = null
        }
        try {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } catch (e: Exception) {
            Log.w(TAG, "停止前台服务通知异常: ${e.message}")
        }
        Log.d(TAG, "FloatingWindowService 彻底销毁，后台无任务残留")
    }
}
