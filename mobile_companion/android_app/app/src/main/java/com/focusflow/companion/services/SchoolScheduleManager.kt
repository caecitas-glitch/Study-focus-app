package com.focusflow.companion.services

import android.content.Context
import android.content.SharedPreferences
import com.focusflow.companion.sync.Deadline
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

data class SchoolDayStatus(
    val scheduledMinutes: Int,
    val eventCount: Int,
    val qualifiesForAttendance: Boolean, // >= 330 minutes (5.5h)
    val hasImminentDeadline: Boolean,
    val imminentDeadlineName: String? = null,
    val daysUntilDeadline: Int = -1,
    val alreadyMarkedToday: Boolean = false,
    val errorMessage: String? = null
)

class SchoolScheduleManager(private val context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    companion object {
        private const val PREFS_NAME = "focusflow_school_prefs"
        const val KEY_SCHOOL_ICAL_URL = "key_school_ical_url"
        const val KEY_LAST_ATTENDED_DATE = "key_last_attended_school_date"
        const val KEY_CACHED_MINUTES_TODAY = "key_cached_school_minutes_today"
        const val KEY_CACHED_DATE = "key_cached_school_date"
        const val KEY_LOCAL_STREAK = "key_local_streak_count"
        const val KEY_LOCAL_LAST_STUDY_DATE = "key_local_last_study_date"

        const val MIN_HOURS_REQUIRED = 5.5
        const val MIN_MINUTES_REQUIRED = 330 // 5.5 hours = 330 minutes
        const val DEADLINE_THRESHOLD_DAYS = 5
    }

    fun getSchoolIcalUrl(): String {
        return prefs.getString(KEY_SCHOOL_ICAL_URL, "") ?: ""
    }

    fun setSchoolIcalUrl(url: String) {
        prefs.edit().putString(KEY_SCHOOL_ICAL_URL, url.trim()).apply()
    }

    fun isAlreadyMarkedToday(): Boolean {
        val lastDate = prefs.getString(KEY_LAST_ATTENDED_DATE, "") ?: ""
        val todayStr = getTodayDateStr()
        return lastDate == todayStr
    }

    fun getTodayDateStr(): String {
        return SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
    }

    /**
     * Checks if any uncompleted deadline is within 5 days.
     */
    fun checkImminentDeadlines(deadlines: List<Deadline>): Pair<Boolean, Deadline?> {
        val today = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }.timeInMillis

        var mostUrgent: Deadline? = null
        var lowestDays = Int.MAX_VALUE

        val formats = listOf(
            SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()),
            SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        )

        for (d in deadlines) {
            if (d.completed) continue
            var dueTime: Long? = null
            for (fmt in formats) {
                try {
                    val parsed = fmt.parse(d.due)
                    if (parsed != null) {
                        dueTime = parsed.time
                        break
                    }
                } catch (e: Exception) { }
            }

            if (dueTime != null) {
                val diffDays = ((dueTime - today) / (1000 * 60 * 60 * 24)).toInt()
                // If deadline is today, overdue, or within 5 days
                if (diffDays in 0..DEADLINE_THRESHOLD_DAYS || (diffDays < 0 && diffDays >= -1)) {
                    if (diffDays < lowestDays) {
                        lowestDays = diffDays
                        mostUrgent = d
                    }
                }
            }
        }

        return if (mostUrgent != null) {
            Pair(true, mostUrgent)
        } else {
            Pair(false, null)
        }
    }

    /**
     * Fetches the user's iCal feed and calculates total scheduled minutes for today.
     */
    suspend fun fetchTodaySchoolSchedule(deadlines: List<Deadline>): SchoolDayStatus = withContext(Dispatchers.IO) {
        val rawUrl = getSchoolIcalUrl()
        val alreadyMarked = isAlreadyMarkedToday()
        val (hasImminentDeadline, urgentDeadline) = checkImminentDeadlines(deadlines)

        var daysUntil = -1
        if (hasImminentDeadline && urgentDeadline != null) {
            val todayCal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 0)
                set(Calendar.MINUTE, 0)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            try {
                val parsed = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).parse(urgentDeadline.due.substring(0, 10))
                if (parsed != null) {
                    daysUntil = ((parsed.time - todayCal.timeInMillis) / (1000 * 60 * 60 * 24)).toInt().coerceAtLeast(0)
                }
            } catch (e: Exception) { }
        }

        if (rawUrl.isEmpty()) {
            return@withContext SchoolDayStatus(
                scheduledMinutes = 0,
                eventCount = 0,
                qualifiesForAttendance = false,
                hasImminentDeadline = hasImminentDeadline,
                imminentDeadlineName = urgentDeadline?.summary,
                daysUntilDeadline = daysUntil,
                alreadyMarkedToday = alreadyMarked,
                errorMessage = "No iCal URL configured"
            )
        }

        // Handle webcal:// protocol
        val url = if (rawUrl.startsWith("webcal://", ignoreCase = true)) {
            "https://" + rawUrl.substring(9)
        } else {
            rawUrl
        }

        try {
            val req = Request.Builder()
                .url(url)
                .header("User-Agent", "FocusFlow-Companion/1.1.2")
                .build()

            val resp = httpClient.newCall(req).execute()
            if (!resp.isSuccessful) {
                return@withContext SchoolDayStatus(
                    scheduledMinutes = getCachedMinutesForToday(),
                    eventCount = 0,
                    qualifiesForAttendance = getCachedMinutesForToday() >= MIN_MINUTES_REQUIRED,
                    hasImminentDeadline = hasImminentDeadline,
                    imminentDeadlineName = urgentDeadline?.summary,
                    daysUntilDeadline = daysUntil,
                    alreadyMarkedToday = alreadyMarked,
                    errorMessage = "HTTP ${resp.code} fetching schedule"
                )
            }

            val icsContent = resp.body?.string() ?: ""
            val (totalMins, count) = parseTotalSchoolMinutesForToday(icsContent)

            // Cache result for today
            saveCachedMinutesForToday(totalMins)

            return@withContext SchoolDayStatus(
                scheduledMinutes = totalMins,
                eventCount = count,
                qualifiesForAttendance = totalMins >= MIN_MINUTES_REQUIRED,
                hasImminentDeadline = hasImminentDeadline,
                imminentDeadlineName = urgentDeadline?.summary,
                daysUntilDeadline = daysUntil,
                alreadyMarkedToday = alreadyMarked,
                errorMessage = null
            )
        } catch (e: Exception) {
            val cachedMins = getCachedMinutesForToday()
            return@withContext SchoolDayStatus(
                scheduledMinutes = cachedMins,
                eventCount = 0,
                qualifiesForAttendance = cachedMins >= MIN_MINUTES_REQUIRED,
                hasImminentDeadline = hasImminentDeadline,
                imminentDeadlineName = urgentDeadline?.summary,
                daysUntilDeadline = daysUntil,
                alreadyMarkedToday = alreadyMarked,
                errorMessage = "Sync failed (${e.localizedMessage ?: "Network error"})"
            )
        }
    }

    /**
     * Parses RFC 5545 iCalendar format and computes sum of event minutes occurring on today.
     */
    fun parseTotalSchoolMinutesForToday(icsContent: String): Pair<Int, Int> {
        val todayCal = Calendar.getInstance()
        val todayYear = todayCal.get(Calendar.YEAR)
        val todayMonth = todayCal.get(Calendar.MONTH)
        val todayDay = todayCal.get(Calendar.DAY_OF_MONTH)

        var totalMinutes = 0
        var eventCount = 0

        val lines = icsContent.lines()
        var inEvent = false
        var dtStartStr: String? = null
        var dtEndStr: String? = null

        val utcFormat = SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val localFormat = SimpleDateFormat("yyyyMMdd'T'HHmmss", Locale.US).apply {
            timeZone = TimeZone.getDefault()
        }
        val dateOnlyFormat = SimpleDateFormat("yyyyMMdd", Locale.US).apply {
            timeZone = TimeZone.getDefault()
        }

        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed == "BEGIN:VEVENT") {
                inEvent = true
                dtStartStr = null
                dtEndStr = null
            } else if (trimmed == "END:VEVENT") {
                if (inEvent && dtStartStr != null && dtEndStr != null) {
                    val startDate = parseIcalDate(dtStartStr, utcFormat, localFormat, dateOnlyFormat)
                    val endDate = parseIcalDate(dtEndStr, utcFormat, localFormat, dateOnlyFormat)

                    if (startDate != null && endDate != null) {
                        val startCal = Calendar.getInstance().apply { time = startDate }
                        val isToday = startCal.get(Calendar.YEAR) == todayYear &&
                                startCal.get(Calendar.MONTH) == todayMonth &&
                                startCal.get(Calendar.DAY_OF_MONTH) == todayDay

                        if (isToday) {
                            val durationMs = endDate.time - startDate.time
                            if (durationMs > 0) {
                                val mins = (durationMs / (1000 * 60)).toInt()
                                // Cap individual events to 8 hours to avoid corrupted multi-day events
                                val safeMins = mins.coerceIn(5, 480)
                                totalMinutes += safeMins
                                eventCount++
                            }
                        }
                    }
                }
                inEvent = false
            } else if (inEvent) {
                if (trimmed.startsWith("DTSTART")) {
                    dtStartStr = trimmed.substringAfter(':')
                } else if (trimmed.startsWith("DTEND")) {
                    dtEndStr = trimmed.substringAfter(':')
                }
            }
        }

        return Pair(totalMinutes, eventCount)
    }

    private fun parseIcalDate(
        raw: String,
        utcFormat: SimpleDateFormat,
        localFormat: SimpleDateFormat,
        dateOnlyFormat: SimpleDateFormat
    ): Date? {
        val clean = raw.trim()
        return try {
            if (clean.endsWith("Z")) {
                utcFormat.parse(clean)
            } else if (clean.contains("T")) {
                localFormat.parse(clean)
            } else {
                dateOnlyFormat.parse(clean)
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun saveCachedMinutesForToday(minutes: Int) {
        prefs.edit()
            .putInt(KEY_CACHED_MINUTES_TODAY, minutes)
            .putString(KEY_CACHED_DATE, getTodayDateStr())
            .apply()
    }

    private fun getCachedMinutesForToday(): Int {
        val cachedDate = prefs.getString(KEY_CACHED_DATE, "") ?: ""
        return if (cachedDate == getTodayDateStr()) {
            prefs.getInt(KEY_CACHED_MINUTES_TODAY, 0)
        } else {
            0
        }
    }

    /**
     * Marks school attendance for today.
     * Upkeeps streak, records today's date, and ensures no fake time is added.
     */
    fun markSchoolAttended(currentStreak: Int): Int {
        val todayStr = getTodayDateStr()
        prefs.edit().putString(KEY_LAST_ATTENDED_DATE, todayStr).apply()

        val lastStudyDate = prefs.getString(KEY_LOCAL_LAST_STUDY_DATE, "") ?: ""
        var newStreak = currentStreak

        if (lastStudyDate != todayStr) {
            if (lastStudyDate.isEmpty()) {
                newStreak = 1
            } else {
                try {
                    val lastD = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).parse(lastStudyDate)
                    val todayD = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).parse(todayStr)
                    if (lastD != null && todayD != null) {
                        val cur = Calendar.getInstance().apply { time = lastD; add(Calendar.DAY_OF_YEAR, 1) }
                        var missedWeekdays = 0
                        val todayCal = Calendar.getInstance().apply { time = todayD }
                        while (cur.before(todayCal)) {
                            val dow = cur.get(Calendar.DAY_OF_WEEK)
                            if (dow != Calendar.SATURDAY && dow != Calendar.SUNDAY) {
                                missedWeekdays++
                            }
                            cur.add(Calendar.DAY_OF_YEAR, 1)
                        }

                        newStreak = if (missedWeekdays == 0 && todayD.after(lastD)) {
                            currentStreak + 1
                        } else if (missedWeekdays >= 1) {
                            1
                        } else {
                            currentStreak
                        }
                    }
                } catch (e: Exception) {
                    newStreak = currentStreak + 1
                }
            }
            prefs.edit()
                .putString(KEY_LOCAL_LAST_STUDY_DATE, todayStr)
                .putInt(KEY_LOCAL_STREAK, newStreak)
                .apply()
        }

        return newStreak
    }
}
