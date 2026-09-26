package me.snhgn.schedule.network

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.snhgn.schedule.config.AppConfig
import org.json.JSONArray
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * 极简、可靠的 HTTP 原生网络客户端
 * 优先采用 HttpURLConnection，零大型外部框架依赖
 */
object ApiClient {
    private const val TAG = "ApiClient"
    private const val CONNECT_TIMEOUT_MS = 6000
    private const val READ_TIMEOUT_MS = 6000

    /**
     * 异步拉取后端最新课程列表
     */
    suspend fun fetchCourses(apiUrl: String = AppConfig.COURSE_API_URL): Result<List<Course>> =
        withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL(apiUrl)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = CONNECT_TIMEOUT_MS
                    readTimeout = READ_TIMEOUT_MS
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("User-Agent", "SnhgnScheduleAndroid/1.0")
                    doInput = true
                }

                val responseCode = connection.responseCode
                if (responseCode in 200..299) {
                    val reader = BufferedReader(InputStreamReader(connection.inputStream, "UTF-8"))
                    val sb = StringBuilder()
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        sb.append(line)
                    }
                    reader.close()

                    val rawJson = sb.toString().trim()
                    val courseList = mutableListOf<Course>()

                    if (rawJson.startsWith("[")) {
                        val jsonArray = JSONArray(rawJson)
                        for (i in 0 until jsonArray.length()) {
                            val obj = jsonArray.optJSONObject(i)
                            if (obj != null) {
                                val course = Course.fromJson(obj)
                                if (course.id > 0 && course.startTime.isNotEmpty()) {
                                    courseList.add(course)
                                }
                            }
                        }
                    } else if (rawJson.startsWith("{")) {
                        // 兼容包装格式 {"code": 200, "data": [...]}
                        val rootObj = org.json.JSONObject(rawJson)
                        val dataArray = rootObj.optJSONArray("data") ?: rootObj.optJSONArray("courses")
                        if (dataArray != null) {
                            for (i in 0 until dataArray.length()) {
                                val obj = dataArray.optJSONObject(i)
                                if (obj != null) {
                                    val course = Course.fromJson(obj)
                                    if (course.id > 0 && course.startTime.isNotEmpty()) {
                                        courseList.add(course)
                                    }
                                }
                            }
                        }
                    }

                    Log.d(TAG, "成功拉取到 ${courseList.size} 门课程")
                    Result.success(courseList)
                } else {
                    val errorMsg = "HTTP 请求失败，状态码: $responseCode"
                    Log.w(TAG, errorMsg)
                    Result.failure(Exception(errorMsg))
                }
            } catch (e: Exception) {
                Log.e(TAG, "拉取课程异常: ${e.message}", e)
                Result.failure(e)
            } finally {
                connection?.disconnect()
            }
        }
}
