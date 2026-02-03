package com.flightalert.app

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton

class MainActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvSearchCount: TextView
    private lateinit var tvLastResult: TextView
    private lateinit var tvLog: TextView
    private lateinit var tvDelay: TextView
    private lateinit var btnToggle: MaterialButton
    private lateinit var btnEnableService: MaterialButton
    private lateinit var btnStopAlarm: MaterialButton
    private lateinit var seekDelay: SeekBar
    private lateinit var statusIndicator: android.view.View

    private var delaySeconds = 5

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupListeners()
        setupStatusCallback()
        updateUI()

        // Request notification permission on Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    override fun onResume() {
        super.onResume()
        updateUI()
    }

    private fun initViews() {
        tvStatus = findViewById(R.id.tvStatus)
        tvSearchCount = findViewById(R.id.tvSearchCount)
        tvLastResult = findViewById(R.id.tvLastResult)
        tvLog = findViewById(R.id.tvLog)
        tvDelay = findViewById(R.id.tvDelay)
        btnToggle = findViewById(R.id.btnToggle)
        btnEnableService = findViewById(R.id.btnEnableService)
        btnStopAlarm = findViewById(R.id.btnStopAlarm)
        seekDelay = findViewById(R.id.seekDelay)
        statusIndicator = findViewById(R.id.statusIndicator)
    }

    private fun setupListeners() {
        btnEnableService.setOnClickListener {
            // Open Accessibility settings
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
            Toast.makeText(this, "Enable 'Flight Search Alert' in the list", Toast.LENGTH_LONG).show()
        }

        btnToggle.setOnClickListener {
            if (!isAccessibilityServiceEnabled()) {
                Toast.makeText(this, getString(R.string.service_not_enabled), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }

            if (FlightSearchService.isMonitoring) {
                // Stop
                val intent = Intent(this, FlightSearchService::class.java).apply {
                    action = FlightSearchService.ACTION_STOP
                }
                startService(intent)
            } else {
                // Start
                val intent = Intent(this, FlightSearchService::class.java).apply {
                    action = FlightSearchService.ACTION_START
                    putExtra(FlightSearchService.EXTRA_DELAY, delaySeconds.toLong())
                }
                startService(intent)
                Toast.makeText(this, "Switch to the flight app now!", Toast.LENGTH_SHORT).show()
            }
            updateUI()
        }

        btnStopAlarm.setOnClickListener {
            FlightSearchService.instance?.stopAlarm()
            updateUI()
        }

        seekDelay.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                delaySeconds = progress.coerceAtLeast(3)
                tvDelay.text = "${delaySeconds}s"
            }

            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })
    }

    private fun setupStatusCallback() {
        FlightSearchService.onStatusChanged = {
            runOnUiThread { updateUI() }
        }
    }

    private fun updateUI() {
        val isRunning = FlightSearchService.isMonitoring
        val serviceEnabled = isAccessibilityServiceEnabled()

        // Update status text
        tvStatus.text = when {
            !serviceEnabled -> "Status: Service not enabled"
            isRunning -> getString(R.string.status_running)
            else -> getString(R.string.status_idle)
        }

        // Update status indicator color
        val indicatorDrawable = statusIndicator.background as? GradientDrawable
        val color = when {
            !serviceEnabled -> 0xFF999999.toInt()
            isRunning -> ContextCompat.getColor(this, R.color.green_active)
            else -> 0xFF999999.toInt()
        }
        indicatorDrawable?.setColor(color)

        // Update search count
        tvSearchCount.text = getString(R.string.search_count, FlightSearchService.searchCount)

        // Update last result
        tvLastResult.text = "Last result: ${FlightSearchService.lastResult}"
        if (FlightSearchService.lastResult.contains("AVAILABLE")) {
            tvLastResult.setTextColor(ContextCompat.getColor(this, R.color.green_active))
        } else {
            tvLastResult.setTextColor(ContextCompat.getColor(this, R.color.gray_text))
        }

        // Update button
        btnToggle.text = if (isRunning) getString(R.string.stop_monitoring) else getString(R.string.start_monitoring)
        btnToggle.backgroundTintList = ContextCompat.getColorStateList(
            this,
            if (isRunning) R.color.red_alert else R.color.gold
        )

        // Show/hide stop alarm button
        btnStopAlarm.visibility = if (FlightSearchService.isAlarmPlaying) {
            android.view.View.VISIBLE
        } else {
            android.view.View.GONE
        }

        // Update log
        tvLog.text = if (FlightSearchService.logMessages.isNotEmpty()) {
            FlightSearchService.logMessages.joinToString("\n")
        } else {
            "Waiting to start..."
        }

        // Enable service button visibility
        btnEnableService.visibility = if (serviceEnabled) android.view.View.GONE else android.view.View.VISIBLE
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val am = getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
        val enabledServices = am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
        for (service in enabledServices) {
            if (service.resolveInfo.serviceInfo.packageName == packageName) {
                return true
            }
        }
        return false
    }

    override fun onDestroy() {
        super.onDestroy()
        FlightSearchService.onStatusChanged = null
    }
}
