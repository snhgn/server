package me.snhgn.schedule.network

import android.util.Log
import me.snhgn.schedule.config.AppConfig
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Locale

/**
 * 课程数据实体
 */
data class Course(
    val id: Long,
    val courseName: String,
    val classRoom: String,
    val startTime: String, // 格式: "yyyy-MM-dd HH:mm"
    val endTime: String    // 格式: "yyyy-MM-dd HH:mm"
) {
    /**
     * 唯一课程 Key: course.id + "_" + startTime
     * 用于幂等去重和防冲突注册
     */
    val uniqueKey: String
        get() = "${id}_$startTime"

    /**
     * 开始闹钟唯一 Key (课前 5 分钟)
     */
    val startKey: String
        get() = "${id}_start_$startTime"

    /**
     * 结束闹钟唯一 Key (课程结束时间)
     */
    val endKey: String
        get() = "${id}_end_$endTime"

    /**
     * 上课时间戳 (毫秒)
     */
    val startMillis: Long
        get() = parseTimeToMillis(startTime)

    /**
     * 下课时间戳 (毫秒)
     */
    val endMillis: Long
        get() = parseTimeToMillis(endTime)

    /**
     * 闹钟触发时间戳 (上课前 5 分钟)
     */
    val reminderMillis: Long
        get() = startMillis - (AppConfig.ADVANCE_REMINDER_MINUTES * 60 * 1000L)

    companion object {
        private const val PATTERN = "yyyy-MM-dd HH:mm"

        /**
         * 每次调用新建一个 SimpleDateFormat。
         *
         * 曾经这里放了一个 companion 级共享实例，但 SimpleDateFormat 明确不是线程安全的：
         * startMillis/endMillis 会被 AlarmBroadcastReceiver(IO 协程)、
         * ScheduleSyncManager(IO 协程)、FloatingWindowService(主线程) 并发解析，
         * 竞争下 parse() 会抛异常或返回错值 —— 后者更糟，会让 endMillis 变成一个
         * 看似合法的未来时间，闹钟于是被注册到一个错误的时间点且毫无日志。
         * 解析不在热点路径上，新建实例的开销可以忽略。
         */
        fun parseTimeToMillis(timeStr: String): Long {
            if (timeStr.isBlank()) return 0L
            return try {
                SimpleDateFormat(PATTERN, Locale.getDefault()).apply {
                    isLenient = false
                }.parse(timeStr)?.time ?: 0L
            } catch (e: Exception) {
                Log.w("Course", "课程时间解析失败: '$timeStr' -> ${e.message}")
                0L
            }
        }

        /**
         * 时间是否可解析。用于自检：不可解析的课程会静默拿不到闹钟。
         */
        fun isTimeValid(timeStr: String): Boolean = parseTimeToMillis(timeStr) > 0L

        fun fromJson(json: JSONObject): Course {
            return Course(
                id = json.optLong("id", 0L),
                courseName = json.optString("courseName", "未知课程"),
                classRoom = json.optString("classRoom", "未知教室"),
                startTime = json.optString("startTime", ""),
                endTime = json.optString("endTime", "")
            )
        }

        fun toJson(course: Course): JSONObject {
            return JSONObject().apply {
                put("id", course.id)
                put("courseName", course.courseName)
                put("classRoom", course.classRoom)
                put("startTime", course.startTime)
                put("endTime", course.endTime)
            }
        }
    }
}
