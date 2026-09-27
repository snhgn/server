# snhgn 极简 Android 课程 APP

本项目是专为课程网站打造的极简 Android 原生伴生客户端与独立提醒引擎。

---

## 核心设计理念

1. **前台纯净 WebView 容器**：
   - 全屏无 ActionBar 浏览体验，与网站前端完全一致（“把网站装进 APP”）。
   - 自动维护网站 Cookie 与 LocalStorage 登录凭证，支持返回键网页逐级返回，不篡改前端任何样式与交互。
2. **独立无常驻短生命周期课程提醒引擎**：
   - **平时不常驻后台**，零进程轮询、零常驻通知、零无谓唤醒。
   - **双独立 Alarm 架构**：
     - **开始 Alarm (`startTime - 5min`)**：精准唤醒广播接收器，再次向后端 API 发送 HTTP GET 请求校验课程（核验教室、临时调课、停课等），校验通过后启动短生命周期的流体云前台服务。
     - **结束 Alarm (`endTime`)**：准时唤醒广播向 Service 发送终结指令，立即移除流体云悬浮窗、停止倒计时并调用 `stopSelf()` 退出。
   - 不依赖 Service 内部长时间 Timer 保活，杜绝 ColorOS 息屏进程冻结与中途失控，下课后后台零任何活动残留。
   - 手机重启（`BOOT_COMPLETED`）后全自动恢复未来 7 天开始与结束双闹钟。

---

## 项目结构

```
android/
├── app/
│   ├── build.gradle.kts
│   ├── proguard-rules.pro
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/me/snhgn/schedule/
│       │   ├── config/
│       │   │   └── AppConfig.kt                  // 全局地址与定时参数配置
│       │   ├── network/
│       │   │   ├── ApiClient.kt                  // 原生轻量 HttpURLConnection 客户端
│       │   │   └── Course.kt                     // 课程数据实体与唯一 Key 生成
│       │   ├── permission/
│       │   │   └── PermissionHelper.kt           // 悬浮窗、精确闹钟与 ColorOS 权限辅助
│       │   ├── reminder/
│       │   │   ├── AlarmBroadcastReceiver.kt     // 课前 5 分钟唤醒与实时校验
│       │   │   ├── AlarmManagerHelper.kt         // 系统精确闹钟调度与取消
│       │   │   ├── BootReceiver.kt               // 手机开机自启恢复闹钟
│       │   │   ├── FloatingWindowService.kt      // 流体云悬浮胶囊前台服务与倒计时
│       │   │   └── ScheduleSyncManager.kt        // 课表增量同步与本地持久化缓存
│       │   └── ui/
│       │       ├── MainActivity.kt               // 全屏 WebView 容器
│       │       └── PermissionGuideActivity.kt    // 首次启动权限引导页
│       └── res/
│           ├── drawable/                         // 极简圆角胶囊与按钮资源
│           ├── layout/                           // WebView、权限引导与悬浮胶囊布局
│           └── values/                           // 统一深色主题与颜色规范
├── build.gradle.kts                              // 根工程构建脚本
├── settings.gradle.kts                           // 模块设置
├── gradle.properties
├── COLOROS_GUIDE.md                              // ColorOS 专项适配指引
└── README.md
```

---

## 导入与构建指南 (Android Studio)

1. 打开 **Android Studio** (推荐 Hedgehog 2023.1.1 或更高版本)。
2. 点击 **Open**，直接选中当前目录：`android`。
3. 等待 Gradle 同步完成（工程使用纯原生 API，无需任何复杂的 NDK 或私有仓库配置）。
4. 连接 Android 12+ 设备（推荐 OPPO / 一加设备），点击 **Run 'app'** 即可直接编译安装。

---

## 配置修改 (`AppConfig.kt`)

如需修改网页地址或 API 接口，直接编辑 `me.snhgn.schedule.config.AppConfig.kt`：

```kotlin
// 网页主地址 (WebView)
const val WEBVIEW_URL = "https://snhgn.me/schedule"

// 后端课程数据 API (GET)
const val COURSE_API_URL = "https://snhgn.me/api/course/list"

// 课前提醒提前量 (分钟，默认 5 分钟)
const val ADVANCE_REMINDER_MINUTES = 5L
```
