package me.snhgn.schedule.ui

import android.app.KeyguardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import me.snhgn.schedule.R
import me.snhgn.schedule.network.Course
import me.snhgn.schedule.reminder.CourseNotificationHelper
import java.util.Locale

/**
 * 课程强提醒居中弹窗 Activity
 *
 * 专门配合系统闹钟与 FullScreenIntent 使用：
 *  - 锁屏/息屏状态下：系统闹钟触发时自动唤醒并点亮屏幕，直接以半透明高亮弹窗呈现给用户
 *  - 亮屏状态下：作为 FullScreenIntent 的前台入口，点击横幅即刻展开完整弹窗
 *  - 穿透锁屏（showWhenLocked + turnScreenOn），无需用户繁琐解锁即可获取上课地点与倒计时
 */
class CourseReminderActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_COURSE_ID = "extra_course_id"
        const val EXTRA_COURSE_NAME = "extra_course_name"
        const val EXTRA_CLASSROOM = "extra_classroom"
        const val EXTRA_START_TIME = "extra_start_time"
        const val EXTRA_END_TIME = "extra_end_time"
        const val EXTRA_START_MILLIS = "extra_start_millis"
        const val EXTRA_END_MILLIS = "extra_end_millis"

        fun createIntent(context: Context, course: Course): Intent {
            return Intent(context, CourseReminderActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                        Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra(EXTRA_COURSE_ID, course.id)
                putExtra(EXTRA_COURSE_NAME, course.courseName)
                putExtra(EXTRA_CLASSROOM, course.classRoom)
                putExtra(EXTRA_START_TIME, course.startTime)
                putExtra(EXTRA_END_TIME, course.endTime)
                putExtra(EXTRA_START_MILLIS, course.startMillis)
                putExtra(EXTRA_END_MILLIS, course.endMillis)
            }
        }
    }

    private var courseId: Long = 0L
    private var courseName: String = "课程提醒"
    private var classroom: String = "待定教室"
    private var startTime: String = ""
    private var endTime: String = ""
    private var startMillis: Long = 0L
    private var endMillis: Long = 0L

    private val handler = Handler(Looper.getMainLooper())
    private var tvCountdown: TextView? = null

    private val tickerRunnable = object : Runnable {
        override fun run() {
            updateCountdownText()
            handler.postDelayed(this, 1000L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setupLockscreenAndWake()

        setContentView(R.layout.activity_course_reminder)

        parseIntentData(intent)
        initViews()
        handler.post(tickerRunnable)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        parseIntentData(intent)
        initViews()
    }

    private fun setupLockscreenAndWake() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            val km = getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
            km?.requestDismissKeyguard(this, null)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
                WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
            )
        }
    }

    private fun parseIntentData(intent: Intent?) {
        if (intent == null) return
        courseId = intent.getLongExtra(EXTRA_COURSE_ID, 0L)
        courseName = intent.getStringExtra(EXTRA_COURSE_NAME) ?: "课程提醒"
        classroom = intent.getStringExtra(EXTRA_CLASSROOM) ?: "待定教室"
        startTime = intent.getStringExtra(EXTRA_START_TIME) ?: ""
        endTime = intent.getStringExtra(EXTRA_END_TIME) ?: ""
        startMillis = intent.getLongExtra(EXTRA_START_MILLIS, 0L)
        endMillis = intent.getLongExtra(EXTRA_END_MILLIS, 0L)

        // 兜底时间戳解析
        if (startMillis == 0L && startTime.isNotEmpty()) {
            startMillis = Course.parseTimeToMillis(startTime)
        }
        if (endMillis == 0L && endTime.isNotEmpty()) {
            endMillis = Course.parseTimeToMillis(endTime)
        }
    }

    private fun initViews() {
        findViewById<TextView>(R.id.tv_reminder_course_name)?.text = courseName
        findViewById<TextView>(R.id.tv_reminder_classroom)?.text = classroom

        val timeSlot = if (startTime.isNotEmpty() && endTime.isNotEmpty()) {
            val startClean = startTime.substringAfter(" ", startTime)
            val endClean = endTime.substringAfter(" ", endTime)
            "$startClean ~ $endClean"
        } else {
            "即将开始"
        }
        findViewById<TextView>(R.id.tv_reminder_time_slot)?.text = timeSlot

        tvCountdown = findViewById(R.id.tv_reminder_countdown_pill)
        updateCountdownText()

        // 点击外部深色遮罩关闭弹窗
        findViewById<View>(R.id.layout_reminder_root)?.setOnClickListener {
            dismissReminder()
        }

        // 卡片自身消费点击，防止误触发遮罩关闭
        findViewById<View>(R.id.card_reminder_content)?.setOnClickListener { }

        // 右上角关闭图标
        findViewById<ImageView>(R.id.btn_reminder_close_icon)?.setOnClickListener {
            dismissReminder()
        }

        // “我知道了”按钮
        findViewById<Button>(R.id.btn_reminder_dismiss)?.setOnClickListener {
            dismissReminder()
        }

        // “打开课表”主按钮
        findViewById<Button>(R.id.btn_reminder_open_schedule)?.setOnClickListener {
            openMainActivity()
        }
    }

    private fun updateCountdownText() {
        val now = System.currentTimeMillis()
        val diffToStart = startMillis - now

        val statusStr = if (diffToStart > 0) {
            val totalSeconds = diffToStart / 1000
            val minutes = totalSeconds / 60
            val seconds = totalSeconds % 60
            String.format(Locale.getDefault(), "还有 %02d:%02d 上课", minutes, seconds)
        } else if (now < endMillis) {
            val elapsedSec = (now - startMillis) / 1000
            val minutes = elapsedSec / 60
            String.format(Locale.getDefault(), "正在上课 (已进行 %d 分钟)", minutes)
        } else {
            "课程已结束"
        }
        tvCountdown?.text = statusStr
    }

    private fun dismissReminder() {
        CourseNotificationHelper.cancelCourseAlarm(this)
        finish()
    }

    private fun openMainActivity() {
        CourseNotificationHelper.cancelCourseAlarm(this)
        val mainIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        startActivity(mainIntent)
        finish()
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(tickerRunnable)
    }
}
