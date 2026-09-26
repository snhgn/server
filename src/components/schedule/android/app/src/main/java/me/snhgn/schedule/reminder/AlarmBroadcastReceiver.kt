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

                    AlarmManagerHelper.ACTION_COURSE_REMINDER -> {
                        handleCourseReminder(context, intent)
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
     * 课前 5 分钟二次校验与提醒触发
     */
    private suspend fun handleCourseReminder(context: Context, intent: Intent) {
        val courseId = intent.getLongExtra(AlarmManagerHelper.EXTRA_COURSE_ID, 0L)
        val defaultName = intent.getStringExtra(AlarmManagerHelper.EXTRA_COURSE_NAME) ?: "课程"
        val defaultRoom = intent.getStringExtra(AlarmManagerHelper.EXTRA_CLASSROOM) ?: "待定"
        val startTime = intent.getStringExtra(AlarmManagerHelper.EXTRA_START_TIME) ?: ""
        val endTime = intent.getStringExtra(AlarmManagerHelper.EXTRA_END_TIME) ?: ""
        val uniqueKey = intent.getStringExtra(AlarmManagerHelper.EXTRA_UNIQUE_KEY) ?: ""

        Log.d(TAG, "开始核验即将上课的课程: id=$courseId, name=$defaultName, startTime=$startTime")

        // 1. 优先尝试从服务端获取实时最新课程列表
        val fetchResult = ApiClient.fetchCourses()
        var validCourse: Course? = null

        if (fetchResult.isSuccess) {
            val latestList = fetchResult.getOrDefault(emptyList())
            ScheduleSyncManager.saveCoursesToCache(context, latestList)
            // 查找对应课程
            validCourse = latestList.find { it.id == courseId && it.startTime == startTime }
            if (validCourse == null) {
                Log.w(TAG, "课程已取消或时间已变更，放弃提醒并重新同步课表: id=$courseId")
                AlarmManagerHelper.cancelCourseAlarm(context, uniqueKey)
                ScheduleSyncManager.syncSchedule(context)
                return
            }
        } else {
            // 2. 网络不可用/超时策略：回退到本地可靠缓存
            Log.w(TAG, "课前网络请求失败，使用本地课表缓存校验")
            val cachedList = ScheduleSyncManager.getCachedCourses(context)
            validCourse = cachedList.find { it.id == courseId && it.startTime == startTime }
            if (validCourse == null && courseId > 0 && startTime.isNotEmpty()) {
                // 如果缓存中也没有对应对象，但 Intent 携带了完整有效参数，予以信任并提醒
                validCourse = Course(
                    id = courseId,
                    courseName = defaultName,
                    classRoom = defaultRoom,
                    startTime = startTime,
                    endTime = endTime
                )
            }
        }

        // 3. 课程校验确认有效，启动流体云/灵动岛悬浮胶囊服务
        if (validCourse != null) {
            val now = System.currentTimeMillis()
            if (validCourse.endMillis > now) {
                Log.d(TAG, "课程有效，唤起流体云悬浮胶囊: ${validCourse.courseName}")
                FloatingWindowService.startService(context, validCourse)
            } else {
                Log.d(TAG, "课程已经结束，跳过提醒: ${validCourse.courseName}")
            }
        } else {
            Log.w(TAG, "未能确认课程有效性，静默结束本次任务")
        }
    }
}
