plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
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
        versionCode = 6
        versionName = "1.0.5"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        // MainActivity 用 BuildConfig.DEBUG 门控 WebView 远程调试开关
        buildConfig = true
    }
    buildTypes {
        release {
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
    buildFeatures {
        viewBinding = true
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
