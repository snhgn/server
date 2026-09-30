package me.snhgn.schedule.network

import android.os.SystemClock
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.net.HttpURLConnection
import java.net.URL

/**
 * 候选线路预探测：在 WebView 真正发起加载之前，先挑一条通的。
 *
 * 为什么需要它：
 * [me.snhgn.schedule.config.AppConfig.CANDIDATE_URLS] 里排第一的 lan.snhgn.me 是校园网内网直连，
 * 第二条 cn.snhgn.me 是国内中继，这两条在校园网之外没有公网 DNS 记录。而原来的故障转移完全依赖
 * WebView 自己的 DNS + 连接超时（移动网络上动辄二三十秒），且没有自定超时：
 *
 *   冷启动 → 试 lan（长时间空白）→ 试 cn（又一段长时间空白）→ 试 snhgn.me（这才进去）
 *
 * 这正是"长时间等待、报错、最后才能进入"的成因。探测把"等 WebView 超时"换成"等我们自己的短超时"，
 * 最坏情况从几十秒压到 [GLOBAL_DEADLINE_MS]。
 *
 * 并发而非顺序：顺序探测在离校场景下要串行付两次超时；并发后 snhgn.me 一通即可定案，
 * 而在校场景下 lan 因为是内网直连、往返最小而胜出——不靠候选顺序靠谁先到，
 * 顺序只作为全部不通时的兜底偏好。
 */
object UrlProbe {

    private const val TAG = "UrlProbe"

    /** 单条线路的连接/读取超时。够走完一次 TLS 握手（内网直连通常 <100ms），又不至于拖成一次长等待。 */
    private const val CONNECT_TIMEOUT_MS = 2500
    private const val READ_TIMEOUT_MS = 2500

    /** 整体上限：三条线路并发跑，正常数百毫秒出结果；这个上限只兜"网络整体不通"的病态情况。 */
    private const val GLOBAL_DEADLINE_MS = 5000L

    data class Outcome(
        val url: String,
        val index: Int,
        val reachable: Boolean,
        val elapsedMs: Long,
        val detail: String,
    )

    /**
     * 返回第一条探测通的线路。
     *
     * 全都不通时返回 [fallbackIndex] 指定的候选（默认列表末位，即公网隧道），
     * 而不是直接判定失败：探测只是"择优加载"，最终成不成功仍由 WebView 的加载结果说了算，
     * 这样错误页与重试流程保持唯一一套，不会出现探测与 WebView 各说各话。
     */
    suspend fun pickFirstReachable(
        candidates: List<String>,
        fallbackIndex: Int = (candidates.size - 1).coerceAtLeast(0),
    ): Outcome {
        if (candidates.isEmpty()) {
            return Outcome("", -1, reachable = false, elapsedMs = 0, detail = "候选线路为空")
        }
        val safeFallback = fallbackIndex.coerceIn(candidates.indices)

        return withContext(Dispatchers.IO) {
            val startedAt = SystemClock.elapsedRealtime()
            coroutineScope {
                // 无缓冲上限：输掉竞争的探测即便比赢家晚返回，也不至于把结果卡在 send 上
                val arrivals = Channel<Outcome>(Channel.UNLIMITED)
                candidates.forEachIndexed { index, url ->
                    launch(Dispatchers.IO) { arrivals.send(probe(index, url)) }
                }

                var failures = 0
                var lastArrival: Outcome? = null
                while (true) {
                    val budget = GLOBAL_DEADLINE_MS - (SystemClock.elapsedRealtime() - startedAt)
                    if (budget <= 0L) break
                    val outcome = withTimeoutOrNull(budget) { arrivals.receive() } ?: break
                    lastArrival = outcome
                    if (outcome.reachable) {
                        Log.i(TAG, "线路可用: ${outcome.url} (${outcome.elapsedMs}ms, ${outcome.detail})")
                        return@coroutineScope outcome
                    }
                    Log.w(TAG, "线路不可用: ${outcome.url} (${outcome.elapsedMs}ms, ${outcome.detail})")
                    if (++failures >= candidates.size) break
                }

                val fallback = candidates[safeFallback]
                val elapsed = SystemClock.elapsedRealtime() - startedAt
                val detail = if (lastArrival == null) "整体超时" else "全部候选均不可达"
                Log.w(TAG, "交回兜底线路: $fallback ($detail)")
                Outcome(fallback, safeFallback, reachable = false, elapsedMs = elapsed, detail = detail)
            }
        }
    }

    /**
     * 探测单条线路。
     *
     * 只读响应头不读响应体：线路通不通在首个响应字节到达时就已知晓，
     * 没必要为了判断可达性把整个页面下完。
     *
     * 判定放宽到"拿到任何 HTTP 响应"：4xx/5xx 说明链路本身通到了我们的服务器，
     * 那是网页侧的问题，不构成换线路的理由；只有连 DNS/TCP/TLS 都没过去才算不可用。
     */
    private fun probe(index: Int, url: String): Outcome {
        val startedAt = SystemClock.elapsedRealtime()
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("Cache-Control", "no-cache")
                setRequestProperty("User-Agent", "SnhgnScheduleAndroid/probe")
            }
            val code = conn.responseCode
            Outcome(url, index, reachable = true, SystemClock.elapsedRealtime() - startedAt, "HTTP $code")
        } catch (e: Exception) {
            Outcome(
                url, index, reachable = false, SystemClock.elapsedRealtime() - startedAt,
                "${e.javaClass.simpleName}: ${e.message ?: "无详细信息"}"
            )
        } finally {
            conn?.disconnect()
        }
    }
}