package me.snhgn.schedule.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import me.snhgn.schedule.network.ApiClient
import me.snhgn.schedule.network.Course

/**
 * 核心闹钟触发广播接收器
 * 负责接收 AlarmManager 唤醒、课前二次校验、与启动流体云服务
 */
class AlarmBroadcastReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "AlarmReceiver"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent == null) return
        val action = intent.action
        Log.d(TAG, "收到系统闹钟广播: action=$action")

        val pendingResult = goAsync()

        CoroutineScope(Dispatchers.IO).launch {
            try {
                when (action) {
                    AlarmManagerHelper.ACTION_DAILY_SYNC -> {
                        Log.d(TAG, "执行每日定时课表同步任务...")
                        ScheduleSyncManager.syncSchedule(context)
                    }

                    AlarmManagerHelper.ACTION_COURSE_START -> {
                        handleCourseStart(context, intent)
                    }

                    AlarmManagerHelper.ACTION_COURSE_END -> {
                        handleCourseEnd(context, intent)
                    }

                    else -> {
                        Log.d(TAG, "未知 Action: $action")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "处理闹钟广播时发生异常: ${e.message}", e)
            } finally {
                pendingResult.finish()
            }
        }
    }

    /**
     * 课前 5 分钟 (开始 Alarm)：本地秒级校验并立即唤起流体云悬浮胶囊
     */
    private suspend fun handleCourseStart(context: Context, intent: Intent) {
        val courseId = intent.getLongExtra(AlarmManagerHelper.EXTRA_COURSE_ID, 0L)
        val defaultName = intent.getStringExtra(AlarmManagerHelper.EXTRA_COURSE_NAME) ?: "课程"
        val defaultRoom = intent.getStringExtra(AlarmManagerHelper.EXTRA_CLASSROOM) ?: "待定"
        val startTime = intent.getStringExtra(AlarmManagerHelper.EXTRA_START_TIME) ?: ""
        val endTime = intent.getStringExtra(AlarmManagerHelper.EXTRA_END_TIME) ?: ""
        val uniqueKey = intent.getStringExtra(AlarmManagerHelper.EXTRA_UNIQUE_KEY) ?: ""

        Log.d(TAG, "【开始 Alarm 触发】即将上课: id=$courseId, name=$defaultName, startTime=$startTime, room=$defaultRoom")

        // 1. 优先使用 Intent 自身携带的完整课程实体，杜绝后台阻塞网络请求导致广播超时强杀
        var validCourse: Course? = null
        if (courseId > 0 && startTime.isNotEmpty()) {
            validCourse = Course(
                id = courseId,
                courseName = defaultName,
                classRoom = defaultRoom,
                startTime = startTime,
                endTime = endTime
            )
        }

        // 2. 若 Intent 数据不完整，回退读取本地可靠课表缓存
        if (validCourse == null) {
            val cachedList = ScheduleSyncManager.getCachedCourses(context)
            validCourse = cachedList.find { it.id == courseId && it.startTime == startTime }
        }

        // 3. 校验确认有效且未过下课时间，立即唤起流体云/灵动岛悬浮胶囊前台服务
        if (validCourse != null) {
            val now = System.currentTimeMillis()
            if (validCourse.endMillis > now) {
                Log.i(TAG, "课程有效，立即唤起短生命周期流体云悬浮胶囊: ${validCourse.courseName}")
                FloatingWindowService.startService(context, validCourse)
            } else {
                Log.d(TAG, "课程已经结束，跳过提醒: ${validCourse.courseName}")
            }
        } else {
            Log.w(TAG, "未能确认课程有效性，静默结束本次任务")
        }
    }

    /**
     * 下课时间到达 (结束 Alarm)：精准终结短生命周期任务并释放全部资源
     */
    private fun handleCourseEnd(context: Context, intent: Intent) {
        val courseName = intent.getStringExtra(AlarmManagerHelper.EXTRA_COURSE_NAME) ?: "课程"
        val courseId = intent.getLongExtra(AlarmManagerHelper.EXTRA_COURSE_ID, 0L)
        Log.d(TAG, "【结束 Alarm 触发】下课时间到达，通知关闭流体云悬浮窗并释放前台服务: id=$courseId, name=$courseName")

        // 发送关闭指令给 FloatingWindowService
        FloatingWindowService.stopService(context)
    }
}
