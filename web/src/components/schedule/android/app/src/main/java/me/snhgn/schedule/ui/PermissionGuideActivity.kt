package me.snhgn.schedule.ui

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import me.snhgn.schedule.R
import me.snhgn.schedule.permission.PermissionHelper
import me.snhgn.schedule.reminder.ScheduleSyncManager

/**
 * 首次启动引导页
 * 帮助用户便捷开启悬浮窗、精确闹钟、电池优化、ColorOS 自启动权限
 */
class PermissionGuideActivity : AppCompatActivity() {

    private lateinit var tvOverlayStatus: TextView
    private lateinit var tvAlarmStatus: TextView
    private lateinit var tvBatteryStatus: TextView
    private lateinit var tvNotificationStatus: TextView

    private val requestNotificationLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {
        refreshPermissionStates()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_permission_guide)

        initViews()
    }

    override fun onResume() {
        super.onResume()
        refreshPermissionStates()
    }

    private fun initViews() {
        tvOverlayStatus = findViewById(R.id.tv_status_overlay)
        tvAlarmStatus = findViewById(R.id.tv_status_alarm)
        tvBatteryStatus = findViewById(R.id.tv_status_battery)
        tvNotificationStatus = findViewById(R.id.tv_status_notification)

        findViewById<View>(R.id.card_overlay).setOnClickListener {
            PermissionHelper.requestOverlayPermission(this)
        }

        findViewById<View>(R.id.card_alarm).setOnClickListener {
            PermissionHelper.requestExactAlarmPermission(this)
        }

        findViewById<View>(R.id.card_battery).setOnClickListener {
            PermissionHelper.requestIgnoreBatteryOptimization(this)
        }

        findViewById<View>(R.id.card_autostart).setOnClickListener {
            PermissionHelper.openColorOsAutoStartSetting(this)
        }

        findViewById<View>(R.id.card_notification).setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                requestNotificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        findViewById<View?>(R.id.btn_test_capsule)?.setOnClickListener {
            if (!PermissionHelper.hasOverlayPermission(this)) {
                android.widget.Toast.makeText(this, "请先开启上方【悬浮窗权限】", android.widget.Toast.LENGTH_SHORT).show()
                PermissionHelper.requestOverlayPermission(this)
                return@setOnClickListener
            }
            val now = System.currentTimeMillis()
            val dateFormat = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
            val testCourse = me.snhgn.schedule.network.Course(
                id = 999999L,
                courseName = "高等数学 (流体云测试)",
                classRoom = "学研大厦 A0101",
                startTime = dateFormat.format(java.util.Date(now + 3 * 60 * 1000L)),
                endTime = dateFormat.format(java.util.Date(now + 45 * 60 * 1000L))
            )
            me.snhgn.schedule.reminder.FloatingWindowService.startService(this, testCourse)
            android.widget.Toast.makeText(this, "已唤起顶部流体云胶囊！", android.widget.Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btn_proceed).setOnClickListener {
            completeGuideAndEnterMain()
        }
    }

    private fun refreshPermissionStates() {
        // 1. 悬浮窗
        val hasOverlay = PermissionHelper.hasOverlayPermission(this)
        applyBadgeState(tvOverlayStatus, hasOverlay, "✓ 已开启", "去开启 →")

        // 2. 精确闹钟
        val hasAlarm = PermissionHelper.hasExactAlarmPermission(this)
        applyBadgeState(tvAlarmStatus, hasAlarm, "✓ 已开启", "去开启 →")

        // 3. 电池优化
        val isBatteryIgnored = PermissionHelper.isIgnoringBatteryOptimizations(this)
        applyBadgeState(tvBatteryStatus, isBatteryIgnored, "✓ 已优化", "去允许 →", isWarning = true)

        // 4. 通知
        val hasNotification = PermissionHelper.hasNotificationPermission(this)
        applyBadgeState(tvNotificationStatus, hasNotification, "✓ 已开启", "去开启 →")
    }

    private fun applyBadgeState(
        textView: TextView,
        isGranted: Boolean,
        grantedText: String,
        deniedText: String,
        isWarning: Boolean = false
    ) {
        if (isGranted) {
            textView.text = grantedText
            textView.setBackgroundResource(R.drawable.bg_badge_success)
            textView.setTextColor(0xFF4ADE80.toInt())
        } else {
            textView.text = deniedText
            if (isWarning) {
                textView.setBackgroundResource(R.drawable.bg_badge_warning)
                textView.setTextColor(0xFFFBBF24.toInt())
            } else {
                textView.setBackgroundResource(R.drawable.bg_badge_action)
                textView.setTextColor(0xFF9CA3AF.toInt())
            }
        }
    }

    private fun completeGuideAndEnterMain() {
        PermissionHelper.setGuideCompleted(this)

        // 触发首次全量课表同步与闹钟下发
        lifecycleScope.launch {
            ScheduleSyncManager.syncSchedule(applicationContext)
        }

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        startActivity(intent)
        finish()
    }
}
