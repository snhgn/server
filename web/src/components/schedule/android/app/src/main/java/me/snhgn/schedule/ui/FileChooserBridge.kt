package me.snhgn.schedule.ui

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.util.Log
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.IntentCompat

/**
 * WebView 里 `<input type="file">` 的系统选择器承接。
 *
 * 为什么要专门写这个：Android 的 WebView **不自带**文件选择能力。
 * 页面上的 input 被点击时，WebView 会回调 [WebChromeClient.onShowFileChooser]，
 * 而基类实现直接返回 false 且不做任何事——既不报错也不弹窗，表现就是"点了没反应"。
 * 原先 WebChromeClient 只重写了 onProgressChanged，于是 App 内"设置背景"点上传毫无反应，
 * 而同一段网页在浏览器里是好的，差别就在宿主 App 有没有提供这个承接。
 *
 * 拖拽与粘贴两条路径在手机上都不存在，所以这个 input 是 App 端设置背景的唯一入口，
 * 断在这里等于整个功能不可用。
 *
 * 另外两条容易踩的规则（都不直观，但都会让功能"只生效一次"或"永久失灵"）：
 * 1. 存新回调前必须先把上一个未消费的回调喂 null。ValueCallback 是一次性的，
 *    留着不消费，WebView 内部的待处理回调不会清空，之后点多少次都不再拉起选择器。
 * 2. 用户取消也必须回调（值为 null）。漏掉这一步等同于把下一次请求一起作废。
 */
class FileChooserBridge(private val host: ComponentActivity) {

    private var pending: ValueCallback<Array<Uri>>? = null

    private val launcher = host.registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result -> deliver(result) }

    fun onShowFileChooser(
        filePathCallback: ValueCallback<Array<Uri>>,
        params: WebChromeClient.FileChooserParams?,
    ): Boolean {
        pending?.onReceiveValue(null)
        pending = filePathCallback

        val intent = buildIntent(params)
        if (intent == null) {
            pending?.onReceiveValue(null)
            pending = null
            return false
        }

        return try {
            launcher.launch(intent)
            true
        } catch (e: ActivityNotFoundException) {
            Log.w(TAG, "系统没有可处理该类型的文件选择器: ${e.message}")
            pending?.onReceiveValue(null)
            pending = null
            false
        }
    }

    /** 页面被销毁时把悬着的回调结掉，别让它悬到下次进页面。 */
    fun dispose() {
        pending?.onReceiveValue(null)
        pending = null
    }

    private fun buildIntent(params: WebChromeClient.FileChooserParams?): Intent? {
        if (params == null) return null
        val acceptTypes = params.acceptTypes?.filter { it.isNotBlank() }.orEmpty()
        // 通配符优先：页面写 accept="image/*" 是最常见的情况，
        // 直接取第一个值在只有一个具体类型（如 image/png）时反而把范围收得过窄
        val mimeType = when {
            acceptTypes.any { it == "image/*" } -> "image/*"
            acceptTypes.isEmpty() -> "*/*"
            else -> acceptTypes.first()
        }
        return Intent(Intent.ACTION_GET_CONTENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = mimeType
            // 多个具体类型时一并给出，过滤条件比单个 type 更准
            if (acceptTypes.size > 1) {
                putExtra(Intent.EXTRA_MIME_TYPES, acceptTypes.toTypedArray())
            }
            if (params.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE) {
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            }
        }
    }

    private fun deliver(result: ActivityResult) {
        val callback = pending
        pending = null
        if (callback == null) return
        if (result.resultCode != Activity.RESULT_OK) {
            callback.onReceiveValue(null)
            return
        }
        callback.onReceiveValue(extractUris(result.data))
    }

    private fun extractUris(data: Intent?): Array<Uri>? {
        // 平台自带的解析覆盖单选（getData）与多选（getClipData）两种主流回传方式
        val parsed = WebChromeClient.FileChooserParams.parseResult(Activity.RESULT_OK, data)
        if (parsed != null) return parsed
        // 个别机型用 EXTRA_STREAM 列表回传多选，上面那个解析不到，补一次
        if (data == null) return null
        val streamUris = IntentCompat.getParcelableArrayListExtra(data, Intent.EXTRA_STREAM, Uri::class.java)
        if (streamUris.isNullOrEmpty()) return null
        return streamUris.toTypedArray()
    }

    private companion object {
        const val TAG = "FileChooser"
    }
}