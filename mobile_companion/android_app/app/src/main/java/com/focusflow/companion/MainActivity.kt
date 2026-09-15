package com.focusflow.companion

import android.Manifest
import android.content.Context
import android.content.DialogInterface
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.focusflow.companion.databinding.ActivityMainBinding
import com.focusflow.companion.databinding.DialogAppLimitConfigBinding
import com.focusflow.companion.databinding.ItemMonitoredAppBinding
import com.focusflow.companion.services.AppRule
import com.focusflow.companion.services.DndManager
import com.focusflow.companion.services.FocusBlockerService
import com.focusflow.companion.services.UsageLimitManager
import com.focusflow.companion.sync.ActiveSession
import com.focusflow.companion.sync.FocusStatusResponse
import com.focusflow.companion.sync.SyncClient
import com.focusflow.companion.updater.AppUpdateManager
import com.focusflow.companion.updater.UpdateInfo
import com.focusflow.companion.workers.DailyReminderReceiver
import com.google.gson.Gson
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity(), SyncClient.SyncCallback {

    private lateinit var binding: ActivityMainBinding
    private lateinit var dndManager: DndManager
    private lateinit var syncClient: SyncClient
    private lateinit var usageLimitManager: UsageLimitManager
    private lateinit var appUpdateManager: AppUpdateManager

    private var currentSession: ActiveSession? = null
    private var selectedSubject: String = "#General Study"
    private var selectedDurationMinutes: Int = 30
    private val universityTags = mutableListOf<String>()
    private var pendingUpdateInfo: UpdateInfo? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        dndManager = DndManager(this)
        syncClient = SyncClient(this)
        usageLimitManager = UsageLimitManager(this)
        appUpdateManager = AppUpdateManager(this)

        setupPrefsAndIp()
        setupListeners()
        setupDurationListeners()
        requestNotificationPermission()

        // Schedule daily morning motivational quote reminder at 07:00 AM
        DailyReminderReceiver.scheduleDailyAlarm(this, 7, 0)
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        binding.switchGuardianToggle.isChecked = prefs.getBoolean(KEY_GUARDIAN_ENABLED, true)
        updatePermissionBadges()
        updateUsageLimitsUI()
        startGuardianServiceIfPermitted()
        checkAppUpdates()
    }

    private fun startGuardianServiceIfPermitted() {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val isGuardianEnabled = prefs.getBoolean(KEY_GUARDIAN_ENABLED, true)
        if (isGuardianEnabled && FocusBlockerService.hasUsageStatsPermission(this) && currentSession?.isActive != true) {
            val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                action = FocusBlockerService.ACTION_START_GUARD
            }
            try {
                ContextCompat.startForegroundService(this, serviceIntent)
            } catch (e: Exception) { }
        } else if (!isGuardianEnabled && currentSession?.isActive != true) {
            val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                action = FocusBlockerService.ACTION_STOP_ALL
            }
            startService(serviceIntent)
        }
    }

    private fun setupPrefsAndIp() {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val savedIp = prefs.getString(KEY_BRIDGE_IP, "")
        if (!savedIp.isNullOrEmpty()) {
            binding.etBridgeIp.setText(savedIp)
            connectToBridge(savedIp)
        }

        val savedTagsJson = prefs.getString(KEY_SAVED_TAGS, null)
        if (!savedTagsJson.isNullOrEmpty()) {
            try {
                val list = Gson().fromJson(savedTagsJson, Array<String>::class.java).toList()
                universityTags.clear()
                universityTags.addAll(list)
            } catch (e: Exception) { }
        }
        val savedLastSubject = prefs.getString(KEY_LAST_SUBJECT, null)
        if (!savedLastSubject.isNullOrEmpty()) {
            selectedSubject = savedLastSubject
        } else if (universityTags.isNotEmpty()) {
            selectedSubject = universityTags.first()
        }
        binding.tvSessionSubject.text = selectedSubject
        binding.tvTimerCountdown.text = String.format("%02d:00", selectedDurationMinutes)
        binding.btnStartSession.text = "Start ${selectedDurationMinutes}m Focus"
    }

    private fun setupListeners() {
        binding.btnConnect.setOnClickListener {
            val ip = binding.etBridgeIp.text.toString().trim()
            if (ip.isEmpty()) {
                Toast.makeText(this, "Please enter your PC's IP address and port", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_BRIDGE_IP, ip)
                .apply()

            connectToBridge(ip)
            checkAppUpdates()
        }

        binding.btnSelectSubject.setOnClickListener {
            if (currentSession?.isActive != true) {
                showSubjectPickerDialog()
            }
        }

        binding.btnGrantDnd.setOnClickListener {
            dndManager.openDndSettings()
        }

        binding.btnGrantBlocker.setOnClickListener {
            if (!FocusBlockerService.hasUsageStatsPermission(this)) {
                startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
            } else if (!FocusBlockerService.hasOverlayPermission(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
        }

        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val isGuardianEnabled = prefs.getBoolean(KEY_GUARDIAN_ENABLED, true)
        binding.switchGuardianToggle.isChecked = isGuardianEnabled

        binding.switchGuardianToggle.setOnCheckedChangeListener { _, isChecked ->
            prefs.edit().putBoolean(KEY_GUARDIAN_ENABLED, isChecked).apply()
            if (isChecked) {
                startGuardianServiceIfPermitted()
                Toast.makeText(this, "🛡️ Silent background guardian enabled", Toast.LENGTH_SHORT).show()
            } else {
                if (currentSession?.isActive != true) {
                    val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                        action = FocusBlockerService.ACTION_STOP_ALL
                    }
                    startService(serviceIntent)
                }
                Toast.makeText(this, "Background guardian disabled (Limits active only during focus)", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnHideGuardianNotif.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val intent = Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).apply {
                    putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
                    putExtra(Settings.EXTRA_CHANNEL_ID, FocusBlockerService.CHANNEL_GUARDIAN)
                }
                startActivity(intent)
            } else {
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.parse("package:$packageName")
                }
                startActivity(intent)
            }
        }

        binding.btnTestQuote.setOnClickListener {
            DailyReminderReceiver.showDailyQuoteNotification(this)
            Toast.makeText(this, "⚡ Morning fuel notification posted!", Toast.LENGTH_SHORT).show()
        }

        binding.btnStartSession.setOnClickListener {
            val ip = binding.etBridgeIp.text.toString().trim()
            val totalSec = selectedDurationMinutes * 60L
            lifecycleScope.launch {
                val dummySession = ActiveSession(
                    isActive = true,
                    subject = selectedSubject,
                    durationMinutes = selectedDurationMinutes,
                    remainingSeconds = totalSec
                )
                onSessionStateChanged(dummySession)

                if (ip.isNotEmpty()) {
                    syncClient.startRemoteSession(ip, selectedDurationMinutes, selectedSubject)
                }
            }
        }

        binding.btnToggleLeisure.setOnClickListener {
            if (usageLimitManager.isLeisureModeActive()) {
                usageLimitManager.disableLeisureMode()
                Toast.makeText(this, "Relax Mode turned off. Focus limits restored.", Toast.LENGTH_SHORT).show()
            } else {
                usageLimitManager.enableLeisureMode(2)
                Toast.makeText(this, "🛋️ Relax Mode enabled for 2 hours. App limits paused!", Toast.LENGTH_LONG).show()
            }
            updateUsageLimitsUI()
        }

        binding.btnAddNewAppRule.setOnClickListener {
            showAddAppDialog()
        }

        binding.btnStopSession.setOnClickListener {
            val ip = binding.etBridgeIp.text.toString().trim()
            lifecycleScope.launch {
                onSessionStateChanged(ActiveSession(isActive = false))
                if (ip.isNotEmpty()) {
                    syncClient.stopRemoteSession(ip)
                }
            }
        }

        binding.btnUpdateNow.setOnClickListener {
            val info = pendingUpdateInfo ?: return@setOnClickListener
            binding.btnUpdateNow.isEnabled = false
            binding.btnUpdateNow.text = "Downloading..."
            binding.pbUpdateDownload.visibility = View.VISIBLE
            binding.tvUpdateProgress.visibility = View.VISIBLE

            lifecycleScope.launch {
                val result = appUpdateManager.downloadAndInstallApk(info.downloadUrl) { percent ->
                    binding.pbUpdateDownload.progress = percent
                    binding.tvUpdateProgress.text = "Downloading: $percent%"
                }
                binding.btnUpdateNow.isEnabled = true
                binding.btnUpdateNow.text = "Update"
                if (result.isFailure) {
                    val err = result.exceptionOrNull()?.localizedMessage ?: "Unknown error"
                    Toast.makeText(this@MainActivity, "Update download error: $err", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun setupDurationListeners() {
        fun setDuration(mins: Int, activeBtn: Button) {
            selectedDurationMinutes = mins
            binding.tvTimerCountdown.text = String.format("%02d:00", mins)
            binding.btnStartSession.text = "Start ${mins}m Focus"

            val activeColor = ContextCompat.getColor(this, R.color.accent_primary)
            val dimColor = ContextCompat.getColor(this, R.color.text_muted)
            val activeBorder = activeColor
            val dimBorder = ContextCompat.getColor(this, R.color.card_border)

            val allBtns = listOf(
                binding.btnDur15, binding.btnDur25, binding.btnDur30,
                binding.btnDur45, binding.btnDur60, binding.btnDurCustom
            )
            for (btn in allBtns) {
                val isActive = (btn == activeBtn)
                btn.setTextColor(if (isActive) activeColor else dimColor)
                (btn as? com.google.android.material.button.MaterialButton)?.strokeColor =
                    android.content.res.ColorStateList.valueOf(if (isActive) activeBorder else dimBorder)
            }
        }

        binding.btnDur15.setOnClickListener { setDuration(15, binding.btnDur15) }
        binding.btnDur25.setOnClickListener { setDuration(25, binding.btnDur25) }
        binding.btnDur30.setOnClickListener { setDuration(30, binding.btnDur30) }
        binding.btnDur45.setOnClickListener { setDuration(45, binding.btnDur45) }
        binding.btnDur60.setOnClickListener { setDuration(60, binding.btnDur60) }

        binding.btnDurCustom.setOnClickListener {
            val input = EditText(this).apply {
                hint = "Minutes (e.g. 50)"
                inputType = android.text.InputType.TYPE_CLASS_NUMBER
                setTextColor(ContextCompat.getColor(context, R.color.text_main))
                setHintTextColor(ContextCompat.getColor(context, R.color.text_dim))
            }
            AlertDialog.Builder(this)
                .setTitle("Custom Session Duration")
                .setView(input)
                .setPositiveButton("Set") { _, _ ->
                    val mins = input.text.toString().trim().toIntOrNull()
                    if (mins != null && mins > 0) {
                        binding.btnDurCustom.text = "${mins}m"
                        setDuration(mins, binding.btnDurCustom)
                    }
                }
                .setNegativeButton("Cancel", null)
                .show()
        }
    }

    private fun showSubjectPickerDialog() {
        val allTags = mutableListOf<String>()
        allTags.addAll(universityTags)
        if (!allTags.contains("#General Study")) {
            allTags.add(0, "#General Study")
        }
        val options = allTags.toTypedArray()
        val currentIndex = allTags.indexOf(selectedSubject).let { if (it >= 0) it else 0 }

        AlertDialog.Builder(this)
            .setTitle("Select Study Subject / Tag")
            .setSingleChoiceItems(options, currentIndex) { dialog, which ->
                selectedSubject = options[which]
                binding.tvSessionSubject.text = selectedSubject
                getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                    .edit()
                    .putString(KEY_LAST_SUBJECT, selectedSubject)
                    .apply()
                dialog.dismiss()
            }
            .setPositiveButton("+ Custom Tag") { _, _ ->
                showCustomTagInputDialog()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showCustomTagInputDialog() {
        val input = EditText(this).apply {
            hint = "e.g. #Physics or #Exam Prep"
            setTextColor(ContextCompat.getColor(context, R.color.text_main))
            setHintTextColor(ContextCompat.getColor(context, R.color.text_dim))
        }
        AlertDialog.Builder(this)
            .setTitle("Enter Custom Subject Tag")
            .setView(input)
            .setPositiveButton("Set") { _, _ ->
                var tag = input.text.toString().trim()
                if (tag.isNotEmpty()) {
                    if (!tag.startsWith("#")) tag = "#$tag"
                    if (!universityTags.contains(tag)) {
                        universityTags.add(tag)
                        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                        prefs.edit().putString(KEY_SAVED_TAGS, Gson().toJson(universityTags)).apply()
                    }
                    selectedSubject = tag
                    binding.tvSessionSubject.text = selectedSubject
                    getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                        .edit()
                        .putString(KEY_LAST_SUBJECT, selectedSubject)
                        .apply()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun checkAppUpdates() {
        val ip = binding.etBridgeIp.text.toString().trim()
        lifecycleScope.launch {
            val info = appUpdateManager.checkForUpdates(if (ip.isNotEmpty()) ip else null)
            if (info != null && appUpdateManager.isUpdateAvailable(info)) {
                pendingUpdateInfo = info
                binding.cardUpdateBanner.visibility = View.VISIBLE
                binding.tvUpdateTitle.text = "New Update Available (${info.versionName})"
                val sizeText = if (!info.apkSize.isNullOrEmpty()) " • ${info.apkSize}" else ""
                binding.tvUpdateNotes.text = "${info.releaseNotes}$sizeText"
            } else {
                binding.cardUpdateBanner.visibility = View.GONE
            }
        }
    }

    private fun connectToBridge(ip: String) {
        binding.tvSyncStatus.text = "Connecting..."
        binding.tvSyncStatus.setTextColor(ContextCompat.getColor(this, R.color.accent_amber))

        lifecycleScope.launch {
            syncClient.fetchStatus(ip)
            syncClient.startEventStream(ip)
        }
    }

    private fun updatePermissionBadges() {
        if (dndManager.hasDndPermission()) {
            binding.btnGrantDnd.text = "Active ✓"
            binding.btnGrantDnd.isEnabled = false
            binding.tvDndStatus.text = "Notifications will automatically mute during focus"
        } else {
            binding.btnGrantDnd.text = "Grant"
            binding.btnGrantDnd.isEnabled = true
            binding.tvDndStatus.text = "Grant permission to mute alerts automatically"
        }

        val hasUsage = FocusBlockerService.hasUsageStatsPermission(this)
        val hasOverlay = FocusBlockerService.hasOverlayPermission(this)
        if (hasUsage && hasOverlay) {
            binding.btnGrantBlocker.text = "Active ✓"
            binding.btnGrantBlocker.isEnabled = false
            binding.tvBlockerStatus.text = "Monitored apps blocked during study sessions"
        } else {
            binding.btnGrantBlocker.text = "Grant"
            binding.btnGrantBlocker.isEnabled = true
            binding.tvBlockerStatus.text = when {
                !hasUsage -> "Requires Usage Access to detect distracting apps"
                else -> "Requires Display Over Apps to show blocker screen"
            }
        }
    }

    private fun updateUsageLimitsUI() {
        if (usageLimitManager.isLeisureModeActive()) {
            binding.tvLeisureStatus.text = "Relax Mode Active (Limits bypassed)"
            binding.btnToggleLeisure.text = "Active (On)"
            binding.btnToggleLeisure.setTextColor(ContextCompat.getColor(this, R.color.accent_emerald))
        } else {
            binding.tvLeisureStatus.text = "Limits strictly enforced"
            binding.btnToggleLeisure.text = "Relax Mode"
            binding.btnToggleLeisure.setTextColor(ContextCompat.getColor(this, R.color.accent_cyan))
        }

        renderMonitoredAppsList()
    }

    private fun renderMonitoredAppsList() {
        val container = binding.llMonitoredAppsContainer
        container.removeAllViews()

        val rules = usageLimitManager.getAllRules()
        val inflater = LayoutInflater.from(this)

        for (rule in rules) {
            val itemBinding = ItemMonitoredAppBinding.inflate(inflater, container, false)
            itemBinding.tvAppEmoji.text = rule.iconEmoji
            itemBinding.tvAppName.text = rule.displayName

            val summaries = mutableListOf<String>()
            if (rule.isStudyBlocked) {
                summaries.add("🚫 Study Block")
            }
            if (rule.sessionLimitMinutes > 0) {
                summaries.add("⏳ ${rule.sessionLimitMinutes}m/session")
            }
            if (rule.warnAfter9Pm) {
                summaries.add("🌙 9 PM Alert")
            }
            if (summaries.isEmpty()) {
                summaries.add("Unrestricted")
            }

            itemBinding.tvAppRulesSummary.text = summaries.joinToString(" • ")

            val clickListener = View.OnClickListener {
                showAppConfigDialog(rule)
            }
            itemBinding.layoutAppRow.setOnClickListener(clickListener)
            itemBinding.btnEditAppRule.setOnClickListener(clickListener)

            container.addView(itemBinding.root)
        }
    }

    private fun showAppConfigDialog(rule: AppRule) {
        val dialogBinding = DialogAppLimitConfigBinding.inflate(layoutInflater)
        dialogBinding.tvDialogAppEmoji.text = rule.iconEmoji
        dialogBinding.tvDialogAppName.text = rule.displayName
        dialogBinding.tvDialogAppPkg.text = rule.packageName

        dialogBinding.switchStudyBlock.isChecked = rule.isStudyBlocked
        dialogBinding.switchLateNight.isChecked = rule.warnAfter9Pm

        var selectedLimit = rule.sessionLimitMinutes
        fun updateChipStyles() {
            val activeColor = ContextCompat.getColor(this, R.color.accent_primary)
            val dimColor = ContextCompat.getColor(this, R.color.text_muted)
            val activeBorder = activeColor
            val dimBorder = ContextCompat.getColor(this, R.color.card_border)

            fun styleBtn(btn: Button, isActive: Boolean) {
                btn.setTextColor(if (isActive) activeColor else dimColor)
                (btn as? com.google.android.material.button.MaterialButton)?.strokeColor =
                    android.content.res.ColorStateList.valueOf(if (isActive) activeBorder else dimBorder)
            }

            styleBtn(dialogBinding.chipLimitOff, selectedLimit == 0)
            styleBtn(dialogBinding.chipLimit15, selectedLimit == 15)
            styleBtn(dialogBinding.chipLimit30, selectedLimit == 30)
            styleBtn(dialogBinding.chipLimit45, selectedLimit == 45)
            styleBtn(dialogBinding.chipLimit60, selectedLimit == 60)
        }

        updateChipStyles()
        if (selectedLimit > 0 && selectedLimit !in listOf(15, 30, 45, 60)) {
            dialogBinding.etCustomMinutes.setText(selectedLimit.toString())
        }

        dialogBinding.chipLimitOff.setOnClickListener {
            selectedLimit = 0
            dialogBinding.etCustomMinutes.text.clear()
            updateChipStyles()
        }
        dialogBinding.chipLimit15.setOnClickListener {
            selectedLimit = 15
            dialogBinding.etCustomMinutes.text.clear()
            updateChipStyles()
        }
        dialogBinding.chipLimit30.setOnClickListener {
            selectedLimit = 30
            dialogBinding.etCustomMinutes.text.clear()
            updateChipStyles()
        }
        dialogBinding.chipLimit45.setOnClickListener {
            selectedLimit = 45
            dialogBinding.etCustomMinutes.text.clear()
            updateChipStyles()
        }
        dialogBinding.chipLimit60.setOnClickListener {
            selectedLimit = 60
            dialogBinding.etCustomMinutes.text.clear()
            updateChipStyles()
        }

        val dialog = AlertDialog.Builder(this)
            .setView(dialogBinding.root)
            .create()

        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)

        dialogBinding.btnCancelDialog.setOnClickListener {
            dialog.dismiss()
        }

        dialogBinding.btnSaveDialog.setOnClickListener {
            val customText = dialogBinding.etCustomMinutes.text.toString().trim()
            val finalLimit = if (customText.isNotEmpty()) {
                customText.toIntOrNull() ?: selectedLimit
            } else {
                selectedLimit
            }

            val updated = rule.copy(
                isStudyBlocked = dialogBinding.switchStudyBlock.isChecked,
                warnAfter9Pm = dialogBinding.switchLateNight.isChecked,
                sessionLimitMinutes = finalLimit
            )
            usageLimitManager.updateRule(updated)
            renderMonitoredAppsList()
            Toast.makeText(this, "Updated rules for ${rule.displayName}", Toast.LENGTH_SHORT).show()
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun showAddAppDialog() {
        val inputView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(60, 40, 60, 20)
        }
        val etPkg = EditText(this).apply {
            hint = "Package name (e.g. com.spotify.music)"
            setTextColor(ContextCompat.getColor(context, R.color.text_main))
            setHintTextColor(ContextCompat.getColor(context, R.color.text_dim))
            textSize = 13f
        }
        val etName = EditText(this).apply {
            hint = "Display name (e.g. Spotify)"
            setTextColor(ContextCompat.getColor(context, R.color.text_main))
            setHintTextColor(ContextCompat.getColor(context, R.color.text_dim))
            textSize = 13f
        }
        inputView.addView(etName)
        inputView.addView(etPkg)

        AlertDialog.Builder(this)
            .setTitle("Add App to Blocklist & Limits")
            .setView(inputView)
            .setPositiveButton("Add") { dialog: DialogInterface, which: Int ->
                val pkg = etPkg.text.toString().trim()
                val name = etName.text.toString().trim().ifEmpty { pkg.substringAfterLast('.') }
                if (pkg.isNotEmpty()) {
                    val newRule = AppRule(
                        packageName = pkg,
                        displayName = name,
                        iconEmoji = "📱",
                        isStudyBlocked = true,
                        sessionLimitMinutes = 0,
                        warnAfter9Pm = false
                    )
                    usageLimitManager.updateRule(newRule)
                    renderMonitoredAppsList()
                    Toast.makeText(this, "Added $name to monitored apps", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                    101
                )
            }
        }
    }

    // --- SyncClient Callback implementations ---

    override fun onConnectionStatusChanged(isConnected: Boolean, message: String) {
        runOnUiThread {
            if (isConnected) {
                binding.tvSyncStatus.text = "Synced ✓"
                binding.tvSyncStatus.setTextColor(ContextCompat.getColor(this, R.color.accent_emerald))
            } else {
                binding.tvSyncStatus.text = "Offline"
                binding.tvSyncStatus.setTextColor(ContextCompat.getColor(this, R.color.accent_rose))
            }
        }
    }

    override fun onStatusReceived(status: FocusStatusResponse) {
        runOnUiThread {
            binding.tvStreak.text = "🔥 ${status.streakCount} day${if (status.streakCount == 1) "" else "s"}"

            if (status.nextRank != null) {
                val needed = status.nextRank.threshold - status.rewardTierMinutes
                binding.tvNextReward.text = "${maxOf(0, needed)}m to ${status.nextRank.reward}"
            } else {
                binding.tvNextReward.text = "Max Tier Achieved!"
            }

            // Sync university custom tags
            if (status.customTags.isNotEmpty()) {
                universityTags.clear()
                universityTags.addAll(status.customTags)
                val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                prefs.edit().putString(KEY_SAVED_TAGS, Gson().toJson(universityTags)).apply()

                if (selectedSubject == "#General Study" && universityTags.isNotEmpty()) {
                    selectedSubject = universityTags.first()
                    binding.tvSessionSubject.text = selectedSubject
                }
            }

            // Render upcoming deadlines
            if (status.upcomingDeadlines.isNotEmpty()) {
                val sb = StringBuilder()
                for ((idx, d) in status.upcomingDeadlines.take(3).withIndex()) {
                    sb.append("• ${d.due}: ${d.summary}")
                    if (idx < 2) sb.append("\n")
                }
                binding.tvUpcomingDeadlines.text = sb.toString()
            } else {
                binding.tvUpcomingDeadlines.text = "No pending university deadlines!"
            }

            status.activeSession?.let { onSessionStateChanged(it) }
        }
    }

    override fun onSessionStateChanged(session: ActiveSession) {
        currentSession = session
        runOnUiThread {
            if (session.isActive) {
                selectedSubject = session.subject.ifEmpty { selectedSubject }
                binding.tvSessionSubject.text = selectedSubject
                binding.tvSelectSubjectArrow.visibility = View.GONE
                binding.scrollDurationOptions.visibility = View.GONE
                binding.tvSessionStateText.text = "Session Active • Distractions & Alerts Muted"
                binding.btnStartSession.visibility = View.GONE
                binding.btnStopSession.visibility = View.VISIBLE

                updateTimerDisplay(session.remainingSeconds)

                // Start Android Foreground Monitoring Service + DND
                val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                    action = FocusBlockerService.ACTION_START
                    putExtra(FocusBlockerService.EXTRA_SUBJECT, selectedSubject)
                    putExtra(FocusBlockerService.EXTRA_REMAINING_SEC, session.remainingSeconds)
                }
                ContextCompat.startForegroundService(this, serviceIntent)

            } else {
                binding.tvSessionSubject.text = selectedSubject
                binding.tvSelectSubjectArrow.visibility = View.VISIBLE
                binding.scrollDurationOptions.visibility = View.VISIBLE
                binding.tvSessionStateText.text = "Ready for deep work"
                binding.tvTimerCountdown.text = String.format("%02d:00", selectedDurationMinutes)
                binding.btnStartSession.text = "Start ${selectedDurationMinutes}m Focus"
                binding.btnStartSession.visibility = View.VISIBLE
                binding.btnStopSession.visibility = View.GONE

                // Stop active study session, transition back to low-power guard
                val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                    action = FocusBlockerService.ACTION_STOP
                }
                startService(serviceIntent)
            }
        }
    }

    override fun onSessionTick(remainingSec: Long, subject: String) {
        runOnUiThread {
            updateTimerDisplay(remainingSec)

            // Update foreground service notification timer
            val serviceIntent = Intent(this, FocusBlockerService::class.java).apply {
                action = FocusBlockerService.ACTION_UPDATE_TIMER
                putExtra(FocusBlockerService.EXTRA_REMAINING_SEC, remainingSec)
            }
            startService(serviceIntent)
        }
    }

    private fun updateTimerDisplay(remainingSec: Long) {
        val mins = remainingSec / 60
        val secs = remainingSec % 60
        binding.tvTimerCountdown.text = String.format("%02d:%02d", mins, secs)
    }

    override fun onDestroy() {
        syncClient.stopEventStream()
        super.onDestroy()
    }

    companion object {
        const val PREFS_NAME = "focusflow_prefs"
        const val KEY_BRIDGE_IP = "key_bridge_ip"
        const val KEY_SAVED_TAGS = "key_saved_tags"
        const val KEY_LAST_SUBJECT = "key_last_subject"
        const val KEY_GUARDIAN_ENABLED = "key_guardian_enabled"
    }
}
