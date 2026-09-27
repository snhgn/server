package me.snhgn.schedule.network

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
        private val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())

        fun parseTimeToMillis(timeStr: String): Long {
            return try {
                dateFormat.parse(timeStr)?.time ?: 0L
            } catch (e: Exception) {
                0L
            }
        }

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
