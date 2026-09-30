package me.snhgn.schedule.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebChromeClient.FileChooserParams
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import me.snhgn.schedule.BuildConfig
import me.snhgn.schedule.R
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.network.UrlProbe
import me.snhgn.schedule.permission.PermissionHelper
import me.snhgn.schedule.reminder.ReminderDiagnostics
import me.snhgn.schedule.reminder.ScheduleSyncManager
import org.json.JSONObject

/**
 * APP 主界面：纯粹、无边框、支持持久登录态的全屏 WebView 容器
 * 体验与“把课表网站装进一个 APP”一致
 */
class MainActivity : AppCompatActivity() {

    private var webView: WebView? = null

    // 这几个是"可空"而不是 lateinit：首次启动时 onCreate 会在完成权限引导前
    // 提前 return，initViews() 根本不会执行，但 onDestroy 照样会被调用。
    // 用 lateinit 时，onDestroy 里一次 splash.animate() 就足以让全新安装的用户
    // 在启动瞬间崩掉（实测：OnePlus 装完会盖一层 InstallFinishActivity，
    // MainActivity 随即被销毁）。
    private var progressBar: ProgressBar? = null
    private var layoutError: View? = null
    private var btnRetry: Button? = null
    private var currentUrlIndex = 0

    /** 承接网页里的文件选择（设置背景的上传入口），见 [FileChooserBridge] */
    private val fileChooser = FileChooserBridge(this)

    // ---- 冷启动缓冲层 ----
    // 进程起来到网页出首帧之间 WebView 是纯白屏，只有一根顶边细条。
    // 这里盖一层与网页端同一套语言的缓冲界面（wordmark + 骨架 + 状态文案），
    // 加载完淡出，把画面交给网页自己的 ScheduleLoading 接手。
    private var splash: View? = null
    private var splashDismissed = false
    private var slowHintJob: Job? = null
    private var splashFadeJob: Job? = null
    private var probeJob: Job? = null

    /**
     * 本轮加载中已确认主文档失败的 URL。
     *
     * 用它拦住一个具体陷阱：主文档加载失败时，WebView 会渲染它自带的错误页，
     * 并对这个错误页同样回调 onPageFinished。onPageFinished 因此不能当作"网页已就绪"的信号，
     * 否则缓冲层会在第一条线路失败的瞬间被撤掉，把系统那张"网页不可用"直接甩给用户看——
     * 恰好是最不该露出来的时刻。
     *
     * 记 URL 而不是记布尔量：onReceivedError 与下一条线路的 onPageFinished 之间没有固定的先后，
     * 单一标志位会被回调乱序击穿。
     */
    private val erroredUrls = HashSet<String>()

