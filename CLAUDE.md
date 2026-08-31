# Context

The owner is a working mechanic in Jeddah, Saudi Arabia. He does the
hands-on work himself — give him diagnostic reasoning, specs and procedures,
not "see a mechanic."

## His truck

**2014 Ford F-150 XL Regular Cab · 3.7L V6 Ti-VCT · 6R80 auto · 4x2**
VIN `1FTMF1EM1EFC80632` · 131,000 km (Aug 2026) · Jeddah

### The open problem

Small shake felt in the cab, and unstable RPM held around 1,000–2,000.
**Present before any repair work — not caused by it.**

Key test result: **at a standstill, the shake is LESS in D/R than in N.**
That is the inverse of a bad mount, so mounts, flexplate and torque
converter are ruled out. The torque converter damps the pulses when
coupled — meaning the engine is genuinely running rough and the converter
masks it in gear. **The fault is combustion: mixture, ignition, or
mechanical.**

### Already done — none of it fixed the shake

Spark plugs · air filter · injector clean · oil and filter · coolant flush ·
6R80 fluid (at 113,000 km) · O2 sensors "cleaned" (this may have *damaged*
them — check upstream HO2S switching rate).

### Top unexplored lead

**The throttle body has never been cleaned.** Cheapest candidate, needs no
scan tool. Clean it, then run the idle relearn — mandatory, or it idles
worse afterward.

### Blocked on

Scan data: fuel trims (LTFT both banks, idle in P/N vs D vs 2,500 rpm),
per-cylinder misfire counters, EGR actual position at idle, and codes
(stored, pending **and permanent**).

Two numbers collapse most of the diagnosis — fuel trims say whether it's a
mixture problem, misfire counters say whether it's one cylinder or all six.

### Careful

- The purchased history report wrongly lists fuel type as "Electric" and
  drive as "4WD". The VIN says **4x2**. Ignore the report on both.
- The odometer history is non-monotonic (a 2016 reading sits 9,000 km above
  the 2020 ones). **True distance may exceed 131,000 km** — treat wear
  intervals as "at least."
- This engine has an **internal, timing-chain-driven water pump**. If
  coolant disappears with no external leak, check the oil for coolant before
  chasing anything else.

**Full detail: [`docs/f150-diagnosis.md`](docs/f150-diagnosis.md)** — history
report findings, ranked suspects with the test that isolates each, and
reference values for reading scan data.

## Secondary task

Finding a used laptop under ~500 SAR in Jeddah to run FORScan and the
diagnostic tooling. Any Core i5 with 8 GB RAM is sufficient. See
`haraj_laptops.py` and the buying spec in the README.

## Working preferences

- **One shell command per code block.** Never combine multiple commands in
  a single block.
- Don't hand him unverified listing URLs as if they were live — classifieds
  links from search indexes are frequently dead.
