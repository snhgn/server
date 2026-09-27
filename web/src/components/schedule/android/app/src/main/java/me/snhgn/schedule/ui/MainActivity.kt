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

        // 加载课程网站
        webView?.loadUrl(AppConfig.WEBVIEW_URL)
    }

    private fun setupImmersiveWindow() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller.isAppearanceLightStatusBars = false
    }

    private fun initViews() {
        webView = findViewById(R.id.web_view)
        progressBar = findViewById(R.id.progress_bar)
        layoutError = findViewById(R.id.layout_error)
        btnRetry = findViewById(R.id.btn_retry)

        btnRetry.setOnClickListener {
            layoutError.visibility = View.GONE
            webView?.visibility = View.VISIBLE
            webView?.reload()
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
            cacheMode = WebSettings.LOAD_DEFAULT // 不强制清除 Cache，维持网站正常速度与缓存
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

        wv.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                progressBar.visibility = View.GONE
                // 页面加载完成后持久化刷入 Cookie，防止闪退或划掉时丢失登录 Session
                CookieManager.getInstance().flush()
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                // 仅针对主页面加载失败显示错误提示
                if (request?.isForMainFrame == true) {
                    progressBar.visibility = View.GONE
                    webView?.visibility = View.GONE
                    layoutError.visibility = View.VISIBLE
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
