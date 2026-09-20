package com.focusflow.companion.services

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.SharedPreferences
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.util.Calendar

data class AppRule(
    val packageName: String,
    val displayName: String,
    val iconEmoji: String,
    var isStudyBlocked: Boolean = true,
    var sessionLimitMinutes: Int = 0, // 0 = no session limit; minutes per sitting
    var warnAfter9Pm: Boolean = false
) {
    // Backward compatibility property
    var dailyLimitMinutes: Int
        get() = sessionLimitMinutes
        set(value) { sessionLimitMinutes = value }
}

class UsageLimitManager(private val context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val gson = Gson()

    companion object {
        private const val PREFS_NAME = "focusflow_usage_limits"
        private const val KEY_LEISURE_UNTIL = "leisure_mode_until_timestamp"
        private const val KEY_BEDTIME_SNOOZE_UNTIL = "bedtime_snooze_until_timestamp"
        private const val KEY_CUSTOM_RULES_JSON = "custom_rules_json_v3"

        // Cooldown required between sessions in minutes (e.g. step away for 3 minutes before allowance resets)
        const val SESSION_COOLDOWN_MINUTES = 3

        val DEFAULT_RULES = listOf(
            AppRule("com.google.android.youtube", "YouTube", "📺", isStudyBlocked = true, sessionLimitMinutes = 20, warnAfter9Pm = true),
            AppRule("com.google.android.apps.bard", "Google Gemini", "🤖", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true),
            AppRule("com.google.android.googlequicksearchbox", "Google / Gemini", "🤖", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true),
            AppRule("com.instagram.android", "Instagram", "📸", isStudyBlocked = true, sessionLimitMinutes = 15, warnAfter9Pm = true),
            AppRule("com.zhiliaoapp.musically", "TikTok", "🎵", isStudyBlocked = true, sessionLimitMinutes = 15, warnAfter9Pm = true),
            AppRule("com.ss.android.ugc.trill", "TikTok", "🎵", isStudyBlocked = true, sessionLimitMinutes = 15, warnAfter9Pm = true),
            AppRule("com.reddit.frontpage", "Reddit", "💬", isStudyBlocked = true, sessionLimitMinutes = 20, warnAfter9Pm = true),
            AppRule("com.twitter.android", "X (Twitter)", "🐦", isStudyBlocked = true, sessionLimitMinutes = 15, warnAfter9Pm = true),
            AppRule("com.discord", "Discord", "🎮", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true),
            AppRule("com.netflix.mediaclient", "Netflix", "🍿", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true),
            AppRule("tv.twitch.android.app", "Twitch", "👾", isStudyBlocked = true, sessionLimitMinutes = 30, warnAfter9Pm = true),
            AppRule("com.snapchat.android", "Snapchat", "👻", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true),
            AppRule("com.android.chrome", "Google Chrome", "🌐", isStudyBlocked = true, sessionLimitMinutes = 20, warnAfter9Pm = true)
        )
    }

    fun isGeminiOrAiPackage(pkg: String): Boolean {
        val lower = pkg.lowercase()
        return lower.contains("apps.bard") ||
                lower.contains("gemini") ||
                lower.contains("googlequicksearchbox") ||
                lower.contains("googleassistant") ||
                lower.contains("openai.chatgpt") ||
                lower.contains("anthropic.claude") ||
                lower.contains("copilot")
    }

    /**
     * Retrieves all configured app rules, merged with defaults.
     */
    fun getAllRules(): List<AppRule> {
        val json = prefs.getString(KEY_CUSTOM_RULES_JSON, null)
        if (json.isNullOrEmpty()) {
            return DEFAULT_RULES
        }
        return try {
            val type = object : TypeToken<List<AppRule>>() {}.type
            val savedList: List<AppRule> = gson.fromJson(json, type)
            val savedPkgs = savedList.map { it.packageName }.toSet()
            val merged = savedList.toMutableList()
            for (def in DEFAULT_RULES) {
                if (!savedPkgs.contains(def.packageName)) {
                    merged.add(def)
                }
            }
            // Ensure Gemini, AI assistants, and all distracting apps retain bedtime lock
            for (r in merged) {
                if (isGeminiOrAiPackage(r.packageName) || r.isStudyBlocked || r.sessionLimitMinutes > 0) {
                    r.warnAfter9Pm = true
                }
            }
            merged
        } catch (e: Exception) {
            DEFAULT_RULES
        }
    }

    fun saveRules(rules: List<AppRule>) {
        val json = gson.toJson(rules)
        prefs.edit().putString(KEY_CUSTOM_RULES_JSON, json).apply()
    }

    fun getRuleForPackage(pkg: String): AppRule {
        if (isGeminiOrAiPackage(pkg)) {
            return AppRule(pkg, "Google Gemini", "🤖", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = true)
        }
        val direct = getAllRules().firstOrNull { it.packageName == pkg }
        if (direct != null) return direct
        return AppRule(pkg, formatUnknownPackage(pkg), "📱", isStudyBlocked = true, sessionLimitMinutes = 0, warnAfter9Pm = false)
    }

    fun updateRule(rule: AppRule) {
        val current = getAllRules().toMutableList()
        val index = current.indexOfFirst { it.packageName == rule.packageName }
        if (index >= 0) {
            current[index] = rule
        } else {
            current.add(rule)
        }
        saveRules(current)
    }

    fun isStudyBlocked(pkg: String): Boolean {
        val rule = getAllRules().firstOrNull { it.packageName == pkg }
        return rule?.isStudyBlocked ?: false
    }

    fun isLateNightAlertEnabled(pkg: String): Boolean {
        if (isGeminiOrAiPackage(pkg)) {
            return true
        }
        val rule = getAllRules().firstOrNull { it.packageName == pkg }
        if (rule != null) {
            return rule.warnAfter9Pm || rule.isStudyBlocked || rule.sessionLimitMinutes > 0
        }
        val lower = pkg.lowercase()
        return lower.contains("youtube") || lower.contains("tiktok") || 
               lower.contains("instagram") || lower.contains("reddit") || 
               lower.contains("twitter") || lower.contains("netflix") || 
               lower.contains("twitch") || lower.contains("discord") || 
               lower.contains("snapchat") || lower.contains("chrome")
    }

    fun simulateBedtimeForTesting(durationSeconds: Int = 120) {
        val until = System.currentTimeMillis() + (durationSeconds * 1000L)
        prefs.edit().putLong("bedtime_test_simulation_until", until).apply()
    }

    fun isBedtimeTestingActive(): Boolean {
        val until = prefs.getLong("bedtime_test_simulation_until", 0L)
        return System.currentTimeMillis() < until
    }

    fun getSessionLimitForPackage(pkg: String): Int {
        val rule = getAllRules().firstOrNull { it.packageName == pkg }
        if (rule != null) return rule.sessionLimitMinutes
        val key = "limit_$pkg"
        return prefs.getInt(key, 0)
    }

    fun setSessionLimitForPackage(pkg: String, minutes: Int) {
        val rule = getRuleForPackage(pkg).copy(sessionLimitMinutes = minutes)
        updateRule(rule)
        prefs.edit().putInt("limit_$pkg", minutes).apply()
    }

    // Aliases for compatibility
    fun getLimitForPackage(pkg: String): Int = getSessionLimitForPackage(pkg)
    fun setLimitForPackage(pkg: String, minutes: Int) = setSessionLimitForPackage(pkg, minutes)

    fun getBonusMinutesForToday(pkg: String): Int {
        val todayKey = getTodayBonusKey(pkg)
        return prefs.getInt(todayKey, 0)
    }

    fun addBonusMinutes(pkg: String, additionalMinutes: Int) {
        val todayKey = getTodayBonusKey(pkg)
        val current = getBonusMinutesForToday(pkg)
        prefs.edit().putInt(todayKey, current + additionalMinutes).apply()
    }

    fun isLeisureModeActive(): Boolean {
        val until = prefs.getLong(KEY_LEISURE_UNTIL, 0L)
        return System.currentTimeMillis() < until
    }

    fun enableLeisureMode(durationHours: Int = 2) {
        val until = System.currentTimeMillis() + (durationHours * 3600 * 1000L)
        prefs.edit().putLong(KEY_LEISURE_UNTIL, until).apply()
    }

    fun disableLeisureMode() {
        prefs.edit().putLong(KEY_LEISURE_UNTIL, 0L).apply()
    }

    fun snoozeBedtime(minutes: Int = 15) {
        val until = System.currentTimeMillis() + (minutes * 60 * 1000L)
        prefs.edit().putLong(KEY_BEDTIME_SNOOZE_UNTIL, until).apply()
    }

    fun isBedtimeSnoozed(): Boolean {
        val until = prefs.getLong(KEY_BEDTIME_SNOOZE_UNTIL, 0L)
        return System.currentTimeMillis() < until
    }

    fun setPackageExtensionUntil(pkg: String, minutes: Int = 15) {
        val until = System.currentTimeMillis() + (minutes * 60 * 1000L)
        prefs.edit().putLong("extension_until_$pkg", until).apply()
    }

    fun isPackageExtensionActive(pkg: String): Boolean {
        val until = prefs.getLong("extension_until_$pkg", 0L)
        return System.currentTimeMillis() < until
    }

    fun extendAppUsage(pkg: String, minutes: Int = 15) {
        setPackageExtensionUntil(pkg, minutes)
        if (isGeminiOrAiPackage(pkg)) {
            setPackageExtensionUntil("com.google.android.apps.bard", minutes)
            setPackageExtensionUntil("com.google.android.googlequicksearchbox", minutes)
        }
        snoozeBedtime(minutes)
        addBonusMinutes(pkg, minutes)
    }

    fun getTodayUsageMinutes(pkg: String): Int {
        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager
            ?: return 0

        val calendar = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val startTime = calendar.timeInMillis
        val endTime = System.currentTimeMillis()

        val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startTime, endTime)
        if (stats.isNullOrEmpty()) return 0

        for (s in stats) {
            if (s.packageName == pkg) {
                return (s.totalTimeInForeground / (1000 * 60)).toInt()
            }
        }
        return 0
    }

    private fun getTodayBonusKey(pkg: String): String {
        val cal = Calendar.getInstance()
        val dateStr = "${cal.get(Calendar.YEAR)}_${cal.get(Calendar.DAY_OF_YEAR)}"
        return "bonus_${dateStr}_$pkg"
    }

    private fun formatUnknownPackage(pkg: String): String {
        val simple = pkg.substringAfterLast('.')
        return simple.replaceFirstChar { it.uppercase() }
    }
}