    private companion object {
        /** 超过该时长仍在加载，状态文案改为安抚措辞（与网页端 slowAfter 同量级） */
        const val SPLASH_SLOW_AFTER_MS = 6000L

        /** 淡出时长：短到几乎察觉不到，只为消除"啪"地一下的硬切 */
        const val SPLASH_FADE_MS = 180L
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 首次启动检查：若未完成必要权限引导，进入引导页
        if (!PermissionHelper.hasCompletedGuide(this)) {
            startActivity(Intent(this, PermissionGuideActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_main)

        // 沉浸式边缘到边缘体验
        setupImmersiveWindow()

        initViews()
        setupWebView()

        // 每次打开 APP 时在后台自动静默同步一次最新课表及闹钟
        lifecycleScope.launch {
            ScheduleSyncManager.syncSchedule(applicationContext)
        }

        // 先探测再加载：在校走 lan 内网直连，离校直接落到公网隧道，
        // 不必先在一条解析不了的线路前干等二三十秒
        startLoad()
    }

    /**
     * 探测候选线路后把选中的那条交给 WebView。
     *
     * 冷启动与"重新加载"都走这里：重试同样需要重新择优，否则每次重试都要把
     * lan / cn 的超时重付一遍，用户按几次就是几次长等待。
     */
    private fun startLoad() {
        erroredUrls.clear()
        layoutError?.visibility = View.GONE
        webView?.visibility = View.VISIBLE
        showSplash()
        setSplashStatus(R.string.splash_probing)

        probeJob?.cancel()
        probeJob = lifecycleScope.launch {
            val picked = UrlProbe.pickFirstReachable(AppConfig.CANDIDATE_URLS)
            currentUrlIndex = picked.index
            android.util.Log.i("MainActivity", "选定线路 ${picked.url}（${picked.detail}）")
            // 探测只解决"选谁"，成败仍由 WebView 的加载结果判定；
            // 探测没选出可用线路时也照常往下走，好让错误卡片与重试保持唯一一套流程
            setSplashStatus(R.string.splash_connecting)
            webView?.loadUrl(picked.url)
        }
    }

    private fun setupImmersiveWindow() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller.isAppearanceLightStatusBars = false

        val rootView = findViewById<View>(R.id.root_layout)
        ViewCompat.setOnApplyWindowInsetsListener(rootView) { view, insets ->
            val statusBars = insets.getInsets(WindowInsetsCompat.Type.statusBars())
            val navBars = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            view.setPadding(0, statusBars.top, 0, navBars.bottom)
            insets
        }
    }

    private fun initViews() {
        webView = findViewById(R.id.web_view)
        progressBar = findViewById(R.id.progress_bar)
        layoutError = findViewById(R.id.layout_error)
        btnRetry = findViewById(R.id.btn_retry)
        splash = findViewById(R.id.splash_container)

        findViewById<View>(R.id.btn_open_settings).setOnClickListener {
            startActivity(Intent(this, PermissionGuideActivity::class.java))
        }

        btnRetry?.setOnClickListener {
            // 重试要连线路选择一起重来：只把 currentUrlIndex 归零再 load，
            // 等于每次都先把 lan / cn 的超时重付一遍
            startLoad()
        }

        // 适配 Android 13+ 返回键逻辑：网页内部跳转支持返回上一页
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val wv = webView
                if (wv != null && wv.canGoBack()) {
                    wv.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }

    /**
     * 重新盖上缓冲层（冷启动或点击重试时调用）。
     * 幂等：已在显示时只重置文案与计时，不会叠加动画。
     */
    private fun showSplash() {
        splashDismissed = false
        splashFadeJob?.cancel()
        val sp = splash ?: return
        sp.animate().cancel()
        sp.alpha = 1f
        sp.visibility = View.VISIBLE
        setSplashStatus(R.string.splash_connecting)

        slowHintJob?.cancel()
        slowHintJob = lifecycleScope.launch {
            delay(SPLASH_SLOW_AFTER_MS)
            // 只在仍然等待时才改文案：加载早就结束时不该再冒出"网络较慢"
            if (!splashDismissed) {
                setSplashStatus(R.string.splash_slow)
            }
        }
    }

    /** 统一改写缓冲层状态文案，避免各处 findViewById 散落。 */
    private fun setSplashStatus(resId: Int) {
        findViewById<TextView>(R.id.splash_status).setText(resId)
    }

    private fun setSplashStatus(text: String) {
        findViewById<TextView>(R.id.splash_status).text = text
    }

    /**
     * 网页首帧已渲染，淡出缓冲层。
     *
     * 时机说明：用 onPageFinished 而不是 onProgressChanged=100。
     * 资源加载进度到 100 只代表字节下完，网页此时可能还没画出任何东西；
     * onPageFinished 更接近"用户真的能看到内容"，此时交棒才不会白一下。
     */
    private fun dismissSplash() {
        if (splashDismissed) return
        splashDismissed = true
        slowHintJob?.cancel()
        splashFadeJob?.cancel()
        val sp = splash ?: return
        splashFadeJob = lifecycleScope.launch {
            sp.animate()
                .alpha(0f)
                .setDuration(SPLASH_FADE_MS)
                .withEndAction { sp.visibility = View.GONE }
                .start()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        // 仅 debug 包开启 WebView 远程调试（CDP），用于在真机上驱动页面做端到端验证。
        // release 包这一行不执行。历史上"编译通过 + 产物常量齐全"连续放过了
        // 一个启动即崩的 bug，只有真机跑才暴露得出来，这个开关就是为此留的抓手。
        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true)
        }

        val wv = webView ?: return
        val settings = wv.settings
        settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true    // 支持 LocalStorage
            databaseEnabled = true      // 支持 Web SQL / IndexDB
            // Caddy 服务器对 index.html 标头设为 no-cache，每次打开必然请求最新 HTML；
            // 对带 hash 的静态脚本/样式使用正常缓存 (LOAD_DEFAULT)，实现毫秒级秒开，免每次重新下载全站代码
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(false)
            displayZoomControls = false
            // content:// 与 file:// 是两套开关：设置背景选中的图片由系统选择器以 content:// 返回，
            // 由 allowContentAccess 决定能否读取（默认 true，这里写明以免日后有人一并关掉）。
            // allowFileAccess 管的是 file://，保持关闭：不需要它，且开着等于把本地文件
            // 暴露给网页脚本。若日后出现"选择器能打开但图片读不出来"，先看这一行。
            allowContentAccess = true
            allowFileAccess = false
            userAgentString = "${settings.userAgentString} SnhgnScheduleAndroid/1.0"
        }

        // 维持 Cookie 与登录状态
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(wv, true)

        wv.addJavascriptInterface(object {
            @android.webkit.JavascriptInterface
            fun openSettings() {
                startActivity(Intent(this@MainActivity, PermissionGuideActivity::class.java))
            }

            @android.webkit.JavascriptInterface
            fun syncCourses(jsonStr: String) {
                android.util.Log.d("AndroidBridge", "收到前端推送的课程数据，长度: ${jsonStr.length}")
                lifecycleScope.launch {
                    ScheduleSyncManager.updateFromWebJson(applicationContext, jsonStr)
                }
            }

            /**
             * 灵动岛自检数据。
             *
             * "到课时间不弹胶囊"这个故障此前完全不可观测：闹钟没注册、广播没收到、
             * 前台服务被系统拒绝，三种情况在用户侧都是同一副面孔。
             * 把 ReminderDiagnostics 的结论透出到网页，才能定位到具体哪一环断了。
             */
            @android.webkit.JavascriptInterface
            fun getReminderStatus(): String {
                return try {
                    ReminderDiagnostics.toJson(applicationContext).toString()
                } catch (e: Exception) {
                    android.util.Log.e("AndroidBridge", "生成自检数据失败", e)
                    JSONObject().put("error", e.message ?: "未知错误").toString()
                }
            }

            @android.webkit.JavascriptInterface
            fun testFluidCloud() {
                android.util.Log.d("AndroidBridge", "触发流体云悬浮胶囊即刻测试")
                val now = System.currentTimeMillis()
                val dateFormat = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault())
                val testCourse = me.snhgn.schedule.network.Course(
                    id = 999999L,
                    courseName = "高等数学 (测试提醒)",
                    classRoom = "学研大厦 A0101",
                    startTime = dateFormat.format(java.util.Date(now + 3 * 60 * 1000L)),
                    endTime = dateFormat.format(java.util.Date(now + 45 * 60 * 1000L))
                )
                me.snhgn.schedule.reminder.FloatingWindowService.startService(this@MainActivity, testCourse)
            }
        }, "AndroidBridge")

