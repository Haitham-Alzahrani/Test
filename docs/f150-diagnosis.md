# 2014 F-150 3.7L — Unstable Idle Diagnosis

Working log for VIN `1FTMF1EM1EFC80632`. Records what was checked, what it
ruled out, and what is still open.

**Status:** open — awaiting scan data (fuel trims, misfire counters, codes).

---

## Vehicle identification

Decoded from the VIN and the door jamb label.

| Field | Value |
|---|---|
| VIN | `1FTMF1EM1EFC80632` |
| Model | Ford F-150 XL, Regular Cab, 8-ft box |
| Engine | 3.7L V6 Ti-VCT (Cyclone), ~302 hp |
| Transmission | 6R80 6-speed automatic |
| Drive | **4x2** — VIN position 5 (`F1E`) |
| Built | 08/2014 · in service 19 Nov 2014 |
| Odometer | 131,000 km (Aug 2026) |

Door label: GVWR 3016 kg (6650 lb) · FAWR 1497 kg · RAWR 1588 kg ·
P255/65R17 108H on 17x7.5J · **35 psi cold, front and rear** ·
WB 126" · axle code 26 · paint UJ Sterling Gray · interior CS Steel Gray.

### Errors in the vehicle history report

The purchased report contains two fields that contradict the VIN. Do not
act on them:

- Lists fuel type as **"Electric"** — it is gasoline.
- Lists drive as **"Four-wheel Drive"** — VIN says 4x2. Confirm visually
  (look for a front driveshaft and transfer case) before ordering any
  driveline part.

---

## History report findings

Source: Saudi vehicle history report #9016795, dated 2025-01-26.
32 dealer visits with Aljazirah Vehicles, 2015–2021.

### Odometer sequence is not monotonic

| Date | Reading |
|---|---|
| 2016-12-26 | 49,306 km |
| 2020-03-08 | **40,124 km** ← lower than 2016 |
| 2020-03-23 | 40,547 km |
| 2021-03-04 | 49,381 km |
| 2021-04-29 | 54,533 km |
| 2022-08-28 | 91,205 km |
| 2023-08-18 | 108,905 km |
| 2025-01-03 | 117,029 km |

The 2016 entry sits ~9,000 km above the 2020 readings. Either a data-entry
error in 2016, or a cluster was swapped or rolled back between 2016 and
2020. Note that 49,306 (2016) and 49,381 (2021) are suspiciously close,
which points toward a mis-keyed record — but it cannot be proven from the
report alone.

**Consequence: true accumulated distance may exceed 131,000 km. Treat all
wear-item intervals as "at least."**

### Service gap

Last dealer visit 2021-04-29 at 54,533 km. That leaves roughly **76,500 km
with no dealer service record.** Whatever was or wasn't done in that period
is unknown — relevant to cam phaser condition, which depends on oil history.

### Other notes

- 2020-02-26 visit logged as *فحص الماكينة لا تعمل* — engine inspection,
  no-start / not running.
- No accident history. Two owners. No recalls on file.
- Warranty expired 2017-11-19.
- Service life in Aseer, Jizan and Dammam — hot climate, so every
  maintenance interval should be treated as severe duty.

---

## Symptom

Small shake, felt in the cab. Unstable RPM when held around 1,000–2,000.
Present **before** any of the repair work below — not introduced by it.

---

## Work already performed

Improved throttle response. **Did not affect the shake.**

- Spark plugs replaced
- Air filter replaced
- Fuel injectors cleaned
- Engine oil and filter changed
- Oxygen sensors cleaned
- Coolant flushed and replaced
- 6R80 transmission fluid changed at 113,000 km

### Concern: the oxygen sensors

Heated O2 sensors are not serviceable by cleaning. Solvent on the ceramic
element can poison or slow them permanently, and a lazy upstream sensor
causes fuel control to hunt — which is itself an unstable-idle symptom.

**Check upstream HO2S switching rate at 2,500 rpm.** A healthy sensor
crosses 0.1↔0.9 V several times per second. If either upstream sensor is
slow or parked mid-range, replace it rather than cleaning again.

---

## Diagnostic test performed

**Shake at a complete stop, comparing gear positions:**

> Shake in D and R is **less** than in N.

### What this rules out

This is the inverse of the classic mount signature. A collapsed engine or
transmission mount gets *worse* under load in gear; this gets better.

| Suspect | Status |
|---|---|
| Engine / transmission mounts | **Ruled down** — wrong direction |
| Cracked flexplate | **Ruled down** — would worsen in gear |
| Torque converter shudder | **Ruled down** — fluid changed 18,000 km ago, and TC shudder does not appear at a standstill |
| Combustion roughness | **Confirmed as the branch** |

