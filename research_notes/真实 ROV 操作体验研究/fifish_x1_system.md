# QYSEA FIFISH X1 and FIFISH family: vehicle, Q-iRC controller, app and operating behaviour (as of Nov 2026)

Reading guide: every fact is tagged with the model it applies to. **[X1]** = FIFISH X1 specifically. **[V6/V6s]**, **[V6E]** (V6 Expert), **[V-EVO]**, **[E-GO]**, **[Q-iRC]**, **[Q-DVL]**, **[App]** = other products. "Verified" means I read the page or document text myself; "snippet" means the fact came only from a search-result summary and the page itself was not opened (lower confidence).

Access notes: the official X1 technical-specification PDF (NauticExpo catalogue) returned HTTP 403, and no X1 user manual is publicly downloadable (QYSEA distributes manuals via a request form). The only full primary operating document I could read end to end was the FIFISH V6/V6s Quick Start Guide V1.4 and the FIFISH V6 APP/Help/FAQ V1.4. X1 numbers therefore come from QYSEA's X1 product page and one reseller page.

## X1 specifications (and sibling specs for comparison)

### Takeaway
The X1 is a 350 m, ≤30 kg, six-thruster vectored industrial ROV that is tether-powered (no onboard battery in the standard kit), with dual 4K cameras, 2 × 6,000 lm lights, forward and downward Q-DVL, and a 15 kg payload; it is a different class of vehicle from the 4–5 kg, 100 m, battery-powered V6 family. Per-axis speeds (4.5 / 3.5 / 2.5 / 1.5 kn) come from a single reseller page only; the official page confirms just "4.5 kn max, 4.0 kn current holding".

### Cited Findings

