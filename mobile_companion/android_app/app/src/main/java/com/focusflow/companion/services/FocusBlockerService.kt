package com.focusflow.companion.services

import android.app.AppOpsManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Process
import android.provider.Settings
import android.widget.Toast
import androidx.core.app.NotificationCompat
import com.focusflow.companion.MainActivity
import com.focusflow.companion.ui.BlockerOverlayActivity
import java.util.Calendar

class FocusBlockerService : Service() {

    private lateinit var dndManager: DndManager
    private lateinit var usageLimitManager: UsageLimitManager
    private val handler = Handler(Looper.getMainLooper())

    private var isMonitoring = false
    private var isScreenOn = true

    private var isSessionActive = false
    private var isGuardActive = false
    private var currentSubject: String = "#Focus"
    private var remainingSeconds: Long = 0
    private var lastActionTimestamp: Long = 0
    private var lastBedtimeAlertTimestamp: Long = 0
    private var lastBedtimeAlertPkg: String = ""

    private var lastForegroundPackage: String? = null
    private var activeMonitoredPackage: String? = null
    private val packageSessionStartTimes = mutableMapOf<String, Long>()
    private val packageLastExitTimes = mutableMapOf<String, Long>()

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_OFF -> {
                    // Screen turned dark / phone in pocket or nightstand
                    isScreenOn = false
                    if (activeMonitoredPackage != null) {
                        val now = System.currentTimeMillis()
                        usageLimitManager.setPackageLastActiveTime(activeMonitoredPackage!!, now)
                        packageLastExitTimes[activeMonitoredPackage!!] = now
                        activeMonitoredPackage = null
                    }
                }
                Intent.ACTION_SCREEN_ON -> {
                    // Screen turned on
                    isScreenOn = true
                    if (isMonitoring) {
                        handler.removeCallbacksAndMessages(null)
                        handler.post(checkRunnable)
                    }
                }
            }
        }
    }

    private val checkRunnable = object : Runnable {
        override fun run() {
            if (!isMonitoring) return

            // If screen is dark/off, do NOT reschedule: CPU sleeps peacefully in Doze mode
            if (!isScreenOn) return

            if (isSessionActive && remainingSeconds > 0) {
                remainingSeconds--
            }

            val currentPkg = getForegroundAppPackage()
            val now = System.currentTimeMillis()

            if (currentPkg != null && currentPkg != packageName) {
                val hasExtension = usageLimitManager.isPackageExtensionActive(currentPkg)
                val isLeisure = usageLimitManager.isLeisureModeActive()

                // If this package currently has an active extension, keep its timer fresh
                if (hasExtension) {
                    usageLimitManager.resetPackageSessionElapsed(currentPkg)
                    usageLimitManager.setPackageLastActiveTime(currentPkg, now)
                    packageSessionStartTimes[currentPkg] = now
                    packageLastExitTimes[currentPkg] = 0L
                }

                // 1. Check Late-Night Wind-Down Warning (e.g. Gemini after 9:00 PM)
                if (isLateNightHour() && usageLimitManager.isLateNightAlertEnabled(currentPkg)) {
                    if (!usageLimitManager.isBedtimeSnoozed() && !hasExtension && !isLeisure) {
                        if (now - lastActionTimestamp > 2500) {
                            lastActionTimestamp = now
                            showLateNightBedtimeAlert(currentPkg)
                            // If bedtime alert was just triggered, avoid double-firing session limit in same tick
                            return
                        }
                    }
                }

                // 2. Active Study Session Blocking
                if (isSessionActive && usageLimitManager.isStudyBlocked(currentPkg)) {
                    if (!hasExtension && !isLeisure && (now - lastActionTimestamp > 2500)) {
                        lastActionTimestamp = now
                        forceCloseAndExplain(currentPkg, BlockerOverlayActivity.REASON_STUDY_SESSION)
                    }
                } else if (!hasExtension && !isLeisure) {
                    // 3. Per-Session Continuous Usage Limit Check (e.g. 1m, 15m, 20m, 30m sitting limit)
                    val sessionLimit = usageLimitManager.getSessionLimitForPackage(currentPkg)
                    if (sessionLimit > 0) {
                        val lastActive = usageLimitManager.getPackageLastActiveTime(currentPkg)
                        val cooldownMs = UsageLimitManager.SESSION_COOLDOWN_MINUTES * 60 * 1000L

                        if (lastActive == 0L || (now - lastActive > cooldownMs)) {
                            // User took a full break (or first launch) -> reset to fresh session
                            usageLimitManager.resetPackageSessionElapsed(currentPkg)
                            packageSessionStartTimes[currentPkg] = now
                        } else if (activeMonitoredPackage == currentPkg) {
                            // Active continuous usage in currentPkg: add elapsed delta
                            val deltaMs = (now - lastActive).coerceIn(0L, 5000L)
                            usageLimitManager.addPackageSessionElapsedMs(currentPkg, deltaMs)
                        }
                        // Update last active time for currentPkg
                        usageLimitManager.setPackageLastActiveTime(currentPkg, now)

                        val bonusMinutes = usageLimitManager.getBonusMinutesForToday(currentPkg)
                        val totalAllowedMins = sessionLimit + bonusMinutes
                        val totalAllowedSec = totalAllowedMins * 60L
                        val elapsedSec = usageLimitManager.getPackageSessionElapsed(currentPkg)

                        if (elapsedSec >= totalAllowedSec) {
                            if (now - lastActionTimestamp > 2500) {
                                lastActionTimestamp = now
                                forceCloseAndExplain(currentPkg, BlockerOverlayActivity.REASON_SESSION_LIMIT)
                            }
                        }
                    }
                }

                if (activeMonitoredPackage != null && activeMonitoredPackage != currentPkg) {
                    usageLimitManager.setPackageLastActiveTime(activeMonitoredPackage!!, now)
                    packageLastExitTimes[activeMonitoredPackage!!] = now
                }
                activeMonitoredPackage = currentPkg
            } else {
                if (activeMonitoredPackage != null) {
                    usageLimitManager.setPackageLastActiveTime(activeMonitoredPackage!!, now)
                    packageLastExitTimes[activeMonitoredPackage!!] = now
                    activeMonitoredPackage = null
                }
            }

            // Adaptive polling rate: 1.5s during active study session, 2.0s in guardian mode for responsiveness
            val intervalMs = if (isSessionActive) 1500L else 2000L
            handler.postDelayed(this, intervalMs)
        }
    }

    override fun onCreate() {
        super.onCreate()
        dndManager = DndManager(this)
        usageLimitManager = UsageLimitManager(this)
        createNotificationChannels()

        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_SCREEN_OFF)
        }
        registerReceiver(screenReceiver, filter)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: ACTION_START_GUARD

        when (action) {
            ACTION_START -> {
                isSessionActive = true
                isGuardActive = false
                currentSubject = intent?.getStringExtra(EXTRA_SUBJECT) ?: "#Focus"
                remainingSeconds = intent?.getLongExtra(EXTRA_REMAINING_SEC, 1800L) ?: 1800L

                startForegroundCompat(NOTIFICATION_ID, buildForegroundNotification())
                dndManager.muteNotifications()
                startAppMonitoring()
            }
            ACTION_UPDATE_TIMER -> {
                remainingSeconds = intent?.getLongExtra(EXTRA_REMAINING_SEC, remainingSeconds) ?: remainingSeconds
                if (isSessionActive) {
                    val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    nm.notify(NOTIFICATION_ID, buildForegroundNotification())
                }
            }
            ACTION_START_GUARD -> {
                // Low power silent guardian mode (app limits & bedtime outside study session)
                val prefs = getSharedPreferences("focusflow_prefs", Context.MODE_PRIVATE)
                val isGuardianEnabled = prefs.getBoolean("key_guardian_enabled", true)
                if (!isSessionActive && isGuardianEnabled) {
                    isGuardActive = true
                    startForegroundCompat(NOTIFICATION_ID, buildGuardNotification())
                    startAppMonitoring()
                } else if (!isGuardianEnabled && !isSessionActive) {
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                }
            }
            ACTION_STOP -> {
                isSessionActive = false
                dndManager.restoreNotifications()

                val prefs = getSharedPreferences("focusflow_prefs", Context.MODE_PRIVATE)
                val isGuardianEnabled = prefs.getBoolean("key_guardian_enabled", true)
                if (isGuardianEnabled) {
                    isGuardActive = true
                    val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    nm.notify(NOTIFICATION_ID, buildGuardNotification())
                } else {
                    isGuardActive = false
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                }
            }
            ACTION_STOP_ALL -> {
                isSessionActive = false
                isGuardActive = false
                val prefs = getSharedPreferences("focusflow_prefs", Context.MODE_PRIVATE)
                prefs.edit().putBoolean("key_guardian_enabled", false).apply()
                dndManager.restoreNotifications()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
            ACTION_EXTEND_SESSION -> {
                val pkg = intent?.getStringExtra(EXTRA_RAW_PACKAGE)
                if (!pkg.isNullOrEmpty()) {
                    val now = System.currentTimeMillis()
                    usageLimitManager.resetPackageSessionElapsed(pkg)
                    usageLimitManager.setPackageLastActiveTime(pkg, now)
                    packageSessionStartTimes[pkg] = now
                    packageLastExitTimes[pkg] = 0L
                    activeMonitoredPackage = null
                    lastActionTimestamp = now
                }
            }
        }

        return START_STICKY
    }

    private fun startForegroundCompat(notificationId: Int, notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            try {
                startForeground(
                    notificationId,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                )
            } catch (e: Exception) {
                startForeground(notificationId, notification)
            }
        } else {
            startForeground(notificationId, notification)
        }
    }

    private fun startAppMonitoring() {
        if (isMonitoring) return
        isMonitoring = true
        isScreenOn = true
        handler.removeCallbacksAndMessages(null)
        handler.post(checkRunnable)
    }

    private fun isLateNightHour(): Boolean {
        if (usageLimitManager.isBedtimeTestingActive()) return true
        val cal = Calendar.getInstance()
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        // 9:00 PM (21:00) until 05:00 AM
        return hour >= 21 || hour < 5
    }

    private fun showLateNightBedtimeAlert(pkg: String) {
        val appName = formatPackageName(pkg)

        // Clear active monitored package and record exit
        packageLastExitTimes[pkg] = System.currentTimeMillis()
        activeMonitoredPackage = null

        // Android 14 (API 34) requires explicit opt-in for background activity launches
        val options = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            android.app.ActivityOptions.makeBasic().apply {
                setPendingIntentBackgroundActivityStartMode(
                    android.app.ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
                )
            }.toBundle()
        } else {
            android.app.ActivityOptions.makeBasic().toBundle()
        }

        val overlayIntent = Intent(this, BlockerOverlayActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            putExtra(BlockerOverlayActivity.EXTRA_RAW_PACKAGE, pkg)
            putExtra(BlockerOverlayActivity.EXTRA_PACKAGE_NAME, appName)
            putExtra(BlockerOverlayActivity.EXTRA_REASON, BlockerOverlayActivity.REASON_BEDTIME)
        }

        val pendingOverlay = PendingIntent.getActivity(
            this,
            (System.currentTimeMillis() % 10000).toInt(),
            overlayIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        var overlayLaunched = false
        try {
            startActivity(overlayIntent, options)
            overlayLaunched = true
        } catch (e: Exception) {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    pendingOverlay.send(options)
                } else {
                    pendingOverlay.send()
                }
                overlayLaunched = true
            } catch (e2: Exception) { }
        }

        // If overlay couldn't launch directly, bounce user to Home Screen
        if (!overlayLaunched) {
            val homeIntent = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            try {
                startActivity(homeIntent, options)
            } catch (e: Exception) { }
        }

        // High-priority full screen intent notification (guarantees display on Android 10-14)
        val title = "🌙 Past 9:00 PM: Time for Bed!"
        val message = "FocusFlow closed $appName. Step away, protect your sleep, and recharge."

        val notification = NotificationCompat.Builder(this, CHANNEL_BEDTIME)
            .setContentTitle(title)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText("FocusFlow closed $appName because it's past 9:00 PM. Put your phone away, protect your sleep schedule, and recharge!"))
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setFullScreenIntent(pendingOverlay, true)
            .setAutoCancel(true)
            .setContentIntent(pendingOverlay)
            .setDefaults(Notification.DEFAULT_ALL)
            .build()

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_BEDTIME_ID, notification)

        handler.post {
            Toast.makeText(applicationContext, "🌙 Past 9 PM! FocusFlow closed $appName for sleep.", Toast.LENGTH_LONG).show()
        }
    }

    /**
     * Actively closes the distracting app by bouncing user to Home and showing overlay.
     */
    private fun forceCloseAndExplain(pkg: String, reason: String) {
        val appName = formatPackageName(pkg)

        // Clear active monitored package and record exit
        val now = System.currentTimeMillis()
        usageLimitManager.setPackageLastActiveTime(pkg, now)
        packageLastExitTimes[pkg] = now
        activeMonitoredPackage = null

        val explanation = when (reason) {
            BlockerOverlayActivity.REASON_SESSION_LIMIT -> {
                val limit = usageLimitManager.getSessionLimitForPackage(pkg)
                "FocusFlow closed $appName: Session limit of ${limit}m reached. Take a 15-minute break!"
            }
            BlockerOverlayActivity.REASON_DAILY_LIMIT -> {
                val limit = usageLimitManager.getLimitForPackage(pkg)
                "FocusFlow closed $appName: Limit of ${limit}m reached. Take a 15-minute break!"
            }
            else -> {
                val mins = remainingSeconds / 60
                "FocusFlow closed $appName: Study session active for $currentSubject (${mins}m left)."
            }
        }

        handler.post {
            Toast.makeText(applicationContext, "⚠️ $explanation", Toast.LENGTH_LONG).show()
        }

        val options = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            android.app.ActivityOptions.makeBasic().apply {
                setPendingIntentBackgroundActivityStartMode(
                    android.app.ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED
                )
            }.toBundle()
        } else {
            android.app.ActivityOptions.makeBasic().toBundle()
        }

        val overlayIntent = Intent(this, BlockerOverlayActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                    Intent.FLAG_ACTIVITY_REORDER_TO_FRONT
            putExtra(BlockerOverlayActivity.EXTRA_RAW_PACKAGE, pkg)
            putExtra(BlockerOverlayActivity.EXTRA_PACKAGE_NAME, appName)
            putExtra(BlockerOverlayActivity.EXTRA_REASON, reason)
            putExtra(BlockerOverlayActivity.EXTRA_SUBJECT, currentSubject)
            putExtra(BlockerOverlayActivity.EXTRA_REMAINING_SEC, remainingSeconds)
            putExtra(BlockerOverlayActivity.EXTRA_LIMIT_MINS, usageLimitManager.getSessionLimitForPackage(pkg))
        }

        val pendingOverlay = PendingIntent.getActivity(
            this,
            (System.currentTimeMillis() % 10000).toInt(),
            overlayIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        var overlayLaunched = false
        try {
            startActivity(overlayIntent, options)
            overlayLaunched = true
        } catch (e: Exception) {
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    pendingOverlay.send(options)
                } else {
                    pendingOverlay.send()
                }
                overlayLaunched = true
            } catch (e2: Exception) { }
        }

        if (!overlayLaunched) {
            val homeIntent = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            try {
                startActivity(homeIntent, options)
            } catch (e: Exception) { }
        }

        postClosureNotification(appName, explanation, pendingOverlay)
    }

    private fun postClosureNotification(appName: String, text: String, pendingOverlay: PendingIntent? = null) {
        val openIntent = Intent(this, MainActivity::class.java)
        val defaultPendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val targetPending = pendingOverlay ?: defaultPendingIntent

        val notificationBuilder = NotificationCompat.Builder(this, CHANNEL_ALERTS)
            .setContentTitle("FocusFlow Closed $appName")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(targetPending)

        if (pendingOverlay != null) {
            notificationBuilder.setFullScreenIntent(pendingOverlay, true)
        }

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ALERT_ID, notificationBuilder.build())
    }

    /**
     * Stably detects the currently foreground package.
     * Looks back over recent events so watching a video without touch navigation doesn't drop detection.
     */
    private fun getForegroundAppPackage(): String? {
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager ?: return lastForegroundPackage
        val now = System.currentTimeMillis()

        // Query events from the last 15 minutes to find the most recently resumed activity
        try {
            val events = usm.queryEvents(now - 15 * 60 * 1000L, now)
            if (events != null) {
                val event = UsageEvents.Event()
                var latestResumedPkg: String? = null
                var latestResumedTime = 0L

                while (events.hasNextEvent()) {
                    events.getNextEvent(event)
                    if (event.eventType == UsageEvents.Event.ACTIVITY_RESUMED) {
                        if (event.timeStamp >= latestResumedTime) {
                            latestResumedTime = event.timeStamp
                            latestResumedPkg = event.packageName
                        }
                    }
                }
                if (latestResumedPkg != null) {
                    lastForegroundPackage = latestResumedPkg
                    return lastForegroundPackage
                }
            }
        } catch (e: Exception) { }

        // Secondary fallback using queryUsageStats
        try {
            val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_BEST, now - 10_000L, now)
            if (!stats.isNullOrEmpty()) {
                val topApp = stats.maxByOrNull { it.lastTimeUsed }
                if (topApp != null && (now - topApp.lastTimeUsed) < 10_000L) {
                    lastForegroundPackage = topApp.packageName
                }
            }
        } catch (e: Exception) { }

        return lastForegroundPackage
    }

    private fun formatPackageName(pkg: String): String {
        return usageLimitManager.getRuleForPackage(pkg).displayName
    }

    private fun buildForegroundNotification(): Notification {
        val mins = remainingSeconds / 60
        val secs = remainingSeconds % 60
        val timeStr = String.format("%02d:%02d", mins, secs)

        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_SESSION)
            .setContentTitle("FocusFlow Study Session Active")
            .setContentText("$timeStr remaining • $currentSubject (Alerts Muted & Apps Blocked)")
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun buildGuardNotification(): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Action: Hide notification from status bar via OS channel settings
        val hideSettingsIntent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).apply {
                putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
                putExtra(Settings.EXTRA_CHANNEL_ID, CHANNEL_GUARDIAN)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        } else {
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:$packageName")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        }
        val hidePendingIntent = PendingIntent.getActivity(
            this, 11, hideSettingsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_GUARDIAN)
            .setContentTitle("FocusFlow Silent Guardian")
            .setContentText("Limits & 9:00 PM lock active silently")
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setShowWhen(false)
            .addAction(android.R.drawable.ic_menu_preferences, "Hide Icon", hidePendingIntent)
            .build()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java) ?: return

            // Clean up old cached channels so OS doesn't use old noisy priorities
            try {
                nm.deleteNotificationChannel("focusflow_guardian")
                nm.deleteNotificationChannel("focusflow_guardian_v2")
            } catch (e: Exception) { }

            val sessionChannel = NotificationChannel(
                CHANNEL_SESSION,
                "FocusFlow Active Session",
                NotificationManager.IMPORTANCE_LOW
            )
            val guardianChannel = NotificationChannel(
                CHANNEL_GUARDIAN,
                "Background Guardian (Silent)",
                NotificationManager.IMPORTANCE_MIN
            ).apply {
                description = "Silent background guardian that enforces app limits without cluttering status bar"
                setShowBadge(false)
                enableLights(false)
                enableVibration(false)
                setSound(null, null)
                lockscreenVisibility = Notification.VISIBILITY_SECRET
            }
            val alertChannel = NotificationChannel(
                CHANNEL_ALERTS,
                "FocusFlow App Closures & Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifies when a distracting app is closed by FocusFlow"
            }
            val bedtimeChannel = NotificationChannel(
                CHANNEL_BEDTIME,
                "FocusFlow Bedtime & Wind-Down Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifies when late-night apps (like Gemini) are used past 9:00 PM"
                enableVibration(true)
            }

            nm.createNotificationChannel(sessionChannel)
            nm.createNotificationChannel(guardianChannel)
            nm.createNotificationChannel(alertChannel)
            nm.createNotificationChannel(bedtimeChannel)
        }
    }

    override fun onDestroy() {
        isMonitoring = false
        handler.removeCallbacksAndMessages(null)
        try {
            unregisterReceiver(screenReceiver)
        } catch (e: Exception) { }
        dndManager.restoreNotifications()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val CHANNEL_SESSION = "focusflow_active_session"
        const val CHANNEL_GUARDIAN = "focusflow_guardian_v3"
        const val CHANNEL_ALERTS = "focusflow_app_closure_alerts"
        const val CHANNEL_BEDTIME = "focusflow_bedtime_alerts"

        const val NOTIFICATION_ID = 101
        const val NOTIFICATION_ALERT_ID = 102
        const val NOTIFICATION_BEDTIME_ID = 103

        const val ACTION_START = "com.focusflow.action.START"
        const val ACTION_STOP = "com.focusflow.action.STOP"
        const val ACTION_START_GUARD = "com.focusflow.action.START_GUARD"
        const val ACTION_STOP_ALL = "com.focusflow.action.STOP_ALL"
        const val ACTION_UPDATE_TIMER = "com.focusflow.action.UPDATE_TIMER"
        const val ACTION_EXTEND_SESSION = "com.focusflow.action.EXTEND_SESSION"

        const val EXTRA_SUBJECT = "extra_subject"
        const val EXTRA_REMAINING_SEC = "extra_remaining_sec"
        const val EXTRA_RAW_PACKAGE = "extra_raw_package"
        const val EXTRA_EXTENSION_MINUTES = "extra_extension_minutes"

        private const val BEDTIME_THROTTLE_MS = 300_000L // 5 minutes between bedtime warnings

        fun hasUsageStatsPermission(context: Context): Boolean {
            val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
            val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                appOps.unsafeCheckOpNoThrow(
                    AppOpsManager.OPSTR_GET_USAGE_STATS,
                    Process.myUid(),
                    context.packageName
                )
            } else {
                appOps.checkOpNoThrow(
                    AppOpsManager.OPSTR_GET_USAGE_STATS,
                    Process.myUid(),
                    context.packageName
                )
            }
            return mode == AppOpsManager.MODE_ALLOWED
        }

        fun hasOverlayPermission(context: Context): Boolean {
            return Settings.canDrawOverlays(context)
        }
    }
}
