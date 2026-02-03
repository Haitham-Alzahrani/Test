package com.flightalert.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class FlightSearchService : AccessibilityService() {

    companion object {
        const val TAG = "FlightSearchService"
        const val ACTION_START = "com.flightalert.app.ACTION_START"
        const val ACTION_STOP = "com.flightalert.app.ACTION_STOP"
        const val ACTION_STOP_ALARM = "com.flightalert.app.ACTION_STOP_ALARM"
        const val EXTRA_DELAY = "extra_delay"

        var instance: FlightSearchService? = null
        var isMonitoring = false
        var searchCount = 0
        var lastResult = "-"
        var logMessages = mutableListOf<String>()
        var isAlarmPlaying = false

        // Callbacks for UI updates
        var onStatusChanged: (() -> Unit)? = null
    }

    private val handler = Handler(Looper.getMainLooper())
    private var mediaPlayer: MediaPlayer? = null
    private var retryDelaySeconds = 5L
    private var isSearching = false
    private var isWaitingForResults = false
    // alarmPlaying is tracked in companion object as isAlarmPlaying

    // State machine
    private enum class State {
        IDLE,
        CLICKING_SEARCH,
        WAITING_FOR_LOADING,
        CHECKING_RESULTS,
        CLICKING_NEW_SEARCH,
        WAITING_BEFORE_RETRY,
        FLIGHT_FOUND
    }

    private var currentState = State.IDLE

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        addLog("Service connected")
        Log.d(TAG, "Accessibility service connected")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isMonitoring = false
        stopAlarm()
        handler.removeCallbacksAndMessages(null)
        addLog("Service destroyed")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                retryDelaySeconds = intent.getLongExtra(EXTRA_DELAY, 5L)
                startMonitoring()
            }
            ACTION_STOP -> stopMonitoring()
            ACTION_STOP_ALARM -> stopAlarm()
        }
        return super.onStartCommand(intent, flags, startId)
    }

    private fun startMonitoring() {
        isMonitoring = true
        searchCount = 0
        lastResult = "-"
        logMessages.clear()
        currentState = State.CLICKING_SEARCH
        addLog("Monitoring started - delay: ${retryDelaySeconds}s")
        notifyStatusChanged()

        // Start the search cycle with a short initial delay
        handler.postDelayed({ performSearchCycle() }, 1500)
    }

    private fun stopMonitoring() {
        isMonitoring = false
        currentState = State.IDLE
        isSearching = false
        isWaitingForResults = false
        handler.removeCallbacksAndMessages(null)
        addLog("Monitoring stopped")
        notifyStatusChanged()
    }

    fun stopAlarm() {
        mediaPlayer?.let {
            if (it.isPlaying) {
                it.stop()
            }
            it.release()
        }
        mediaPlayer = null
        isAlarmPlaying = false
        addLog("Alarm stopped")
        notifyStatusChanged()
    }

    private fun performSearchCycle() {
        if (!isMonitoring) return

        addLog("Looking for Search button...")
        currentState = State.CLICKING_SEARCH

        val rootNode = rootInActiveWindow ?: run {
            addLog("Cannot access window - retrying...")
            handler.postDelayed({ performSearchCycle() }, 2000)
            return
        }

        // Try to find and click "Search" button
        if (findAndClickButton(rootNode, "Search", "search")) {
            searchCount++
            addLog("Clicked Search (#$searchCount)")
            currentState = State.WAITING_FOR_LOADING
            notifyStatusChanged()

            // Wait for loading and then check results
            handler.postDelayed({ waitAndCheckResults() }, 5000)
        } else {
            addLog("Search button not found - retrying...")
            handler.postDelayed({ performSearchCycle() }, 2000)
        }

        rootNode.recycle()
    }

    private fun waitAndCheckResults() {
        if (!isMonitoring) return

        addLog("Checking results...")
        currentState = State.CHECKING_RESULTS

        // Poll for results - check multiple times as page may still be loading
        checkResultsWithRetry(0)
    }

    private fun checkResultsWithRetry(attempt: Int) {
        if (!isMonitoring) return
        if (attempt > 10) {
            // After 10 attempts (20 seconds), assume loading issue and retry
            addLog("Timeout waiting for results - retrying search")
            retrySearch()
            return
        }

        val rootNode = rootInActiveWindow ?: run {
            handler.postDelayed({ checkResultsWithRetry(attempt + 1) }, 2000)
            return
        }

        // Check if still loading (look for "Finding the best flights" text)
        if (findTextInTree(rootNode, "Finding the best flights") ||
            findTextInTree(rootNode, "Finding") ||
            findTextInTree(rootNode, "Loading")) {
            addLog("Still loading... (attempt ${attempt + 1})")
            rootNode.recycle()
            handler.postDelayed({ checkResultsWithRetry(attempt + 1) }, 2000)
            return
        }

        // Check for "No Flights Found"
        if (findTextInTree(rootNode, "No Flights Found") ||
            findTextInTree(rootNode, "No flights found") ||
            findTextInTree(rootNode, "no flights")) {
            addLog("No flights found")
            lastResult = "No flights found"
            currentState = State.CLICKING_NEW_SEARCH
            notifyStatusChanged()
            rootNode.recycle()

            // Click "New Search" button
            handler.postDelayed({ clickNewSearchAndRetry() }, 1000)
            return
        }

        // Check if we're still on search page (search button visible means we haven't searched yet)
        if (findButtonInTree(rootNode, "Search") != null &&
            !findTextInTree(rootNode, "No Flights") &&
            attempt < 3) {
            // Might still be on search page, wait more
            rootNode.recycle()
            handler.postDelayed({ checkResultsWithRetry(attempt + 1) }, 2000)
            return
        }

        // If we don't see "No Flights Found" and we're not loading, flights might be available!
        // Check for typical flight result indicators
        if (findTextInTree(rootNode, "No Flights Found") ||
            findTextInTree(rootNode, "No flights")) {
            rootNode.recycle()
            lastResult = "No flights found"
            handler.postDelayed({ clickNewSearchAndRetry() }, 1000)
            return
        }

        // If we got past loading and don't see "No Flights Found", FLIGHTS ARE AVAILABLE!
        addLog("*** FLIGHTS FOUND! ***")
        lastResult = "FLIGHTS AVAILABLE!"
        currentState = State.FLIGHT_FOUND
        notifyStatusChanged()
        rootNode.recycle()

        triggerAlarm()
    }

    private fun clickNewSearchAndRetry() {
        if (!isMonitoring) return

        val rootNode = rootInActiveWindow ?: run {
            addLog("Cannot access window for New Search")
            handler.postDelayed({ clickNewSearchAndRetry() }, 2000)
            return
        }

        // Try to click "New Search" button
        if (findAndClickButton(rootNode, "New Search", "new_search") ||
            findAndClickButton(rootNode, "New search", "new_search") ||
            findAndClickButton(rootNode, "new search", "new_search")) {
            addLog("Clicked New Search")
            currentState = State.WAITING_BEFORE_RETRY
            notifyStatusChanged()
            rootNode.recycle()

            // Wait for the search page to load, then search again
            addLog("Waiting ${retryDelaySeconds}s before next search...")
            handler.postDelayed({ performSearchCycle() }, retryDelaySeconds * 1000)
        } else {
            addLog("New Search button not found - trying tap approach")
            rootNode.recycle()
            // Try tapping approximate location of "New Search" button based on screenshots
            // The button appears to be roughly in the center-bottom area of the screen
            tryTapNewSearchByLocation()
        }
    }

    private fun tryTapNewSearchByLocation() {
        if (!isMonitoring) return

        val rootNode = rootInActiveWindow
        if (rootNode != null) {
            // Try finding any clickable node with relevant text
            val allNodes = getAllNodes(rootNode)
            for (node in allNodes) {
                val text = node.text?.toString()?.lowercase() ?: ""
                val desc = node.contentDescription?.toString()?.lowercase() ?: ""
                if ((text.contains("new") && text.contains("search")) ||
                    (desc.contains("new") && desc.contains("search"))) {
                    val rect = Rect()
                    node.getBoundsInScreen(rect)
                    addLog("Found New Search at: $rect - tapping")
                    tapAt(rect.centerX().toFloat(), rect.centerY().toFloat())
                    rootNode.recycle()
                    handler.postDelayed({ performSearchCycle() }, retryDelaySeconds * 1000)
                    return
                }
            }
            rootNode.recycle()
        }

        // If still can't find it, just wait and retry the whole cycle
        addLog("Could not find New Search - retrying cycle")
        handler.postDelayed({ performSearchCycle() }, retryDelaySeconds * 1000)
    }

    private fun retrySearch() {
        if (!isMonitoring) return
        addLog("Retrying search cycle...")
        handler.postDelayed({ performSearchCycle() }, retryDelaySeconds * 1000)
    }

    private fun triggerAlarm() {
        addLog("TRIGGERING ALARM!")

        // Play alarm sound
        try {
            val alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build()
                )
                setDataSource(this@FlightSearchService, alarmUri)
                isLooping = true
                prepare()
                start()
            }
            isAlarmPlaying = true

            // Set volume to max
            val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
            val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
            audioManager.setStreamVolume(AudioManager.STREAM_ALARM, maxVolume, 0)

        } catch (e: Exception) {
            addLog("Error playing alarm: ${e.message}")
            Log.e(TAG, "Alarm error", e)
        }

        // Vibrate
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vibratorManager.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(VIBRATOR_SERVICE) as Vibrator
            }

            val pattern = longArrayOf(0, 1000, 500, 1000, 500, 1000)
            vibrator.vibrate(VibrationEffect.createWaveform(pattern, 0))
        } catch (e: Exception) {
            addLog("Error vibrating: ${e.message}")
        }

        notifyStatusChanged()
    }

    // --- Helper methods ---

    private fun findAndClickButton(root: AccessibilityNodeInfo, text: String, fallbackId: String): Boolean {
        // First try by text
        val nodesByText = root.findAccessibilityNodeInfosByText(text)
        for (node in nodesByText) {
            if (node.isClickable) {
                node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                return true
            }
            // Try clicking parent if node itself isn't clickable
            var parent = node.parent
            var depth = 0
            while (parent != null && depth < 5) {
                if (parent.isClickable) {
                    parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    return true
                }
                parent = parent.parent
                depth++
            }
        }

        // Try by content description
        val allNodes = getAllNodes(root)
        for (node in allNodes) {
            val nodeText = node.text?.toString() ?: ""
            val contentDesc = node.contentDescription?.toString() ?: ""
            if (nodeText.equals(text, ignoreCase = true) ||
                contentDesc.equals(text, ignoreCase = true)) {
                if (node.isClickable) {
                    node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                    return true
                }
                // Try tapping the coordinates
                val rect = Rect()
                node.getBoundsInScreen(rect)
                if (rect.width() > 0 && rect.height() > 0) {
                    tapAt(rect.centerX().toFloat(), rect.centerY().toFloat())
                    return true
                }
            }
        }

        return false
    }

    private fun findButtonInTree(root: AccessibilityNodeInfo, text: String): AccessibilityNodeInfo? {
        val nodes = root.findAccessibilityNodeInfosByText(text)
        return nodes.firstOrNull()
    }

    private fun findTextInTree(root: AccessibilityNodeInfo, text: String): Boolean {
        val nodes = root.findAccessibilityNodeInfosByText(text)
        if (nodes.isNotEmpty()) return true

        // Also do a manual DFS check
        return searchTreeForText(root, text.lowercase())
    }

    private fun searchTreeForText(node: AccessibilityNodeInfo, lowerText: String): Boolean {
        val nodeText = node.text?.toString()?.lowercase() ?: ""
        val contentDesc = node.contentDescription?.toString()?.lowercase() ?: ""
        if (nodeText.contains(lowerText) || contentDesc.contains(lowerText)) {
            return true
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            if (searchTreeForText(child, lowerText)) return true
        }
        return false
    }

    private fun getAllNodes(root: AccessibilityNodeInfo): List<AccessibilityNodeInfo> {
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        collectNodes(root, nodes)
        return nodes
    }

    private fun collectNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        list.add(node)
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectNodes(child, list)
        }
    }

    private fun tapAt(x: Float, y: Float) {
        val path = Path()
        path.moveTo(x, y)

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()

        dispatchGesture(gesture, null, null)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // We handle everything through the handler-based polling approach
        // This callback is required but we don't need it for our state machine
    }

    override fun onInterrupt() {
        addLog("Service interrupted")
        Log.d(TAG, "Service interrupted")
    }

    private fun addLog(message: String) {
        val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        val timestamp = timeFormat.format(Date())
        val logEntry = "[$timestamp] $message"
        logMessages.add(0, logEntry) // Add to beginning
        if (logMessages.size > 100) {
            logMessages.removeAt(logMessages.size - 1)
        }
        Log.d(TAG, message)
    }

    private fun notifyStatusChanged() {
        handler.post {
            onStatusChanged?.invoke()
        }
    }
}
