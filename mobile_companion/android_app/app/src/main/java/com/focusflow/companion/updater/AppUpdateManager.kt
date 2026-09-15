package com.focusflow.companion.updater

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.FileProvider
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

data class UpdateInfo(
    val versionCode: Int,
    val versionName: String,
    val downloadUrl: String,
    val releaseNotes: String,
    val apkSize: String? = null
)

class AppUpdateManager(private val context: Context) {

    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    fun getCurrentVersionCode(): Int {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                pInfo.longVersionCode.toInt()
            } else {
                @Suppress("DEPRECATION")
                pInfo.versionCode
            }
        } catch (e: Exception) {
            1
        }
    }

    fun getCurrentVersionName(): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            pInfo.versionName ?: "1.0"
        } catch (e: Exception) {
            "1.0"
        }
    }

    /**
     * Checks Bridge server or GitHub for updates.
     */
    suspend fun checkForUpdates(bridgeBaseUrl: String?): UpdateInfo? {
        return withContext(Dispatchers.IO) {
            // 1. Try local Bridge server first if configured
            if (!bridgeBaseUrl.isNullOrBlank()) {
                val info = checkBridgeServer(bridgeBaseUrl)
                if (info != null) return@withContext info
            }

            // 2. Fallback to GitHub Releases
            checkGitHubReleases()
        }
    }

    private fun checkBridgeServer(baseUrl: String): UpdateInfo? {
        return try {
            var url = baseUrl.trim()
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://$url"
            }
            if (url.endsWith("/")) {
                url = url.substring(0, url.length - 1)
            }

            val request = Request.Builder().url("$url/api/version").get().build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val bodyStr = response.body?.string() ?: return null
                val info = gson.fromJson(bodyStr, UpdateInfo::class.java)

                // If downloadUrl is relative, prepend baseUrl
                val finalDownloadUrl = if (info.downloadUrl.startsWith("http")) {
                    info.downloadUrl
                } else {
                    "$url${if (info.downloadUrl.startsWith("/")) "" else "/"}${info.downloadUrl}"
                }
                info.copy(downloadUrl = finalDownloadUrl)
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun checkGitHubReleases(): UpdateInfo? {
        return try {
            val request = Request.Builder()
                .url("https://api.github.com/repos/caecitas-glitch/Study-focus-app/releases/latest")
                .header("User-Agent", "FocusFlow-Companion")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val bodyStr = response.body?.string() ?: return null
                val map = gson.fromJson(bodyStr, Map::class.java)
                val tagName = map["tag_name"] as? String ?: return null
                val body = map["body"] as? String ?: "New release available on GitHub"

                // Find APK asset
                var apkUrl: String? = null
                val assets = map["assets"] as? List<*>
                assets?.forEach { asset ->
                    val aMap = asset as? Map<*, *>
                    val name = aMap?.get("name") as? String
                    if (name != null && name.endsWith(".apk")) {
                        apkUrl = aMap["browser_download_url"] as? String
                    }
                }

                if (apkUrl == null) return null

                // Parse tag version like v1.0.5 or 1.0.5
                val cleanTag = tagName.removePrefix("v").removePrefix("V")
                // Assume each version bump has versionCode higher than 1
                val code = parseVersionCodeFromTag(cleanTag)

                UpdateInfo(
                    versionCode = code,
                    versionName = cleanTag,
                    downloadUrl = apkUrl!!,
                    releaseNotes = body
                )
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun parseVersionCodeFromTag(tag: String): Int {
        val parts = tag.split('.').mapNotNull { it.toIntOrNull() }
        if (parts.isEmpty()) return 1
        return when (parts.size) {
            1 -> parts[0] * 100
            2 -> parts[0] * 100 + parts[1]
            else -> parts[0] * 10000 + parts[1] * 100 + parts[2]
        }
    }

    /**
     * Checks whether an UpdateInfo represents a strictly newer version than currently installed.
     * Uses semantic version comparison (e.g. 1.0.5 > 1.0.4) rather than raw codes, preventing
     * infinite update loops when tag names match the installed version.
     */
    fun isUpdateAvailable(info: UpdateInfo?): Boolean {
        if (info == null) return false
        val currentName = getCurrentVersionName().trim().removePrefix("v").removePrefix("V")
        val remoteName = info.versionName.trim().removePrefix("v").removePrefix("V")

        // Exact match -> definitely not an update
        if (remoteName.equals(currentName, ignoreCase = true)) {
            return false
        }

        val currentParts = currentName.split('.').mapNotNull { it.toIntOrNull() }
        val remoteParts = remoteName.split('.').mapNotNull { it.toIntOrNull() }

        if (currentParts.isNotEmpty() && remoteParts.isNotEmpty()) {
            val maxParts = maxOf(currentParts.size, remoteParts.size)
            for (i in 0 until maxParts) {
                val curr = currentParts.getOrElse(i) { 0 }
                val rem = remoteParts.getOrElse(i) { 0 }
                if (rem > curr) return true
                if (rem < curr) return false
            }
            return false
        }

        // Fallback to versionCode comparison only if version names couldn't be parsed
        return info.versionCode > getCurrentVersionCode()
    }

    /**
     * Downloads the APK with progress reporting and automatically launches the package installer.
     */
    suspend fun downloadAndInstallApk(
        downloadUrl: String,
        onProgress: (percent: Int) -> Unit
    ): Result<Unit> {
        return withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder().url(downloadUrl).get().build()
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        return@withContext Result.failure(Exception("HTTP ${response.code} downloading update"))
                    }

                    val body = response.body ?: return@withContext Result.failure(Exception("Empty download response"))
                    val contentLength = body.contentLength()
                    val targetDir = File(context.getExternalFilesDir(null) ?: context.cacheDir, "updates")
                    if (!targetDir.exists()) targetDir.mkdirs()

                    val targetFile = File(targetDir, "focusflow-companion-update.apk")
                    if (targetFile.exists()) targetFile.delete()

                    val inputStream = body.byteStream()
                    val outputStream = FileOutputStream(targetFile)
                    val buffer = ByteArray(8192)
                    var totalBytesRead = 0L
                    var bytesRead: Int

                    while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                        outputStream.write(buffer, 0, bytesRead)
                        totalBytesRead += bytesRead
                        if (contentLength > 0) {
                            val percent = ((totalBytesRead * 100) / contentLength).toInt()
                            withContext(Dispatchers.Main) {
                                onProgress(percent)
                            }
                        }
                    }
                    outputStream.flush()
                    outputStream.close()
                    inputStream.close()

                    withContext(Dispatchers.Main) {
                        onProgress(100)
                        triggerPackageInstall(targetFile)
                    }

                    Result.success(Unit)
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    fun triggerPackageInstall(apkFile: File) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!context.packageManager.canRequestPackageInstalls()) {
                val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                    data = Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                Toast.makeText(
                    context,
                    "Please enable 'Allow from this source' for FocusFlow, then tap Update again.",
                    Toast.LENGTH_LONG
                ).show()
                return
            }
        }

        try {
            val apkUri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                apkFile
            )

            val installIntent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(apkUri, "application/vnd.android.package-archive")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            }
            val resInfoList = context.packageManager.queryIntentActivities(installIntent, PackageManager.MATCH_DEFAULT_ONLY)
            for (resolveInfo in resInfoList) {
                val packageName = resolveInfo.activityInfo.packageName
                context.grantUriPermission(packageName, apkUri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(installIntent)
        } catch (e: Exception) {
            Toast.makeText(context, "Failed to start installer: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
        }
    }
}
