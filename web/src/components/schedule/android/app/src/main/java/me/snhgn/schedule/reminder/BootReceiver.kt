package me.snhgn.schedule.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 手机开机/重启广播监听器
 * 负责在系统重启后无感重新恢复注册未来所有课程的系统闹钟
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "BootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action
        Log.d(TAG, "收到开机重启广播: action=$action")

        if (Intent.ACTION_BOOT_COMPLETED == action ||
            Intent.ACTION_LOCKED_BOOT_COMPLETED == action ||
            "android.intent.action.QUICKBOOT_POWERON" == action ||
            "com.htc.intent.action.QUICKBOOT_POWERON" == action
        ) {
            val pendingResult = goAsync()

            // 后台静默执行课表同步并重新下发 AlarmManager 闹钟，严禁在此弹出任何 UI/WebView
            CoroutineScope(Dispatchers.IO).launch {
                try {
                    Log.d(TAG, "开机自启完成，开始自动恢复未来 7 天课程闹钟...")
                    ScheduleSyncManager.syncSchedule(context)
                } catch (e: Exception) {
                    Log.e(TAG, "开机恢复课表闹钟失败: ${e.message}", e)
                } finally {
                    pendingResult.finish()
                }
            }
        }
    }
}
