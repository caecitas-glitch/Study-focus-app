package com.focusflow.companion.workers

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.focusflow.companion.MainActivity
import java.util.Calendar

class DailyReminderReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            // Reschedule morning quotes and 9:00 PM bedtime lock after phone reboot
            scheduleDailyAlarm(context, DEFAULT_REMINDER_HOUR, DEFAULT_REMINDER_MINUTE)
            scheduleBedtimeAlarm(context, BEDTIME_HOUR, BEDTIME_MINUTE)

            // Auto-start background guardian service if enabled and permissions granted
            val prefs = context.getSharedPreferences("focusflow_prefs", Context.MODE_PRIVATE)
            val isGuardianEnabled = prefs.getBoolean("key_guardian_enabled", true)
            if (isGuardianEnabled && com.focusflow.companion.services.FocusBlockerService.hasUsageStatsPermission(context)) {
                val serviceIntent = Intent(context, com.focusflow.companion.services.FocusBlockerService::class.java).apply {
                    action = com.focusflow.companion.services.FocusBlockerService.ACTION_START_GUARD
                }
                try {
                    androidx.core.content.ContextCompat.startForegroundService(context, serviceIntent)
                } catch (e: Exception) { }
            }
            return
        }

        if (intent.action == ACTION_BEDTIME_REMINDER) {
            // 9:00 PM Bedtime alarm triggered
            showBedtimeReminderNotification(context)

            // Ensure FocusBlockerService is awake and actively enforcing the bedtime lock
            val serviceIntent = Intent(context, com.focusflow.companion.services.FocusBlockerService::class.java).apply {
                action = com.focusflow.companion.services.FocusBlockerService.ACTION_START_GUARD
            }
            try {
                androidx.core.content.ContextCompat.startForegroundService(context, serviceIntent)
            } catch (e: Exception) { }

            // Reschedule next night's 9:00 PM alarm
            scheduleBedtimeAlarm(context, BEDTIME_HOUR, BEDTIME_MINUTE)
            return
        }

        showDailyQuoteNotification(context)
        // Ensure next day's alarm is scheduled for 7:00 AM
        scheduleDailyAlarm(context, DEFAULT_REMINDER_HOUR, DEFAULT_REMINDER_MINUTE)
    }

    companion object {
        const val CHANNEL_ID = "focusflow_daily_quotes"
        const val NOTIFICATION_ID = 202
        const val ACTION_DAILY_REMINDER = "com.focusflow.companion.ACTION_DAILY_REMINDER"

        const val BEDTIME_CHANNEL_ID = "focusflow_bedtime_daily"
        const val BEDTIME_NOTIFICATION_ID = 203
        const val ACTION_BEDTIME_REMINDER = "com.focusflow.companion.ACTION_BEDTIME_REMINDER"

        const val DEFAULT_REMINDER_HOUR = 7
        const val DEFAULT_REMINDER_MINUTE = 0

        const val BEDTIME_HOUR = 21
        const val BEDTIME_MINUTE = 0

        fun scheduleDailyAlarm(context: Context, hour: Int = DEFAULT_REMINDER_HOUR, minute: Int = DEFAULT_REMINDER_MINUTE) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val intent = Intent(context, DailyReminderReceiver::class.java).apply {
                action = ACTION_DAILY_REMINDER
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val calendar = Calendar.getInstance().apply {
                timeInMillis = System.currentTimeMillis()
                set(Calendar.HOUR_OF_DAY, hour)
                set(Calendar.MINUTE, minute)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
                if (before(Calendar.getInstance())) {
                    add(Calendar.DAY_OF_YEAR, 1)
                }
            }

            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        calendar.timeInMillis,
                        pendingIntent
                    )
                } else {
                    alarmManager.setRepeating(
                        AlarmManager.RTC_WAKEUP,
                        calendar.timeInMillis,
                        AlarmManager.INTERVAL_DAY,
                        pendingIntent
                    )
                }
            } catch (e: SecurityException) {
                // If exact alarm permission is restricted on Android 12+, fallback to inexact
                alarmManager.set(
                    AlarmManager.RTC_WAKEUP,
                    calendar.timeInMillis,
                    pendingIntent
                )
            }
        }

        fun showDailyQuoteNotification(context: Context) {
            createNotificationChannel(context)

            val (quote, author) = QuoteBank.getRandomQuote()

            val openIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            val pendingIntent = PendingIntent.getActivity(
                context, 0, openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val notification = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("FocusFlow • Morning Fuel ⚡")
                .setContentText("\"$quote\" — $author")
                .setStyle(NotificationCompat.BigTextStyle().bigText("\"$quote\"\n\n— $author\n\nRise and grind. Conquer today."))
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .build()

            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIFICATION_ID, notification)
        }

        private fun createNotificationChannel(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val channel = NotificationChannel(
                    CHANNEL_ID,
                    "Daily Morning Fuel (7 AM)",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Daily 7:00 AM motivational fuel and quotes to conquer the day"
                }
                val nm = context.getSystemService(NotificationManager::class.java)
                nm.createNotificationChannel(channel)
            }
        }

        fun scheduleBedtimeAlarm(context: Context, hour: Int = BEDTIME_HOUR, minute: Int = BEDTIME_MINUTE) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val intent = Intent(context, DailyReminderReceiver::class.java).apply {
                action = ACTION_BEDTIME_REMINDER
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context, 1, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val calendar = Calendar.getInstance().apply {
                timeInMillis = System.currentTimeMillis()
                set(Calendar.HOUR_OF_DAY, hour)
                set(Calendar.MINUTE, minute)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
                if (before(Calendar.getInstance())) {
                    add(Calendar.DAY_OF_YEAR, 1)
                }
            }

            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    alarmManager.setExactAndAllowWhileIdle(
                        AlarmManager.RTC_WAKEUP,
                        calendar.timeInMillis,
                        pendingIntent
                    )
                } else {
                    alarmManager.setRepeating(
                        AlarmManager.RTC_WAKEUP,
                        calendar.timeInMillis,
                        AlarmManager.INTERVAL_DAY,
                        pendingIntent
                    )
                }
            } catch (e: SecurityException) {
                alarmManager.set(
                    AlarmManager.RTC_WAKEUP,
                    calendar.timeInMillis,
                    pendingIntent
                )
            }
        }

        fun showBedtimeReminderNotification(context: Context) {
            createBedtimeNotificationChannel(context)

            val openIntent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            val pendingIntent = PendingIntent.getActivity(
                context, 2, openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val notification = NotificationCompat.Builder(context, BEDTIME_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
                .setContentTitle("🌙 9:00 PM Bedtime Wind-Down")
                .setContentText("Put distracting apps away and recharge for tomorrow.")
                .setStyle(NotificationCompat.BigTextStyle().bigText("It's 9:00 PM! FocusFlow bedtime protection is now active. Gemini, video streams, and addictive apps will be closed so you get great sleep and wake up refreshed."))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .build()

            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(BEDTIME_NOTIFICATION_ID, notification)
        }

        private fun createBedtimeNotificationChannel(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val channel = NotificationChannel(
                    BEDTIME_CHANNEL_ID,
                    "Bedtime Wind-Down (9 PM)",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Daily 9:00 PM bedtime notification to wrap up screen time"
                }
                val nm = context.getSystemService(NotificationManager::class.java)
                nm.createNotificationChannel(channel)
            }
        }
    }
}
