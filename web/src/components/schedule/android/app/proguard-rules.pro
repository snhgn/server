# Keep native and serialization models
-keep class me.snhgn.schedule.network.Course { *; }
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