        wv.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                progressBar?.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                progressBar?.visibility = View.GONE

                // 失败线路的错误页也会回调 onPageFinished。这里直接返回而不撤缓冲层，
                // 让 WebView 自带的报错页始终盖在缓冲层下面——故障转移期间不该把它露出来。
                val finishedUrl = url ?: view?.url
                if (finishedUrl != null && finishedUrl in erroredUrls) {
                    android.util.Log.w("MainActivity", "onPageFinished 命中失败线路 $finishedUrl，视为错误页，保留缓冲层")
                    return
                }

                dismissSplash()
                CookieManager.getInstance().flush()

                // 彻底注销旧 ServiceWorker 并清理 CacheStorage，确保页面直接拉取最新代码
                view?.evaluateJavascript("""
                    (function() {
                        if ('serviceWorker' in navigator) {
                            navigator.serviceWorker.getRegistrations().then(function(regs) {
                                for (let reg of regs) { reg.unregister(); }
                            });
                        }
                        if (window.caches) {
                            caches.keys().then(function(keys) {
                                for (let k of keys) { caches.delete(k); }
                            });
                        }
                    })();
                """.trimIndent(), null)
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                // 仅针对主页面加载失败时尝试候选故障转移线路，若所有线路均失败再显示错误重试界面
                if (request?.isForMainFrame == true) {
                    val failedUrl = request.url?.toString() ?: view?.url
                    if (failedUrl != null) erroredUrls.add(failedUrl)

                    if (currentUrlIndex + 1 < AppConfig.CANDIDATE_URLS.size) {
                        currentUrlIndex++
                        val fallbackUrl = AppConfig.CANDIDATE_URLS[currentUrlIndex]
                        android.util.Log.w(
                            "MainActivity",
                            "线路 $failedUrl 加载失败（${error?.errorCode} ${error?.description}），切换至: $fallbackUrl"
                        )
                        // 缓冲层保持盖住，并说明正在换线：这段时间用户看得见发生了什么，
                        // 而不是一段不知所以然的空白
                        setSplashStatus(
                            getString(
                                R.string.splash_switching,
                                currentUrlIndex + 1,
                                AppConfig.CANDIDATE_URLS.size,
                            )
                        )
                        view?.loadUrl(fallbackUrl)
                    } else {
                        progressBar?.visibility = View.GONE
                        // 缓冲层必须让位：否则会盖住错误卡片，用户只看到"还在加载"
                        splash?.visibility = View.GONE
                        splashDismissed = true
                        slowHintJob?.cancel()
                        webView?.visibility = View.GONE
                        layoutError?.visibility = View.VISIBLE
                    }
                }
            }

            @SuppressLint("WebViewClientOnReceivedSslError")
            override fun onReceivedSslError(
                view: WebView?,
                handler: SslErrorHandler?,
                error: SslError?
            ) {
                // 遇到合法证书直接通行，避免误拦截
                handler?.proceed()
            }
        }

        wv.webChromeClient = object : WebChromeClient() {

            /**
             * 网页里的 `<input type="file">`（设置背景的上传入口）需要宿主提供选择器，
             * WebView 自己不会弹。基类实现返回 false 且什么都不做，
             * 缺了这一段就是"点了上传毫无反应"，详见 [FileChooserBridge]。
             */
            override fun onShowFileChooser(
                view: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                val callback = filePathCallback
                    ?: run {
                        android.util.Log.w("MainActivity", "onShowFileChooser 收到空回调，忽略")
                        return false
                    }
                return fileChooser.onShowFileChooser(callback, fileChooserParams)
            }

            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                val bar = progressBar
                if (newProgress in 1..99) {
                    bar?.visibility = View.VISIBLE
                    bar?.progress = newProgress
                } else {
                    bar?.visibility = View.GONE
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        webView?.onResume()
    }

    override fun onPause() {
        super.onPause()
        webView?.onPause()
        CookieManager.getInstance().flush()
    }

    override fun onDestroy() {
        // 协程随 lifecycleScope 自动取消，这里只需停掉 View 动画，
        // 否则 onDestroy 后动画回调仍可能触碰已脱离窗口的 View
        splashFadeJob?.cancel()
        slowHintJob?.cancel()
        probeJob?.cancel()
        splash?.animate()?.cancel()
        fileChooser.dispose()
        webView?.destroy()
        webView = null
        super.onDestroy()
    }
}
