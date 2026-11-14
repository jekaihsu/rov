# Tethered observation-class ROV: communication link, video link and power, how they fail, and repo gaps

Scope: QYSEA FIFISH X1 (and V6 family as proxy), BlueROV2 (Fathom-X / Outland), Deep Trekker, VideoRay. Part B audits `simulator/` read-only. Part C ranks gaps.
Tags: [verified] = read on the fetched page; [snippet] = only seen in a search-result summary, not the full page; [inference] = my derivation.

## Tether communications: bandwidth, latency, degradation, what the pilot sees, reconnect

### Takeaway
Small ROVs typically run Ethernet over one copper twisted pair with HomePlug AV modems (Fathom-X: 200 Mbps PHY, about 80 Mbps best case, about 15–30 Mbps measured at 300 m). Degradation is not gradual and graceful. Throughput can collapse to under 1 Mbps while the link still associates, latency spikes to 0.5–3.5 s, and video freezes or lags 4–5 s while control and telemetry can keep working. Water ingress into the tether, connectors and topside modem faults are the dominant causes. No public fibre-vs-copper data or reconnect times exist for X1. The only vendor figure is about 30 s to reconnect after a mid-dive cable unplug on the V6.

### Cited Findings
- Fathom-X: HomePlug AV (IEEE 1901) module, 2–30 MHz, 200 Mbps physical-layer rate, about 80 Mbps "max practical" vendor-tested. It needs a single twisted pair (12–30 AWG). Rated length is 300 m tested and 2000 m "published". It draws 2.5 W max. The page lists power, link and data LEDs and gives no bandwidth-vs-length or latency data [verified] — [Blue Robotics Fathom-X](https://bluerobotics.com/store/comm-control-power/tether-interface/fathom-x-tether-interface-board-set-copy/)
- Blue Robotics staff: HomePlug uses 84 subcarriers in 4.5–21 MHz. Some cable constructions show bandwidth that *increases* past a certain length before falling again, so range is hard to predict [verified] — [BR forum 7304](https://discuss.bluerobotics.com/t/new-purchase-pending/7304/11)
- Staff: the maximum reliable comms distance is 300 m over Fathom tether with Fathom-X and 200 m over Fathom Slim [snippet] — [BR forum search summary](https://discuss.bluerobotics.com/t/fathom-x-link-speed/6914)
- Field case, 300 m Fathom tether (26 AWG, about 42 Ω per conductor, about 85 Ω loop) [verified] — [BR forum 23523](https://discuss.bluerobotics.com/t/300m-tether-link-associates-but-throughput-collapsed-from-30-mbps-to-0-3-mbps-overnight/23523):
  - Healthy baseline: about 30 Mbps. A 2 ft direct pair gave 35/61 Mbps (down/up) at PHY 148/139 Mbps.
  - Individual pairs over 300 m: 18.5/27, 15/22.5 and 13/15.5 Mbps (PHY 55, 48, oscillating 0–41 Mbps). One pair gave no link at all.
  - At fault onset, throughput was 0.3–1.5 Mbps while the link still "associated". Ping lost 12% (6/50) with min 13 ms, avg 717 ms and max 3455 ms, and later lost 20/20. Latency through the 300 m tether alone was 500–3000 ms.
  - The pilot saw no connection in the control app (Cockpit/BlueOS) or the camera software (VMS), or intermittent links with 0.5–3.5 s latency.
  - Cause: a slow leak into the tether sheath, giving frequency-dependent loss. Drying for a week restored 78/77 Mbps, which then decayed to 35–61 Mbps after further dives. Staff advised cutting the ROV end, where tension and pressure are highest.
- Field case: intermittent video loss, video lag of up to about 4–5 s and compression artefacts, while lights, helm and camera tilt **still responded**. The mission was scrubbed. A bench test isolated the fault to the topside Fathom-X board, and replacing that board fixed it. A heat build-up hypothesis was raised but not confirmed [verified] — [BR forum 3344](https://discuss.bluerobotics.com/t/fathom-x-video-freeze-five-second-lag/3344)
- Other reports [snippet] — [BR forum search summary](https://discuss.bluerobotics.com/t/lost-connection-issues/1812):
  - Video freezes about 5 s roughly every 20 s.
  - Over 30–90 m of tether without Fathom-X, packet loss jumps between 0% and about 50% without a full disconnect.
  - Fathom-X boards are sensitive to salt water, and a batch from 2022 had an incorrect TVS diode ([BR TB06](https://bluerobotics.com:443/wp-content/uploads/2022/07/Blue-Robotics-TB06-FathomX-Diode-1.pdf), not opened).
- HomePlug AV in general: real throughput is about 20–30% of the rated rate [snippet] — [TP-Link FAQ](https://www.omadanetworks.com/ar/support/faq/2928/); about 40 Mbps typical for AV-200 [snippet] — [SmallNetBuilder](https://www.smallnetbuilder.com/?p=31585)
- FIFISH V6 (vendor FAQ):
  - Live video latency is 150–200 ms. It gets worse with the phone more than 5 m from the remote, 720P, an old phone or indoor Wi-Fi interference.
  - After a mid-dive cable unplug, control and video are lost and reconnect takes about 30 s.
  - Already captured in the repo's research report; cited there to [FIFISH V6 APP/Help/FAQ V1.4](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf), see `docs/reference/real-rov-research.md:33`.
- QYSEA "Disconnected" troubleshooting guide [verified] — [QYSEA guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide):
  - Causes:
    - low ROV or RC battery (RC LED: white ≥70%, yellow 30–70%, red <30%)
    - loose or backed-out couplings at the ROV port, spool or RC
    - app permissions
    - the phone leaving the RC's `FIFISHRC_` hotspot (Android drops networks that have no internet access)
    - RF interference from towers, broadcast equipment or large metal structures (fix: a wired Lightning-to-Ethernet adapter)
    - water ingress or impact damage
  - Symptoms: the app shows "Disconnected" and RC LEDs keep blinking instead of staying solid.
  - The guide gives no reconnect interval and no Wi-Fi range.
- X1 / Q-iRC: the remote has a built-in screen and HDMI/USB-A/USB-C/Ethernet ports, and runs "up to 8 hours". The reseller page does not mention Wi-Fi or the tether conductor type (copper vs fibre) [verified] — [Blue Skies X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1)

### Inferences
- [inference] On copper/HomePlug systems, link quality is a hidden stochastic state that collapses in steps. Throughput falls first, then latency balloons (queueing; avg about 0.7 s, max about 3.5 s), then packets drop. Video, being the largest stream, fails first: freeze, lag, artefacts. Control and telemetry, at kbps scale, often survive. The trainee-relevant cue is "video frozen but the vehicle still responds".
- [inference] Video latency is not fixed. A baseline of 150–200 ms can grow to seconds when bandwidth falls below the stream bitrate, because buffers fill. The pilot then sees stale video with a growing gap that recovers in a jump.
- [inference] Because X1 has an integrated Q-iRC screen, the V6 "phone more than 5 m from the remote / Wi-Fi" degradation mostly does not apply to X1 piloting, except for secondary displays. That is unverified.

### Gaps
- No published Mbps-vs-length curve for Fathom-X or HomePlug on ROV tether. Only the single 300 m case above.
- No X1 tether construction (copper pair vs fibre), modem type, video bitrate, codec or reconnect time. The measurement checklist item 17 (`docs/reference/x1-measurement-checklist.md:34`) covers this.
- No VideoRay or Deep Trekker link-degradation data was retrieved within the budget.

## Failsafes on loss of comms

### Takeaway
ArduSub (BlueROV2) offers configurable actions on two independent timers:
- Pilot-input loss: 0.1–3.0 s range; disarm or warn.
- GCS-heartbeat loss: default 5 s; warn, disarm, depth hold or surface.

The vehicle stays in the failsafe mode after the link returns, and the pilot must re-arm or reselect the mode. A Deep Trekker ROV disables motors and lights at "empty" battery. X1's failsafe behaviour is undocumented.

### Cited Findings
- `FS_GCS_ENABLE` values: 0 disabled, 1 warn, 2 disarm, 3 depth hold (ALTHOLD; disarm if the mode change fails), 4 surface. `FS_GCS_TIMEOUT` defaults to **5 s**. The failsafe is inactive if no GCS has ever connected. After the GCS returns, the vehicle "will remain in its failsafe mode" [verified] — [ArduSub GCS failsafe](https://ardupilot.org/sub/docs/gcs-failsafe.html)
- `FS_PILOT_INPUT`: 0 disabled, 1 warn, 2 disarm. `FS_PILOT_TIMEOUT` range is 0.1–3.0 s. It triggers when both RC and MAVLink RC overrides are absent. After clearing, the vehicle stays in failsafe, and if disarmed it must be re-armed [verified] — [ArduSub pilot control failsafe](https://ardupilot.org/sub/docs/pilot-control-failsafe.html); [ArduSub params 4.5.7](https://ardupilot.org/sub/docs/parameters-Sub-stable-V4.5.7.html)
- A forum user says the pilot-input failsafe by default disarms after 3 s without new input, and another post says a later PR doubled the default [snippet, conflicting] — [BR forum 18718](https://discuss.bluerobotics.com/t/failsafe-configuration-while-overriding-rc-with-pymavlink/18718); [BR forum 11162](https://discuss.bluerobotics.com/t/python-script-manual-mode-thrusters-return-to-neutral-after-a-few-seconds/11162)
- Other ArduSub failsafes [verified] — [ArduSub params 4.5.7](https://ardupilot.org/sub/docs/parameters-Sub-stable-V4.5.7.html):
  - leak (`FS_LEAK_ENABLE`: warn or surface)
  - internal temperature (`FS_TEMP_ENABLE` / `FS_TEMP_MAX` in °C: warn only)
  - internal pressure (`FS_PRESS_*`: warn only)
  - EKF (warn or disarm)
  - crash check (warn or disarm)
  - terrain (disarm, hold, surface)
  - battery (`BATT2_FS_LOW_ACT`: none, disarm, surface; `BATT2_LOW_TIMER` 0–120 s)
- Blue Robotics operation guide: on loss of power or communications, recover the vehicle by pulling the tether at moderate speed. Captured in the repo report at `docs/reference/real-rov-research.md:100` — [BR BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Deep Trekker: recovery can be by thrusters, or by disabling motors and pulling the tether. The DTG3 has a user-toggleable controller auto-shutdown [snippet] — [Deep Trekker DTG3 getting started](https://support.deeptrekker.com/vehicles/rovs/dtg3/getting-started)

### Inferences
- [inference] On loss of commands, ArduSub with disarm zeroes thrust, so a positively buoyant ROV slowly ascends and drifts with current and tether. With depth hold it actively holds depth until the battery is exhausted. A training sim should let the instructor choose the policy and should show the latched state that needs a deliberate re-arm.
- [inference] Real timers are in seconds (3–5 s). The repo's 0.6 s lock is a network-input watchdog, not a vehicle failsafe model (see Part B).

### Gaps
- X1/FIFISH loss-of-comms behaviour (stop thrusters? hold depth? timeout?) is not published. Only "lose control and video, about 30 s reconnect" (V6).
- VideoRay failsafe behaviour was not retrieved.
- The exact ArduSub default for `FS_GCS_ENABLE` and the current `FS_PILOT_TIMEOUT` were not confirmed.

## Power: tether-powered vs battery, voltage drop, thrust caps, thermal, lights

### Takeaway
Tether-powered systems send high-voltage DC (BlueROV2/Outland about 400 VDC, converted to 15 VDC subsea, 1000 W max, 92% efficient). This keeps I²R drop small. Low-voltage tether power is limited by Ohm's law, and maximum delivered power occurs at a 50% voltage drop. Battery ROVs disable motors and lights at an "empty" threshold. The reseller "700–800 VDC" claim for X1 could not be verified on any page fetched.

### Cited Findings
- Outland Technology Power Supply for BlueROV2 [snippet] — [BR integration guide](https://bluerobotics.com/learn/outland-technology-power-supply-bluerov2-integration/); [Hydro International](https://www.hydro-international.com/content/news/bluerov2-connected-through-the-tether-cable-eliminates-the-need-for-batteries):
  - 100–240 VAC in, about 400 VDC on the tether.
  - Two 23 AWG pairs carry power, plus a 24 AWG pair for earth ground used in fault detection.
  - A built-in ground fault interrupter (GFI, also called a line insulation monitor or LIM) cuts output on unsafe leakage.
  - The subsea converter goes from 400 VDC to 15 VDC, 1000 W max, 92% nominal efficiency, rated to 300 m.
- A forum reply: AC or tether power without a line isolation monitor is "EXTREMELY DANGEROUS"; tether damage must immediately cut subsea power [verified] — [BR forum 23040](https://discuss.bluerobotics.com/t/powering-bluerov2-from-shore-power-230v-ac-over-150m-tether/23040)
- Forum/staff: maximum power transfer occurs at a 50% voltage drop. One estimate is 22 AWG at 400 m giving about 20% drop at 500 W and 15 VDC. A 250–300 m tether has run an 8-thruster BlueROV2 from a 500 W supply when currents are low [snippet] — [BR forum 686](https://discuss.bluerobotics.com/t/external-power-via-tether/686); [BR forum 7488](https://discuss.bluerobotics.com/t/maximum-tether-size/7488)
- QYSEA sells a separate direct power system for its E-series with 110 VAC in, 400 VDC out and a 400 m cable. It is **not** the X1 unit [snippet] — [Adorama QYSEA E-series PSU](https://www.adorama.com/qysea-direct-power-supply-system-e-serial-rov/p/qyeserialrov)
- X1 is tether-powered with no battery, marketed as continuous "24/7", with a 350 m, 9.5 mm, 300 kgf tether. Two 6,000 lm LEDs with no wattage given. No voltage or power is published [verified] — [Blue Skies X1](https://www.blueskiesdroneshop.com/products/qysea-fifish-x1). The X1 catalogue lists headings for input voltage, output voltage and maximum output power, but the values were not extractable [snippet] — [NauticExpo X1 spec](https://pdf.nauticexpo.com/pdf/shenzhen-qi-yuan-science/fifish-x1-technical-specifications/70155-137888.html)
- Deep Trekker battery behaviour [snippet] — [Deep Trekker power systems](https://support.deeptrekker.com/power-systems):
  - Motors and lights are disabled when voltage hits the "empty" threshold, and re-enabled once voltage rises enough above it.
  - Charging takes about 2.5 h from empty, at 4–35 °C.
  - A fully charged DTG3 reads 19.72 V.
- BlueROV2 Li-ion: recover at 12.5 V, with permanent damage risk below 12.0 V (4S). Already in the repo report at `docs/reference/real-rov-research.md:100` — [BR BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- FIFISH V6: never arm in air, and thrusters must not run in air more than 30 s. In the repo report at `real-rov-research.md:31` — [FIFISH V6 FAQ](https://aonic.com/la/wp-content/uploads/2023/03/APP_Help_FAQ-V1.4-20200608-EN.pdf)
- ArduSub internal-temperature failsafe is warn-only [verified] — [ArduSub params](https://ardupilot.org/sub/docs/parameters-Sub-stable-V4.5.7.html)

### Inferences
- [inference] Voltage drop for an Outland-style tether, using the standard copper table (23 AWG ≈ 0.067 Ω/m, two conductors in parallel per leg ≈ 0.033 Ω/m):
  - At 250 m, the loop is 500 m ≈ 17 Ω.
  - Delivering 1000 W at 92% takes about 2.7 A, so the drop is about 46 V (about 11% of 400 V).
  - At 15 VDC on the same tether, it would be impossible.
  - This is why the high-voltage architecture exists. A sim does not need a full electrical solver.
- [inference] Model for a tether-powered vehicle: an available-power budget P_max (vehicle-specific, provisional for X1). Thrusters, lights and payload share it.
  - When total demand exceeds P_max, scale thruster commands so all thrusters running at once cannot reach individual maximums.
  - A further rule only if supported: an under-voltage trip, where the GFI/LIM or converter cuts power, means total loss of thrust, lights and video.
- [inference] Thermal: out-of-water thrusters overheat in seconds to tens of seconds (vendor 30 s rule). Electronics heat under continuous high thrust in warm water. Real vendors expose temperature telemetry and warnings, and sometimes derate. ArduSub is warn-only.

### Gaps
- X1 supply voltage (the "700–800 VDC" reseller claim) is unverified. X1 P_max, light wattage, thruster current and thermal derating are all unknown and need measurement or vendor documentation.
- BlueROV2 per-thruster current and light wattage were not fetched. The Blue Robotics T200 and Lumen pages give these.
- No source found on surface-generator issues for small ROVs (sag, frequency drift, tripping GFI).

## Topside equipment failures and what the operator app shows

### Takeaway
The commonly reported failures are:
- water creeping into the tether jacket or connectors (gradual bandwidth loss, recoverable by drying, recurring)
- a degraded or salt-damaged topside modem board
- loose couplings
- ground-fault/insulation trips on high-voltage supplies
- phone or Wi-Fi hotspot problems on the FIFISH family

Operator displays show a link state (connected/disconnected, LEDs), battery or power, and on BlueOS a tether diagnostics extension.

### Cited Findings
- Tether sheath leak → asymmetric per-pair degradation, partial recovery after drying [verified] — [BR forum 23523](https://discuss.bluerobotics.com/t/300m-tether-link-associates-but-throughput-collapsed-from-30-mbps-to-0-3-mbps-overnight/23523)
- Topside Fathom-X degradation → video freeze or lag, control still working [verified] — [BR forum 3344](https://discuss.bluerobotics.com/t/fathom-x-video-freeze-five-second-lag/3344)
- Staff diagnostics: check that the topside link LED stays lit, and use the BlueOS Tether Diagnostics extension or iperf3 [verified] — [BR forum 23523](https://discuss.bluerobotics.com/t/300m-tether-link-associates-but-throughput-collapsed-from-30-mbps-to-0-3-mbps-overnight/23523)
- Intermittent Outland power-supply faults and isolation faults are reported in forum threads [snippet] — [BR forum 11802](https://discuss.bluerobotics.com/t/outland-power-supply-intermittent-fault/11802)
- BlueOS Cockpit flashes the screen border green or red on connect or disconnect. FIFISH V6 HUD shows battery and signal strength top-centre. Already in the repo report at `docs/reference/real-rov-research.md:27,57` — [Cockpit docs](https://blueos.cloud/cockpit/docs/latest/usage/advanced/)
- QYSEA: RC LEDs blink while disconnected and stay solid when connected. RC battery LED is white, yellow or red at the 70% and 30% thresholds [verified] — [QYSEA guide](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)
- IMCA SF 02/23: a tether chafed on a jacket structure in strong current, which caused loss of power **and** telemetry. In the repo report at `real-rov-research.md:112` — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

### Inferences
- [inference] A useful sim HUD set:
  - link indicator (bitrate or latency, with a "video stale N s" badge)
  - supply voltage/power for tether vehicles, or SOC for battery vehicles
  - internal temperature
  - leak alarm
  - a ground-fault trip alarm with a reset procedure

### Gaps
- No X1 app screenshots of power, overcurrent or link warnings (in the repo report `real-rov-research.md:151`, still open).
- No sources found on generator-related failures on small boats.

## Part B — Repository audit (read-only)

### Takeaway
The repo models link loss only as a 0.6 s server-side input watchdog that latches a lock. It models video latency as a constant, settable delay (150 ms default). It models "power" as a battery percentage drained by thrust, even though X1 is tether-powered. There is no model of link quality, bandwidth, jitter spikes, video freeze or artefacts, telemetry lag, power-budget thrust capping, voltage, thermal state or ground faults. The instructor "freeze" injection pauses the vehicle's physics, not the video feed.

### Cited Findings (file:line)
- **Battery**
  - `simulator/qysim/engine.py:94` sets `self.battery = 100.0`.
  - `engine.py:209-210` drains it: `load = mean(|thrust|)/thruster_max; battery -= dt*(0.004 + 0.05*load**1.5)`. Lights, camera and tools draw nothing. There is no thrust cap at low charge and no voltage.
  - `engine.py:292-295` and `:533-534`: SDK telemetry reports `"power": {"type": "battery", ...}` and `endurance = battery/100*5000`. This contradicts X1 being tether-powered (`real-rov-research.md:11`).
  - `engine.py:622-623`: VCCM precheck refuses below 10% ("Battery low").
  - `engine.py:471`: self-test battery status flips below 5%.
- **Thermal**
  - `engine.py:467` self-test returns constant `"temp": 31, "humi": 22, "mos_temp": 38`, and `network_plc: 1` etc. are always healthy. There is no thermal state, no out-of-water overheating and no derating.
  - `engine.py:530` water temperature is `26 - 0.15*depth` (environment only).
- **Input watchdog / failsafe**
  - `simulator/qysim/room.py:29` sets `input_timeout = 0.6`. `room.py:165-170`: `check_timeouts` locks any connected player whose last RC packet is older than 0.6 s. The USB Q-iRC vehicle is exempt.
  - `room.py:54-69` `lock()`: centres sticks, `rc_lock=1`, clears photo and record, `reset_assist()`, `assist=0`, drops SDK remote control, `nav.mode="IDLE"`, `nav.hold=None`, freezes the arm targets, and latches `input_latched`.
  - Net effect: the vehicle disarms and stops holding depth or heading, the same as ArduSub "disarm".
  - `simulator/qysim/server.py:215-219`: the physics loop runs the timeout check and the same 0.6 s check for the USB bridge.
  - `server.py:536-541`: latched failsafe; a delayed unlocked packet cannot undo it.
  - `server.py:529-531`: Q-iRC disconnect or generation change forces a lock.
  - `room.py:30` `reconnect_grace = 30.0` is a session-resume window, not a modelled reconnect delay.
  - `simulator/PROTOCOL.md:36-38` documents the latch and resync. `PROTOCOL.md:157`: send RC at about 30 Hz, and at least every 0.5 s.
- **RC cadence (client)**
  - `simulator/viewer/input/rc_scheduler.js:5-10`: `sampleMs 33`, `renewMs 100`, `heartbeatMs 150`, `holdMs 2000`, `workerTickMs 25`.
  - `input/rc_worker.js:1,21-23`: the worker re-sends held packets so heartbeats survive a stalled page.
  - `input/rc_link.js:129,142`: the pump sends with `holdMs`.
  - This is engineering for the real network. There is no simulated control latency, loss or jitter.
- **Reconnect (client)**
  - `simulator/viewer/app.js:505-509`: on socket close, the "offline" overlay shows and retries back off `min(5000, 800*2**retry)` ms.
  - This is a real-network reconnect, not a modelled ROV link with about 30 s recovery.
- **Video delay**
  - `simulator/viewer/state_buffer.js:172-179`: `videoDelayMs` comes from the URL or fidelity store, default 150 ms, clamped 0–1000 ms; 0 selects the assisted, predicted view.
  - `state_buffer.js:137-143`: a positive delay override samples the interpolation buffer at now − delay. Adaptive jitter delay (2·interval + 2·jitter, 40–250 ms) applies otherwise.
  - `state_buffer.js:188` comment: the delay applies to the vehicle view while switches, missions and room data stay current. Telemetry is therefore *not* delayed consistently with video, which is arguably correct (telemetry is often fresher) but untested against the real vehicle.
  - `simulator/viewer/fidelity.js:20-21,297-300`: the "影像延遲" (video delay) setting is provisional 150 ms, and real-mode values below it are flagged `exceedsReal`.
- **Instructor injections**
  - `simulator/qysim/instructor.py:59`: only `thruster`, `battery`, `current`, `visibility`, `freeze` are allowed.
  - `instructor.py:93-94`: battery is clamped to `original*(1-strength)`.
  - `instructor.py:103-104`: `freeze` sets `sim.paused=True`, which stops the vehicle's physics. It is not a video freeze or comms loss.
  - `simulator/viewer/instructor/instructor.js:5,76`: the UI labels match.
  - There is no injection for video delay, video outage, link degradation, telemetry loss, leak, overheating or power trip, although `PROTOCOL.md:326` lists the five kinds above.
- **HUD**
  - `simulator/viewer/hud/flight_hud.js:16-18,278,296,313-316` shows battery %, and "電量偏低" (battery low) below 20% (info level).
  - `app.js:891` gauge goes "low" below 20%.
  - The connection pill (`app.js:486-505`) reflects the browser↔server socket only.
  - There is no link-quality indicator, voltage, current, temperature, leak or ground-fault display, and no "video stale" indicator.

### Inferences
- [inference] The 0.6 s watchdog is a safety mechanism for the simulator's own network, and should stay. A *simulated* ROV comms-loss model has to be a separate layer on top, injected or stochastic, so that trainees experience frozen video, lagging telemetry, the vehicle's failsafe action and a reconnect delay without the server losing real control authority.
- [inference] Battery drain on a tether-powered X1 is a fidelity error in real mode. It should become a power budget (and supply health) for tether vehicles, keeping battery SOC only for battery vehicle models.

### Gaps
- I did not run the code. Line numbers come from the working tree on 2026-11-14.
- I did not audit `simulator/sdk_mock` for how power or link fields propagate to SDK clients.

## Part C — Ranked gaps, suggested models, validation targets

### Takeaway
The top priorities are:
1. A simulated comms-degradation layer (video freeze/lag/artefacts with control still working, and full loss with a vendor-like failsafe and reconnect).
2. Replacing battery-percentage power with a tether power budget for X1.
3. Instructor injections and HUD indicators for both.

All X1 numbers stay provisional pending checklist item 17.

### Cited Findings
1. **Video-link degradation (highest).**
   - Missing: bitrate, freeze, lag growth and artefacts.
   - Model: a link-quality state `q ∈ [0,1]` with capacity C(q) Mbps against a video bitrate B.
     - When C < B, video latency grows with the queue, (B−C)/C × elapsed, capped about 5 s; on recovery the buffer drops and the picture jumps.
     - Frames freeze for 1–5 s episodes.
     - Optionally, an artefact shader.
   - Control and telemetry stay live unless q < q_ctrl.
   - Validation targets:
     - Baseline delay 150–200 ms (FIFISH V6 vendor).
     - Fault-mode lag 4–5 s with controls responsive ([BR 3344](https://discuss.bluerobotics.com/t/fathom-x-video-freeze-five-second-lag/3344)).
     - Freeze of about 5 s every about 20 s ([snippet](https://discuss.bluerobotics.com/t/lost-connection-issues/1812)).
     - Latency spikes avg 0.7 s, max 3.5 s ([BR 23523](https://discuss.bluerobotics.com/t/300m-tether-link-associates-but-throughput-collapsed-from-30-mbps-to-0-3-mbps-overnight/23523)).
   - Frontend-only (presentation layer) plus an optional `state` field. It must stay toggleable per AGENTS.md.
2. **Simulated comms loss + vehicle failsafe + reconnect.**
   - Model: on injected loss, video goes black or frozen and the HUD shows "Disconnected". After T_fs the vehicle applies a configurable policy: `disarm` (default, matching ArduSub option 2 and the current lock semantics), `depth_hold`, or `surface`.
   - The link returns after T_reconnect. The vehicle stays latched until the pilot re-arms (ArduSub "remains in failsafe").
   - Validation:
     - ArduSub GCS timeout 5 s and pilot timeout ≤3 s ([ArduSub](https://ardupilot.org/sub/docs/gcs-failsafe.html)).
     - FIFISH reconnect about 30 s (vendor FAQ, `real-rov-research.md:33`).
     - X1 values are an assumption until measured.
3. **Tether power budget instead of battery for X1.**
   - Model: `P_avail` (provisional), with demand = Σ thruster power(thrust) + lights(brightness) + payload.
   - When demand exceeds P_avail, scale thruster commands uniformly and set `limited` (reusing the T01 `assist.limited` concept or adding a `power` object).
   - SDK `power.type` should become `"tether"` for X1 as an optional new field. Battery semantics stay for other models (AGENTS rule 1 compatibility).
   - Validation: Outland 400 VDC → 15 VDC, 1000 W, 92% ([BR](https://bluerobotics.com/learn/outland-technology-power-supply-bluerov2-integration/)). The X1 voltage and P_avail are unverified.
4. **Instructor injections.**
   - Add `video_delay`, `video_freeze`/`link_degrade` (strength = capacity loss), `comms_loss`, `power_trip` (GFI/LIM trip: all thrust, lights and video off until reset), `leak` and `overtemp`.
   - Currently only five kinds exist (`instructor.py:59`). `freeze` is a physics pause and should be renamed in the UI or complemented, to avoid confusion with a video freeze.
5. **HUD indicators.**
   - Link quality/latency badge, "video stale N s", supply voltage/power or SOC per vehicle type, internal temperature and leak.
   - Validation: Cockpit's red/green border on disconnect; V6 HUD signal strength; QYSEA blinking LEDs ([QYSEA](https://store.qysea.com/blogs/rov-knowledge/fifish-app-disconnected-troubleshooting-guide)).
6. **Thermal.**
   - Model: a first-order electronics/thruster temperature with heat ∝ power and cooling much stronger in water than in air.
   - Out of water: warning at 30 s of thruster run (vendor rule), then derate or cut.
   - In water: warn-only by default (ArduSub `FS_TEMP_ENABLE` is warn-only).
   - Replace the constant 31/38 °C self-test (`engine.py:467`).
7. **Battery vehicle realism (for non-X1 models).**
   - Hard cutoff of motors and lights at "empty" ([Deep Trekker](https://support.deeptrekker.com/power-systems)), with a warning tier, and current-dependent sag.
   - The current HUD threshold of 20% and the 10% VCCM refusal are not sourced.
8. **Tether-length-dependent link capacity (low priority).**
   - Only one data point exists (300 m giving 13–30 Mbps on 26 AWG). Treat as a scenario parameter, not a physics law. Add slow-onset water-ingress degradation as a "worn tether" scenario.

### Inferences
- [inference] Items 1, 2, 4 and 5 can be built without X1 numbers by using provisional defaults marked as assumptions. Items 3 and 6 need X1 measurements (checklist items 17 and new power/thermal items) before they become real-mode defaults.
- [inference] All new state fields must be optional, and the frontend must send nothing new unless the server advertises support, mirroring the `assist` contract in AGENTS.md.

### Gaps
- X1 numbers still missing: supply voltage and power, light wattage, thruster current, loss-of-comms action and timeout, reconnect time, video bitrate and codec, and the warning screens.
- I found no HomePlug-on-tether bandwidth-vs-length study, no VideoRay failsafe documentation, and no generator-failure sources.
