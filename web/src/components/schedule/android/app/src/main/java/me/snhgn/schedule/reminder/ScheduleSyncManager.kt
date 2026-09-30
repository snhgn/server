package me.snhgn.schedule.reminder

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.network.Course
import org.json.JSONArray

/**
 * 课表核心同步管理器
 * 负责从后端拉取、本地缓存、比较差量并自动化增删闹钟
 */
object ScheduleSyncManager {
    private const val TAG = "ScheduleSyncManager"

    /**
     * 来自 WebView 前端 JS 桥梁的直接推送：全量更新具体课程并注册系统闹钟
     */
    suspend fun updateFromWebJson(context: Context, jsonStr: String): Int = withContext(Dispatchers.IO) {
        val courseList = mutableListOf<Course>()
        var badTimeCount = 0
        try {
            val jsonArray = JSONArray(jsonStr)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.optJSONObject(i)
                if (obj != null) {
                    val course = Course.fromJson(obj)
                    if (course.id > 0 && course.startTime.isNotEmpty()) {
                        // 时间解析失败的门课会在 scheduleAlarm 里因
                        // "触发时间已过" 被静默跳过，用户侧表现为某门课从不提醒。
                        // 这里先统计出来，交给自检面板显示，避免无从排查。
                        if (!Course.isTimeValid(course.startTime) || !Course.isTimeValid(course.endTime)) {
                            badTimeCount++
                            Log.w(TAG, "课程时间无法解析，将无法注册闹钟: ${course.courseName} " +
                                "[${course.startTime} ~ ${course.endTime}]")
                            continue
                        }
                        courseList.add(course)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "解析前端课程 JSON 异常: ${e.message}", e)
            return@withContext 0
        }

        if (courseList.isEmpty()) {
            Log.w(TAG, "从前端解析得到的课程列表为空")
            ReminderDiagnostics.recordAttempt(
                context, "同步", ReminderDiagnostics.OUTCOME_EMPTY_CACHE,
                "前端推送 ${jsonArrayLength(jsonStr)} 门课，但全部不可用（时间无法解析 $badTimeCount 门）"
            )
            return@withContext 0
        }

        saveCoursesToCache(context, courseList)
        val registeredCount = scheduleFutureCourses(context, courseList)
        Log.i(TAG, "前端推送课表同步完成！解析得到 ${courseList.size} 门具体课程，已注册未来 7 天内 $registeredCount 个闹钟")
        registeredCount
    }

    private fun jsonArrayLength(jsonStr: String): Int = try {
        JSONArray(jsonStr).length()
    } catch (e: Exception) {
        0
    }

    /**
     * 统一入口：全量同步课表并更新系统闹钟 (本地缓存唯一来源，开机/每日定时/App 打开时调用)
     *
     * 数据来源说明：课表数据的唯一来源是 WebView 前端通过 JS 桥推送
     * (见 MainActivity 的 AndroidBridge.syncCourses)。这里原先还有一条
     * "本地无缓存就去拉后端 API"的兜底，但 AppConfig.API_CANDIDATE_URLS
     * 里的三个端点 /api/course/list 实测全部返回 404，从未成功过。
     *
     * 保留它有两个实际危害，不是"多一条保险"：
     *  1) 3 个 URL × (6s 连接 + 6s 读取) 最坏 36 秒，而 BootReceiver /
     *     AlarmBroadcastReceiver 走 goAsync() 只有 10 秒预算 —— 一旦本地
     *     无缓存，广播处理必然超时被杀，闹钟一个也注册不上。
     *  2) 3 次注定失败的请求在每次同步里重复付出延迟。
     * 因此改为纯本地缓存：无缓存就是无缓存，如实记录，不再假装还有网络兜底。
     */
    suspend fun syncSchedule(context: Context): Result<Int> = withContext(Dispatchers.IO) {
        Log.d(TAG, "开始执行课表同步...")

        val courses = getCachedCourses(context)
        if (courses.isEmpty()) {
            Log.w(TAG, "本地无课表缓存，无法注册任何闹钟（需先在 App 内加载一次课表）")
            ReminderDiagnostics.recordAttempt(
                context, "同步", ReminderDiagnostics.OUTCOME_EMPTY_CACHE,
                "本地无课表缓存：打开 App 加载一次课表即可恢复"
            )
            return@withContext Result.success(0)
        }

        val registeredCount = scheduleFutureCourses(context, courses)
        Log.i(TAG, "课表同步调度完成！成功注册闹钟数: $registeredCount（本地课程 ${courses.size} 门）")
        Result.success(registeredCount)
    }

    /**
     * 针对给定的课程列表，筛选未来 7 天待上课程并注册成对闹钟
     */
    private fun scheduleFutureCourses(context: Context, allCourses: List<Course>): Int {
        val now = System.currentTimeMillis()
        val sevenDaysLater = now + (AppConfig.SYNC_FUTURE_DAYS * 24 * 60 * 60 * 1000L)

        // 筛选尚未结束且在未来 7 天内的课程
        val validFutureCourses = allCourses.filter { course ->
            course.endMillis > now && course.startMillis <= sevenDaysLater
        }

        val sp = getPrefs(context)
        val oldRegisteredKeys = sp.getStringSet(AppConfig.KEY_REGISTERED_KEYS, emptySet())?.toMutableSet()
            ?: mutableSetOf()

        val currentActiveAlarmKeys = mutableSetOf<String>()
        var registeredCount = 0
        // 记录"下一次开课提醒"的时间，供 App 内自检面板显示。
        // 不依赖进程内状态：进程被杀后从 SharedPreferences 依然读得到。
        var nextReminderAt = 0L

        for (course in validFutureCourses) {
            val (startOk, endOk) = AlarmManagerHelper.registerCourseAlarms(context, course)
            if (startOk) {
                currentActiveAlarmKeys.add(course.startKey)
                registeredCount++
                if (course.reminderMillis > now &&
                    (nextReminderAt == 0L || course.reminderMillis < nextReminderAt)
                ) {
                    nextReminderAt = course.reminderMillis
                }
            }
            if (endOk) {
                currentActiveAlarmKeys.add(course.endKey)
                registeredCount++
            }

            // 特殊场景：若当前正好处于课前 5 分钟内或正在上课中，立即唤起流体云悬浮胶囊。
            // 注意这是"前台路径"——打开 App 就能看到灵动岛，与闹钟路径是否可用无关，
            // 所以它曾经掩盖了"后台闹钟从不触发"的问题。
            if (course.reminderMillis <= now && now < course.endMillis) {
                Log.i(TAG, "当前正处于即将上课或上课中，立即拉起流体云胶囊: ${course.courseName}")
                FloatingWindowService.startService(context, course)
            }
        }

        // 清理已不再生效的旧闹钟
        val keysToCancel = oldRegisteredKeys - currentActiveAlarmKeys
        for (key in keysToCancel) {
            when {
                key.contains("_start_") -> {
                    AlarmManagerHelper.cancelAlarmByKey(context, AlarmManagerHelper.ACTION_COURSE_START, key)
                }
                key.contains("_end_") -> {
                    AlarmManagerHelper.cancelAlarmByKey(context, AlarmManagerHelper.ACTION_COURSE_END, key)
                }
                else -> {
                    AlarmManagerHelper.cancelCourseAlarm(context, key)
                }
            }
            Log.d(TAG, "取消已失效闹钟: $key")
        }

        sp.edit().putStringSet(AppConfig.KEY_REGISTERED_KEYS, currentActiveAlarmKeys).apply()
        AlarmManagerHelper.scheduleDailySync(context)
        ReminderDiagnostics.recordScheduling(context, registeredCount, nextReminderAt)

        if (registeredCount == 0) {
            Log.w(TAG, "未来 ${AppConfig.SYNC_FUTURE_DAYS} 天内没有可注册的课程闹钟")
        }
        return registeredCount
    }

    /**
     * 将课程列表持久化到 SharedPreferences
     */
    fun saveCoursesToCache(context: Context, courses: List<Course>) {
        val jsonArray = JSONArray()
        for (course in courses) {
            jsonArray.put(Course.toJson(course))
        }
        getPrefs(context).edit().putString(AppConfig.KEY_CACHED_COURSES, jsonArray.toString()).apply()
        Log.d(TAG, "已持久化 ${courses.size} 门课程到本地存储")    }

    /**
     * 从本地存储读取缓存的课程数据
     */
    fun getCachedCourses(context: Context): List<Course> {
        val rawJson = getPrefs(context).getString(AppConfig.KEY_CACHED_COURSES, null) ?: return emptyList()
        val result = mutableListOf<Course>()
        try {
            val jsonArray = JSONArray(rawJson)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.optJSONObject(i)
                if (obj != null) {
                    val course = Course.fromJson(obj)
                    if (course.id > 0) {
                        result.add(course)
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "读取本地课表缓存解析异常: ${e.message}", e)
        }
        return result
    }

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)
    }
}
