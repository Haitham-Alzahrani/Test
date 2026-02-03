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

    // The 3 pages the user described:
    // Page 1: Search form  (has "Search" button, route info, passenger, economy)
    // Page 2: Loading       (has "Finding the best flights")
    // Page 3: Results       (has flights with prices OR "No Flights Found")
    private enum class ScreenState {
        UNKNOWN,
        SEARCH_FORM,
        LOADING,
        NO_FLIGHTS,
        FLIGHT_RESULTS
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        addLog("Service connected")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isMonitoring = false
        stopAlarm()
        handler.removeCallbacksAndMessages(null)
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
        addLog("Waiting for flight app screen...")
        notifyStatusChanged()
        handler.postDelayed({ stepDetectAndAct() }, 2000)
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
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
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
    // MAIN LOOP
    // =========================================================================

    private fun stepDetectAndAct() {
        if (!isMonitoring) return

        val rootNode = rootInActiveWindow
        if (rootNode == null) {
            addLog("No window - waiting...")
            handler.postDelayed({ stepDetectAndAct() }, 2000)
            return
        }

        // Collect ALL text visible on screen
        val allText = collectAllText(rootNode)
        val joined = allText.joinToString(" ").lowercase()

        // Log a snippet for debugging
        addLog("TXT: ${joined.take(150)}")

        val state = detectScreen(joined, allText)
        addLog("=> $state")

        when (state) {
            ScreenState.SEARCH_FORM -> handleSearchForm(rootNode)
            ScreenState.LOADING -> handleLoading()
            ScreenState.NO_FLIGHTS -> handleNoFlights(rootNode)
            ScreenState.FLIGHT_RESULTS -> handleFlightResults()
            ScreenState.UNKNOWN -> handleUnknown()
        }
    }

    private fun handleSearchForm(rootNode: AccessibilityNodeInfo) {
        addLog("Page 1: Search form - clicking Search...")
        val clicked = clickSearchButton(rootNode)
        if (clicked) {
            searchCount++
            addLog("Clicked Search (#$searchCount)")
            notifyStatusChanged()
            // Page 2 (loading) appears - wait before checking
            handler.postDelayed({ stepDetectAndAct() }, 5000)
        } else {
            addLog("Search button click failed - retry")
            handler.postDelayed({ stepDetectAndAct() }, 2000)
        }
    }

    private fun handleLoading() {
        addLog("Page 2: Loading - waiting...")
        handler.postDelayed({ stepDetectAndAct() }, 3000)
    }

    private fun handleNoFlights(rootNode: AccessibilityNodeInfo) {
        lastResult = "No flights (#$searchCount)"
        addLog("Page 3: No flights - clicking New Search...")
        notifyStatusChanged()

        val clicked = clickNodeWithText(rootNode, "New Search")
        if (clicked) {
            addLog("Clicked New Search - waiting ${retryDelaySeconds}s")
            // Wait then re-detect (should be back on Page 1)
            handler.postDelayed({ stepDetectAndAct() }, retryDelaySeconds * 1000)
        } else {
            addLog("New Search click failed - retry")
            handler.postDelayed({ stepDetectAndAct() }, 2000)
        }
    }

    private fun handleFlightResults() {
        addLog("*** FLIGHTS AVAILABLE! ***")
        lastResult = "FLIGHTS AVAILABLE!"
        notifyStatusChanged()
        triggerAlarm()
        // Stop looping - alarm rings until user stops it
    }

    private fun handleUnknown() {
        // NOT the flight app, or transitional screen
        // NEVER trigger alarm - just wait patiently
        addLog("Not on flight app - waiting...")
        handler.postDelayed({ stepDetectAndAct() }, 3000)
    }

    // =========================================================================
    // SCREEN DETECTION
    //
    // The logic ONLY identifies screens it RECOGNIZES.
    // Anything it doesn't recognize => UNKNOWN => wait (no alarm).
    //
    // Flight results require STRONG positive evidence (price in SAR).
    // =========================================================================

    private fun detectScreen(screenText: String, allText: List<String>): ScreenState {

        // --- Page 2: Loading ---
        // Screenshot shows: "Finding the best flights for you"
        if (screenText.contains("finding the best flights") ||
            screenText.contains("finding the best")) {
            return ScreenState.LOADING
        }

        // --- Page 3a: No Flights Found ---
        // Screenshot shows: "No Flights Found", "couldn't find any flights"
        if (screenText.contains("no flights found") ||
            screenText.contains("no flights") ||
            screenText.contains("couldn't find any flights")) {
            return ScreenState.NO_FLIGHTS
        }

        // --- Page 1: Search Form ---
        // Screenshot shows: "RUH - Riyadh", "NUM - NEOM", "Passenger",
        //   "Economy", "Business", "Round trip", "One way", "Search" button
        //   "Monthly Tickets", "Discounted Tickets"
        val isSearchForm = hasSearchFormIndicators(screenText, allText)
        if (isSearchForm) {
            return ScreenState.SEARCH_FORM
        }

        // --- "New Search" button visible (fallback for No Flights page) ---
        // If we see "New Search" text, it's the No Flights page even if
        // we couldn't read the "No Flights Found" text
        if (allText.any { it.contains("New Search", ignoreCase = true) }) {
            return ScreenState.NO_FLIGHTS
        }

        // --- Page 3b: Flight Results (flights actually found) ---
        // This is the screen we've NEVER seen (user always gets "No Flights").
        // We require STRONG positive evidence: a price in SAR.
        // This avoids false positives from home screen, app drawer, etc.
        val hasFlightResults = hasFlightResultIndicators(screenText, allText)
        if (hasFlightResults) {
            return ScreenState.FLIGHT_RESULTS
        }

        // --- Anything else: UNKNOWN ---
        // Home screen, app drawer, other apps, transition screens, etc.
        // NEVER alarm on unknown.
        return ScreenState.UNKNOWN
    }

    private fun hasSearchFormIndicators(screenText: String, allText: List<String>): Boolean {
        // Must have a "Search" button (exact text, not "New Search")
        val hasSearchButton = allText.any {
            it.equals("Search", ignoreCase = true)
        }
        if (!hasSearchButton) return false

        // Must also have at least one of the form elements from the screenshot
        val formIndicators = listOf(
            "ruh", "riyadh", "num", "neom",           // route
            "passenger", "passengers",                  // passenger count
            "economy", "business",                      // class
            "round trip", "one way",                    // trip type
            "monthly ticket", "discounted ticket",      // travel purpose
            "departure", "select a departure",          // header
            "travel purpose", "legs"                    // sections
        )
        return formIndicators.any { screenText.contains(it) }
    }

    private fun hasFlightResultIndicators(screenText: String, allText: List<String>): Boolean {
        // Based on actual flight results screenshot:
        //   - "Edit search" button (NOT "Search" alone, NOT "New Search")
        //   - Airline name: "Saudia"
        //   - Flight number: "SV1558" (pattern: 2 letters + digits)
        //   - "Non-stop" or "1 stop" etc.
        //   - Price: "963.7" (just a number, no SAR text)
        //   - Times: "18:25", "20:25"
        //
        // We require "Edit search" (unique to results page) AND at least
        // one flight-specific indicator.

        // Safety: must NOT be on search form or no-flights page
        if (screenText.contains("no flights found")) return false
        if (screenText.contains("finding the best flights")) return false

        // PRIMARY indicator: "Edit search" is ONLY on the results page
        val hasEditSearch = screenText.contains("edit search")

        // SECONDARY indicators (need at least 2 to confirm):
        var score = 0

        // Airline name
        if (screenText.contains("saudia") || screenText.contains("flynas") ||
            screenText.contains("flyadeal")) score++

        // Flight number pattern (SV1558, XY123, etc.)
        if (Regex("\\b[a-z]{2}\\d{3,4}\\b", RegexOption.IGNORE_CASE).containsMatchIn(screenText)) score++

        // "Non-stop" or "X stop" with duration
        if (screenText.contains("non-stop") || screenText.contains("nonstop") ||
            Regex("\\d+\\s*stop", RegexOption.IGNORE_CASE).containsMatchIn(screenText)) score++

        // Time pattern HH:MM (like 18:25, 20:25)
        if (Regex("\\b\\d{1,2}:\\d{2}\\b").containsMatchIn(screenText)) score++

        // Price pattern (decimal number like 963.7, 1200.0)
        if (Regex("\\b\\d{3,}(\\.\\d)?\\b").containsMatchIn(screenText)) score++

        // SAR text (if present)
        if (screenText.contains("sar") || screenText.contains("sr ") ||
            Regex("\\d+\\s*sar", RegexOption.IGNORE_CASE).containsMatchIn(screenText)) score++

        // "Edit search" + any 1 flight indicator = CONFIRMED
        if (hasEditSearch && score >= 1) return true

        // No "Edit search" but 3+ strong indicators = also confirmed
        if (score >= 3) return true

        return false
    }

    // =========================================================================
    // CLICK: Find "Search" button specifically
    // Must be exact "Search" text, not "New Search" or "flight search alert"
    // =========================================================================

    private fun clickSearchButton(root: AccessibilityNodeInfo): Boolean {
        val allNodes = mutableListOf<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)

        // Find nodes where text is exactly "Search" (not "New Search", not "Flight Search Alert")
        for (node in allNodes) {
            val text = node.text?.toString()?.trim() ?: ""
            val desc = node.contentDescription?.toString()?.trim() ?: ""

            val isExactSearch = text.equals("Search", ignoreCase = true) ||
                    desc.equals("Search", ignoreCase = true)

            val isNotNewSearch = !text.contains("New", ignoreCase = true) &&
                    !desc.contains("New", ignoreCase = true) &&
                    !text.contains("Alert", ignoreCase = true) &&
                    !desc.contains("Alert", ignoreCase = true) &&
                    !text.contains("Flight Search", ignoreCase = true) &&
                    !desc.contains("Flight Search", ignoreCase = true)

            if (isExactSearch && isNotNewSearch) {
                addLog("Found Search node: text='$text' desc='$desc'")
                if (tryClickNode(node)) return true
            }
        }

        // Also try findAccessibilityNodeInfosByText as backup
        val nodes = root.findAccessibilityNodeInfosByText("Search")
        for (node in nodes) {
            val text = node.text?.toString()?.trim() ?: ""
            val desc = node.contentDescription?.toString()?.trim() ?: ""
            if (text.contains("New", ignoreCase = true) ||
                desc.contains("New", ignoreCase = true) ||
                text.contains("Alert", ignoreCase = true) ||
                desc.contains("Alert", ignoreCase = true)) {
                continue
            }
            addLog("Found Search via API: text='$text'")
            if (tryClickNode(node)) return true
        }

        return false
    }

    // =========================================================================
    // CLICK: Generic node by text
    // =========================================================================

    private fun clickNodeWithText(root: AccessibilityNodeInfo, targetText: String): Boolean {
        // Try API search first
        val nodes = root.findAccessibilityNodeInfosByText(targetText)
        for (node in nodes) {
            if (tryClickNode(node)) return true
        }

        // Walk tree
        val allNodes = mutableListOf<AccessibilityNodeInfo>()
        collectAllNodes(root, allNodes)
        for (node in allNodes) {
            val text = node.text?.toString() ?: ""
            val desc = node.contentDescription?.toString() ?: ""
            if (text.contains(targetText, ignoreCase = true) ||
                desc.contains(targetText, ignoreCase = true)) {
                if (tryClickNode(node)) return true
            }
        }

        return false
    }

    // =========================================================================
    // CLICK: Try all methods to click a node
    // =========================================================================

    private fun tryClickNode(node: AccessibilityNodeInfo): Boolean {
        // 1. Direct click
        if (node.isClickable) {
            addLog("Direct click")
            node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            return true
        }

        // 2. Click parent chain (button might wrap a text view)
        var parent = node.parent
        var depth = 0
        while (parent != null && depth < 6) {
            if (parent.isClickable) {
                addLog("Parent click (depth=$depth)")
                parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                return true
            }
            parent = parent.parent
            depth++
        }

        // 3. Gesture tap at the node's screen coordinates
        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() > 10 && rect.height() > 10) {
            addLog("Gesture tap at (${rect.centerX()}, ${rect.centerY()})")
            tapAt(rect.centerX().toFloat(), rect.centerY().toFloat())
            return true
        }

        return false
    }

    // =========================================================================
    // Helpers
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

    private fun collectAllNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        list.add(node)
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectAllNodes(child, list)
        }
    }

    private fun tapAt(x: Float, y: Float) {
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 150))
            .build()
        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                addLog("Tap OK at ($x, $y)")
            }
            override fun onCancelled(gestureDescription: GestureDescription?) {
                addLog("Tap FAILED at ($x, $y)")
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
            audioManager.setStreamVolume(
                AudioManager.STREAM_ALARM,
                audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM),
                0
            )
        } catch (e: Exception) {
            addLog("Alarm error: ${e.message}")
        }
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(VIBRATOR_SERVICE) as Vibrator
            }
            vibrator.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 1000, 500, 1000, 500, 1000), 0))
        } catch (e: Exception) {
            addLog("Vibrate error: ${e.message}")
        }
        notifyStatusChanged()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() { addLog("Service interrupted") }

    private fun addLog(message: String) {
        val ts = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        logMessages.add(0, "[$ts] $message")
        if (logMessages.size > 200) logMessages.removeAt(logMessages.size - 1)
        Log.d(TAG, message)
    }

    private fun notifyStatusChanged() {
        handler.post { onStatusChanged?.invoke() }
    }
}
