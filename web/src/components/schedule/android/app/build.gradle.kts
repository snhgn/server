import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ------------------------------------------------------------
// release 签名
//
// 口令与私钥都不入库：凭据放 android/keystore.properties（已 gitignore），
// 私钥放 android/keystore/release.jks（已 gitignore）。两者必须成对备份——
// 丢任何一个，之后所有版本都无法覆盖安装（Android 强制签名一致）。
//
// 缺配置时**直接失败**，不退回 debug 签名：一个被 debug key 签过的
// "release" 包会一路发出去，直到某台机器上不了更新才暴露出来，
// 那时已经无法与正式签名共存，只能卸载重来。
val keystorePropsFile = rootProject.file("keystore.properties")
val keystoreProps = Properties().apply {
    if (keystorePropsFile.exists()) {
        keystorePropsFile.inputStream().use { load(it) }
    }
}

val hasReleaseSigning = listOf("storeFile", "storePassword", "keyAlias", "keyPassword")
    .all { !keystoreProps.getProperty(it).isNullOrBlank() }

if (hasReleaseSigning && !rootProject.file(keystoreProps.getProperty("storeFile")).exists()) {
    error(
        "keystore.properties 指向的密钥文件不存在: " +
            rootProject.file(keystoreProps.getProperty("storeFile")).absolutePath
    )
}

android {
    namespace = "me.snhgn.schedule"
    compileSdk = 34

    defaultConfig {
        applicationId = "me.snhgn.schedule"
        minSdk = 31
        targetSdk = 34
        // 同版本号无法覆盖安装（INSTALL_FAILED_VERSION_DOWNGRADE），每次发布必须递增。
        // 历史：1 = 线上初版
        //      2 = 1.0.1 冷启动缓冲层
        //      3 = 1.0.2 灵动岛自唤醒修复
        //      4 = 1.0.3 启动前线路探测（修 lan/cn 不可达导致的长等待与报错页外露）
        //      5 = 1.0.4 补 WebView 文件选择器（修 App 端"设置背景"拉不起相册）
        //      6 = 1.0.5 修 <include> 覆盖根节点 id 导致的启动即崩（v2~v4 全部有此问题）
        //      7 = 1.0.6 改用 release 签名（此前所有版本都是 debug key 签的）
        //          + 修首次启动 onDestroy 访问未初始化 splash 导致的启动即崩
        versionCode = 7
        versionName = "1.0.6"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(keystoreProps.getProperty("storeFile"))
                storePassword = keystoreProps.getProperty("storePassword")
                keyAlias = keystoreProps.getProperty("keyAlias")
                keyPassword = keystoreProps.getProperty("keyPassword")
            }
        }
    }

    buildFeatures {
        // MainActivity 用 BuildConfig.DEBUG 门控 WebView 远程调试开关
        buildConfig = true
        viewBinding = true
    }

    buildTypes {
        release {
            if (!hasReleaseSigning) {
                // 用 release 关键字构建却拿不到签名配置时在这里停下，
                // 好过产出一个装不上的包。
                throw GradleException(
                    "缺少 android/keystore.properties，无法构建已签名的 release 包。\n" +
                        "参见 keystore.properties.example 生成；密钥一旦丢失将无法再发布更新。"
                )
            }
            signingConfig = signingConfigs.getByName("release")
            // 刻意不开 R8：这个包的核心是 WebView + @JavascriptInterface 桥接，
            // 混淆后 JS 侧方法名对不上，表现是功能"莫名其妙失效"而不是构建失败。
            // 真要开，必须先把 keep 规则连同真机回归一起补上。
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
