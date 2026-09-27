package me.snhgn.schedule.config

/**
 * 全局应用配置常量
 */
object AppConfig {
    /**
     * 前台 WebView 打开的课程表网址
     * 支持全屏独立浏览、Cookie 与 LocalStorage 登录持久化
     */
    const val WEBVIEW_URL = "https://snhgn.me/schedule"

    /**
     * 后端课程同步 API 地址 (GET)
     * 返回标准 JSON 数组: [{"id": 1, "courseName": "高等数学", "classRoom": "教2-301", "startTime": "...", "endTime": "..."}]
     */
    const val COURSE_API_URL = "https://snhgn.me/api/course/list"

    /**
     * 课前提醒提前量 (分钟)
     */
    const val ADVANCE_REMINDER_MINUTES = 5L

    /**
     * 自动同步未来课程天数 (默认 7 天)
     */
    const val SYNC_FUTURE_DAYS = 7

    /**
     * 每日定时清晨全量同步课表的小时 (03:00)
     */
    const val DAILY_SYNC_HOUR = 3
    const val DAILY_SYNC_MINUTE = 0

    /**
     * SharedPreferences 存储名称
     */
    const val PREFS_NAME = "snhgn_schedule_prefs"
    const val KEY_CACHED_COURSES = "key_cached_courses"
    const val KEY_REGISTERED_KEYS = "key_registered_keys"
    const val KEY_PERMISSION_GUIDED = "key_permission_guided"
}
