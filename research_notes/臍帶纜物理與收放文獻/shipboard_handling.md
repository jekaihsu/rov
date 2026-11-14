# Shipboard tether and umbilical handling: spools, reels, winches, LARS, TMS and tender practice (as of 2026-11)

Scope note: findings are split into **[SMALL]** (observation/inspection-class ROVs worked from small boats, hand spools or small powered reels) and **[WORK]** (work-class ROVs on vessels with LARS, umbilical winches and TMS). Tags: **(MFR)** = manufacturer claim; **(SNIPPET)** = the figure came only from a search-result summary and I could not read the primary page in full; **(VERIFIED)** = I read the primary document text myself.

---

## 1. Small-ROV topside equipment (manual spools, powered reels, slip rings) [SMALL]

### Takeaway
Small-ROV topside tether gear is mostly a **hand-cranked spool with an 8-circuit slip ring** that holds about 100–300 m (copper) of tether. Powered reels exist (VideoRay Expeditionary, QYSEA electric spool, Deep Trekker powered reel). Where speeds are published they are slow: about 25–40 m/min, from QYSEA's 300 m-in-8–12-min figure. Published sheets rarely give brake, tension-limit or line-pull figures. Pilots and tenders treat the tether as something to **pay out and haul in by hand**, not as a lifting line.

