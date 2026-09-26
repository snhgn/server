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
     * 统一入口：全量同步课表并更新系统闹钟
     */
    suspend fun syncSchedule(context: Context): Result<Int> = withContext(Dispatchers.IO) {
        Log.d(TAG, "开始执行课表同步...")

        // 1. 尝试从服务端拉取最新课表
        val fetchResult = ApiClient.fetchCourses()
        val latestCourses: List<Course> = if (fetchResult.isSuccess) {
            val list = fetchResult.getOrDefault(emptyList())
            saveCoursesToCache(context, list)
            list
        } else {
            Log.w(TAG, "服务端请求失败，回退读取本地持久化课表缓存")
            getCachedCourses(context)
        }

        if (latestCourses.isEmpty()) {
            Log.w(TAG, "未获取到任何有效课程数据，结束同步")
            return@withContext Result.success(0)
        }

        // 2. 筛选当前时间之后、且在未来 7 天以内的课程
        val now = System.currentTimeMillis()
        val sevenDaysLater = now + (AppConfig.SYNC_FUTURE_DAYS * 24 * 60 * 60 * 1000L)

        val validFutureCourses = latestCourses.filter { course ->
            val end = course.endMillis
            val start = course.startMillis
            // 只要课程还没结束，并且在未来 7 天内
            end > now && start <= sevenDaysLater
        }

        // 3. 与本地已注册闹钟集合进行比对
        val sp = getPrefs(context)
        val oldRegisteredKeys = sp.getStringSet(AppConfig.KEY_REGISTERED_KEYS, emptySet())?.toMutableSet()
            ?: mutableSetOf()

        // 收集新课表需要生效的全部 Alarm Key
        val targetStartKeys = mutableSetOf<String>()
        val targetEndKeys = mutableSetOf<String>()
        val currentActiveAlarmKeys = mutableSetOf<String>()

        var registeredCount = 0
        for (course in validFutureCourses) {
            val (startOk, endOk) = AlarmManagerHelper.registerCourseAlarms(context, course)
            if (startOk) {
                targetStartKeys.add(course.startKey)
                currentActiveAlarmKeys.add(course.startKey)
                registeredCount++
            }
            if (endOk) {
                targetEndKeys.add(course.endKey)
                currentActiveAlarmKeys.add(course.endKey)
                registeredCount++
            }
        }

        // 计算需要取消的旧闹钟：已注册但不再存在于新课表中的闹钟
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
                    // 兼容旧格式 Key
                    AlarmManagerHelper.cancelCourseAlarm(context, key)
                }
            }
            Log.d(TAG, "取消已失效或已修改的闹钟: $key")
        }

        // 4. 更新本地已注册的 Key 列表
        sp.edit().putStringSet(AppConfig.KEY_REGISTERED_KEYS, currentActiveAlarmKeys).apply()

        // 5. 安排下一次每日凌晨自动同步任务
        AlarmManagerHelper.scheduleDailySync(context)

        Log.d(TAG, "课表同步完成！未来有效课程数: ${validFutureCourses.size}, 成功注册闹钟数: $registeredCount")
        Result.success(registeredCount)
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