**[X1] vehicle**
- Six-motor vector layout with "Q-Motor Pro" thrusters; modular thrusters for quick swap; built-in overcurrent / overvoltage / overload alerts (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- Max speed 4.5 kn; current holding 4.0 kn; angle control ±0.1°; 360° omnidirectional control (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- Per-axis speeds: forward 4.5 kn, backward 3.5 kn, lateral 2.5 kn, vertical 1.5 kn; "up to 30 kg forward thrust"; 6 DoF with 360° roll, pitch, yaw (verified on reseller page; not confirmed on a QYSEA page) — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- The official catalogue wording is "4.0 knots* Max. Forward Current Holding" (snippet; PDF blocked) — [NauticExpo X1 technical specifications](https://pdf.nauticexpo.com/pdf/shenzhen-qi-yuan-science/fifish-x1-technical-specifications/70155-137888.html). One retailer describes this as "4-knot speed" (snippet) — [Maverick Drone X1](https://www.maverickdrone.com/products/fifish-x1); treat 4.0 kn as station-holding current, 4.5 kn as top speed.
- Operating depth 350 m; weight ≤30 kg; volume 0.17 m³; deployable by 1–2 people (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- Dimensions 770 × 560 × 400 mm (verified on reseller; matches catalogue snippet) — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Power: direct power supply through the tether, "24h×7" operating time; swappable battery appears as an option in the comparison table with unclear X1 status (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/). Reseller kit is "direct power supply system … no battery included" — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Tether: 350 m, 9.5 mm diameter, 300 kgf tensile strength, manual spool, IP66 (reseller, verified) — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Cameras: dual camera system, 1/1.8" CMOS sensors, 4K UHD, "ultra-wide" FOV with no figure given (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/). 12 MP stills, 1080p up to 120 fps, EIS, 2 × 128 GB internal storage (one per camera) (reseller) — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Lights: dual LED, 12,000 lm total (2 × 6,000 lm), 120° beam (verified on both) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/); [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Navigation sensors: forward and downward Q-DVL; station-lock hovering "in 4.0-knot currents"; optional U-INS Plus fused inertial navigation; real-time depth control; 3D route planning with point marking; tri-directional collision-avoidance sonar with adjustable avoidance distance (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- Dual lasers for ruler measurement (reseller) — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1); "QY-MT" AI vision measurement claimed at millimetre-level accuracy with offline data capture (verified, vendor claim) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- Payload: max 15 kg; four "Q-interface" power ports; payload swap about 5 minutes; "1+N" NDT / tool skids; listed tools: ultrasonic thickness gauge, cathodic-protection probe, multi-parameter sensor, water-jet cleaner; optional 2-axis robotic arm (verified) — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- In the box (reseller): ROV, direct-power system with 350 m tether on manual spool, Q-iRC controller, two industrial cases, two GNSS locators — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)
- Target applications: offshore oil and gas, offshore wind, large vessels, underwater foundations and pipelines — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- FIFISH app added "Support for the X1" in version 4.9.7, dated 20 Sep 2025 — [App Store FIFISH listing](https://apps.apple.com/ly/app/fifish/id1364364991)

**[V6 / V6s] (primary source: Quick Start Guide V1.4)**
- 383 × 331 × 143 mm; 3.9 kg; 6 thrusters = 4 vectored + 2 horizontal; 6 DoF (360° yaw, pitch, roll); max 3 kn (1.5 m/s) in still water; depth 100 m; operating temperature −10 to 60 °C; dive time up to 4 h; V6 battery 9,000 mAh / 97.2 Wh, V6s 14,400 mAh / 155.5 Wh — [FIFISH V6 Quick Start V1.4 (Adorama-hosted PDF)](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Posture Lock ±0.1° pitch or roll while moving in any direction; depth holding ±1 cm — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Camera: 1/2.3" Sony CMOS, 12 MP, FOV 166°, f/2.5, min focus 0.4 m, ISO 100–6400, shutter 5–1/5000 s, WB 2500–8000 K, EV ±3; 4K at 25/30 fps, 1080p up to 120 fps, 720p up to 240 fps; H.264/H.265; EIS; 64 GB internal (128 GB optional) — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Lights: 2 × 2,000 lm (4,000 lm total), 5500 K, 120° beam, 3 dimming steps — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Tether 100 m on spool, breaking force 80 kgf; spool 238 × 205 × 207 mm; V6s arm: 140 mm claw opening, 5.0 kg grip — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)

**[V6E] V6 Expert**
- 38.3 × 33.1 × 14.3 cm; 4.6 kg; 100 m; payload 5 kg; 3 kn (1.5 m/s); 156 Wh; runtime 1–4 h; 90% charge in about 1 h; −10 to 60 °C; one accessory port (9–12 V at 5 A, Ethernet, UART) — [QYSEA store V6 Expert](https://store.qysea.com/products/fifish-v6-expert)
- Camera FOV 166° in air, 96° underwater; 4K 25/30 fps; ISO 100–3200; lights 2 × 3,000 lm = 6,000 lm, 5500 K, 120°, 3 levels — [same](https://store.qysea.com/products/fifish-v6-expert)
- Sensor accuracies: gyro ±0.1°, accelerometer ±0.1°, magnetometer ±1°, depth lock ±1 cm, temperature ±1 °C — [same](https://store.qysea.com/products/fifish-v6-expert)
- Tether 100 m or 200 m, 4.6 mm diameter, 100 kgf, listed as neutrally buoyant; standard controller 5 GHz Wi-Fi, up to 4 h — [same](https://store.qysea.com/products/fifish-v6-expert)
- Accessories listed: laser scaler, external 4K Q-Camera, metal detector, retrieval hook, 500 mL water sampler, mud sampler, 2-finger arm, 3/100/200/300 m spools, propeller guards, Q-iRC — [same](https://store.qysea.com/products/fifish-v6-expert)

**[V-EVO], [E-GO]**
- Batteries: V-EVO 97.2 Wh; E-GO 69.12 Wh per swappable unit; all three (V-EVO, V6E, E-GO) rated −10 to 60 °C — [QYSEA store FAQ](https://store.qysea.com/pages/faq)
- V-EVO: 100 m tether, 3 kn max (snippet) — [Videomaker](https://www.videomaker.com/news/the-fifish-v-evo-shoots-4k-video-underwater/)

**[Q-DVL] accessory family**
- Station-lock hovering over a 0.1–100 m height range; max detection range 100 m; "centimetre-level" hover accuracy (no figure); "360° omnidirectional adaptive current resistance"; forward-inline and downward units both give real-time distance lock; downward unit gives altitude lock; variants: Q-DVL Plus, Q-DVL Max, Forward Inline Q-DVL, Q-Cam D/L, Tri-directional Inline Q-DVL — [QYSEA Q-DVL page](https://www.qysea.com/products/q-dvl-sensor/)
- AR Ruler / laser scaler: 650 nm red spot laser, 10 cm scale length, 100 m depth rating (snippet) — [QYSEA store AR ruler](https://store.qysea.com/ar-ruler.html)

### Inferences
- The X1 is roughly 6–7× the mass of a V6 Expert and has asymmetric axis speeds (forward 4.5 kn ≈ 2.3 m/s, lateral 2.5 kn ≈ 1.3 m/s, vertical 1.5 kn ≈ 0.77 m/s by unit conversion). A simulator tuned on V6-class numbers (3 kn all-round, 4–5 kg) would feel wrong for an X1.
- Because the X1 is tether-powered, "battery remaining" is not the operator's limiting resource in the standard configuration; tether length/drag (9.5 mm × 350 m) is.
- The "4.0 kn" figure is consistently phrased as current holding with Q-DVL station lock, not as speed.

### Gaps
- No verified official X1 spec sheet text: weight in water/buoyancy, thruster geometry (which of the six are vertical vs vectored), bollard thrust per axis, power draw, camera FOV and low-light figures, light colour temperature, tether buoyancy, operating temperature. The catalogue PDF exists but was blocked (403).
- X1 swappable-battery capacity and runtime: not found.
- W6 and PRO-series (V6 Plus, W6 Navi/Max) spec tables were not retrieved; I have no cited numbers for them.
- USBL accessory details: not found in any opened source.

## Q-iRC controller and the standard FIFISH remote

### Takeaway
The Q-iRC is an all-in-one controller with a built-in 7-inch 1500-nit screen running the FIFISH app, two sticks, two dials, two three-position switches, a five-way key and 12 buttons including 8 programmable keys; its default per-control mapping is not published. The standard V6-family remote's layout and mapping are fully documented and are the best available reference for default behaviour.

### Cited Findings

**[Q-iRC]**
- Controls: 2 joysticks, 2 rotary dials, 2 three-position switches, 1 five-directional key, 12 buttons — [QYSEA store Q-iRC](https://store.qysea.com/products/q-irc-remote-controller)
- 8 custom keys: L1, L2, R1, R2, K1, K2 are single-function customisable; K3, K4 are combination keys that switch operation windows — [same](https://store.qysea.com/products/q-irc-remote-controller)
- Screen 7 inch, 1920 × 1200, 1500 nits peak; brightness via swipe-down shade — [same](https://store.qysea.com/products/q-irc-remote-controller); QYSEA's other copy calls it "1080p Full HD" (snippet) — [QYSEA Q-iRC page](https://www.qysea.com/Q-irc/)
- Battery 10,400 mAh at 7.2 V; 8 h runtime (5.5 h at full power); 9 W; about 4.5 h charge with 27 W USB-C — [QYSEA store Q-iRC](https://store.qysea.com/products/q-irc-remote-controller)
- Ports: TF card, Ethernet, HDMI (external); USB-A, USB-C, ROV port (under cover); 4 GB RAM, 64 GB eMMC; Wi-Fi 2.4/5 GHz, Bluetooth, GNSS — [same](https://store.qysea.com/products/q-irc-remote-controller)
- IP54; operating −20 to 55 °C; 29.2 × 16 × 8 cm — [same](https://store.qysea.com/products/q-irc-remote-controller)
- HDMI at the bottom outputs the live FPV to an external monitor; FIFISH app is pre-installed and can be reinstalled from an APK on USB; no phone or tablet needed — [QYSEA Q-iRC support](https://store.qysea.com/pages/user-guide-q-irc); [QYSEA store FAQ](https://store.qysea.com/pages/faq)
- Two hardware versions: v1.5 for new-version V-EVO / V6 Expert / E-GO; v1.0 only for ROVs produced before 2024-11; not interchangeable — [QYSEA store Q-iRC](https://store.qysea.com/products/q-irc-remote-controller)
- Software on it: multi-window mission interface (video, heading, sensor data, system status), switchable/combinable windows for tool data, sonar and maps, one-tap view switch between camera / sonar / map, one-tap shortcuts for station keeping, diver tracking, obstacle avoidance — [same](https://store.qysea.com/products/q-irc-remote-controller)
- Reseller description: stick and scroll-wheel calibration, and Attitude / Sport / Combination mode options are available on the Q-iRC (snippet, reseller) — [Blue Skies Q-iRC](https://www.blueskiesdroneshop.com/products/qysea-industrial-remote-control)
- **[X1]** ships with the Q-iRC ("QY-iRC anti-water remote controller"), 7-inch 1500-nit, up to 8 h, HDMI/USB-A/USB-C/Ethernet — [Blue Skies Drone Shop X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)

**[V6/V6s] standard remote (primary source)**
- Labelled controls: 1 ON/OFF; 2 Depth Holding (ON/OFF); 3 LOCK/UNLOCK; 4 left stick; 5 right stick; 6 right wheel; 7 left wheel; 8 video record/stop; 9 control-mode switch (Attitude / Sport / Combine); 10 tether port; 11 Ethernet port; 12 LED brightness (OFF, 1, 2); 13 photo; 14 charging port; 15 micro-SD slot; 16 clamp release; 17 clamp for smart device — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Stick-mode presets are selected in the app under Go Dive / General Settings / second column, as "ROV Modes (USA/JPN/CHN)" and "UAV Modes (USA/JPN/CHN)". In the manual's mapping table for one stick axis pair, ROV mode gives ascend / descend / left / right while UAV mode gives pitch up / pitch down / roll counter-clockwise / roll clockwise — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Roll is only available in Sport or Combination mode — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- V6s arm: usable only in Attitude mode; right wheel opens/closes the claw — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Phone link: remote broadcasts 5 GHz Wi-Fi SSID "FIFISHRC_xxxx", password "1234567890"; at most 2 viewing devices (the HDMI box counts as one) — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf); [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- Remote battery LED colours: red <30%, yellow 30–70%, white ≥70%; up to 4 h life — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- Stick response is tunable in the app: "curvature" (0 = linear; >0 = steeper slope at larger stick deflection) and "attenuation" (max thruster output; 50 = 50% at full stick), set separately for "move" and "rotate" — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)

### Inferences
- The Q-iRC's two three-position switches plausibly correspond to the standard remote's two three-position controls (A/S/C control mode; lights OFF/1/2), and the two dials to the left/right wheels (camera tilt/pitch and arm/claw), but no opened source states the Q-iRC default mapping.
- "Attenuation" is the documented equivalent of a speed gear on the V6 family; I found no source describing discrete numbered speed gears.

### Gaps
- Q-iRC default function of each stick axis, dial, switch, five-way key and L/R/K key: not published on any page I could open (manual is request-only).
- The full ROV/UAV × USA/JPN/CHN mapping table (all four stick axes and both wheels) is a graphic in the manual; only the one axis pair above survived text extraction.
- What the left/right wheels do by default on the V6 remote (other than claw on V6s) is not in the extracted text.
- Q-iRC weight: not listed.

## Control and assist modes; behaviour on stick release

### Takeaway
Documented FIFISH flight modes are A (Attitude), S (Sport) and C (Combination/VR head tracking), plus a separate Depth Holding toggle, Posture Lock, and, with Q-DVL hardware, station lock / distance lock / altitude lock. Without a DVL the vehicle holds depth and attitude but not horizontal position; with Q-DVL (standard on X1) it holds position against current.

### Cited Findings
- **[V6/V6s]** Attitude mode: for beginners; the ROV will not roll; with depth holding ON it stays at the same depth while moving, even with a pitch angle — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6/V6s]** Sport mode: enables roll, so all 6 DoF; fly from first-person view; with depth holding ON the ROV only holds depth when there is no command input — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6/V6s]** Combination mode: activates VR-goggle head tracking for pitch, roll and yaw, working together with the remote; head-tracking icon is greyed out unless in C mode — [same](https://www.adorama.com/col/productManuals/QYM200A.pdf); [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6/V6s]** Depth Holding is a dedicated button on the remote; accuracy ±1 cm. Posture Lock holds ±0.1° pitch or roll while translating in any direction (e.g. moving sideways while tilted ±90°) — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6/V6s]** With thrusters connected but in air, the motors keep running because the attitude algorithm is trying to balance the vehicle; this is stated as normal — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6/V6s]** A continuous beep after power-on is a "battery saving alarm"; turning Depth Holding on stops it — [same](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V-EVO/V6E/E-GO]** Current FAQ: depth holding applies in A and S modes; Posture Lock holds the ROV's angle while moving forward/backward; "Station Hovering" is listed as precision hovering in current (no numbers) — [QYSEA store FAQ](https://store.qysea.com/pages/faq)
- **[Q-DVL]** Fuses DVL with IMU, depth sensor and magnetometer for underwater inertial navigation, station-lock hovering and collision avoidance (snippet) — [NauticExpo Q-DVL](https://www.nauticexpo.com/prod/shenzhen-qi-yuan-science/product-70155-620320.html); height range 0.1–100 m, distance lock and altitude lock — [QYSEA Q-DVL page](https://www.qysea.com/products/q-dvl-sensor/)
- **[X1]** Station-lock hovering stable in 4.0 kn current using forward + downward Q-DVL; AI collision avoidance with adjustable avoidance distance; 3D route planning with point marking — [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- **[All FIFISH per vendor]** AI Vision Lock: modes named Focus Lock (centre of frame is held as the target and re-acquired as attitude changes), One-touch Lock, Slide Lock, Station Zoom, Off-center Lock, plus "Station Hold" against current; subject selected by tap, pinch or swipe; uses dead reckoning; free app upgrade for V6, V6s, V6 Expert, PRO V6 Plus, PRO W6 — [QYSEA AI Vision Lock](https://www.qysea.com/technology/underwater-ai-vision-lock/)
- **[E-series, V6E, V-EVO]** Diver tracking added in app releases 4.7.x–4.9.3 — [App Store FIFISH listing](https://apps.apple.com/ly/app/fifish/id1364364991)

### Inferences
- Stick-release behaviour by mode on a non-DVL FIFISH: depth is held (if Depth Holding ON), pitch/roll/heading attitude is held by the stabiliser, but horizontal position is not; the vehicle coasts and drifts with current. This follows from the manuals describing only depth and attitude holds, and station hold being tied to Q-DVL / vision lock. No source states the coast-down distance or time.
- The Attitude vs Sport distinction on depth hold is material: in Attitude, forward stick at a pitched attitude still yields level travel at constant depth (world-frame); in Sport, translation is body-frame and depth hold only re-engages when sticks are centred.
- For the X1, station lock is the documented hands-off behaviour; whether it auto-engages on stick release or needs a button press is not stated.

### Gaps
- No source describes a separate "heading hold" toggle; heading stabilisation appears implicit.
- Numeric speed gears, yaw-rate limits and acceleration limits: not published for any model.
- X1 mode names (whether A/S/C applies to X1) are not confirmed by an X1-specific source.
- Station-lock position accuracy in numbers, and behaviour when DVL bottom-lock is lost: not found.

## FIFISH app live-view interface

### Takeaway
The V6-generation app HUD is documented by a labelled screenshot: depth bar on the left, attitude (3D model) lower-left, compass and ROV heading lower-right, status/lights/depth-hold/RC settings/battery along the top, record controls down the right side and camera parameters along the bottom. The Q-iRC/X1-generation app adds multi-window layouts (camera/sonar/map), a customisable toolbox and accessory windows, but no detailed layout for it is public.

### Cited Findings
- **[V6/V6s] HUD layout** (from the labelled FPV figure): top row = Status, LED brightness, Depth Holding ON/OFF, RC settings, Battery, General settings; upper middle = Control Mode and Signal Strength; left edge top-to-bottom = Main Menu, Depth Indicator, FPV Flip, Posture Indicator; right edge top-to-bottom = VR ON/OFF, Photo/Video switch, Picture, Record/Stop, Video Mode select, ROV Heading; bottom row = ISO, WB, Shutter speed, EV, Resolution & frame rate, Time/photos remaining, Camera settings, Compass — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Depth bar auto-scales through three ranges: 0–5 m, 5–30 m, 30–100 m — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6]** Depth may read over 1 m before the dive because of zero-pressure offset; fix via calibration ("…" icon top-right, third column: Gyro-Acce Calibration, then Mag Calibration) — [same](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6]** Compass in the right corner indicates the operator's direction; ROV heading shown in degrees (0 N, 90 E, 180 S, 270 W); a 3D model of the vehicle shows attitude in the FPV — [same](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6]** Home page shows "Connected" at bottom-right before "Go Dive"; "Help" on the home page contains "Maintain" (motor cleaning program) and FAQ — [same](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6]** Settings include Live Resolution (480P/720P) and Live Bitrate (e.g. 1M) — [same](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[App]** ROV battery percentage appears on the camera screen once "Connected" — [QYSEA disconnect troubleshooting guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)
- **[App]** Store description: real-time 1080p video with real-time depth, direction and camera-parameter data; one-button photo/record — [App Store FIFISH listing](https://apps.apple.com/ly/app/fifish/id1364364991)
- **[App] release notes relevant to HUD/features**: 4.9.0 (Nov 2024) Q-DVL Range Mode, QCamDL AR ruler; 4.9.2 Q-DVL range setting, NDT thickness gauge, two-axis arm; 4.9.3 manual/automatic ranging, pre-use self-check (E-series); 4.9.4 depth-status interaction for all ROVs, motor status logs (E/W series); 4.9.5 tri-directional Q-DVL (W series), custom ToolBox; 4.9.6 custom watermark and humidity reminder (E-series); 4.9.7 X1 support; 4.9.8 E-series direct power — [same](https://apps.apple.com/ly/app/fifish/id1364364991)
- **[Q-iRC / X1]** Multi-window display with video, heading, sensor data and status; windows for tool data, sonar and maps; mission log recording with voice memos; sonar and mapping data on one screen — [QYSEA store Q-iRC](https://store.qysea.com/products/q-irc-remote-controller); [QYSEA X1 page](https://www.qysea.com/fifish-x1/)
- **[V-EVO]** Adaptive AI plankton-filtering algorithm suppresses white particles from plankton/bacteria (snippet) — [QYSEA V-EVO page](https://new.qysea.com/fifish-v-evo)
- **[App]** AR Ruler combines AR overlay with laser scaling inside the app (snippet) — [QYSEA store AR ruler](https://store.qysea.com/ar-ruler.html)

### Inferences
- Temperature and tether-length readouts are not in the V6 HUD figure labels; a water temperature sensor exists on the V6 Expert (±1 °C), so a temperature readout probably exists in later app versions, but placement is unverified.
- There is no evidence of a tether-payout counter in the app; the documented spools are manual.

### Gaps
- No current (2025–2026) annotated screenshot of the app on Q-iRC with X1 was found; element positions for the X1 layout are unknown.
- Sonar overlay appearance, DVL velocity/altitude readout placement, and collision-avoidance warnings on screen: not described in any opened source.
- App Store page showed no user reviews or ratings.

## Operating procedures, warnings and limits

### Takeaway
The documented V6-family sequence is: power the remote, connect the tether (the ROV powers on automatically), wait for solid LEDs and "Connected", place the ROV in water by the tether, then unlock thrusters; recovery is lock, stop recording, pull by tether; post-dive is a freshwater soak plus a 10-minute motor cleaning program. No X1-specific procedure is public.

### Cited Findings
- **[V6/V6s] Power-on**: hold ON/OFF until 7 rising chimes; the three button LEDs (ON/OFF, Depth Holding, LOCK/UNLOCK) rotate clockwise = "ready to be connected"; plug tether into remote; remove cap and tie the tether loop around the rear wing; plug tether into ROV, which powers on automatically with 5 chimes (Do Re Mi Do Mi); ON/OFF and LOCK/UNLOCK solid = hardware link good — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V-EVO/V6E/E-GO]** Current guide: long-press ON/OFF 3 s; three LEDs flashing in sequence means the remote cannot talk to the ROV — [QYSEA disconnect troubleshooting guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)
- **[V6/V6s] Launch**: lower into the water by the tether only, do not throw; unlock thrusters once in the water; depth should exceed 1 m for best behaviour — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Do NOT unlock thrusters in air; do not run thrusters in air more than 30 seconds (overheating) — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf); [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** If unlocked on the surface and it will not move or spins in place, the two horizontal motors are out of the water; dive first and turn on depth holding — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6/V6s] Recovery**: lock thrusters and stop recording before closing the app; retrieve by pulling only on the tether — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Tether unplugged mid-dive: control and video are lost; the remote reconnects in about 30 s, or reboot the remote — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V6/V6s] Post-dive**: soak at least 1 hour, run motors in fresh water at least 10 minutes (app Help > Maintain > cleaning program, auto-stops at about 10 min), rinse, air-dry out of direct sun; keep connectors dry and capped; check propellers for weed/line; shake sand out through vent holes; inspect tether — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf). Newer FAQ says soak/rinse at least 30 minutes — [QYSEA store FAQ](https://store.qysea.com/pages/faq) (sources differ: 1 h vs 30 min)
- **[V6]** Safety list: do not touch running propellers; do not look into LEDs; mind tide, water level and traffic; avoid reefs, rocks, weed and fishing line — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Limits: operating −10 to 60 °C (ROV, remote and spool); charge only at 10–45 °C; phone/tablet above 0 °C; storage 5–25 °C at 50–60% charge, cycle every 90 days — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf); [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Warranty excludes damage from "bad water conditions (i.e. strong currents, huge waves)"; no numeric current limit is given — [FIFISH V6 Quick Start V1.4](https://www.adorama.com/col/productManuals/QYM200A.pdf)
- **[V6]** Troubleshooting off-axis motion (e.g. climbing on a slope instead of straight up): test one axis at a time, check thrusters for entanglement, run Maintain, then gyro/accelerometer and magnetometer calibration, then remote calibration — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[E-series]** App has a pre-use self-check (4.9.3) and humidity reminder (4.9.6) — [App Store FIFISH listing](https://apps.apple.com/ly/app/fifish/id1364364991)
- **[Q-iRC]** Wipe dry after use; damp cloth after salt spray; check gaskets and port covers — [QYSEA Q-iRC support](https://store.qysea.com/pages/user-guide-q-irc)

### Inferences
- The X1 probably follows the same lock/unlock and "do not run in air" logic, since it uses the same app, but its topside power unit adds steps (mains/generator, power-on of the supply) that are undocumented publicly.

### Gaps
- X1 pre-dive checklist, power-supply start-up sequence, launch/recovery method for a 30 kg vehicle, and its numeric environmental limits: not found.
- No manual states a maximum operating current speed for V6-class vehicles.

## Behaviours reported by real users and reviewers

### Takeaway
I found almost no credible independent first-hand operator reports; the web results are dominated by vendor pages, reseller copy and low-quality affiliate "best drone" lists. The only hard handling numbers are vendor-stated: 150–200 ms video latency and the specs above.

### Cited Findings
- **[V6, also quoted for V-EVO/V6E/E-GO]** Vendor-stated FPV latency 150–200 ms; worse if the phone is more than 5 m from the remote, at 720P live resolution, on pre-2017 phones, or indoors with Wi-Fi interference; mitigation is 480P live and 1M bitrate — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf); [QYSEA store FAQ](https://store.qysea.com/pages/faq)
- **[V6]** Known operator-facing quirks acknowledged by the vendor: spinning in place on the surface when horizontal thrusters are not submerged; ascending/descending on a slope when thrusters are fouled or sensors need calibration; depth reading offset before dive; 3D attitude model not matching the real orientation until calibration; FPV black when a third device connects — [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- **[V-EVO/V6E/E-GO]** "Disconnected" is common enough to have a dedicated vendor guide; causes listed include loose/dirty tether connectors, phone auto-switching off the no-internet Wi-Fi, VPN/Private Relay, and magnetic or RF interference near large metal structures — [QYSEA disconnect troubleshooting guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)
- **[General]** Vendor's own buyer guide concedes that current makes drones drift, tilts the shot and raises pilot workload, and its spool page recommends shorter tethers to minimise cable drag (snippets) — [QYSEA buyer's guide](https://store.qysea.com/blogs/rov-knowledge/rov-buyers-guide-how-to-choose-an-underwater-drone); [QYSEA 100 m spool](https://store.qysea.com/products/100m-328ft-tether-spool)
- **[V6]** A 2020 Blue Robotics forum thread asking for V6 experiences got no first-hand answers; a respondent noted closed-source drones are rarely discussed there — [Blue Robotics forum](https://discuss.bluerobotics.com/t/any-perspectives-on-the-fifish-v6/7212)
- **[V-EVO]** An affiliate review site claims the tether "will still drift with the current" and that the vehicle held frame on a coral head for over 90 s in calm water (snippet; site quality is poor and mixes other brands' text, treat as unreliable) — [markus-hagner-photography.com](https://markus-hagner-photography.com/?p=129755)

### Inferences
- Realistic "feel" details that are supported: roughly 0.15–0.2 s glass-to-glass latency; no horizontal position hold without DVL; calibration-dependent heading/attitude display; surface handling is poor until fully submerged.
- Tether drag for the X1 should be much more significant than for V6-class vehicles (9.5 mm vs 4.6 mm diameter, 350 m), but no source quantifies it.

### Gaps
- No independent X1 operator reviews, videos transcripts or forum posts were found (the X1 only gained app support in Sept 2025).
- No measured data on drift rate, stopping distance, yaw rate, thrust response time, or tether drag for any FIFISH model.
- Reddit, YouTube transcripts and underwaterdroneforum.com were not reachable through the search tool; a targeted manual check of those would be the next step.
- QYSEA OpenSDK documentation was not located in this pass.
