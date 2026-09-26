package me.snhgn.schedule.permission

import android.app.AlarmManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import androidx.core.content.ContextCompat
import me.snhgn.schedule.config.AppConfig

/**
 * 权限检测与 ColorOS / Android 原生设置跳转引导助手
 */
object PermissionHelper {
    private const val TAG = "PermissionHelper"

    /**
     * 判断是否已完成过首次启动权限引导
     */
    fun hasCompletedGuide(context: Context): Boolean {
        val sp = context.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)
        return sp.getBoolean(AppConfig.KEY_PERMISSION_GUIDED, false)
    }

    /**
     * 标记完成权限引导
     */
    fun setGuideCompleted(context: Context) {
        val sp = context.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)
        sp.edit().putBoolean(AppConfig.KEY_PERMISSION_GUIDED, true).apply()
    }

    /**
     * 检查悬浮窗权限 (SYSTEM_ALERT_WINDOW)
     */
    fun hasOverlayPermission(context: Context): Boolean {
        return Settings.canDrawOverlays(context)
    }

    /**
     * 请求悬浮窗权限设置页
     */
    fun requestOverlayPermission(context: Context) {
        try {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${context.packageName}")
            ).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "打开悬浮窗设置异常: ${e.message}")
            openAppDetailsSettings(context)
        }
    }

    /**
     * 检查精确闹钟权限 (SCHEDULE_EXACT_ALARM)
     */
    fun hasExactAlarmPermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
            alarmManager?.canScheduleExactAlarms() ?: false
        } else {
            true
        }
    }

    /**
     * 请求精确闹钟权限设置页
     */
    fun requestExactAlarmPermission(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                val intent = Intent(
                    Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                    Uri.parse("package:${context.packageName}")
                ).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            } catch (e: Exception) {
                Log.e(TAG, "打开精确闹钟设置异常: ${e.message}")
                openAppDetailsSettings(context)
            }
        }
    }

    /**
     * 检查是否已忽略电池优化
     */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        return powerManager?.isIgnoringBatteryOptimizations(context.packageName) ?: true
    }

    /**
     * 请求忽略电池优化 (防 ColorOS 休眠强杀)
     */
    fun requestIgnoreBatteryOptimization(context: Context) {
        try {
            val intent = Intent(
                Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:${context.packageName}")
            ).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "打开电池优化设置异常: ${e.message}")
            openAppDetailsSettings(context)
        }
    }

    /**
     * 检查通知权限 (Android 13+ POST_NOTIFICATIONS)
     */
    fun hasNotificationPermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    /**
     * 尝试跳转 ColorOS 自启动 / 关联启动管理页面
     * 采用多重 Intent Fallback 机制，严禁因类名变更崩溃
     */
    fun openColorOsAutoStartSetting(context: Context) {
        val colorOsIntents = listOf(
            // ColorOS / OPPO 自启动页面路径 1
            Intent().apply {
                component = ComponentName(
                    "com.coloros.safecenter",
                    "com.coloros.safecenter.permission.startup.StartupAppListActivity"
                )
            },
            // ColorOS / OPPO 自启动页面路径 2 (新版本 Oplus)
            Intent().apply {
                component = ComponentName(
                    "com.oplus.safecenter",
                    "com.oplus.safecenter.permission.startup.StartupAppListActivity"
                )
            },
            // ColorOS 电池省电管理页面
            Intent().apply {
                component = ComponentName(
                    "com.coloros.oppoguardelf",
                    "com.coloros.powermanager.fuelga设置.PowerUsageModelActivity"
                )
            },
            // 通用安全中心
            Intent().apply {
                component = ComponentName(
                    "com.coloros.safecenter",
                    "com.coloros.safecenter.permission.PermissionManagerActivity"
                )
            }
        )

        for (intent in colorOsIntents) {
            try {
                intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                context.startActivity(intent)
                return
            } catch (_: Exception) {
                // 当前型号或版本不匹配，继续尝试下一个
            }
        }

        // 最终 Fallback：打开系统标准应用信息页
        openAppDetailsSettings(context)
    }

    /**
     * 保底方案：打开系统标准应用详细信息页
     */
    fun openAppDetailsSettings(context: Context) {
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:${context.packageName}")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "打开应用设置详情失败: ${e.message}")
        }
    }
}
