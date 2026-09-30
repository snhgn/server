package me.snhgn.schedule.config

/**
 * 全局应用配置常量
 */
object AppConfig {
    /**
     * 前台 WebView 打开的课程表网址与候选故障转移端点
     * 1. 优先尝试校园网直连 (lan.snhgn.me)，内网极速，即使首次未完成校园网外网认证也可直接访问
     * 2. 兜底回退公网 Cloudflare 隧道 (snhgn.me)
     */
    val CANDIDATE_URLS = listOf(
        "https://lan.snhgn.me/schedule?app=1",
        "https://cn.snhgn.me/schedule?app=1",
        "https://snhgn.me/schedule?app=1"
    )

    const val WEBVIEW_URL = "https://lan.snhgn.me/schedule?app=1"

    // 注意：这里曾经有 API_CANDIDATE_URLS / COURSE_API_URL（/api/course/list），
    // 作为"本地无缓存就去后端拉课表"的兜底。实测三个候选端点全部返回
    // 404 {"detail":"Not Found"}，从未成功过；且 3 URL × (6s 连接 + 6s 读取)
    // 最坏 36 秒，会把走 goAsync()（仅 10 秒预算）的开机/每日同步广播拖到超时被杀。
    // 课表数据的唯一来源现为 WebView 前端经 JS 桥 syncCourses 推送，见 ScheduleSyncManager。

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