### Interpretation

In D/R the torque converter is coupled and loaded, and the fluid coupling
damps torsional pulses before they reach the chassis. In N the driveline is
decoupled and the engine rocks freely on its mounts, so identical roughness
reads louder in the seat.

**The engine is genuinely running rough; the converter is masking it in
gear.** Mounts are likely fine. The fault is in combustion — mixture,
ignition, or mechanical.

---

## Open suspects, ranked

Nothing in the completed work addresses any of these.

| # | Suspect | Why it fits | Test |
|---|---|---|---|
| 1 | **Throttle body carbon** | Never cleaned. Carbon around the plate distorts the small airflow the PCM meters at idle. Sets no code. | Inspect plate edge and bore. Clean, then **run idle relearn** — mandatory, or it idles worse afterward. |
| 2 | **Vacuum leak (age)** | Brake booster hose, PCV valve and hose, intake gaskets — all original, 11 years, heat-cycled. Pre-existing; nothing done would have fixed it. | Smoke test intake. Plus PCV pinch test at idle in N. |
| 3 | **EGR stuck or leaking** | Fits the D-vs-N result: dilution hurts most at idle where airflow is lowest, shrinks under load. Often sets no code. | Commanded vs actual EGR position at idle — must be **0% / closed**. |
| 4 | **Weak ignition coil** | Plugs changed, coils not. A tired coil misfires worst at idle and light load. | Per-cylinder misfire counters, then swap suspect coil with a neighbour and see whether the count follows the coil. |
| 5 | **VCT cam phaser** | 76,000 km of unknown oil history. Phasers are the first casualty of poor oil maintenance on this engine. | Commanded vs actual cam position at idle. Listen for a 1–2 s rattle at first cold start. |
| 6 | **Low compression, one cylinder** | The one cause consistent with "nothing fixes it." Valve seat recession or sticky valve. Remember the odometer may understate real distance. | Relative compression / cylinder balance, or wet-dry compression test. |

### Also worth checking

Verify the spark plug **part number and gap** against the Motorcraft
catalogue for this VIN. Wrong heat range or reach produces exactly this
symptom, and plugs get dropped and closed up in shipping. Check every gap
with a wire gauge.

Firing order is **1-4-2-5-3-6**; bank 1 is passenger side (1-2-3), bank 2
driver side (4-5-6). Verify against the manual before acting on it.

---

## Data still needed

The suspect ranking above is informed guesswork until these exist.

1. **Codes** — stored, pending **and permanent**, all modules. Pending and
   permanent codes often hold misfire history with no dash light.
2. **LTFT bank 1 and bank 2** at warm idle in P/N, then in D with foot on
   brake, then at 2,500 rpm.
3. **Misfire counters per cylinder.**
4. **EGR actual position at idle.**
5. **VCT commanded vs actual**, including a cold-start log.

### How to read the results

| Reading | Healthy | Fault indication |
|---|---|---|
| LTFT B1 / B2, warm idle | within ±5%, ±10% tolerable | Double-digit positive that **shrinks** at 2,500 rpm → unmetered air. The key reading. |
| LTFT split between banks | within a few % of each other | One bank high → narrows to three cylinders |
| Misfire counters | 0, or a stray count | One cylinder dominant → that cylinder's coil, injector or compression. Even spread → global cause |
| EGR actual, idle | 0% closed | Anything open → dilution |
| VCT actual vs commanded | tracks within a few degrees | Lagging or not following → phaser or solenoid |
| HO2S upstream @ 2,500 rpm | 0.1↔0.9 V, several times/sec | Slow or parked mid-range → sensor damaged |
| ECT warm | ~88–100 °C | Running cold → thermostat stuck open, causes rich idle |

**Two numbers collapse most of the table:** fuel trims tell you whether it's
a mixture problem, and misfire counters tell you whether it's one cylinder
or all six.

---

## Recommended next actions

1. **Clean the throttle body and run the idle relearn.** Cheapest, undone,
   needs no scan tool, and addresses the top suspect.
2. **Smoke test the intake.** ~20 minutes, resolves the entire leak branch.
3. **Read EGR position at idle.** One PID.
4. **Pull codes and log fuel trims + misfire counters.**

---

## Note on this engine

The 3.7L Cyclone uses an **internal, timing-chain-driven water pump.** When
it fails it dumps coolant into the oil pan rather than onto the ground. If
any coolant loss appears with no external leak, check the dipstick for milky
oil or an over-full pan before chasing anything else.
