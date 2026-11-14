# Small-ROV sensors: real behaviour and failure modes, and a gap audit of the simulator's sensor models

Scope: observation-class and light work-class ROVs (BlueROV2/ArduSub, FIFISH/QYSEA, Blueye, Deep Trekker class). Sources were checked as primary vendor datasheets or docs where possible. Tags: **[datasheet]** primary spec, **[forum]** single field report, **[snippet]** seen only in a search-result snippet or summary and not read in full, **[inference]** my reasoning, not a sourced fact. Repo citations are `path:line` against the current checkout (branch `claude/awesome-brahmagupta-2zupid`, HEAD `634075b`).

---

## 1. Depth / pressure sensors (Bar30/Bar02, FIFISH)

### Takeaway
Small-ROV depth comes from a MEMS pressure cell (MS5837 family). Its resolution is millimetric (2 mm for Bar30), but absolute accuracy is poor (±2 m for Bar30 at 0–45 °C). Real systems therefore zero the gauge at the surface, and the main visible errors are a surface zero offset, a fresh/salt density scale error of about 3 %, quantisation of about 2 mm, and a reading rate of tens of Hz. No FIFISH or X1 depth-sensor specification is public.

### Cited Findings
- Bar30 (MS5837-30BA): 0–30 bar, operating depth 0–295.6 m, **resolution 0.2 mbar (2 mm freshwater)**, **absolute accuracy ±200 mbar (≈204 cm freshwater) at 0–45 °C, ±400 mbar (≈409 cm) at −20–85 °C**. Temperature absolute accuracy ±4 °C. In-water operating temperature 2–40 °C — [Blue Robotics Bar30/Bar02 product page](https://bluerobotics.com/store/sensors-cameras/sensors/bar30-sensor-r1/) [datasheet]
- Bar02 (MS5837-02BA): 0–10 m, **resolution 0.016 mbar (0.16 mm freshwater)**, **relative accuracy ±2 mbar (2 cm) at 0–60 °C, ±4 mbar (4 cm) at −20–85 °C**, temperature ±2 °C — [Blue Robotics Bar30/Bar02 page](https://bluerobotics.com/store/sensors-cameras/sensors/bar30-sensor-r1/) [datasheet]
- Blue Robotics says the sensing element "must be dried for at least 2 hours each day to maintain accuracy" and is rated for intermittent submersion, with 24 h maximum continuous submersion. This is a known long-dive drift caveat — [Blue Robotics Bar30 page](https://bluerobotics.com/store/sensors-cameras/sensors/bar30-sensor-r1/) [datasheet]
- MS5837-30BA at OSR 8192: **conversion time 16.44 ms typical (14.80–18.08 ms)**, **RMS pressure resolution 0.20 mbar**, temperature resolution 0.0022 °C. This caps a single sensor at about 50–60 Hz for pressure+temperature pairs [inference from the conversion time] — [TE MS5837-30BA datasheet (Farnell copy)](https://www.farnell.com/datasheets/2917217.pdf) [snippet: table values seen via search summary only]
- Density conversion: Blue Robotics code examples use **997 kg/m³ fresh and 1029 kg/m³ salt** (`ms5837.DENSITY_FRESHWATER = 997`, `DENSITY_SALTWATER = 1029`). In ArduSub the fluid is selected with `BARO_SPEC_DENSITY` / `BARO_SPEC_GRAV`, and the **default is freshwater** — [BR forum: change depth sensor density for salt water](https://discuss.bluerobotics.com/t/change-depth-sensor-density-for-salt-water/14113); [Bar sensors guide](https://bluerobotics.com/?p=227172) [snippet]
- Surface reference: ArduSub stores ground pressure in `BARO2_GND_PRESS`. One user reported depth readings going wrong mid-session with that parameter unchangeable — [BR forum: calibrate Bar30 via MAVLink](https://discuss.bluerobotics.com/t/calibrate-bar30-depth-sensor-using-mavlink/19572) [snippet, forum]
- FIFISH (V6 generation) FAQ: **before launch the depth may read a zero offset of more than 1 m**, and the 3D attitude model is wrong until calibrated — summarised in the repo's own research report, `docs/reference/real-rov-research.md:33`, citing [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- FIFISH depth bar on the HUD auto-ranges across 0–5 m, 5–30 m and 30–100 m — `docs/reference/real-rov-research.md:27`, citing the same FAQ
- QYSEA's X1 page claims "attitude control ±0.1°". The repo report also records a V6 claim of depth hold ±1 cm (`real-rov-research.md:82`) [vendor claim, not a sensor accuracy]

### Inferences
- A 997-vs-1029 kg/m³ mis-selection gives a **scale error of about 3.2 %**: (1029−997)/997 ≈ 3.2 %, so a true 30 m reads about 31 m if the vehicle is set to fresh in seawater [inference, arithmetic on cited densities].
- After zeroing at the surface, the relevant error is the *relative* one: centimetre-level short-term noise, a slow drift with temperature (sensor temperature-compensated only to the ±4 °C class), and the zero offset if the pilot forgot to zero or zeroed in air/sun. The ±2 m absolute figure matters only if no surface zero is done [inference].
- A realistic sim model: `depth_meas = (p_true − p_zero_est)/(ρ_set·g) + n`, with n ~ N(0, 2–5 mm) white noise, quantisation 2 mm, a zero-offset bias set at power-up (0–1 m possible per the FIFISH FAQ, typically a few cm), a slow thermal drift of order cm per 10 °C step [assumption], output at 10–50 Hz [inference].

### Gaps
- No FIFISH/X1 depth-sensor model, resolution, accuracy or rate is published. The X1 measurement checklist should capture a static-depth noise trace.
- I did not find a measured temperature-step response (thermal-shock spike on entering cold water) for MS5837 in a housing. This is commonly reported but not sourced here.

---

## 2. Heading: magnetic compass, IMU/AHRS, interference, fusion, runaway

### Takeaway
Small ROVs fuse a MEMS gyro with a magnetometer (ArduSub EKF, or an AHRS in the DVL/USBL). Gyro-only yaw drifts at about 0.1–0.3°/min after calibration. Magnetic heading is accurate to about 0.5–1° when clean, but near steel it shifts by 5–10° (ports) and up to about 45° (pool rebar). The EKF may "re-align" yaw abruptly, which turns heading hold into a spin. Pilots respond by backing away from the steel and disabling auto-heading.

### Cited Findings
- Water Linked A50 AHRS: the DVL's yaw "may experience drift", reducible to **0.1–0.3° per minute** by gyro calibration once per boot — [Water Linked dead-reckoning docs](https://waterlinked.github.io/dvl/dead-reckoning) [snippet; direct fetch returned 404]
- SeaTrac X150/X110 USBL internal 9-DOF AHRS: **±1° yaw, ±0.2° pitch and roll (std-dev)** — [SeaTrac USBL datasheet (VideoRay mirror)](https://videoray.com/wp-content/uploads/SeaTrac-USBL-Data-Sheet.pdf) [datasheet, text extracted with pdftotext]
- Xsens MTi-680 heading accuracy is **0.5° RMS** per datasheet, and needs a good compass calibration to achieve it — [element14 MTi-680 road test](https://community.element14.com/products/roadtest/b/blog/posts/xsens-mti-680-dk-experimenting-with-performance---part-2) [snippet]
- Xsens: "the distance to the object and the amount of ferromagnetic material determines the magnitude of disturbance". Static disturbance can be mapped out. Under structural disturbance lasting **>10–30 s** (filter-profile dependent), heading "will slowly converge to a solution using the 'new' local magnetic north". Disturbances from objects moving independently "cannot be fully compensated for" — [Xsens magnetic distortion theory](https://mtidocs.xsens.com/magnetic-distortion-theory); [Xsens Magnetic Calibration Manual](https://www.mouser.com/pdfDocs/MagneticCalibrationManual-2.pdf); [Xsens blog: six ways to keep accurate heading](https://www.xsens.com/blog/six-ways-to-keep-an-accurate-heading-in-a-magnetically-disturbed-environment) [snippet]
- Field magnitudes: an ROV in a port with ferrous objects saw magnetic compass drift of **about 5–10°** — [Sonardyne article](https://www.sonardyne.com/?p=24035) [snippet]. Pool rebar gave **about 45° compass offset** on an OpenROV 2.8 — [BR forum: compass heading incorrect](https://discuss.bluerobotics.com/t/compass-heading-incorrect/854) [snippet, forum]
- Self-interference: moving an LSM303 compass **about 5 in (≈13 cm) away from thrusters** eliminated heading-hold interference — [BR forum thread "Frustrated. Any suggestions?"](https://discuss.bluerobotics.com/t/frustrated-any-suggestions/305) [snippet, forum]
- Runaway case: an ROV at **85 m on a steel wreck** showed `Warning: EKF2 IMU0 ground mag anomaly, yaw re-aligned` and "wants to spin around". An experienced pilot's advice: the wreck hull's magnetics are deviating the compass, he has seen it on several iron wrecks, and the fix is to move away; "do not use auto heading when close to the wreck" — [BR forum: ROV problem spinning around](https://discuss.bluerobotics.com/t/rov-problem-spinning-around/10680) [forum, read in full]
- An ArduPilot reply notes that a well-placed, well-calibrated compass away from interference "will not trigger the EKF to do a yaw realignment". It implies that realignments are the observable symptom of a magnetic anomaly — [ArduPilot forum: EKF yaw reset](https://discuss.ardupilot.org/t/data-ekf-yaw-reset/10994) [snippet]
- Distance dependence of steel anomalies: the anomaly "decreases as the inverse cube – so 8 times smaller when twice as far away" (far-field dipole). A coaster in 30 m water gives a few hundred nT at the surface, a several-thousand-ton ship several thousand nT, and old sailing ships <50 nT — [Liverpool: using a magnetometer to find wrecks](https://www.liverpool.ac.uk/~cmi/mag/magInf.html) [snippet]. Geometrics' rule of thumb: **1 ton of steel ≈ 1 nT at 100 ft (30.5 m)**, linear in mass, cubic in distance — [Geometrics: magnetometer detection range](https://www.geometrics.com/support/what-is-the-detection-range-of-a-magnetometer) [snippet]
- Cerulean: check IMU heading at every power-up against a known direction, and "the IMU is the main dead-reckoning error source" — [Cerulean DVL-75 hints and tips](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips) [read in full]
- Diver DVL study (Cobra-Tac): DVL speed was "extremely accurate"; most position error came from **heading-dependent compass error, up to 5 % of track length** — cited in a search summary from [U. Michigan / Eustice 2005](https://robots.engin.umich.edu/publications/reustice-2005d.pdf) [snippet; attribution to that specific PDF not verified]
- QYSEA lists magnetic or RF interference near large metal structures as a cause of FIFISH "Disconnected" — `docs/reference/real-rov-research.md:33`, citing [QYSEA disconnection guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)

### Inferences
- Deviation estimate: deviation ≈ atan(ΔB_⊥ / B_h), where B_h is Earth's horizontal field. B_h is typically a few × 10⁴ nT [assumption, not sourced here]. With the Geometrics rule, 1,000 t of steel gives about 1,000 nT at 30 m (≈1–3°), about 8,000 nT at 15 m (≈10–20°) and ≫B_h at 5 m (heading meaningless). This matches the reported 5–10° in ports and tens of degrees beside rebar. The dipole approximation breaks down within about one structure length, so near-field behaviour should be modelled as a stronger and spatially erratic deviation [inference].
- The runaway mechanism: heading hold servos toward a target in the *estimated* frame. When the estimate jumps (EKF re-align) or rotates with position (deviation field), the controller yaws the real vehicle to chase it. Seen from the camera, this is an uncommanded slow turn or a sudden spin [inference, consistent with the forum case].
- Gyro-only fallback (in a magnetically dead zone) drifts at about 0.1–0.3°/min, i.e. 1.5–4.5° per 15 min [inference from the WL figure].

### Gaps
- No measured heading-error-vs-distance curve for an ROV beside a ship hull or pile exists in the sources found. The magnitudes above are an order-of-magnitude derivation.
- FIFISH/X1 heading fusion (magnetometer vs gyro, DVL AHRS) is undocumented. Whether the X1 app shows any "compass interference" warning is unknown.

---

## 3. Attitude (pitch/roll) accuracy and latency

### Takeaway
Pitch and roll are the easiest states: gravity references them, so they are accurate to about ±0.2° std in AHRS-grade units and better than 1° in hobby IMUs, with output at 50–100+ Hz. The pilot sees error mostly as a calibration offset (FIFISH's "3D model wrong until calibrated") and under sustained acceleration.

### Cited Findings
- SeaTrac AHRS: **±0.2° pitch and roll std-dev** — [SeaTrac datasheet](https://videoray.com/wp-content/uploads/SeaTrac-USBL-Data-Sheet.pdf) [datasheet]
- FIFISH FAQ: the 3D attitude model does not match reality before calibration — `docs/reference/real-rov-research.md:33` ([FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf))
- Water Linked: a DVL mounted with a **5° tilt** over 100 m of horizontal travel displays 99.6 m in X-Y "with a large Z error". Attitude/mounting error leaks into DR — [Water Linked dead-reckoning docs](https://waterlinked.github.io/dvl/dead-reckoning) [snippet]

### Inferences
- A realistic model is a constant mounting/calibration bias of 0.2–2° per axis set at power-up, white noise of about 0.05–0.1°, and accelerometer-induced error during hard accelerations (the complementary filter leaks linear acceleration into tilt) [inference/assumption].

### Gaps
- No public figure for FIFISH attitude-sensor accuracy (±0.1° is an attitude-*control* claim). No measured attitude latency for any small ROV was found.

---

## 4. Altimeter and forward range (single-beam echo sounders, e.g. Ping2)

### Takeaway
Ping-class echo sounders have a wide 25° cone, a 0.3 m blind zone and 0.5 %-of-range resolution. They report the *nearest strong* echo in the cone (not the point straight ahead) and degrade over tall vegetation and fish, so readings jump on slopes and near walls.

### Cited Findings
- Ping Sonar (Ping2): **beamwidth 25° (−3 dB)**, typical usable range **100 m**, typical minimum range **0.3 m**, range resolution **0.5 % of range** (1 cm at 2 m, 50 cm at 100 m). "Performance may suffer over variable density changes from tall vegetation, groups of fish, geysers, etc." It has an "advanced bottom-tracking algorithm" for multiple echoes. No update rate or accuracy is stated on the page — [Blue Robotics Ping Sonar](https://bluerobotics.com/store/sonars/echosounders/ping-sonar-r2-rp/) [datasheet]
- Small tanks: multiple echoes from walls and the surface confuse the sensor — [summary of BR guidance in search results](https://discuss.bluerobotics.com/t/water-linked-dvl-a50-support/9123/52) [snippet]

### Inferences
- With a 25° cone, at 10 m altitude the footprint radius is ≈10·tan(12.5°) ≈ 2.2 m. On a 20° slope the first return comes from the up-slope edge, so the altitude under-reads by roughly 10·(1−cos(12.5°+…)). Simulate this as "minimum range within cone", not a single ray [inference].
- Soft mud returns a weaker and sometimes deeper echo (penetration). Kelp gives a shallow false bottom. Fish schools give transient short ranges [inference consistent with the BR footnote].

### Gaps
- No Ping2 update rate or confidence-field behaviour was found on the product page (it exists in the Ping protocol docs, not retrieved). The specific X1 forward/obstacle sonar (three-way avoidance sonar, `real-rov-research.md:11`) has no public specs.

---

## 5. DVL (Water Linked A50, FIFISH Q-DVL)

### Takeaway
The A50 bottom-tracks from 5 cm to 50 m (>35 m is seabed-dependent). It pings at 4–15 Hz (adaptive to altitude), has 0.1 mm/s resolution and ±1.01 % long-term accuracy (standard version). Lock is lost when too high, too close, on steep slopes, over vegetation or soft mud, in bubbly prop-wash, and in reverberant tanks. On loss, DR stops updating. DR position error is dominated by heading error and grows without bound, so vendors advise resurfacing every 15–20 min. The Q-DVL is advertised for 0.1–100 m, but retail specs conflict.

### Cited Findings
- A50 datasheet: 1 MHz, 4-beam convex Janus, **beam angle 22.5°**, **ping rate 4–15 Hz (adaptive to altitude)**, integrated AHRS, **min altitude 5 cm, max 50 m (>35 m dependent on seabed conditions, salinity etc.)**, **max velocity 3.75 m/s**, **velocity resolution 0.1 mm/s**, **long-term accuracy ±1.01 % (standard), ±0.1 % (performance)**, power 4 W — [Water Linked DVL A50 datasheet WL-21035-4 v5](https://waterlinked.com/datasheets/dvl-a50) [datasheet, text extracted]
- A50 install docs: transducer half-power beamwidth **4.4°**. Keep a **65° cone** below the transducers clear — [Water Linked A50 docs](https://docs.waterlinked.com/dvl/dvl-a50/) [read]
- Q-DVL (QYSEA): advertised **0.1–100 m** altitude for station hold, distance lock and altitude lock. Accuracy is described only as "centimetre-level" — `docs/reference/real-rov-research.md:23`, citing [QYSEA Q-DVL](https://www.qysea.com/products/q-dvl-sensor/) [vendor]
- Conflicting retail specs for the W6 DVL module: min 5 cm and **max "50 cm"** (likely a typo for 50 m), max velocity 2.6 m/s, resolution 0.01 mm/s, with a listing that gives both 1 MHz and 680 kHz. QYSEA dealer material for the Downward Q-DVL-M (E-Master Navi) gives 600 kHz, 4 m/s max, 0.1 mm/s, **15 cm min altitude**. Another gives 10 cm min — [scuba.com Q-DVL listing](https://www.scuba.com/p-qydvl/href); [Adorama Q-DVL listing](https://www.adorama.com/qysea-fifish-w6-dvl-station-lock-system-module/p/qydvl); [Dynatech E-Master Navi](https://dynatech.ae/?p=250109) [snippet; conflicting]
- Loss-of-lock causes:
  - Too high: "when the maximum altitude is exceeded the DVL stops updating its dead-reckoning position estimate"; "accuracy of the DVL reduces as you approach the maximum altitude" — [Cerulean DVL-75 hints](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips) [read]
  - Too low: the DVL may not notice it is below minimum, and reflections then produce **false motion**. Recovery advice: "hop up to at least 2 meters above the bottom" — [Cerulean](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips) [read]
  - Vegetation: prop wash moves the vegetation, the DVL reads that motion and the ROV drifts, a "positive feedback loop" in position hold — [Cerulean](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips). VideoRay: heavy vegetation reduces signal quality, so move to a new location — [VideoRay DVL diagnostics](https://download.videoray.com/documentation/mss_diagnostics/html/dvl_diagnostics.html) [snippet]
  - Bubbles/silt: crashing into muck stirs gas and particles into the thruster wash, which looks like sudden speed changes. Partially surfacing draws air into the wash, giving false bottom and false motion — [Cerulean](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips). Nortek lists bubble-rich water (prop wash, breaking waves), soft sediment, seaweed-rich bottoms, extreme slopes, and being extremely close to the bottom — [Nortek DVL1000 manual p.28](https://manualshive.com/en/manual/nortek/dvl-1000-300m/1706076?page=28) [snippet]
  - Slopes: Sonardyne Syrinx tracks slopes up to **75° at 10 m altitude** but only about **45° at 1–2 m** — [Sonardyne KB: max seabed slope](https://www.sonardyne.com/products-knowledge-base/what-is-the-maximum-seabed-slope-that-i-can-still-bottom-track/) [snippet]
  - Self-noise: the noise floor was **12 dB higher with the ROV operating**, with interference near 480 kHz from ROV electrics — [Teledyne: DVLs for noisy environments](https://www.teledynemarine.com/news/dvls-for-noisy-environments) [snippet]
  - Tanks/pools: reverberation makes the DVL usually perform poorly in a pool — [Cerulean](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips) [read]
- DR drift:
  - Long-term accuracy ±1.01 % (A50 standard), i.e. a velocity scale error — [A50 datasheet](https://waterlinked.com/datasheets/dvl-a50)
  - Blueye (A50 integrated) recommends resurfacing **every 15–20 min** to reset the start point — [Blueye navigation blog](https://www.blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
  - Nortek reports long-term error settling **below 0.05 % of distance over >6 km** (high-end DVL+INS). Teledyne Wayfinder scale-factor accuracy is **±1.15 %**, with offset within ±1 mm/s in tank tests — [GPS World: Nortek](https://www.gpsworld.com/nortek-enables-usv-navigation-in-gnss-denied-environments/); [Teledyne Wayfinder testing 2021](https://teledynemarine.com/en-us/products/SiteAssets/RD%20Instruments/ST_Wayfinder_Testing_Feb_%202021.pdf) [snippet]
- Field failure: after unlock, A50 velocity readings diverged within **5–10 s**, so thrusters pushed erratically, and the vehicle ran away when position hold engaged — `docs/reference/real-rov-research.md:88`, citing [BR forum: ongoing DVL A50 issues](https://discuss.bluerobotics.com/t/ongoing-dvl-a50-issues/11419) [snippet in that report]. Another user reports the A50 AUV "crab-walking/drifting right after 10 m linear travel" — [BR forum thread](https://discuss.bluerobotics.com/t/water-linked-dvl-a50-drift-issue-auv-starts-crab-walking-drifting-right-after-10m-linear-travel-ros-2-humble-video-code/23407) [snippet, title only]
- Water-tracking caveat: water-referenced velocity carries current error — [arXiv 2110.00661](https://arxiv.org/pdf/2110.00661) [snippet]

### Inferences
- Simulated DVL output should carry: per-beam ranges with dropouts; `velocity_valid` false when <3 beams lock; white velocity noise of order mm/s rising with altitude toward the max [assumption, no published σ found]; scale error ±1 % fixed per dive; false-motion spikes when below min altitude or in bubbly wash; and hold-off/re-acquire hysteresis (climb to about 2 m) [inference].
- For a 15-min dive at 0.3 m/s (≈270 m), ±1 % scale gives ≈2.7 m along-track. A 2° heading bias adds ≈9.4 m cross-track (270·sin 2°). This is why heading dominates [inference, arithmetic].

### Gaps
- The A50 velocity noise standard deviation and `fom` behaviour were not retrieved (protocol page URLs 404'd). Q-DVL altitude window and min altitude are conflicting (5/10/15 cm). No X1 DVL loss-of-lock UI behaviour is documented.

---

## 6. USBL / acoustic positioning (Water Linked UGPS, Blueprint SeaTrac)

### Takeaway
Acoustic positioning gives absolute but jumpy fixes at 0.5–4 Hz. Error is about 1° of bearing (≈1.7 % of slant range) plus 0.1–0.2 % range error. Typical outliers come from multipath at harbour walls, seabed and surface, from noise, and from tanks. Fused systems use the DVL to smooth acoustic jumps and acoustic fixes to correct DVL drift.

### Cited Findings
- Water Linked UGPS G2: 100 m and 300 m range versions. **Ping rate 2 Hz** (catalog) or **2–4 Hz** (Blueye spec sheet). Accuracy: **horizontal range <0.2 %, horizontal angle <1°, vertical range <1 %** — [NauticExpo G2 catalog](https://pdf.nauticexpo.com/pdf/water-linked-as/standard-g2-system/197635-134772.html); [Blueye UGPS G2 spec](https://www.blueyerobotics.com/specsheet/WL-GPS-G2-R300/pdf) [snippet; the two ping-rate figures conflict mildly]
- U1 locator long-term drift: **≈1 m per 6 h in static heading configuration** — [Blueye G2 spec](https://www.blueyerobotics.com/products/waterlinked-gps-g2-r300) [snippet]
- SeaTrac X150: **1 km** hemispherical range. **Range resolution ±0.1 m** (depends on supplied speed of sound). **Angular: typ. 2 % of range (~±1°)**. Sound speed 1300–1700 m/s, auto-computable from temperature and depth. Doppler compensation to 15 kn — [SeaTrac datasheet](https://videoray.com/wp-content/uploads/SeaTrac-USBL-Data-Sheet.pdf) [datasheet]
- Acoustic positioning is absolute but jumps: harbour walls, seabed reflections and other vessels' noise cause erroneous readings. Fusion uses the DVL to smooth and acoustics to correct drift — [Blueye navigation blog](https://www.blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater) (also `real-rov-research.md:106`)
- Field reports: UGPS readings drifting in a lake, with range limiting recommended for pools and tanks — [BR forum: Waterlinked GPS position readings drift](https://discuss.bluerobotics.com/t/waterlinked-gps-position-readings-drifts/12286); [positioning error with UGPS](https://discuss.bluerobotics.com/t/positioning-error-present-with-waterlinked-ugps-system/14317) [snippet, forum]

### Inferences
- Simulate: fix rate 1–4 Hz; Gaussian bearing error σ ≈ 0.5–1° plus range σ ≈ 0.1–0.2 %; 1–5 % outlier rate that rises when the slant path passes within a few metres of a wall or the surface (multipath); full outage when the line of sight is blocked by structure or the vehicle is inside a wreck [inference].

### Gaps
- No quantitative multipath outlier statistics were found. The SeaTrac update interval was not in the datasheet text. X1 has no USBL as standard, and the repo marks `uqps`/`usbl` offline (see §10).

---

## 7. Video link and telemetry latency, update rates

### Takeaway
Glass-to-glass video is 150–250 ms when healthy (FIFISH self-reports 150–200 ms). It reaches 1–2 s when misconfigured or under Wi-Fi interference. Telemetry overlays share the link. A disconnect drops video and control for about 30 s on FIFISH.

### Cited Findings
- FIFISH live-video delay **150–200 ms**, worse with phone >5 m from the remote, 720P, old phones or indoor Wi-Fi. A tether pulled mid-dive costs control and video, with **about 30 s reconnect** — `docs/reference/real-rov-research.md:33,51` ([FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf))
- BlueROV2 ≈200 ms (third-party). Users report 1–2 s when misconfigured and target <250 ms. An optimised custom build reaches 100–110 ms — `real-rov-research.md:51` ([BR forum camera latency](https://discuss.bluerobotics.com/t/bluerov2-camera-latency/2872))
- A50 velocity output follows its 4–15 Hz ping rate. Pressure sensors convert in about 16 ms. UGPS fixes arrive at 2–4 Hz — cited above

### Gaps
- No published FIFISH/X1 telemetry overlay refresh rate. ArduSub/QGC MAVLink stream rates were not retrieved this round. X1-via-Q-iRC latency is unmeasured (repo checklist item).

---

## 8. Temperature, leak, power telemetry (X1 tether-powered)

### Takeaway
Water temperature on small ROVs usually comes from the pressure-sensor die. It is accurate to ±2–4 °C and lags because of the housing. Leak detection is a binary alarm. On a tether-powered vehicle like X1, "battery %" is meaningless: the relevant telemetry is supply voltage, current and power, plus surface-unit faults.

### Cited Findings
- Temperature from Bar30 is accurate to **±4 °C** absolute, Bar02 to **±2 °C** — [Blue Robotics Bar page](https://bluerobotics.com/store/sensors-cameras/sensors/bar30-sensor-r1/) [datasheet]
- X1 is powered by direct tether supply ("24h×7" marketing), and the kit ships without a battery — `docs/reference/real-rov-research.md:11` ([QYSEA X1](https://www.qysea.com/fifish-x1/); [Blue Skies X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1))
- The X1-generation app added "humidity reminder" and pre-use self-check — `real-rov-research.md:27` ([App Store FIFISH](https://apps.apple.com/ly/app/fifish/id1364364991))

### Inferences
- The humidity reminder implies an internal humidity sensor used as a leak or condensation precursor. Simulate it as a slow rise plus a threshold alarm [inference].

### Gaps
- Leak-sensor and power-telemetry fields for X1 are not public. I did not research Blue Robotics' SOS leak sensor specs this round.

---

## 9. How failures appear to the pilot, and what pilots do

### Takeaway
Most failures appear indirectly, not as a labelled fault: the heading tape slowly rotates while the camera shows no turn; the vehicle spins after an "EKF yaw re-aligned" text; the DVL indicator goes grey or position hold drops out; the altitude reading jumps; depth reads +1 m at the surface; a ping drops and video freezes. Standard pilot responses: back away from steel and use manual yaw; climb to about 2 m to re-acquire DVL; move away from vegetation; resurface every 15–20 min to reset DR; zero depth and check heading against a known direction before diving.

### Cited Findings
- Steel wreck: an ArduSub text warning plus spinning. Advice: move off and don't use auto-heading — [BR forum spinning](https://discuss.bluerobotics.com/t/rov-problem-spinning-around/10680)
- DVL: DR freezes above max altitude. Climb to 2 m to re-acquire. Check heading at power-up — [Cerulean](https://docs.ceruleansonar.com/c/dvl-75/usage-considerations-and-scenarios/general-hints-and-tips)
- Resurface every 15–20 min to reset DR — [Blueye](https://www.blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- Cockpit flashes the screen border green or red on connect or disconnect — `real-rov-research.md:57` ([Cockpit docs](https://blueos.cloud/cockpit/docs/latest/usage/advanced/))
- FIFISH symptoms: a surface depth offset above 1 m; a wrong 3D model before calibration; diagonal climb from uncalibrated sensors or tangled thrusters; about 30 s reconnect — `real-rov-research.md:33`

### Gaps
- No X1 app screenshots of DVL-lost, compass-warning or leak alarms are available (`real-rov-research.md:27`).

---

## 10. Part B — repository audit: what the simulator reports today

### Takeaway
Every sensor the pilot or SDK sees is currently **ground truth** read straight from the physics state. There is no noise, bias, quantisation (beyond display rounding), drift, rate limit or dropout. The only "imperfections" are a global 150 ms presentation delay on onboard fields (viewer), a hard 0.1–100 m DVL validity window that disables assist, and the instructor's physical injections (thruster, battery, current, visibility, freeze), none of which are sensor faults. Compass steel deviation and DVL loss of lock are explicitly listed as **not implemented** (`docs/reference/t20-validation.md:52`, required by `docs/tasks/T20-physics-validation.md:16`).

### Cited Findings (repo, file:line)
- **Depth**: `Simulator.depth` returns `vehicle.s.pos[2]` exactly (`simulator/qysim/engine.py:150-151`). It is emitted as `Depth` (`engine.py:297`), as `rov.depth` (`engine.py:529`), and in HF 50 Hz/10 Hz packets (`engine.py:338,346`). There is no surface zero offset, density setting, noise or quantisation beyond `round(…,2)` → **perfect**.
- **Heading / compass**: `Compass` and `Yaw` come from `vehicle.euler` (`engine.py:282,298-299`), `rov.yaw` from `engine.py:530`, and `state.euler` from `engine.py:773`. There is no magnetic model, deviation or gyro drift → **perfect**. `grep` for deviation/magnetic in `simulator/qysim` on all local branches finds nothing. The T20 compass item is unimplemented (`docs/reference/t20-validation.md:52`).
- **Heading hold uses truth**: the controller derives yaw from true `s.q` (`simulator/qysim/controller.py:156,170-177`), so a compass error could never cause a runaway today.
- **Attitude**: pitch and roll come from the true quaternion (`engine.py:299-300,531,773`). The HF 50 Hz packet exposes true specific force, gyro and quaternion (`engine.py:331-338`) → **perfect**, no bias or noise.
- **Altitude / forward range**: a single exact ray, `world.raycast` (sphere tracing, `simulator/qysim/world.py:396-406`), straight down/forward (`engine.py:286-288`, `engine.py:525`). There is no 25° cone, no 0.3 m blind zone, no vegetation or fish false returns. Max range 50 m forward and 100 m down; out-of-range returns the max value rather than "no echo" → **perfect within its range**.
- **Viewer altitude is not even a sensor reading**: the HUD computes `alt = W.seabed_depth - depth` from the *global flat* seabed depth (`simulator/viewer/app.js:888,892,894`), ignoring local terrain (`world.depth_at`) and obstacles. This is ground truth and possibly wrong over relief.
- **DVL velocity**: `QDVL`/`MicroDVL` X/Y/Z speeds equal the true body ground velocity `s.vel` (`engine.py:289-291,319-320`). `DVL_Status` is always `"OnLine"` (`engine.py:317`). `get_rov_data.dvl` is always `online: True`, with `vx, vy` = true world velocity, `x, y` = true position, `accuracy: 0.5` constant, and four beam ranges all equal to `alt/cos 22.5°` (`engine.py:540-545`) → **perfect, never loses lock in telemetry**.
- **DVL validity window (control only)**: `dvl_valid = 0.1 <= altitude <= 100.0` from true seabed depth under the vehicle, commented "Provisional simulated bottom-lock window, not a calibrated sensor model" (`engine.py:191-193`). When false, the controller forces `assist = 0` (`controller.py:141-142`). No hysteresis, slope, silt, bubble or vegetation condition applies, and it is not reflected in `DVL_Status` or `state`.
- **Position hold uses truth**: assist level 2 locks `v.s.pos` and servos on `position_hold - v.s.pos` (`controller.py:96-99`), and velocity feedback uses true `world_velocity()` (`controller.py:89`). Station-keeping is therefore perfect within thrust limits, with no DR drift.
- **Navigation / DR**: `Navigator.init_dr` only re-anchors the geodetic frame (`simulator/qysim/navigation.py:96-106`). Lat/lng is always `geo.to_geo(true pos)` (`engine.py:153-155`). `nav.step` receives true `s.pos`, yaw and velocity (`engine.py:174`) → DR has **zero drift**.
- **GPS**: online when depth <0.3 m, with fixed `hdop 0.9` and 14 satellites, at true lat/lng (`engine.py:535-539`).
- **USBL/UQPS/micro_dvl**: always `{"online": False}` (`engine.py:546-548`).
- **Temperature**: deterministic `26 − 0.15·depth` °C (`engine.py:296,529`). There is no thermocline, sensor lag or ±2–4 °C error.
- **Battery**: drains with thruster load (`engine.py:209-210`) and is reported as `Battery: Left/Right` and `power.type: "battery"` (`engine.py:293-294,532-533`), although X1 is tether-powered (`real-rov-research.md:11`).
- **Speed and current on HUD**: `speed_kn` is speed *through water* (true vel minus true current, `engine.py:775`), and `current_kn`/`current_here` is the true local current (`engine.py:784-785`). The HUD shows current (`viewer/app.js:894`). A real pilot has no current meter (only DVL-minus-water-track inference) → **ground-truth information leak**.
- **Latency**: physics runs at 100 Hz and the view at 30 Hz (`simulator/qysim/server.py:57`). The viewer delays onboard fields (`pos, q, euler, vel, speed_kn, thrust, battery, current_here, current_kn, silt, tether, events, damage, vehicles`) by the video delay, default 150 ms in real mode (`simulator/viewer/state_buffer.js:172-191`; `simulator/viewer/fidelity.js:297-300`). This is the only sensor imperfection modelled, and it is global (the same for every sensor).
- **Instructor injections**: only `thruster, battery, current, visibility, freeze` (`simulator/qysim/instructor.py:59-60`), with no sensor faults (compass, depth, DVL, sonar, video freeze or latency spike, leak).

### Inferences
- Because control loops also consume truth (`controller.py:89,96-99,156`), adding display-only noise would be the "fake fix" that `t20-validation.md:52` warns against. Sensor models must sit between physics and *both* telemetry and controller/navigator.

### Gaps
- I did not audit the T15 sonar viewer or the 3D HUD modules (`viewer/cockpit.js`, `attitude_indicator.js`) beyond confirming they read `state.euler`/`pos`. The SDK HF stream rate (50/10 Hz labels) vs actual send cadence was not traced.

---

## 11. Part C — ranked gaps and suggested models with validation targets

### Takeaway
Ranked by training impact (does a real pilot's decision depend on it?) and by how directly it is required by AGENTS.md ("定點只在 DVL 有效時可用", "與真實 ROV 一致") or T20. Each item needs a fidelity toggle (real on, assisted off) per AGENTS.md. Numbers are starting values from the cited sources. X1-specific values remain provisional per the AGENTS.md rule.

### Cited Findings (ranked list; sources as in §1–10)
1. **Shared sensor layer feeding controller + telemetry** (prerequisite). Add `qysim/sensors.py` producing a `SensorFrame` (depth, heading, attitude, gyro, altitude, range, DVL vel/valid/beams, DR pos, temp, power) each step with its own rate and latency. The controller (`controller.py:89,96-99,156`), navigator (`engine.py:174`), `sdk_status`, `get_rov_data`, `hf_status` and `state` read from it. Validation: with all noise off, outputs are bit-identical to today (protects `PROTOCOL.md`/sdk_mock). Seeded RNG per vehicle (`engine.py:67` pattern).
2. **Compass: magnetic deviation near steel and heading-hold runaway** (T20 requirement, unimplemented). Model each steel obstacle as a dipole-like disturbance: ΔB ∝ m_steel / r³ (Geometrics: 1 t → 1 nT at 30.5 m), deviation = atan2(ΔB_⊥, B_h), saturating to an erratic near field within about 1 body length. Fuse with a gyro (complementary filter, time constant 10–30 s per Xsens convergence). Fire an EKF-style "yaw re-aligned" step when the innovation exceeds a threshold. Feed the *estimated* heading to heading hold so runaway emerges. Validation: 5–10° deviation in the port/wharf scenario (Sonardyne); ≥30–45° when within 1–2 m of a large steel hull (rebar case); a scenario reproducing the 85 m wreck spin with auto-heading on and no spin with it off; deviation falls by 8× when distance doubles in the far field.
3. **DVL bottom-lock model + DR drift**. Valid when altitude is in the window (A50: 0.05–50 m; X1 provisional 0.1–100 m per Q-DVL claim, flagged) **and** at least 3 of 4 beams return. A beam fails when local slope exceeds a limit (≈45° at 1–2 m, 75° at 10 m, Sonardyne), when its footprint is over a vegetation/silt-cloud/bubble mask (`state.silt` exists, `engine.py:788`), or with probability rising toward max altitude. Add hysteresis: after loss below minimum, require climb to ≥ min+margin (Cerulean "2 m"). Velocity = truth + N(0, σ(alt)) + per-dive scale error U(±1 %). False-motion spikes when below min altitude or in prop-wash bubbles. DR = ∫ R(ψ̂)·v_dvl dt using **estimated** heading, frozen when invalid. Expose `DVL_Status`, `velocity_valid` and beam validity, and drop assist 1/2 to manual with an on-screen notice (AGENTS.md: 定點只在 DVL 有效時可用). Validation: in 15 min at 0.3 m/s, DR error ≈1 % of distance plus heading-induced cross-track (Cobra-Tac: up to 5 % with compass error); lock lost above window or over kelp/slopes; position hold degrades (Cerulean vegetation feedback) rather than staying rock-solid.
4. **Remove ground-truth leaks from the real-mode HUD**. `current_kn`/`current_here` (`app.js:894`), through-water `speed_kn`, and altitude from global seabed (`app.js:888`) should come from sensor outputs: altitude from altimeter/DVL, speed from DVL (ground-relative) or "—" when invalid, and current hidden in real mode (assisted overlay only). Validation: the real-mode HUD contains no field that cannot come from a sensor on the vehicle.
5. **Depth sensor**: surface zero offset at power-up (0 to ±1 m possible, FIFISH FAQ; default a few cm), a fresh/salt density selection (997/1029 kg/m³, a 3.2 % scale error if wrong), quantisation 2 mm, white noise σ ≈ 2–5 mm [assumption], output 10–50 Hz, and an optional pre-dive "zero depth" step (links to T23). Validation: static trace std within a few mm; 30.0 m true reads ≈31.0 m with the wrong water type; depth hold oscillation reflects noise.
6. **Altimeter/forward range as cone sensors**: return the minimum range over a 25° cone (Ping2) sampled with 5–9 rays, with a 0.3 m blind zone, resolution 0.5 % of range, "no echo" instead of max-range, false shallow returns over vegetation/fish masks, and wall multipath in confined scenes. Validation: on a 20° slope at 10 m altitude, altitude under-reads by the cone geometry; it reads "—" below 0.3 m.
7. **Gyro/attitude imperfections**: gyro bias random walk (yaw drift 0.1–0.3°/min after calibration, WL) and pitch/roll mount bias 0.2–2° with σ ≈ 0.1–0.2° (SeaTrac ±0.2°). Validation: with the magnetometer disabled, heading drifts 1.5–4.5° in 15 min.
8. **Instructor sensor-fault injections** (extends `instructor.py:59`): `compass` (offset/deviation), `depth` (offset/freeze), `dvl` (force loss of lock), `sonar` (dropout/false target), `video` (latency spike 1–2 s or freeze; disconnect with about 30 s reconnect per FIFISH FAQ), `leak` (humidity alarm). Each uses the existing `strength`/`duration` contract and reaction-time logging (`instructor.py:131-137`). Validation: each injection appears on the HUD, the corresponding automatic function degrades, and the trainee's reaction is logged.
9. **Per-sensor rates and latency**: replace the single 150 ms delay (`state_buffer.js:172-191`) with per-field sample-and-hold. Starting rates are video 150–200 ms (FIFISH), DVL 4–15 Hz, pressure about 20–50 Hz, USBL 2–4 Hz with an acoustic travel delay of range/1500 m/s. Validation: the HUD altitude updates visibly in steps at high altitude (4 Hz) vs low (15 Hz).
10. **Temperature and power**: a temperature sensor with ±2–4 °C bias and a first-order lag of tens of seconds [assumption], with an optional thermocline from the scenario. Replace X1 "battery %" with tether supply voltage, power draw and fault states (keep the existing SDK fields for compatibility). Validation: SDK `Battery` and `power` fields remain present; the X1 HUD shows supply power, not a draining battery.
11. **Acoustic positioning (optional, non-X1-standard)**: if `uqps`/`usbl` are enabled, fixes at 2–4 Hz with σ_bearing ≈ 1°, σ_range ≈ 0.1–0.2 %, outliers near walls and surface, and outages when the path is occluded (raycast between topside and vehicle). Validation: fix scatter is about 1.7 % of slant range; jumps occur near quay walls.

### Inferences
- Items 2 and 3 are the highest-value "same imperfect information" features. They change pilot decisions (manual yaw near steel, climbing to re-acquire, resurfacing to reset DR), and they are already demanded by T20 and AGENTS.md.
- All noise must be seeded for replay and instructor reproducibility, and must be switchable through `fidelity.js` (real = on, assisted = off) so that "assisted off = real mode" still holds.

### Gaps
- X1-specific values (Q-DVL window, compass placement, depth sensor class, telemetry rates) must come from `docs/reference/x1-measurement-checklist.md`. Suggested additions to that checklist: a static depth trace at 1 m for 5 min; heading readings at 1, 2, 5 and 10 m from a steel pile; DVL lock state vs altitude over sand/mud/weed; and app screenshots of each loss/alarm state.
- No published σ for small-DVL velocity noise or Ping2 range noise was found. Those are assumptions to be tuned.
