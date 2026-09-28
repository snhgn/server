package me.snhgn.schedule.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.http.SslError
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.SslErrorHandler
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import me.snhgn.schedule.R
import me.snhgn.schedule.config.AppConfig
import me.snhgn.schedule.permission.PermissionHelper
import me.snhgn.schedule.reminder.ScheduleSyncManager

/**
 * APP 主界面：纯粹、无边框、支持持久登录态的全屏 WebView 容器
 * 体验与“把课表网站装进一个 APP”一致
 */
class MainActivity : AppCompatActivity() {

    private var webView: WebView? = null
    private lateinit var progressBar: ProgressBar
    private lateinit var layoutError: View
    private lateinit var btnRetry: Button
    private var currentUrlIndex = 0

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

        // 加载课程网站（优先校园网直连，失败自动切公网兜底）
        currentUrlIndex = 0
        webView?.loadUrl(AppConfig.CANDIDATE_URLS[0])
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

        findViewById<View>(R.id.btn_open_settings).setOnClickListener {
            startActivity(Intent(this, PermissionGuideActivity::class.java))
        }

        btnRetry.setOnClickListener {
            layoutError.visibility = View.GONE
            webView?.visibility = View.VISIBLE
            currentUrlIndex = 0
            webView?.loadUrl(AppConfig.CANDIDATE_URLS[0])
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

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
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
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                progressBar.visibility = View.GONE
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
                    if (currentUrlIndex + 1 < AppConfig.CANDIDATE_URLS.size) {
                        currentUrlIndex++
                        val fallbackUrl = AppConfig.CANDIDATE_URLS[currentUrlIndex]
                        android.util.Log.w("MainActivity", "主线路加载失败，自动切换至候选线路: $fallbackUrl")
                        view?.loadUrl(fallbackUrl)
                    } else {
                        progressBar.visibility = View.GONE
                        webView?.visibility = View.GONE
                        layoutError.visibility = View.VISIBLE
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
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress in 1..99) {
                    progressBar.visibility = View.VISIBLE
                    progressBar.progress = newProgress
                } else {
                    progressBar.visibility = View.GONE
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
        webView?.destroy()
        webView = null
        super.onDestroy()
    }
}
