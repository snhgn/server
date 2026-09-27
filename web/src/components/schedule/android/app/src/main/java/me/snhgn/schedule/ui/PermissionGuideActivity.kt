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

        findViewById<Button>(R.id.btn_proceed).setOnClickListener {
            completeGuideAndEnterMain()
        }
    }

    private fun refreshPermissionStates() {
        // 1. 悬浮窗
        val hasOverlay = PermissionHelper.hasOverlayPermission(this)
        tvOverlayStatus.text = if (hasOverlay) "✓ 已开启" else "未开启（点击设置）"
        tvOverlayStatus.setTextColor(if (hasOverlay) 0xFF4ADE80.toInt() else 0xFFF87171.toInt())

        // 2. 精确闹钟
        val hasAlarm = PermissionHelper.hasExactAlarmPermission(this)
        tvAlarmStatus.text = if (hasAlarm) "✓ 已开启" else "未开启（点击设置）"
        tvAlarmStatus.setTextColor(if (hasAlarm) 0xFF4ADE80.toInt() else 0xFFF87171.toInt())

        // 3. 电池优化
        val isBatteryIgnored = PermissionHelper.isIgnoringBatteryOptimizations(this)
        tvBatteryStatus.text = if (isBatteryIgnored) "✓ 已优化" else "建议允许（点击设置）"
        tvBatteryStatus.setTextColor(if (isBatteryIgnored) 0xFF4ADE80.toInt() else 0xFFFBBF24.toInt())

        // 4. 通知
        val hasNotification = PermissionHelper.hasNotificationPermission(this)
        tvNotificationStatus.text = if (hasNotification) "✓ 已开启" else "未开启（点击设置）"
        tvNotificationStatus.setTextColor(if (hasNotification) 0xFF4ADE80.toInt() else 0xFFF87171.toInt())
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
