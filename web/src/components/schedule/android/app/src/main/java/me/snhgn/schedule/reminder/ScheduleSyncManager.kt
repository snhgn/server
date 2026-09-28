package me.snhgn.schedule.reminder

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.network.ApiClient
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
        try {
            val jsonArray = JSONArray(jsonStr)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.optJSONObject(i)
                if (obj != null) {
                    val course = Course.fromJson(obj)
                    if (course.id > 0 && course.startTime.isNotEmpty()) {
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
            return@withContext 0
        }

        saveCoursesToCache(context, courseList)
        val registeredCount = scheduleFutureCourses(context, courseList)
        Log.i(TAG, "前端推送课表同步完成！解析得到 ${courseList.size} 门具体课程，已注册未来 7 天内 ${registeredCount} 个闹钟")
        registeredCount
    }

    /**
     * 统一入口：全量同步课表并更新系统闹钟 (本地缓存优先，手机开机/每日定时调用)
     */
    suspend fun syncSchedule(context: Context): Result<Int> = withContext(Dispatchers.IO) {
        Log.d(TAG, "开始执行课表同步...")

        // 1. 本地可靠缓存优先
        var courses = getCachedCourses(context)

        // 2. 若本地暂无缓存，尝试通过候选 API 端点拉取兜底
        if (courses.isEmpty()) {
            val fetchResult = ApiClient.fetchCourses()
            if (fetchResult.isSuccess) {
                courses = fetchResult.getOrDefault(emptyList())
                if (courses.isNotEmpty()) {
                    saveCoursesToCache(context, courses)
                }
            }
        }

        if (courses.isEmpty()) {
            Log.w(TAG, "未获取到任何有效课程数据，结束同步")
            return@withContext Result.success(0)
        }

        val registeredCount = scheduleFutureCourses(context, courses)
        Log.i(TAG, "课表同步调度完成！成功注册闹钟数: $registeredCount")
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

        for (course in validFutureCourses) {
            val (startOk, endOk) = AlarmManagerHelper.registerCourseAlarms(context, course)
            if (startOk) {
                currentActiveAlarmKeys.add(course.startKey)
                registeredCount++
            }
            if (endOk) {
                currentActiveAlarmKeys.add(course.endKey)
                registeredCount++
            }

            // 特殊场景：若当前正好处于课前 5 分钟内或正在上课中，立即唤起流体云悬浮胶囊
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
        Log.d(TAG, "已持久化 ${courses.size} 门课程到本地存储")
    }

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
