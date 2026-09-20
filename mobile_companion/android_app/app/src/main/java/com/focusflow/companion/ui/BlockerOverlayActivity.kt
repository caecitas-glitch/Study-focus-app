package com.focusflow.companion.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.focusflow.companion.MainActivity
import com.focusflow.companion.databinding.ActivityBlockerOverlayBinding
import com.focusflow.companion.services.FocusBlockerService
import com.focusflow.companion.services.UsageLimitManager
import com.focusflow.companion.workers.QuoteBank

class BlockerOverlayActivity : AppCompatActivity() {

    private lateinit var binding: ActivityBlockerOverlayBinding
    private lateinit var usageLimitManager: UsageLimitManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        )

        binding = ActivityBlockerOverlayBinding.inflate(layoutInflater)
        setContentView(binding.root)

        usageLimitManager = UsageLimitManager(this)

        val rawPkg = intent.getStringExtra(EXTRA_RAW_PACKAGE) ?: ""
        val blockedAppName = intent.getStringExtra(EXTRA_PACKAGE_NAME) ?: "Distracting App"
        val reason = intent.getStringExtra(EXTRA_REASON) ?: REASON_STUDY_SESSION
        val subject = intent.getStringExtra(EXTRA_SUBJECT) ?: "#Focus"
        val remainingSec = intent.getLongExtra(EXTRA_REMAINING_SEC, 0L)
        val limitMinutes = intent.getIntExtra(EXTRA_LIMIT_MINS, 30)

        when (reason) {
            REASON_BEDTIME -> {
                binding.tvHeaderIcon.text = "🌙"
                binding.tvOverlayTitle.text = "PAST 9:00 PM: TIME FOR BED"
                binding.tvBlockedAppNotice.text =
                    "FocusFlow closed $blockedAppName because it's past 9:00 PM. Put your phone away, protect your sleep schedule, and recharge!"
                binding.tvOverlaySubject.text = "🌙 Late-Night Wind-Down"
                binding.tvOverlayTimer.visibility = View.GONE
                binding.btnBackToFocus.text = "Put Phone Away (Home)"
                binding.btnQuickExtension.text = "+15m Extension"
                binding.layoutBypassOptions.visibility = View.VISIBLE
            }
            REASON_SESSION_LIMIT, REASON_DAILY_LIMIT -> {
                binding.tvHeaderIcon.text = "⏳"
                binding.tvOverlayTitle.text = "SESSION LIMIT REACHED"
                binding.tvBlockedAppNotice.text =
                    "FocusFlow closed $blockedAppName because your sitting limit of ${limitMinutes}m was reached. Take a 15-minute break before your next session!"
                binding.tvOverlaySubject.text = "Continuous Sitting Guard"
                binding.tvOverlayTimer.visibility = View.GONE
                binding.btnBackToFocus.text = "Take a Break (Home)"
                binding.btnQuickExtension.text = "+15m Extension"
                binding.layoutBypassOptions.visibility = View.VISIBLE
            }
            else -> {
                binding.tvHeaderIcon.text = "🛡️"
                binding.tvOverlayTitle.text = "APP CLOSED BY FOCUSFLOW"
                binding.tvBlockedAppNotice.text =
                    "FocusFlow closed $blockedAppName because your focus session is active for $subject."
                binding.tvOverlaySubject.text = "Locked in: $subject"
                binding.tvOverlayTimer.visibility = View.VISIBLE

                val mins = remainingSec / 60
                val secs = remainingSec % 60
                binding.tvOverlayTimer.text = String.format("%02d:%02d", mins, secs)

                binding.btnBackToFocus.text = "Back to Focus"
                binding.btnQuickExtension.text = "+15m Extension"
                binding.layoutBypassOptions.visibility = View.VISIBLE
            }
        }

        binding.tvOverlayQuote.text = QuoteBank.formatQuote()

        // Quick 15-minute extension bypass
        binding.btnQuickExtension.setOnClickListener {
            val extensionMins = 15
            if (rawPkg.isNotEmpty()) {
                usageLimitManager.extendAppUsage(rawPkg, extensionMins)
                val extendIntent = Intent(this, FocusBlockerService::class.java).apply {
                    action = FocusBlockerService.ACTION_EXTEND_SESSION
                    putExtra(FocusBlockerService.EXTRA_RAW_PACKAGE, rawPkg)
                    putExtra(FocusBlockerService.EXTRA_EXTENSION_MINUTES, extensionMins)
                }
                try {
                    startService(extendIntent)
                } catch (e: Exception) { }
            } else {
                usageLimitManager.snoozeBedtime(extensionMins)
            }
            Toast.makeText(this, "⚡ Granted +15m extension for $blockedAppName", Toast.LENGTH_SHORT).show()
            finish()
        }

        // 2-Hour Relax / Leisure Mode bypass
        binding.btnLeisureMode.setOnClickListener {
            usageLimitManager.enableLeisureMode(2)
            if (rawPkg.isNotEmpty()) {
                usageLimitManager.extendAppUsage(rawPkg, 120)
                val extendIntent = Intent(this, FocusBlockerService::class.java).apply {
                    action = FocusBlockerService.ACTION_EXTEND_SESSION
                    putExtra(FocusBlockerService.EXTRA_RAW_PACKAGE, rawPkg)
                    putExtra(FocusBlockerService.EXTRA_EXTENSION_MINUTES, 120)
                }
                try {
                    startService(extendIntent)
                } catch (e: Exception) { }
            }
            Toast.makeText(this, "🛋️ Relax Mode activated for 2 hours. App limits paused!", Toast.LENGTH_LONG).show()
            finish()
        }

        binding.btnBackToFocus.setOnClickListener {
            val homeIntent = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            startActivity(homeIntent)
            finish()
        }
    }

    override fun onBackPressed() {
        val homeIntent = Intent(Intent.ACTION_MAIN).apply {
            addCategory(Intent.CATEGORY_HOME)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        startActivity(homeIntent)
        finish()
    }

    companion object {
        const val EXTRA_RAW_PACKAGE = "extra_raw_package"
        const val EXTRA_PACKAGE_NAME = "extra_package_name"
        const val EXTRA_REASON = "extra_reason"
        const val EXTRA_SUBJECT = "extra_subject"
        const val EXTRA_REMAINING_SEC = "extra_remaining_sec"
        const val EXTRA_LIMIT_MINS = "extra_limit_mins"

        const val REASON_STUDY_SESSION = "reason_study_session"
        const val REASON_DAILY_LIMIT = "reason_daily_limit"
        const val REASON_SESSION_LIMIT = "reason_session_limit"
        const val REASON_BEDTIME = "reason_bedtime"
    }
}