### Cited Findings
- **Blue Robotics Fathom Spool:** the standard spool holds ≤150 m of Fathom tether or ≤540 m of Slim tether. The Large spool holds ≤300 m Fathom or ≤1080 m Slim. It has a removable crank handle. (MFR, SNIPPET) — [RobotShop listing (150 m)](https://www.robotshop.com/products/bluerobotics-fathom-spool-150m); [RobotShop listing (300 m)](https://www.robotshop.com/products/bluerobotics-fathom-spool-large-300m)
- **Fathom Spool slip ring:** it carries 8 tether wires while the spool rotates. Electrical ratings conflict between sources:
  - A Blue Robotics staffer said 48 VDC across pairs and 2 A per pin.
  - An older forum post said the Binder 770 connectors are rated 175 V, the supplier rates the slip ring at 240 V but the assembly was not designed for it, and the supplier gives 1.5 A per circuit (not verified by Blue Robotics).
  - (SNIPPET) — [BR forum: slip ring specs](https://discuss.bluerobotics.com/t/what-are-the-slip-ring-specs/5317); [BR forum: slip ring question](https://discuss.bluerobotics.com/t/slip-ring-question/924?page=2)
- **Third-party 400 V drop-in slip ring for the Fathom Spool:** 2 HV passes and 6 data passes. This shows that slip-ring voltage and current limits the power a spooled tether can carry. (SNIPPET) — [BR forum: HV slip ring](https://discuss.bluerobotics.com/t/new-high-voltage-slip-ring-for-fathom-spool/9245)
- **Blue Robotics High Power Tether Reel for its OTPS (on-tether power) system:** priced US$3,475–3,575. I did not get its specs. (SNIPPET) — [Blue Robotics store](https://bluerobotics.com/store/the-reef/high-power-tether-reel-for-otps/)
- **VideoRay Pro 4 TDS (Tether Deployment System):**
  - It is a hand reel in a case with a slip ring at the end opposite the handle, and the handle is removable.
  - Standard capacity: one 76 m (250 ft) negative tether, one 76 m neutral tether and one 40 m PPT. Extended capacity: up to 300 m (1000 ft) of negative tether.
  - "Wind the tether neatly to store the maximum amount."
  - The TDS is not waterproof. Do not spray the slip ring.
  - Its slip-ring voltage rating is too low for the higher-voltage MSS vehicles.
  - (MFR, VERIFIED) — [VideoRay Pro 4 TDS doc](https://download.videoray.com/documentation/pro_4/html/equip_tether_tds.html)
- **VideoRay spec sheets via search:** the standard TDS (Pelican 1620 case with custom slip ring and reel) holds about 152 m (500 ft) and has a 4.5 m (15 ft) lead to the control panel. The extended case is rated ≤400 m PPT. (MFR, SNIPPET) — [2019 STANDARD TDS](https://videoray.com/images/specsheets/2020/2019_STANDARD_TDS.pdf); [2019 EXTENDED TDS](https://videoray.com/images/specsheets/2020/2019_EXTENDED_TDS.pdf)
- **VideoRay Expeditionary Reel, a powered and battery-backed reel (2025 rev 2.0.0 sheet):**
  - Holds 500 m of 4.4 mm copper or 4.5 mm fibre-optic tether.
  - Has a **level wind** and a **tether payout encoder**.
  - Removable handle, so manual operation is possible.
  - Power: 12 VDC in, 48 VDC out, dual NiMH or Li-ion batteries. IP65; the case is IP67.
  - Reel size 45.7 × 46.5 × 46.7 cm. Total weight 28.3 kg.
  - **No line speed, pull or brake figures are given.**
  - (MFR, VERIFIED from PDF text) — [VideoRay Exp Reel 2025 sheet](https://videoray.com/wp-content/uploads/2025_SpecSheet_72743_Exp-Reel_2.0.0.pdf)
  - A 2021 revision listed copper tether up to 550 m at 3.5 mm. (SNIPPET) — [2021 Exp Reels sheet](https://videoray.com/wp-content/uploads/2023/04/2021_SpecSheet_Exp_Reels.pdf)
- **VideoRay on capacity versus range:** reel capacity reduces maximum tether range. Copper is about 550 m on a reel versus 600 m loose. Fibre is about 1.5 km on a reel versus 2 km+ loose. (MFR, SNIPPET) — [VideoRay KB](https://kb.videoray.com/?p=920)
- **VideoRay Defender Base:** tether deployment and storage reel, tether breaking strength 680 kg (1,500 lb), 24 V / 300 W. (MFR, SNIPPET) — [Defender Base sheet](https://videoray.com/wp-content/uploads/2023_SpecSheet_71036_Defender-Base_1.0.1.pdf)
- **QYSEA electric powered spool (listed for FIFISH W6):** IP66, **two adjustable reel-in gears**, and takes up **300 m in 8 min (fast) or 12 min (slow)**. That works out to about **37.5 m/min (0.63 m/s) and 25 m/min (0.42 m/s)**; the m/min figures are my arithmetic. (MFR via reseller, SNIPPET) — [Scuba.com listing](https://www.scuba.com/p-qyelecspool/qysea-electric-powered-spool-for-fifish-w6-version-drone)
- **QYSEA manual 300 m spool:** "heavy-duty rectangular spool", 300 m Kevlar tether with 100 kgf breaking force, 50 × 26 × 26 cm, 7.7 kg, plus a 3 m surface tether to the controller. The page lists no motor, gears or slip-ring specs. (MFR, VERIFIED) — [QYSEA store](https://store.qysea.com/electric-powered-spool.html)
  - A reseller lists 80 kgf breaking force for a 3.5 mm tether, which conflicts with the 100 kgf above. (SNIPPET) — [QYSEA tether spool page](https://store.qysea.com/tether-spool.html)
- **Deep Trekker BRIDGE API `PoweredReel` type:**
  - `speed` runs −120…+120, units not stated. Negative retracts and positive pays out.
  - Boolean fields: `reelForward` ("reel is disengaged. The reel is not forcibly spooled out"), `reelReverse` (spooling in), `stalled`, `eStop` (physical e-stop), `encoderMiscalibrated` (length encoder), and a `spragBearing` state (a one-way clutch).
  - Two motors with diagnostics. AC or battery "hybrid power".
  - (MFR, VERIFIED) — [Deep Trekker BRIDGE API](https://docs.api.deeptrekker.com/types/PoweredReel.html)
- **Deep Trekker submersible tether reel (2018):** holds up to 100 m of tether and has a waterproof slip ring. (MFR, SNIPPET) — [Deep Trekker news](https://www.deeptrekker.com/news/submersible-tether-reel)
- **CHASING E-Reel (a different brand):** retrieval in about 3–9 min, up to 200 m. (SNIPPET) — [Core Electronics listing](https://core-electronics.com.au/chasing-m2-e-reel-no-cable.html.plain.md)
- **Autonomous tether management for inspection-class ROVs:** a vendor (Greensea IQ, per search snippet) released a portable autonomous system in Nov 2026. It claims to keep tether tensioned without slack and to let a single operator manage a tethered ROV locally or remotely. I could not read the article (HTTP 403). (MFR, SNIPPET) — [Unmanned Systems Technology, 2026-11](https://www.unmannedsystemstechnology.com/2026/11/autonomous-tether-management-system-released-for-inspection-class-rovs/)

### Inferences
- **Small-reel model for the simulator:**
  - Capacity: 100–300 m copper on manual spools, up to 500 m on powered reels.
  - Haul-in: about 0.4–0.6 m/s on a powered reel.
  - Payout on powered small reels is mostly passive: the reel is "disengaged" and the tether is pulled off by vehicle thrust and drag, plus a one-way/sprag bearing. Deep Trekker's `reelForward` description implies this.
  - Stall detection and an e-stop are standard features.
- **Manual-spool model for the simulator:**
  - Payout is the tender hand-feeding tether, or the vehicle pulling it off against spool friction.
  - Haul-in rate is limited by crank effort and neat winding.
  - Without a level wind, poorly laid layers reduce capacity, so "neat winding" is a real constraint.
- **Tether strength:** breaking strengths of 80–100 kgf (QYSEA) and 680 kgf (VideoRay Defender) suggest small-ROV tethers can lift the vehicle in an emergency. Manufacturers and SOPs still discourage lifting by the tether (see section 5).
- **Slip-ring limits** (48 V, 1.5–2 A per circuit on the Fathom spool) argue against running high power through hobby spools. This matters if the simulator models power-over-tether limits.

### Gaps
- I found no published brake torque, drag setting, line pull or max tension for any small-ROV reel.
- I found no QYSEA E-Reel official speed sheet. The 8/12 min figure is for the "electric powered spool" via a reseller.
- Deep Trekker reel speed units are unknown.
- I found no information on whether any small reel does tension-based auto-payout. The Greensea claim is the closest, and I could not read it.

---

## 2. Larger systems: LARS, A-frames, umbilical winches, TMS, cursors and heave compensation [WORK]

### Takeaway
Work-class systems separate the **armoured lift umbilical**, on a LARS winch through an A-frame or crane and usually with a cursor or snubber through the splash zone, from the **soft excursion tether**, on a TMS drum subsea. Typical figures are 30–60 m/min for main winches (90–144 m/min claimed with upgrades) and 30–60 m/min with about 150–450 kgf pull for TMS drums. Excursion tethers run about 250 m on small TMSs and up to 1500 m on large ones. Heave compensation is either passive or active (AHC). AHC needs line speeds of about 50–80 m/min to cancel 3–4 m of vessel heave.

### Cited Findings
- **TMS purpose and types:** a TMS is either a garage-like cage that holds the ROV during lowering, or a "top-hat" on top of the ROV. It decouples the ROV from surface vessel motion and extends working radius. (SNIPPET) — [FET TMS page](https://f-e-t.com/subsea/tether-management-systems/)
- **TMS drum figures (MFR, SNIPPET):**
  - Forum/FET Type 6a: holds 1500 m of 27 mm tether (1028 kg in air). Max line pull 300 kgf on the inner layer (adjustable). Haul-in 37 m/min average; payout 40 m/min. — [FET TMS Type 6](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-6.pdf)
  - FET Type 4: 450 kgf max; 30 m/min both directions. — [FET TMS Type 4](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-4.pdf)
  - Imenco TMS: regulated to 150 kg tether pull, with a **drum-releasing clutch to prevent over-pull**. — [Imenco](https://imenco.no/?p=9068)
  - Saab Seaeye TMS 8: up to 250 m of tether. — [Marine Vision TMS 8](https://marinevision.es/en/diving-pro/saab/tms_8.html)
  - SMD Quasar TMS: 0–60 m/min proportional at >300 kgf. — [JFS Quasar datasheet](https://www.jamesfishersubtech.com/media/mvwnetpi/jfs-me-_-ds-_-rov-_-quasar-_-r1.pdf)
- **Main umbilical winch and LARS figures (MFR, SNIPPET):**
  - SMD Quasar umbilical winch: hydraulic, line speed 50 m/min max. — [JFS Quasar datasheet](https://www.jamesfishersubtech.com/media/mvwnetpi/jfs-me-_-ds-_-rov-_-quasar-_-r1.pdf)
  - MacArtney MERMAC R15: 49.5 kN pull at 0–38 m/min on layer 1, 2 × 22 kW motors. Pull and speed are quoted per drum layer. — [MacArtney MERMAC R](https://www.macartney.com/media/5275/mermac-r.pdf)
  - Kongsberg ROV LARS (AHTS): 30 m/min on the outer layer as basic, with 60 or 90 m/min options depending on the HPU. A marketing claim says 144 m/min continuous. — [Kongsberg LARS for ROVs](https://www.kongsberg.com/maritime/products/deck-machinery-and-cranes/anchor-handling-vessels/launch-and-recovery-system-for-rovs-ahts)
- **Active heave compensation (Scantrol):**
  - Winch line speed of 50–80 m/min typically compensates 3–4 m of vessel motion, described as "sufficient for most ROV operations".
  - mTrack modes: AHC (keeps the TMS stable in launch and recovery), Auto Depth, **Anti-Snatch** (reduces umbilical peak loads), AHC without TMS, and **Umbilical Manager** (limits excessive umbilical strain).
  - No sea-state limit is given; the envelope "depends on winch capacity and vessel motion".
  - (MFR, VERIFIED) — [Scantrol AHC for ROV](https://www.scantrol.com/ahc-rov-operations)
- **Snatch damping:** MacGregor overside LARS use a hydraulic shock absorber to damp snatch loads. (MFR, SNIPPET) — [MacGregor deck-mounted overside LARS](https://www.macgregor.com/Products/products/offshore-cranes/deckskid-mounted-overside-lars/)
- **Cursor modes:** an IMCA flash (SF 11/25, BSEE) describes an umbilical parting "during a switch to low-tension mode near the cursor rail transition". This implies LARS winches run distinct tension modes around cursor engagement. (SNIPPET) — [IMCA SF 11/25](https://www.imca-int.com/resources/safety/safety-flashes/1125-bsee-umbilical-termination-failure-leads-to-dropped-rov/)
- **Passive heave compensation, ROPOS caged ROV (Driscoll, Lueck & Nahon 2000):**
  - Field measurements at cage depths 0–1765 m, with tension measured at the ship.
  - Large vertical A-frame excursions caused momentary slack near the cage. Re-tensioning produced snap loads with about 0.5 g vertical accelerations of the cage.
  - In simulation, both ship-mounted and cage-mounted passive compensators reduced rms cage motion and tension, by "a factor of 2" for reasonable parameters, and extended the operating sea state. The cage-mounted unit eliminated all snap loads in extreme seas.
  - (Peer-reviewed; SNIPPET of abstracts) — [Part 1 record](https://vufind-test.katalog.k.utb.cz/SummonRecord/FETCH-LOGICAL-e269t-c2be3d8e0ef75457cc0c5ec919dc440d3a59e2f23e239869386896a8549f9c1d3); [Comparison paper record](https://acnpsearch.tweb-dev.unibo.it/singlejournalindex/79905925); [UVic thesis](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- **Splash-zone mechanism:** wave-induced buoyancy changes temporarily slacken the lift cable, often followed by a snap load when it re-tightens. (Patent, SNIPPET) — [US 10287136](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10287136)

### Inferences
- **TMS model for the simulator:**
  - Drum speed about 0.5–0.67 m/s.
  - Line pull capped at about 150–450 kgf, with a clutch or slip above the cap. Imenco states this explicitly.
  - Payout and haul-in commanded proportionally by the pilot.
  - Excursion length capped at drum capacity (250 m small, up to 1500 m large).
- **Main winch model:** speed and pull depend on drum layer. The outer layer gives more speed and less pull, the inner layer more pull and less speed.
- **AHC:** the speed requirement roughly matches peak heave velocity. For sinusoidal heave of amplitude A and period T, v_peak = 2πA/T. For A = 1.5–2 m and T ≈ 8–10 s this is about 1–1.5 m/s (60–90 m/min), which is consistent with Scantrol's 50–80 m/min for 3–4 m of motion. The calculation is mine.

### Gaps
- I did not read IMCA R 004 Rev 6 (2024) in full, because it is paywalled or members-only. Its exact recommendations on TMS and LARS operation are not captured here.
- I found no quantitative passive-heave-compensator stroke or spring-rate data for a commercial ROV LARS.
- I found no specific Kystdesign, Dynacon, Hydramec or Ashtead figures.

---

## 3. Tension control and auto-payout logic

### Takeaway
On work-class systems, tension and speed control appears as **proportional speed control plus load sensing**:
- adjustable maximum line pull with slip or clutch (TMS),
- AHC with anti-snatch and "umbilical manager" strain limiting (LARS),
- distinct "low-tension" modes around the cursor.

Small-reel "auto payout" is mostly **passive**: a freewheeling, disengaged or one-way-bearing drum is pulled off by the vehicle. A 2026 product claims automated tension-keeping for inspection ROVs.

### Cited Findings
- FET lists "tether path geometry, tether load sensing and proportional speed controls" as TMS design focuses. Its max line pull is adjustable (300 kgf on the inner layer for Type 6a). (MFR, SNIPPET) — [FET TMS Type 6](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-6.pdf)
- Imenco TMS: tether pull is regulated to 150 kg, and a drum-releasing clutch prevents over-pull. (MFR, SNIPPET) — [Imenco](https://imenco.no/?p=9068)
- Scantrol: the mTrack "Umbilical Manager" limits excessive umbilical strain, and "Anti-Snatch" reduces peak loads. AHC adjusts "the speed and tension of a winch". (MFR, VERIFIED) — [Scantrol](https://www.scantrol.com/ahc-rov-operations)
- Deep Trekker powered reel: payout is a disengaged reel ("not forcibly spooled out"), with a sprag bearing, stall flag and encoder. (MFR, VERIFIED) — [Deep Trekker API](https://docs.api.deeptrekker.com/types/PoweredReel.html)
- IMCA SF 13/14: a main ROV lift umbilical parted during recovery while the termination socket was being latched. Contributing factors were an **unrestricted winch line pull**, a short, thin umbilical, and faulty latches. IMCA advises that winch line pull be limited below the umbilical breaking strain. (SNIPPET) — [IMCA SF 13/14](https://imca-int.com/resources/safety/safety-flashes/1314-main-rov-lift-umbilical-parted)
- Autonomous inspection-class TMS (2026): claims to keep tension without slack. (MFR, SNIPPET) — [UST 2026-11](https://www.unmannedsystemstechnology.com/2026/11/autonomous-tether-management-system-released-for-inspection-class-rovs/)

### Inferences
- A realistic simulator "auto payout" can be modelled as a constant-tension controller with these elements. This is my synthesis, not a vendor algorithm.
  - **Tension setpoint:** small, e.g. tens of N for small ROVs, and hundreds of kgf on a TMS.
  - **Deadband:** a band around the setpoint where the drum does nothing.
  - **Payout:** pay out at a rate proportional to (T − T_set) up to v_max when tension exceeds the setpoint.
  - **Haul-in:** haul in slowly when tension drops below T_set − deadband, to prevent slack.
  - **Hard line-pull cap:** slip or clutch at the cap.
  - **Stall detection.**
  - **Quantization:** a payout encoder quantizes the length readout.
- The commercial pattern (Imenco clutch, IMCA advice) is that the winch must not be able to exceed tether breaking strength. The simulator should cap reel pull below tether MBL.

### Gaps
- I found no published control-law parameters (gains, setpoints, deadbands) for any constant-tension ROV winch.
- I found no published tension time series from a small-ROV reel.

---

## 4. Splash zone and vessel motion coupling; limiting sea states

### Takeaway
Snap loads happen when wave or heave-induced slack is suddenly taken up. They are worst in **recovery** and when the winch **stops abruptly**. Measured and modelled peaks reach **about 2.4–3.1 × ROV weight**, against a wire MBL of 1.81 × ROV weight in one case. For a small OSV with a crane-launched work-class ROV, the operational limit is about **Hs 1.0 m**, extendable to **1.25 m** with a slower winch and a shorter crane outreach. Driscoll measured snap-induced cage accelerations of about 0.5 g. I found no robust published sea-state limits for hand-launched small ROVs from small boats.

### Cited Findings
**Deng et al. 2024, Ocean Engineering 309:118541** (work-class ROV with TMS from a 38.9 m, 393 t lightship OSV moored to a wind turbine; numerical model validated with a 1:10 flume test) (VERIFIED) — [Deng et al. 2024 (Strathprints PDF)](https://strathprints.strath.ac.uk/89731/1/Deng-etal-OE-2024-Launch-and-recovery-of-a-work-class-ROV-through-wave-zone.pdf)
- **Setup:**
  - ROV + TMS: 1809 kg in air, 996.2 kg in water. The ROV alone is 1400 kg.
  - Winch wire: 20.6 mm, 0.582 kg/m in air, max dynamic load 32.2 kN.
  - Crane outreach max 4.0 m.
  - Field limit per the vessel operator: **Hs 1.0 m**.
- **Results:**
  - The **peak tension occurs when the crane or winch halts during recovery**.
  - Recovery peak is about **2.4× the launch peak** at the same outreach.
  - Peak is about **2.4 × ROV weight** for stern deployment and about **3.1 × ROV weight** for side deployment, at Hs 0.6 m and 0.5 m/s winch speed.
  - Wire MBL is 1.813 × ROV weight, and traditional practice exceeded it at Hs 1.0 m.
- **Mitigation:**
  - Field practice: stern, 2.0 m outreach, 0.5 m/s. New procedure: stern, 1.0 m outreach, **0.3 m/s ascending**.
  - The new procedure halves recovery peak tension at Hs 1.0 m, keeps it below MBL, and extends the limit to **Hs 1.25 m**, adding about 6–6.5% annual operating time.
  - Winch speed is "typically less than 1.0 m/s". Full speed up to 1.0 m/s is safe only below Hs about 0.4 m. Hs 1.75 m is treated as the extreme for that vessel.
  - Higher speed is fine descending; a slower winch is beneficial ascending.

**Other sources**
- Driscoll et al. 2000 (ROPOS): A-frame heave causes slack near the cage, and re-tension produces snap loads with about 0.5 g vertical accelerations. (SNIPPET) — [Part 1 record](https://vufind-test.katalog.k.utb.cz/SummonRecord/FETCH-LOGICAL-e269t-c2be3d8e0ef75457cc0c5ec919dc440d3a59e2f23e239869386896a8549f9c1d3)
- NTNU SIMO study: large umbilical snap loads during launch are a critical factor. Sheave suspension stiffness reduced snap tension but not the duration of slack. (SNIPPET) — [NTNU Open](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2350695?show=full)
- Patent on AUV LARS: snatch loads arise from slack in the lift wire as the assembly transits the splash zone in high sea states. (SNIPPET) — [US 9387911](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9387911)
- VideoRay, small boats: avoid slack in rough seas, where it can tangle. A live-boated vessel moves unpredictably in rough water, so watch the tether closely. (MFR, VERIFIED) — [VideoRay 13 tips for strong currents](https://videoray.com/13-tips-for-operating-an-underwater-rov-in-strong-currents/)

### Inferences
- **Vessel-motion coupling for the simulator:**
  - Topside tether attachment point = vessel heave/pitch/roll applied at the reel or davit position. A stern-mounted point sees less roll coupling than a side-mounted one; Deng found side deployment worse.
  - Snap load = slack → taut transition with the tether's axial stiffness. Peaks of several times static weight are realistic.
  - Abrupt winch stop during recovery is a realistic trigger the simulator can reproduce.
- **Small-boat launch:** hand launch and recovery is the norm (see section 5), so the "LARS snap" mechanism mainly applies to work-class modes. For small boats, the coupling is the tether being jerked by boat heave and drift.

### Gaps
- I found no published sea-state limit for small-ROV hand launch from RIBs or workboats. Practitioners commonly cite about sea state 3, but I found no citable source, so this is not established.
- I did not extract Deng's measured field tension time series beyond the ratios above.

---

## 5. Tether management practice: slack, tender role, communications, drift/anchor/DP, propellers, recovery by tether [mostly SMALL]

### Takeaway
On small boats a dedicated **tether handler/tender** feeds and recovers tether by hand and keeps scope at the minimum the job needs. The tender calls out deployed length (VideoRay: **about every 5 m**), watches tether angle and tension, and keeps the tether away from propellers and rudders. A snagged tether should **not** simply be pulled. The vehicle is lifted aboard by its frame, not the tether. Work-class practice is governed by IMCA R 004, which I did not read in full.

### Cited Findings
- VideoRay on the tether handler:
  - Calls out to the pilot as tether goes in, "usually every 5 m", and must be ready for the pilot's instructions, since there is usually no time for delays.
  - Keep tether short: excess tether acts like a sail. Release it slowly.
  - Start upstream and work downstream "on a short leash". Drag increases when working perpendicular to the current.
  - In currents above **3 knots**, face the engine upstream and deploy from the bow downstream.
  - Live-boating: hold the tether and move the boat to place the system.
  - Keep the tether away from the ship's propellers and rudders.
  - Clump weight: lash a carabiner or small weight bag to the tether behind the ROV, spread over at least **6 in (15 cm)**, and add weight until the tether hangs straight.
  - Track the number of turns: tether has memory, and each turn adds torque that makes the ROV harder to fly.
  - (MFR, VERIFIED) — [VideoRay 13 tips for strong currents](https://videoray.com/13-tips-for-operating-an-underwater-rov-in-strong-currents/)
- VideoRay tether management:
  - "Only deploy what is needed – too little will affect piloting – too much may result in snags, tangles or propeller cuts."
  - Choose a site up-current with direct line of sight.
  - "Tether should be stored on a TDS or coiled using an over/under or figure eight technique. Coiling the tether in one direction will result in twists that are hard to remove."
  - (MFR, VERIFIED) — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html); [VideoRay MSS tether page](https://download.videoray.com/documentation/mss/html_pro_5/universal_tether.html)
- VideoRay snagged-tether procedure:
  - "Do NOT Panic! Do NOT Pull the Tether!" Assess first, then turn and tilt the camera to find the tether and follow it to the snag.
  - Pull from the surface only if you are sure there are no knots and it won't tighten the snag.
  - Possible aids: manipulator, skid, or a second ROV.
  - If the ROV can surface, power off, disconnect, and retrieve the loose tether.
  - (MFR, VERIFIED) — [VideoRay emergency: snagged tether](https://download.videoray.com/documentation/mss/html/emergency_snag.html)
- Vendor guide on the tether tender:
  - A dedicated crew member, not the pilot, who maintains minimum scope, observes tether angle and tension, and communicates tether condition continuously. The tender can call an abort on a sharp angle change.
  - Target zero free slack near structures, recovering slack to the surface drum, because slack enables additional wraps.
  - A 45° angle call threshold is vendor-specific.
  - (Cable vendor, SNIPPET) — [Rousheng: tether management tips](https://www.rstlkable.com/rov-cable-entanglement-prevention-tether-management-tips-for-structure-heavy-sites/)
- Too little working cable restricts the vehicle; uncontrolled slack creates fouling risk. (SNIPPET) — [Linden Photonics](https://www.lindenphotonics.com/challenges-in-rov-tether-management-and-how-to-overcome-them)
- University BlueROV2 SOP: retrieve tether while avoiding snags and thruster contact, disarm at the surface, and **lift the ROV by the frame, not the tether**. (Third-party SOP, SNIPPET) — [Evergreen State College instrumentation page](https://the-evergreen-state-college.github.io/Scientific-Instrumentation/.\Instrumentation/BlueRobotics-ROV-BlueROV2.html)
- **Work-class reference documents:**
  - IMCA R 004 Rev 6 (Feb 2024) is the guidance on the safe and efficient use of ROV systems. Its contents cover operations and environmental considerations; I could not read the text. (SNIPPET) — [IMCA R 004 page](https://legacy.imca-int.com/?p=28381)
  - IMCA D 054 covers entanglement and collision hazards when an ROV works near divers. (SNIPPET) — [IMCA D 054 PDF mirror](https://www.trauma-training.org/wp-content/uploads/2020/09/IMCA-D054-Publication-352-Remotely-operated-vehicle-intervention-during-diving-operations.pdf)
- Propeller and thruster fouling analogues (IMCA, non-ROV):
  - A pull-in rope went into a propeller due to current, thruster pull and wash from a nearby vessel. Contributing factors included an unfavourable heading relative to current and **insufficient monitoring of the rope catenary**. (SNIPPET) — [IMCA SF 33/21](https://imca-int.com/resources/safety/safety-flashes/3321-uhmpe-pull-in-rope-damaged-during-mooring-connection-to-buoy)
  - A shuttle tanker changed procedures to limit rope in the water after bow-thruster entanglement. (SNIPPET) — [IMCA DP incident](https://www.imca-int.com/resources/dp/dp-incidents/thruster-entanglement-during-shuttle-tanker-operations/)
- Single-point-moored small OSVs deploy work-class ROVs from the stern or side and inspect from about 30–45 m away from the turbine. (VERIFIED) — [Deng et al. 2024](https://strathprints.strath.ac.uk/89731/1/Deng-etal-OE-2024-Launch-and-recovery-of-a-work-class-ROV-through-wave-zone.pdf)

### Inferences
- **Simulator tender role (manual-spool mode):**
  - Length callouts every 5 m.
  - Pilot commands: "pay out", "hold", "take in", "slack".
  - Tender reports: angle/tension and "tether near prop".
  - Scope goal: the minimum needed.
- **Live-boating vs anchored:**
  - In a drifting or live-boated vessel, the tether is pulled by boat motion and the tender must pay out or haul to compensate.
  - Anchored or moored operation is steadier, but current sets the tether downstream.
  - DP vessels add thruster wash and entanglement risk. I found no DP-specific small-ROV guidance.
- **Recovering a dead vehicle by tether:** practitioners do it when there are no snags (VideoRay's conditions). Lifting the vehicle out of the water should be by the frame or a lift line, not the tether.

### Gaps
- I found no formal pilot–tender phraseology standard; the VideoRay 5 m callout is a manufacturer tip.
- I found no published guidance on how much slack to keep in metres or percent, beyond "minimum required" and "short leash".
- I found no DP-specific tether-management guidance for small ROVs.

---

## 6. Twist management: reels, slip rings, figure-eighting, coiling [SMALL]

### Takeaway
Twist comes from vehicle yaw turns and from coiling in one direction. Slip rings let the drum rotate without twisting the topside lead, but they do **not** remove twist from vehicle rotation. Pilots track and unwind turns. Loose tether is coiled over/under or in figure-eights.

### Cited Findings
- Coil over/under or in a figure eight. One-direction coiling creates twists that are hard to remove. — [VideoRay tether mgmt](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- Track the number of turns: each turn adds torque that makes the ROV harder to fly. — [VideoRay 13 tips](https://videoray.com/13-tips-for-operating-an-underwater-rov-in-strong-currents/)
- The slip ring keeps the 8 circuits connected while the spool rotates (Fathom Spool). The VideoRay TDS slip ring sits at the drum end opposite the crank and must be kept dry. — [BR forum](https://discuss.bluerobotics.com/t/what-are-the-slip-ring-specs/5317); [VideoRay TDS](https://download.videoray.com/documentation/pro_4/html/equip_tether_tds.html)
- A level wind is a listed feature on the VideoRay Expeditionary powered reel. — [VideoRay Exp Reel sheet](https://videoray.com/wp-content/uploads/2025_SpecSheet_72743_Exp-Reel_2.0.0.pdf)

### Inferences
- **Simulator twist counter:** accumulate vehicle net yaw turns. A HUD "turns" indicator and pilot unwinding are realistic. The reel slip ring does not reset the count.

### Gaps
- I found no quantitative torque-per-turn data for small-ROV tethers.

---

## 7. Incident and measured data (winches, reels, umbilicals) [WORK]

### Takeaway
IMCA flashes show the recurring failure modes:
- termination, bullet or socket failure during latching,
- unrestricted line pull,
- brake failure causing free-run (800 m in under 90 s),
- latch mis-engagement,
- uncontrolled spool-in after power loss.

### Cited Findings (all SNIPPET via search summaries of IMCA pages)
- **SF 13/14:** the main lift umbilical parted at the termination socket during latching on recovery. Causes: unrestricted winch line pull, a short and thin umbilical, faulty latches. — [IMCA SF 13/14](https://imca-int.com/resources/safety/safety-flashes/1314-main-rov-lift-umbilical-parted)
- **SF 27/19:** the lift wire parted at the potted bullet, and the ROV and TMS were lost to the seabed. — [IMCA SF 27/19](https://imca-int.com/resources/safety/safety-flashes/2719-main-rov-lift-wire-umbilical-and-bullet-parted)
- **SF 13/24:** the TMS failed to latch to the LARS. The umbilical was damaged above the docking bullet, sheared by the docking-head latch, and the ROV was dropped. — [IMCA SF 13/24](https://imca-int.com/resources/safety/safety-flashes/1324-rov-dropped-to-seabed)
- **SF 11/25 (BSEE):** the umbilical parted during a switch to low-tension mode near the cursor rail transition. The root cause was an original attachment flaw. — [IMCA SF 11/25](https://www.imca-int.com/resources/safety/safety-flashes/1125-bsee-umbilical-termination-failure-leads-to-dropped-rov/)
- **Legacy flash:** a winch brake failure let about **800 m of umbilical run off the drum in under 90 s**, at least about 9 m/s average. The root cause was unconfirmed. — [IMCA legacy flash](https://legacy.imca-int.com/?p=964)
- **SF 07/08 (fatal):** during umbilical re-termination, a blackout caused uncontrolled winch spool-in, lifting the TMS into the docking head and killing a person. — [IMCA SF 07/08](https://www.imca-int.com/resources/safety/safety-flashes/0708-fatal-accident-in-connection-with-the-operation-of-an-a-frame-based-launch-and-recovery-system-lars-used-for-rov-operations/)
- **Related flashes:** ROV winch failure — [IMCA SF 09/01](https://imca-int.com/resources/safety/safety-flashes/0901-rov-winch-failure); dropped ROV/TMS — [IMCA SF 11/11](https://imca-int.com/resources/safety/safety-flashes/1111-equipment-damage-dropped-rovtether-management-system-tms) (titles only; content not read)

### Inferences
- **Training scenarios worth simulating:** brake failure (free-run), over-pull beyond tether MBL, slack-then-snap at the splash zone, and loss of power to a powered reel.

### Gaps
- I found no published small-ROV reel incident data and no MAIB/NTSB reports specific to small ROV reels.
- I found no publicly available payout statistics (length versus time over real dives).
