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

        var onStatusChanged: (() -> Unit)? = null
    }

    private val handler = Handler(Looper.getMainLooper())
    private var mediaPlayer: MediaPlayer? = null
    private var retryDelaySeconds = 5L

    // Screen state detection
    private enum class ScreenState {
        UNKNOWN,
        SEARCH_FORM,       // The main search form with "Search" button
        LOADING,            // "Finding the best flights for you"
        NO_FLIGHTS,         // "No Flights Found" screen
        FLIGHT_RESULTS      // Actual flight results are shown
    }

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
        addLog("Started - delay: ${retryDelaySeconds}s")
        addLog("Switch to the flight app now!")
        notifyStatusChanged()

        // Give user time to switch to the flight app
        handler.postDelayed({ stepDetectAndAct() }, 3000)
    }

    private fun stopMonitoring() {
        isMonitoring = false
        handler.removeCallbacksAndMessages(null)
        addLog("Stopped")
        notifyStatusChanged()
    }

    fun stopAlarm() {
        mediaPlayer?.let {
            try { if (it.isPlaying) it.stop() } catch (_: Exception) {}
            try { it.release() } catch (_: Exception) {}
        }
        mediaPlayer = null
        isAlarmPlaying = false

        // Stop vibration
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(VIBRATOR_SERVICE) as Vibrator
            }
            vibrator.cancel()
        } catch (_: Exception) {}

        addLog("Alarm stopped")
        notifyStatusChanged()
    }

    // =========================================================================
    // MAIN LOOP: detect current screen state, then act accordingly
    // =========================================================================

    private fun stepDetectAndAct() {
        if (!isMonitoring) return

        val rootNode = rootInActiveWindow
        if (rootNode == null) {
            addLog("Cannot access window - retrying...")
            handler.postDelayed({ stepDetectAndAct() }, 2000)
            return
        }

        // Collect all visible text on screen
        val allText = collectAllText(rootNode)
        val screenText = allText.joinToString(" ").lowercase()

        // Log screen text for debugging (first time and periodically)
        addLog("Screen: ${screenText.take(120)}...")

        // Detect what screen we're on
        val state = detectScreenState(screenText, allText)
        addLog("Detected: $state")

        when (state) {
            ScreenState.SEARCH_FORM -> {
                // We're on the search form - click "Search"
                addLog("Clicking Search button...")
                val clicked = clickNodeWithText(rootNode, "Search")
                if (clicked) {
                    searchCount++
                    addLog("Clicked Search (#$searchCount)")
                    notifyStatusChanged()
                    // Wait for loading/results
                    handler.postDelayed({ stepDetectAndAct() }, 6000)
                } else {
                    addLog("Could not click Search - retrying")
                    handler.postDelayed({ stepDetectAndAct() }, 3000)
                }
            }

            ScreenState.LOADING -> {
                // Still loading, wait and check again
                addLog("Loading... waiting")
                handler.postDelayed({ stepDetectAndAct() }, 3000)
            }

            ScreenState.NO_FLIGHTS -> {
                // No flights found - click "New Search" to go back
                addLog("No flights found - clicking New Search")
                lastResult = "No flights (#$searchCount)"
                notifyStatusChanged()

                val clicked = clickNodeWithText(rootNode, "New Search")
                if (clicked) {
                    addLog("Clicked New Search, waiting ${retryDelaySeconds}s...")
                    handler.postDelayed({ stepDetectAndAct() }, retryDelaySeconds * 1000)
                } else {
                    addLog("New Search not clickable, retrying...")
                    handler.postDelayed({ stepDetectAndAct() }, 3000)
                }
            }

            ScreenState.FLIGHT_RESULTS -> {
                // FLIGHTS FOUND!
                addLog("*** FLIGHTS AVAILABLE! ***")
                lastResult = "FLIGHTS AVAILABLE!"
                notifyStatusChanged()
                triggerAlarm()
                // Stop the loop - alarm will keep ringing
            }

            ScreenState.UNKNOWN -> {
                // Can't determine screen - DON'T trigger alarm
                // Just wait and try again
                addLog("Unknown screen state - waiting...")
                handler.postDelayed({ stepDetectAndAct() }, 3000)
            }
        }
    }

    // =========================================================================
    // Screen state detection - uses ALL visible text to determine what screen
    // =========================================================================

    private fun detectScreenState(screenText: String, allText: List<String>): ScreenState {
        // 1. Check for loading screen
        if (screenText.contains("finding the best flights") ||
            screenText.contains("finding the best") ||
            (screenText.contains("finding") && screenText.contains("flights"))) {
            return ScreenState.LOADING
        }

        // 2. Check for "No Flights Found" screen
        if (screenText.contains("no flights found") ||
            screenText.contains("no flights") ||
            (screenText.contains("couldn't find any flights") || screenText.contains("could not find any flights"))) {
            return ScreenState.NO_FLIGHTS
        }

        // 3. Check for search form (has the Search button AND route fields)
        //    The search form typically shows: route, date, passenger count, class, and a Search button
        val hasSearchButton = allText.any { it.equals("Search", ignoreCase = true) }
        val hasRouteInfo = screenText.contains("ruh") || screenText.contains("riyadh")
        val hasFormElements = screenText.contains("passenger") || screenText.contains("economy") ||
                screenText.contains("business") || screenText.contains("round trip") ||
                screenText.contains("one way")

        if (hasSearchButton && (hasRouteInfo || hasFormElements)) {
            return ScreenState.SEARCH_FORM
        }

        // 4. Check for flight results - POSITIVE detection only
        //    Flight results typically show: prices (SAR), times, flight numbers, "Select", "Book"
        val hasPrice = screenText.contains("sar") ||
                Regex("\\d{2,4}[.,]?\\d{0,2}\\s*(sar|sr|ر\\.س)").containsMatchIn(screenText) ||
                allText.any { it.matches(Regex(".*\\d{3,}.*")) && (it.contains("SAR") || it.contains("SR")) }

        val hasFlightIndicators = screenText.contains("select") ||
                screenText.contains("book") ||
                screenText.contains("depart") ||
                screenText.contains("arrive") ||
                screenText.contains("direct") ||
                screenText.contains("stop") ||
                screenText.contains("duration") ||
                (screenText.contains("am") || screenText.contains("pm")) &&
                Regex("\\d{1,2}:\\d{2}").containsMatchIn(screenText)

        if (hasPrice || hasFlightIndicators) {
            return ScreenState.FLIGHT_RESULTS
        }

        // 5. If we see "New Search" without "No Flights Found", might be a variant
        val hasNewSearch = allText.any {
            it.equals("New Search", ignoreCase = true) ||
                    it.contains("New Search")
        }
        if (hasNewSearch) {
            // "New Search" button exists but we didn't detect "No Flights" text
            // This is likely the No Flights screen with text we couldn't read
            return ScreenState.NO_FLIGHTS
        }

        // Can't determine - return UNKNOWN (will NOT trigger alarm)
        return ScreenState.UNKNOWN
    }

    // =========================================================================
    // Collect all visible text from the accessibility tree
    // =========================================================================

    private fun collectAllText(root: AccessibilityNodeInfo): List<String> {
        val texts = mutableListOf<String>()
        collectTextFromNode(root, texts)
        return texts
    }

    private fun collectTextFromNode(node: AccessibilityNodeInfo, texts: MutableList<String>) {
        node.text?.toString()?.let { if (it.isNotBlank()) texts.add(it) }
        node.contentDescription?.toString()?.let { if (it.isNotBlank()) texts.add(it) }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectTextFromNode(child, texts)
        }
    }

    // =========================================================================
    // Click a node that contains the given text
    // Uses both performAction and gesture tap for reliability
    // =========================================================================

    private fun clickNodeWithText(root: AccessibilityNodeInfo, targetText: String): Boolean {
        // Strategy 1: findAccessibilityNodeInfosByText + click/tap
        val nodes = root.findAccessibilityNodeInfosByText(targetText)
        for (node in nodes) {
            val nodeText = node.text?.toString() ?: node.contentDescription?.toString() ?: ""

            // For "Search" button, avoid matching "New Search" or partial matches
            if (targetText.equals("Search", ignoreCase = true) &&
                nodeText.contains("New", ignoreCase = true)) {
                continue
            }

            if (tryClickNode(node)) return true
        }

        // Strategy 2: Walk the entire tree and find exact match
        val allNodes = mutableListOf<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)

        for (node in allNodes) {
            val text = node.text?.toString() ?: ""
            val desc = node.contentDescription?.toString() ?: ""

            val matches = when {
                targetText.equals("Search", ignoreCase = true) ->
                    (text.equals("Search", ignoreCase = true) || desc.equals("Search", ignoreCase = true)) &&
                            !text.contains("New", ignoreCase = true) && !desc.contains("New", ignoreCase = true)
                else ->
                    text.contains(targetText, ignoreCase = true) || desc.contains(targetText, ignoreCase = true)
            }

            if (matches) {
                if (tryClickNode(node)) return true
            }
        }

        return false
    }

    private fun tryClickNode(node: AccessibilityNodeInfo): Boolean {
        // Try direct click first
        if (node.isClickable) {
            node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            return true
        }

        // Try clicking parent chain
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

        // Fallback: gesture tap at node center
        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() > 0 && rect.height() > 0) {
            addLog("Tapping at (${rect.centerX()}, ${rect.centerY()})")
            tapAt(rect.centerX().toFloat(), rect.centerY().toFloat())
            return true
        }

        return false
    }

    private fun collectAllNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        list.add(node)
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectAllNodes(child, list)
        }
    }

    // =========================================================================
    // Gesture tap
    // =========================================================================

    private fun tapAt(x: Float, y: Float) {
        val path = Path()
        path.moveTo(x, y)

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 150))
            .build()

        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Tap completed at ($x, $y)")
            }
            override fun onCancelled(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Tap cancelled at ($x, $y)")
                addLog("Tap cancelled at ($x, $y)")
            }
        }, null)
    }

    // =========================================================================
    // Alarm
    // =========================================================================

    private fun triggerAlarm() {
        addLog("TRIGGERING ALARM!")

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

            val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
            val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
            audioManager.setStreamVolume(AudioManager.STREAM_ALARM, maxVolume, 0)

        } catch (e: Exception) {
            addLog("Alarm error: ${e.message}")
            Log.e(TAG, "Alarm error", e)
        }

        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(VIBRATOR_SERVICE) as Vibrator
            }
            val pattern = longArrayOf(0, 1000, 500, 1000, 500, 1000)
            vibrator.vibrate(VibrationEffect.createWaveform(pattern, 0))
        } catch (e: Exception) {
            addLog("Vibrate error: ${e.message}")
        }

        notifyStatusChanged()
    }

    // =========================================================================
    // Accessibility event (unused - we use polling)
    // =========================================================================

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {
        addLog("Service interrupted")
    }

    // =========================================================================
    // Logging
    // =========================================================================

    private fun addLog(message: String) {
        val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        val timestamp = timeFormat.format(Date())
        val logEntry = "[$timestamp] $message"
        logMessages.add(0, logEntry)
        if (logMessages.size > 200) {
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
