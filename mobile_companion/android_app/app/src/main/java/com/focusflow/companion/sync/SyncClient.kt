package com.focusflow.companion.sync

import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.util.concurrent.TimeUnit

class SyncClient(private val callback: SyncCallback) {

    interface SyncCallback {
        fun onStatusReceived(status: FocusStatusResponse)
        fun onSessionStateChanged(session: ActiveSession)
        fun onSessionTick(remainingSec: Long, subject: String)
        fun onConnectionStatusChanged(isConnected: Boolean, message: String)
    }

    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // SSE requires infinite read timeout
        .build()

    private var eventSource: EventSource? = null

    suspend fun fetchStatus(baseUrl: String): FocusStatusResponse? {
        return withContext(Dispatchers.IO) {
            try {
                val cleanUrl = formatBaseUrl(baseUrl)
                val request = Request.Builder()
                    .url("$cleanUrl/api/status")
                    .get()
                    .build()

                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        callback.onConnectionStatusChanged(false, "HTTP ${response.code}")
                        return@withContext null
                    }
                    val bodyStr = response.body?.string() ?: return@withContext null
                    val status = gson.fromJson(bodyStr, FocusStatusResponse::class.java)
                    callback.onConnectionStatusChanged(true, "Connected")
                    callback.onStatusReceived(status)
                    status
                }
            } catch (e: Exception) {
                callback.onConnectionStatusChanged(false, e.localizedMessage ?: "Connection error")
                null
            }
        }
    }

    suspend fun startRemoteSession(baseUrl: String, minutes: Int, subject: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val cleanUrl = formatBaseUrl(baseUrl)
                val jsonBody = gson.toJson(mapOf("minutes" to minutes, "subject" to subject))
                val body = jsonBody.toRequestBody("application/json".toMediaType())

                val request = Request.Builder()
                    .url("$cleanUrl/api/session/start")
                    .post(body)
                    .build()

                client.newCall(request).execute().use { it.isSuccessful }
            } catch (e: Exception) {
                false
            }
        }
    }

    suspend fun stopRemoteSession(baseUrl: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val cleanUrl = formatBaseUrl(baseUrl)
                val body = "{}".toRequestBody("application/json".toMediaType())

                val request = Request.Builder()
                    .url("$cleanUrl/api/session/stop")
                    .post(body)
                    .build()

                client.newCall(request).execute().use { it.isSuccessful }
            } catch (e: Exception) {
                false
            }
        }
    }

    suspend fun markAttendedSchool(baseUrl: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val cleanUrl = formatBaseUrl(baseUrl)
                val body = "{}".toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url("$cleanUrl/api/attend_school")
                    .post(body)
                    .build()

                client.newCall(request).execute().use { it.isSuccessful }
            } catch (e: Exception) {
                false
            }
        }
    }

    fun startEventStream(baseUrl: String) {
        eventSource?.cancel()

        val cleanUrl = formatBaseUrl(baseUrl)
        val request = Request.Builder()
            .url("$cleanUrl/api/events")
            .build()

        val sseFactory = EventSources.createFactory(client)
        eventSource = sseFactory.newEventSource(request, object : EventSourceListener() {
            override fun onOpen(eventSource: EventSource, response: Response) {
                callback.onConnectionStatusChanged(true, "Live Stream Active")
            }

            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                when (type) {
                    "session_state", "session_started" -> {
                        try {
                            val session = gson.fromJson(data, ActiveSession::class.java)
                            callback.onSessionStateChanged(session)
                        } catch (e: Exception) { }
                    }
                    "session_tick" -> {
                        try {
                            val map = gson.fromJson(data, Map::class.java)
                            val rem = (map["remaining_seconds"] as? Number)?.toLong() ?: 0L
                            val subj = map["subject"] as? String ?: "#Focus"
                            callback.onSessionTick(rem, subj)
                        } catch (e: Exception) { }
                    }
                    "session_stopped", "session_ended" -> {
                        callback.onSessionStateChanged(ActiveSession(isActive = false))
                    }
                }
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                callback.onConnectionStatusChanged(false, "Sync stream interrupted")
            }

            override fun onClosed(eventSource: EventSource) {
                callback.onConnectionStatusChanged(false, "Sync stream closed")
            }
        })
    }

    fun stopEventStream() {
        eventSource?.cancel()
        eventSource = null
    }

    private fun formatBaseUrl(input: String): String {
        var url = input.trim()
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://$url"
        }
        if (url.endsWith("/")) {
            url = url.substring(0, url.length - 1)
        }
        return url
    }
}
