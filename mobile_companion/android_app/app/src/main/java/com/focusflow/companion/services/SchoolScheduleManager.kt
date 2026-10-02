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
    val lunchIncluded: Boolean = false,
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
        const val KEY_CACHED_COUNT_TODAY = "key_cached_school_count_today"
        const val KEY_CACHED_LUNCH_TODAY = "key_cached_school_lunch_today"
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
                lunchIncluded = false,
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
                val cachedMins = getCachedMinutesForToday()
                return@withContext SchoolDayStatus(
                    scheduledMinutes = cachedMins,
                    eventCount = getCachedCountForToday(),
                    qualifiesForAttendance = cachedMins >= MIN_MINUTES_REQUIRED,
                    hasImminentDeadline = hasImminentDeadline,
                    imminentDeadlineName = urgentDeadline?.summary,
                    daysUntilDeadline = daysUntil,
                    alreadyMarkedToday = alreadyMarked,
                    lunchIncluded = getCachedLunchForToday(),
                    errorMessage = "HTTP ${resp.code} fetching schedule"
                )
            }

            val icsContent = resp.body?.string() ?: ""
            val (totalMins, count, lunchIncluded) = parseTotalSchoolMinutesForToday(icsContent)

            // Cache result for today
            saveCachedMinutesForToday(totalMins, count, lunchIncluded)

            return@withContext SchoolDayStatus(
                scheduledMinutes = totalMins,
                eventCount = count,
                qualifiesForAttendance = totalMins >= MIN_MINUTES_REQUIRED,
                hasImminentDeadline = hasImminentDeadline,
                imminentDeadlineName = urgentDeadline?.summary,
                daysUntilDeadline = daysUntil,
                alreadyMarkedToday = alreadyMarked,
                lunchIncluded = lunchIncluded,
                errorMessage = null
            )
        } catch (e: Exception) {
            val cachedMins = getCachedMinutesForToday()
            return@withContext SchoolDayStatus(
                scheduledMinutes = cachedMins,
                eventCount = getCachedCountForToday(),
                qualifiesForAttendance = cachedMins >= MIN_MINUTES_REQUIRED,
                hasImminentDeadline = hasImminentDeadline,
                imminentDeadlineName = urgentDeadline?.summary,
                daysUntilDeadline = daysUntil,
                alreadyMarkedToday = alreadyMarked,
                lunchIncluded = getCachedLunchForToday(),
                errorMessage = "Sync failed (${e.localizedMessage ?: "Network error"})"
            )
        }
    }

    /**
     * Parses RFC 5545 iCalendar format and computes sum of event minutes occurring on today.
     * Incorporates university lunch (11:30 - 12:30, 60 minutes) if classes exist today,
     * merging overlapping intervals so no minutes are double counted.
     */
    fun parseTotalSchoolMinutesForToday(icsContent: String): Triple<Int, Int, Boolean> {
        val todayStartCal = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val todayEndCal = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 23)
            set(Calendar.MINUTE, 59)
            set(Calendar.SECOND, 59)
            set(Calendar.MILLISECOND, 999)
        }
        val todayStartMs = todayStartCal.timeInMillis
        val todayEndMs = todayEndCal.timeInMillis

        // Unfold RFC 5545 folded lines (lines starting with space or tab continue previous line)
        val unfoldedLines = mutableListOf<String>()
        for (rawLine in icsContent.lines()) {
            if ((rawLine.startsWith(" ") || rawLine.startsWith("\t")) && unfoldedLines.isNotEmpty()) {
                unfoldedLines[unfoldedLines.size - 1] = unfoldedLines.last() + rawLine.substring(1)
            } else {
                unfoldedLines.add(rawLine)
            }
        }

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

        val rawIntervals = mutableListOf<Pair<Long, Long>>()
        var classEventCount = 0

        for (line in unfoldedLines) {
            val trimmed = line.trim()
            if (trimmed == "BEGIN:VEVENT") {
                inEvent = true
                dtStartStr = null
                dtEndStr = null
            } else if (trimmed == "END:VEVENT") {
                if (inEvent && dtStartStr != null && dtEndStr != null) {
                    val startDate = parseIcalDate(dtStartStr, utcFormat, localFormat, dateOnlyFormat)
                    val endDate = parseIcalDate(dtEndStr, utcFormat, localFormat, dateOnlyFormat)

                    if (startDate != null && endDate != null && endDate.time > startDate.time) {
                        // Check if event intersects today
                        if (startDate.time <= todayEndMs && endDate.time >= todayStartMs) {
                            val eventStart = maxOf(startDate.time, todayStartMs)
                            val eventEnd = minOf(endDate.time, todayEndMs)
                            val durationMins = ((eventEnd - eventStart) / (1000 * 60)).toInt()

                            // Accept valid class sessions (between 10m and 8h to ignore corrupt all-day banners)
                            if (durationMins in 10..480) {
                                rawIntervals.add(Pair(eventStart, eventEnd))
                                classEventCount++
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

        // If the user has classes scheduled today, include university lunch (11:30 - 12:30, 60 minutes).
        // Attended even if there's a gap before/after classes, but only on days with school.
        val lunchIncluded = classEventCount > 0
        if (lunchIncluded) {
            val lunchStartCal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 11)
                set(Calendar.MINUTE, 30)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val lunchEndCal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, 12)
                set(Calendar.MINUTE, 30)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            rawIntervals.add(Pair(lunchStartCal.timeInMillis, lunchEndCal.timeInMillis))
        }

        // Merge overlapping or adjacent intervals so no minutes are double counted
        rawIntervals.sortBy { it.first }
        val mergedIntervals = mutableListOf<Pair<Long, Long>>()
        for (interval in rawIntervals) {
            if (mergedIntervals.isEmpty()) {
                mergedIntervals.add(interval)
            } else {
                val last = mergedIntervals.last()
                if (interval.first <= last.second) {
                    mergedIntervals[mergedIntervals.size - 1] = Pair(last.first, maxOf(last.second, interval.second))
                } else {
                    mergedIntervals.add(interval)
                }
            }
        }

        var totalMinutes = 0
        for (interval in mergedIntervals) {
            totalMinutes += ((interval.second - interval.first) / (1000 * 60)).toInt()
        }

        return Triple(totalMinutes, classEventCount, lunchIncluded)
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

    private fun saveCachedMinutesForToday(minutes: Int, count: Int, lunchIncluded: Boolean) {
        prefs.edit()
            .putInt(KEY_CACHED_MINUTES_TODAY, minutes)
            .putInt(KEY_CACHED_COUNT_TODAY, count)
            .putBoolean(KEY_CACHED_LUNCH_TODAY, lunchIncluded)
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

    private fun getCachedCountForToday(): Int {
        val cachedDate = prefs.getString(KEY_CACHED_DATE, "") ?: ""
        return if (cachedDate == getTodayDateStr()) {
            prefs.getInt(KEY_CACHED_COUNT_TODAY, 0)
        } else {
            0
        }
    }

    private fun getCachedLunchForToday(): Boolean {
        val cachedDate = prefs.getString(KEY_CACHED_DATE, "") ?: ""
        return if (cachedDate == getTodayDateStr()) {
            prefs.getBoolean(KEY_CACHED_LUNCH_TODAY, false)
        } else {
            false
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
