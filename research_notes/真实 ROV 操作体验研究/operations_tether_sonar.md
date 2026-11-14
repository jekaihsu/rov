# Real-world ROV field operations: tether, launch and recovery, sonar, navigation, tasks, failures (observation-class and light work-class, as of 2026)

Reading notes for the report writer:

- Scope is vehicles of roughly 5-150 kg in air. Work-class differences are called out where a source gave them.
- Provenance tags: **[fetched]** means the page itself was opened and read; **[snippet]** means the claim comes only from a search-result summary and the page was not opened. Treat [snippet] items as lower confidence.
- Most procedural material comes from vendor documentation (VideoRay, Blue Robotics, Blueye, Deep Trekker). It is practical but vendor-stated, not independently tested.
- Three requested sources could not be read: The ROV Manual (Christ & Wernli), the full text of IMCA R 004 (members-only), and NORSOK U-102 (only a table of contents surfaced). Nothing below is taken from them.
- Items marked "uncited" in the Gaps and Inferences sections are my own background knowledge with no source checked in this session. They must not be reported as sourced facts.

## 1. Tether: dimensions, strength, buoyancy, drag, pay-out, tender role, twists, clump weights, snags

### Takeaway
Tether is the dominant constraint on a small ROV: operators deploy the minimum length, launch up-current with line of sight, and manage it with a dedicated handler who calls out pay-out to the pilot. The universal snag rule is "do not pull"; the pilot turns round and follows the tether back to the snag point.

### Cited Findings

**Dimensions and strength**
- Blue Robotics standard Fathom tether: 7.6 mm diameter, breaking strength 155 kgf (about 350 lb), working strength 35 kgf (about 80 lb), minimum working bend diameter 75 mm; neutral in fresh water and slightly positive in salt water; polyurethane jacket with water-blocking fibres [snippet] — [RobotShop Fathom 200 m listing](https://robotshop.com/products/bluerobotics-fathom-rov-tether-200m), [RobotShop Fathom 300 m listing](https://www.robotshop.com/products/bluerobotics-fathom-rov-tether-4-twisted-pairs-300m)
- Conflict: other retailer pages give the Fathom breaking strength as "35 lb" or "3-35 lb". This looks like a unit mix-up; 155 kgf / 350 lb is the figure that repeats on the more detailed listings. Not confirmed against the Blue Robotics page itself [snippet] — [RobotShop Fathom listing](https://robotshop.com/products/fathom-rov-tether-rov-ready-twisted-pairs-1-200-m-656-ft)
- Maximum communication length: 300 m for standard Fathom, 200 m for Fathom Slim [snippet] — [Blue Robotics Fathom tether](https://bluerobotics.com/?p=151902). A Blue Robotics staff member said 200 m is the longest communication distance they had seen on the Slim tether with their interface boards, and that they had never deployed a full 300 m of standard tether [fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)
- A forum user's diameter comparison across brands: about 12 mm for a VideoRay neutral tether ("bulky"), about 4 mm for a Deep Trekker tether, 7.5 mm for Fathom; fibre-optic tether about 3-4 mm. 920 ft (280 m) of Fathom weighs about 26 lb (11.8 kg) in air. These are a poster's figures, not manufacturer specs [fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)
- Deep Trekker Revolution: tether rated to pull up to 136 kg to the surface [snippet] — [Janes](https://www.janes.com/defence-news/news-detail/xponential-2019-deep-trekker-unveils-revolution-rov)

**Tether types (VideoRay system)**
- Negative tether sinks and has larger conductors, so longer lengths can be used without losing power at the vehicle. Neutral tether is neutral in fresh water and slightly buoyant in salt water, with thinner conductors. Performance (PPT) tether is the thinnest neutral option: least drag, least power capacity [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- Recommended combination when more length is needed: performance or neutral tether at the vehicle end, negative tether at the control-panel end [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- For long runs use negative tether, but keep a short section of neutral/performance tether at the ROV unless the tether can always be held above the vehicle [fetched] — [VideoRay piloting in deep water](https://download.videoray.com/documentation/v1_7_0/html/pro4/pilot_deep.html)

**How much to pay out, and drag**
- "Use the shortest amount of tether required to operate in the target area." "Only deploy what is needed - too little will affect piloting - too much may result in snags, tangles or propeller cuts." [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- Excess tether in the water "acts like a sail" and pulls on the vehicle; drag rises when working across the current, so pay out when moving up- or downstream. "Treat the tether like a fishing line." Keep a short leash for the required excursion [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- Do not deploy excess tether (drag and snag risk), do not run it over sharp edges or rough ground, do not step on it [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Field anecdote for a BlueROV2: navigational authority can be kept in up to about 1 m/s (about 2 kn) of current, with tether drag manageable to about 50 m depth; in 1 kn of current about 2 kn of reserve speed remains at full power. Anecdotal, not a test standard [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/the-maximum-sea-speed-current/3529)
- Blue Robotics' own current testing was only about 0.5 kn; on 280 m of tether in 1.5 kn their comment was "It is going to be a lot of drag, but it might be doable." Estimated BlueROV2 bollard pull with 30-degree thruster mounts: about 24 lb (11 kgf), a poster's estimate [fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)
- A BlueROV2 can handle over 500 m of 3-4 mm fibre-optic tether in open water because it has very little mass (forum opinion) [fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)

**Handler (tender) role and communication**
- The tether handler deploys the right amount, keeps tether away from surface hazards such as a propeller, keeps loose tether neat, and communicates with the pilot; wears gloves. VideoRay's own nickname for the role is "tether monkey" [fetched] — [VideoRay on-site operations](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)
- Handlers call out each deployment increment, typically about every 5 m, so the pilot knows how much tether is in the water [snippet] — [VideoRay managing-tether training narration](https://download.videoray.com/training/vtl_pro_5_exercises_manual_control/html/_managing_tether_narration.html)
- Watch for tether pinch points around docks and chafing hazards around rocks or coral; tether and power cord are trip hazards on deck [fetched] — [VideoRay on-site operations](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)
- Launch site should be up-current of the work area with direct line of sight to the vehicle, to avoid snags [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- When working from shore, move the control box several times rather than paying out more tether [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)

**Twists and storage**
- Each turn put into the tether tries to unwind and puts torque on the vehicle, making it hard to fly; the pilot watches a turns counter [snippet] — [VideoRay tether-mismanagement training narration](https://download.videoray.com/training/vtl_defender_exercises_manual_control/html/_tether_mismanagement_narration.html)
- Store tether on a deployment reel or coil it over/under or in a figure-eight. "Coiling the tether in one direction will result in twists that are hard to remove." [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- A loosely filled tether bag deploys without tangles or kinks; a reel is required for long lengths [snippet] — [VideoRay ROV tips](https://kb.videoray.com/?p=328)

**Clump weights and TMS**
- Attach a weight to the tether several metres behind the ROV; spread the attachment load along a section of tether rather than one point; plan for retrieval, which is hard on a long tether [fetched] — [VideoRay piloting in deep water](https://download.videoray.com/documentation/v1_7_0/html/pro4/pilot_deep.html)
- In strong current, clip a carabiner or weight bag behind the ROV and add weight until the tether hangs straight (most useful against surface and mid-water current); keep at least 6 in (15 cm) of tether between the clump weight and the ROV [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- To descend faster, carry a weight in the manipulator and release it at working depth [fetched] — [VideoRay piloting in deep water](https://download.videoray.com/documentation/v1_7_0/html/pro4/pilot_deep.html)
- A tether management system is described in the general ROV literature as a way to minimise cable drag in current [snippet] — [Wikipedia mirror: Remotely operated underwater vehicle](https://www.doc.surf/wiki/remotely-operated-underwater-vehicle)

**Snag and entanglement response**
- VideoRay emergency procedure: (1) do not panic, do not pull the tether; (2) assess before manoeuvring; (3) if the ROV can move, turn round and follow the tether back to the snag, yawing left/right and tilting the camera to find it; (4) pull from the surface, or use the ROV to pull the tether clear, only if confident there are no knots and it will not snag tighter [fetched] — [VideoRay emergency snag response](https://download.videoray.com/documentation/mss/html/emergency_snag.html)
- Further options: use a manipulator, or a part of the vehicle such as the skid, to work the tether; use a second ROV to assess or assist; if the ROV can reach the surface, power off, disconnect it and retrieve the loose tether from the other end [fetched] — [VideoRay emergency snag response](https://download.videoray.com/documentation/mss/html/emergency_snag.html)
- Recommended preparation: pool practice of wrapping and unwrapping the tether round a spar; decide in advance whether a lost vehicle will be recovered or the tether cut [snippet] — [VideoRay ROV tips](https://kb.videoray.com/?p=328)
- Tether entanglement or separation is named as a leading cause of ROV loss or damage [snippet] — [VideoRay ROV tips](https://kb.videoray.com/?p=328)

### Inferences
- The gap between breaking strength (155 kgf) and working strength (35 kgf) on a typical small-ROV tether is about 4.4:1. A simulator can use working load as the "tender may pull this hard" limit and treat anything approaching break strength as a loss-of-vehicle event.
- For a simulator, tether drag should scale with wetted length and with the component of current perpendicular to the tether; the sources agree qualitatively on this (sail effect, worse across current) but none gives a formula.
- A tender mechanic with 5 m pay-out call-outs, a turns counter that adds yaw torque, and a "pulling tightens the snag" rule would reproduce the three behaviours every source stresses.
- A snag scenario that rewards "turn round, follow the tether, back out the way you came" and penalises surface pulling matches both the vendor procedure and the Lake Michigan incident in section 7.

### Gaps
- No drag formula or quantified drag-versus-length rule was found. The standard cylinder-drag relation F = 0.5 x rho x Cd x d x L x v^2 (Cd about 1.2 for a cable normal to flow) is uncited background, not from a source read here.
- No sourced ratio of tether paid out to depth. A commonly quoted allowance of extra scope over depth is uncited.
- No documented hand signals or standard radio phraseology between pilot and tender; only the 5 m call-out practice.
- No numeric clump-weight masses, and no TMS specifications (excursion length, garage versus top-hat) for light work-class vehicles.
- VideoRay, Deep Trekker, Saab Seaeye and QYSEA tether break strengths and diameters were not obtained from manufacturer data sheets.
- The ROV Manual's tether chapter was not accessible.

## 2. Launch and recovery: checklists, crew, limits, logs

### Takeaway
Small-ROV launch is a hand deployment preceded by a physical "pull and twist everything" check and a short thruster function test in air; the vehicle is armed only once in the water. Crew is one to three people for observation class, and an IMCA safety flash attributes a vehicle loss partly to running two operators where three were needed.

### Cited Findings

**Pre-dive checklist (BlueROV2, 22 steps)**
- Confirm topside connection; try to twist ballast weights; pull side panels and twist frame; pull cable bundles at the end cap; pull and twist the tether thimble; try to loosen every penetrator by hand; confirm vent plugs fitted; push and twist battery enclosure; check end-cap screws; pull on all thrusters; shake fairings; pull on lights; check dome screws; check radial seals are greased and not cracked [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Function test: set vehicle on the ground with people clear of thrusters; check camera tilt and lights; select Manual mode; arm; push forward stick to confirm horizontal thrusters spin, then vertical stick for vertical thrusters; do not run thrusters more than 30 seconds in air; disarm [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- A more thorough "comprehensive" checklist (re-torque frame and end-cap screws) applies after air travel, after more than 1 hour of car or boat travel, after removing the electronics enclosure, or after replacing a penetrator or sealing O-ring [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)

**Vacuum (seal) test**
- Required before first water entry and after assembling a new vehicle, replacing O-rings, fitting a penetrator or replacing enclosure parts; not required for routine battery swaps [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Pass criterion: pump to 10 inHg (34 kPa) vacuum, wait 15 minutes, acceptable if still above 9 inHg (31 kPa). This comes from a third-party copy of a BlueROV2-derived manual, not the Blue Robotics page [snippet] — [BlueLink BlueROV2 manual](https://manuals.online/bluelink/diving-vehicle/bluerov2/user-manual/1uq8h)
- If it fails: check end-cap screws, penetrator tightness and that all penetrator O-rings are present [snippet] — [BlueLink BlueROV2 manual](https://manuals.online/bluelink/diving-vehicle/bluerov2/user-manual/1uq8h)

**Ballast and trim**
- Vehicle should float level with no pitch or roll; pushed half an arm's length under and released, it should hold depth. Slightly positive is preferred over negative. Re-ballast whenever accessories are added or removed [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)

**Launch**
- Do not arm until the vehicle is in the water and the launcher is clear. Do not release it before it touches the water; lower it on the tether if needed, keeping the dome off hard objects [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- From a boat: keep vehicle and tether clear of propellers or jets and make sure the captain knows a launch is coming. From shore: do not launch in heavy surf; the vehicle may need to be walked out to deeper water. Do not launch near swimmers or divers, or in water too shallow to drive freely [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- When descending, follow a chain or line as a visual reference [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Site set-up: level site; orient the control panel so screen directions match real-world directions; secure the system on a vessel against rough seas [fetched] — [VideoRay on-site operations](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)

**Recovery and post-dive**
- Pull in slack while driving back; clean debris off the tether and inspect it for cuts or nicks; disarm before recovery; allow room for the vehicle to swing when lifting by the tether [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Post-mission: rinse with fresh water, thrusters especially; clear sand and weed from thrusters. If out of the water more than 15 minutes, keep the vehicle shaded [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Maintenance intervals: check radial seals every 24 operating hours or 2 months; replace battery-cap and vent-plug O-rings every 100 hours or 6 months [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)

**Crew and roles**
- One person can operate a VideoRay, but several may be valuable or required. Roles: pilot (wears a dark shirt to cut monitor glare), tether handler, accessory operator (sonar/manipulator, to unload the pilot), supervisor (manages the team, usually keeps the log, rotates roles on long missions), technician (maintenance and repair logs) [fetched] — [VideoRay on-site operations](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)
- In the IMCA lost-ROV case the crew had two operators where the complexity of the operation called for three [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)
- IMCA R 004 vehicle classes: Class I pure observation; Class IIA observation with payload option; Class IIB observation with light intervention, survey or construction capability; later classes cover work-class, towed/crawling, prototype and AUV. Latest revision found is Rev. 6, February 2024 [snippet] — [IMCA R 004 page](https://legacy.imca-int.com/?p=28381)

**Logs**
- Operations logs are "highly recommended to track operations and develop historical profiles of the equipment, operators and missions" [fetched] — [VideoRay on-site operations](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)
- Blueye dive logs export as KML/KMZ, and position is embedded in photo metadata [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)

### Inferences
- A simulator pre-dive phase can be built directly from the 22-step list: a physical-integrity group, a seal group, and an in-air function test with a 30-second thruster limit.
- "Arm only in the water" plus "disarm before recovery" gives two checkable procedural gates at each end of a dive.
- The supervisor-keeps-the-log convention suggests an auto-generated dive log (times, depth, tether out, events) is a realistic debrief artefact.

### Gaps
- No sourced sea-state or wind limits for hand launch from small boats, and no A-frame/LARS procedure for light work-class vehicles.
- IMCA R 004 crew-size tables and environmental limits could not be read (members-only).
- Saab Seaeye Falcon, Deep Trekker and QYSEA pre-dive checklists were not obtained.
- No example of a real dive-log template with field names.

## 3. Imaging sonar on small ROVs

### Takeaway
Two families are in use: multibeam imaging sonars (Oculus, Gemini) that refresh a 120-130 degree fan many times a second, and mechanically scanned sonars (Ping360 type) that sweep slowly and smear if the vehicle moves. Pilots use them by sitting still, scanning, turning to put the target dead ahead, narrowing the sector and driving in.

### Cited Findings

**Specifications**
- Blueprint Oculus M750d: dual frequency 750 kHz / 1.2 MHz; maximum range 120 m / 40 m; minimum range 0.1 m; horizontal aperture 130 degrees at 750 kHz; vertical aperture 20 / 12 degrees; up to 512 beams; angular resolution 1 / 0.6 degrees; update rate up to 40 Hz [snippet] — [Oculus M-Series datasheet](https://download.videoray.com/documentation/mss/pdf/blueprint_subsea/oculus/Oculus_M-Series_Datasheet_EN.pdf)
- Conflict: the 1.2 MHz horizontal aperture is given as 70 degrees on one datasheet and 130 degrees on the Blueye spec sheet; depth rating is given as 300 m on one and 500 m on the other [snippet] — [Oculus M-Series datasheet](https://download.videoray.com/documentation/mss/pdf/blueprint_subsea/oculus/Oculus_M-Series_Datasheet_EN.pdf); contradicted by [Blueye M750d spec sheet](https://www.blueyerobotics.com/specsheet/BPS-OCU-M750D/pdf)
- Other Oculus M-series variants: 375 kHz with 200 m range, and 1.2 / 2.1 MHz with 30 m / 10 m range and 130 / 60 degree aperture [snippet] — [Oculus M-Series datasheet](https://download.videoray.com/documentation/mss/pdf/blueprint_subsea/oculus/Oculus_M-Series_Datasheet_EN.pdf)
- Tritech Gemini 720ik: 720 kHz; range 0.2-120 m; 512 beams; 120 degree horizontal and 20 degree vertical beamwidth; angular resolution 1.0 degree acoustic, 0.25 degree effective [snippet] — [Gemini 720ik datasheet](https://videoray.com/images/specsheets/2017_GEMINI_720ik.pdf)
- Tritech Gemini 720im (the smaller unit): 128 beams, 50 m range [snippet] — [Adorama Gemini 720im listing](https://www.adorama.com/chstg720.html)

**How a scanning sonar works and what the display shows**
- A scanning sonar has a fan beam, wide vertically and narrow horizontally; a stepper motor rotates the transducer and the slices build one image. Range = speed of sound x (echo time / 2); sea-water sound speed is about 1500 m/s and must be set by the operator [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- The image is effectively a top-down view. Brighter means stronger echo. Bearings are relative, clockwise from dead ahead (000 R). A polar scan covers 360 degrees; a sector scan covers less (60 degree example) and refreshes faster [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Strong reflectors: gas, rock, concrete, metal. Weak: mud, silt, sand, plants. Only faces turned toward the sonar return strongly, perpendicular faces strongest. A vertical rope shows brighter than surrounding water [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)

**Shadows and artefacts**
- Targets cast acoustic shadows like a torch beam. High altitude and steep down-angle give short, hard-to-read shadows; low altitude and shallow angle give long ones. Shadows widen as the target gets closer and can hide other targets [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Targets at the same slant range cannot be separated and appear as one return [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Forward-looking sonar has elevation ambiguity because of its wide vertical aperture [snippet] — [Phung et al., OCEANS 2024](https://amyphung.github.io/files/publications/Sonar_Manip__2024_OCEANS.pdf)
- Image smear: on a mechanically scanned unit, moving before the sweep completes distorts the image [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Acoustic shadows show as large drops in return intensity, even over low-reflectance mud, and are stable enough to be used for map matching [snippet] — [Padial et al., OCEANS 2014](https://web.stanford.edu/group/arl/sites/default/files/public/publications/PadialDR_OCEANS_STJOHNS_2014.pdf)
- Echoes off harbour walls and the seabed, and noise from other vessels, produce false acoustic readings (stated for acoustic positioning, same physics) [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)

**How pilots use it**
- In low visibility camera range may be under 1 m; sonar extends the search area [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Six-step target approach: (1) settle the ROV on or near the bottom; (2) run a 360 degree scan; (3) read the target's relative bearing; (4) turn until the target is at 0 degrees; (5) narrow the sector to about 60-90 degrees for faster refresh; (6) keep the target on screen while driving forward [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- "10% rule" (rule of thumb): with a 10-15 degree down-angle and altitude equal to 10% of the range setting, about 70% seabed coverage is achieved; for example 1 m altitude for 10 m range, 2 m for 20 m [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- Before an inspection in current, run a long-range sonar scan to find hazards such as branches and debris [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- In a 2021 recovery attempt on Lake Michigan, a second ROV's sonar located a lost ROV at a wreck's bow within 10 minutes [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)

### Inferences
- The two sonar families need different simulator behaviour: a multibeam fan at tens of hertz that stays usable while flying, versus a sweeping line that takes seconds per revolution and smears with vehicle motion.
- A convincing sonar display needs at least: relative-bearing fan with range rings, intensity by material, face-on brightening, shadows whose length depends on altitude and down-angle, and same-range targets merging.
- Shadow-length dependence on altitude gives a trainable skill: fly low and shallow to read a target, not high and steep.

### Gaps
- Blue Robotics Ping360 numeric specs (frequency, range, beamwidth, scan time) were not confirmed; two searches returned nothing. Figures of about 750 kHz and 50 m range are uncited.
- No specs found for Sonoptix Echo, Tritech Micron or Teledyne BlueView.
- Multipath, gain/time-varied-gain settings, surface reflection and thruster noise artefacts are not described in the sources read; the scanning-sonar guide explicitly omits them.
- The ">10 Hz at short range" behaviour of multibeam update rate versus range setting was not quantified.

## 4. Navigation and sensors: depth, compass, altimeter, DVL, USBL, drift

### Takeaway
Small ROVs navigate on depth plus magnetic heading, which fails near steel; DVL adds precise but drifting dead reckoning, and acoustic positioning adds an absolute but noisy, slower fix. Fused systems use the DVL to smooth acoustic jumps and the acoustic fix to cancel DVL drift.

### Cited Findings

**Compass and magnetic interference**
- Near steel structures underwater compasses become badly inaccurate, and the error changes as the distance to the hull changes [snippet] — [US patent 7400142](https://patents.google.com/patent/US7400142)
- Powering on aboard a large steel ship typically gives a very poor initial magnetic heading alignment [snippet] — [US patent 11193772](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11193772)
- Field report: a BlueROV2 spun on a steel wreck with a yaw re-alignment warning; advice was to back away and not use auto-heading nearby [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/rov-problem-spinning-around/10680)
- Heading drift of roughly 5-10 degrees from ferrous objects in a port, per a vendor case study [snippet] — [Sonardyne case study](https://www.sonardyne.com/case-study/revolutionising-small-rov-navigation/)
- Thruster fields can disturb the compass enough to make heading hold unusable; moving the sensor about 5 in (13 cm) from the thrusters cured it in one case [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/frustrated-any-suggestions/305)
- Fibre-optic-gyro heading does not depend on magnetic north and is unaffected by ferrous structures [snippet] — [Sonardyne SPRINT-Nav](https://www.sonardyne.com/product/sprint-nav/)

**DVL**
- A DVL sends (typically four) acoustic beams at the seabed and measures Doppler shift to get velocity; a Kalman filter dead-reckons position from a known start such as the operator's GPS position. It enables station keeping and auto-altitude [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- Water Linked DVL A50: minimum altitude 5 cm; maximum altitude 50 m, with performance above 35 m dependent on seabed and salinity [snippet] — [Blueye DVL A50 spec sheet](https://www.blueyerobotics.com/specsheet/WL-DVL-A50/pdf), [Deep Trekker DVL page](https://deeptrekker.com/shop/products/dvl-waterlinked)
- Conflict: A50 ping rate is 4-15 Hz per Blueye and 4-26 Hz per Deep Trekker, both adaptive to altitude [snippet] — [Blueye DVL A50 spec sheet](https://www.blueyerobotics.com/specsheet/WL-DVL-A50/pdf); contradicted by [Deep Trekker DVL page](https://deeptrekker.com/shop/products/dvl-waterlinked)
- DVL position is high precision but can have low accuracy depending on the initial heading; it drifts with time. Blueye recommends resurfacing every 15-20 minutes to reset the start point from GPS [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- Navigation accuracy is usually expressed as a percentage of distance travelled [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/dvl-a50-accuracy/14873)
- High-end reference point: Sonardyne SPRINT-Nav station keeping better than 2 m over 24 hours (a much more expensive INS/DVL, not a small-ROV norm) [snippet] — [Sonardyne SPRINT-Nav](https://www.sonardyne.com/product/sprint-nav/)

**Acoustic positioning (USBL / SBL)**
- GPS does not work underwater because radio is damped within a few metres. A transponder on the ROV pings; a topside unit measures direction and range. SBL uses transducers 50 cm to several metres apart and time of flight; USBL packs elements 1-10 cm apart in one head and uses phase for direction. Depth comes from the pressure sensor [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- Water Linked Underwater GPS G2 (an SBL system): ping rate 2-4 Hz; horizontal accuracy better than 0.2% of range; 100 m or 300 m range versions. Vendor-stated [snippet] — [Blueye UGPS G2 spec sheet](https://www.blueyerobotics.com/specsheet/WL-GPS-G2-R100/pdf)
- Users report position drift and errors in lake and pool deployments; an "open water" setting lowers latency and range-limiting is used in tanks [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/waterlinked-gps-position-readings-drifts/12286), [Blue Robotics forum](https://discuss.bluerobotics.com/t/underwater-gps-release-2-5-is-now-available/5927)
- Acoustic update rate is generally lower than DVL rate; fusing the two raises the usable position rate for control [snippet] — [Water Linked DVL/UGPS integration](https://waterlinked.github.io/dvl/bluerov-integration-dvl-ugps)
- In a fused system the DVL smooths jumps in the acoustic fix and the acoustic fix corrects long-term DVL drift [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- Beacon battery matters: in the IMCA lost-ROV case the transponder interrogation rate was set too high and the beacon battery ran out early, so the drifting vehicle could not be tracked [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

**Position display**
- The Blueye app shows a live track on a map, lets the pilot drop pins on points of interest, import points before a dive and use offline charts [fetched] — [Blueye navigation blog](https://blueyerobotics.com/blog/how-do-navigation-and-position-tracking-work-underwater)
- After the IMCA loss, a current reading was added to the pilot's GUI as a corrective action [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

### Inferences
- A simulator can offer three navigation tiers with distinct failure signatures: compass-and-depth only (heading wanders 5-10 degrees or more near steel), DVL (smooth track that drifts and needs a surface reset every 15-20 minutes), and acoustic fix (absolute but jumpy, with multipath outliers near walls).
- Heading-hold and position-hold assists should degrade or misbehave next to steel piles and hulls; "back away and fly manually" is the documented response.
- DVL bottom-lock limits (5 cm to 50 m altitude) imply station keeping drops out in mid-water or when too close to the seabed.

### Gaps
- No sourced depth-sensor accuracy or altimeter (single-beam echosounder) specs.
- No sourced A50 long-term accuracy as percent of distance travelled.
- No Cerulean, Sonardyne Micro-Ranger or Seatrac USBL accuracy and update figures.
- No published measurement of dead-reckoning drift rate for a small ROV without DVL.
- No source on how pilots keep orientation in zero visibility beyond the sonar procedure in section 3.

## 5. Inspection tasks and how they are flown

### Takeaway
The only quantified pattern rules found are VideoRay's visibility-scaled ones: stand off about 0.7 x visibility and space passes about 1.3 x visibility. Piles are flown in alternating vertical passes facing the pile; other task types are described only qualitatively.

### Cited Findings

**Quay and pier wall**
- Starting points: distance from the wall about 0.7 x visibility; pass (transect) spacing about 1.3 x visibility, which gives 10% overlap. Both are adjusted on site [fetched] — [VideoRay pier wall SOP](https://download.videoray.com/documentation/sop_pwi/html/_1_4_define_inspection_parameters.html)
- Parallel transects along the wall between waypoints; curved or cornered piers need extra waypoints; for corners near 90 degrees fly each side as a separate mission; split very long piers into overlapping regions, possibly with several deployment sites [fetched] — [VideoRay pier wall SOP](https://download.videoray.com/documentation/sop_pwi/html/_1_4_define_inspection_parameters.html)

**Piles**
- Each pile is inspected all round from surface to seabed [snippet] — [VideoRay pier piling SOP](https://download.videoray.com/documentation/sop_ppi/html/_1_4_define_inspection_parameters.html)
- Vertical-pass method: face the pile at a stand-off set by water clarity; tilt camera slightly down on descending passes and slightly up on ascending passes; at the end of a pass move round the pile, still facing it, to the next start; alternate direction; repeat until fully covered. Vertical passes are generally the most efficient and may suit piles with cross-bracing [fetched] — [VideoRay pier piling SOP, vertical passes](https://download.videoray.com/documentation/sop_ppi/html/vertical.html)

**Hull**
- General visual inspection is flown from a moderate distance for an overview; detailed inspection is done at about arm's length from the component [snippet] — [Deep Trekker hull inspection](https://www.deeptrekker.com/hull-inspection-vehicle/)
- Holding a consistent stand-off with the camera locked on the target area is what makes hull footage usable as evidence [snippet] — [QYSEA case study](https://new.qysea.com/newsInfo-1851.html)
- A ship's hull, bridge footings and wrecks create eddies that can be used for shelter from current [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)

**Offshore jacket**
- A routine platform jacket inspection is the setting of the IMCA lost-ROV case: the vehicle was pushed inside the structure by tidal current and its tether abraded through on the steel [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

**Aquaculture**
- Net inspection, including mooring lines and anchors, is a primary ROV use in fish farming [snippet] — [Deep Trekker aquaculture case study](https://www.deeptrekker.com/resources/3-ways-kana-upton-and-aqua-cage-fisheries-use-their-rov)
- Case: an anchor line wrapped round a net; the ROV followed the line to find where it ran, then followed lines on the other pens to confirm they were free, so only one anchor had to be pulled [snippet] — [Deep Trekker aquaculture case study](https://www.deeptrekker.com/resources/3-ways-kana-upton-and-aqua-cage-fisheries-use-their-rov)
- Net defects include holes, plastic caught in the net and vegetation growth; research systems traverse the net plane top to bottom using ropes on the net as visual references [snippet] — [arXiv 2308.13826](https://arxiv.org/pdf/2308.13826v1.pdf)

**Pipes and tunnels**
- Blue Robotics had not tested a BlueROV2 in pipes; a straight pipe was said to make long tether deployment easier [fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)

**Search and recovery**
- The scanning-sonar approach in section 3 (settle, 360 degree scan, turn to 0 degrees, narrow sector, drive in) is the documented target-location method [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)

### Inferences
- Scaling stand-off and line spacing to visibility gives a simple scoring rule: coverage is achieved when adjacent passes overlap by about 10% at the current visibility.
- Pile and jacket work combine three hazards documented separately: steel-induced compass error, tether wrapping round members, and current pushing the vehicle into the structure.
- The aquaculture case is a ready-made "follow the line and report where it goes" mission.

### Gaps
- No sourced procedure or reading ranges for cathodic protection probes (contact technique, expected potentials against a silver/silver-chloride reference); the search returned nothing.
- No sourced flying procedure for pipeline survey, tank or tunnel inspection, or monopile inspection.
- No formal class-society stand-off figures for in-water hull surveys.
- No public-safety dive-team search patterns (jackstay, expanding square, sector) with spacing numbers.
- Survey speeds along a transect were not given by any source.

## 6. Manipulators and grabbers on small ROVs

### Takeaway
Small-ROV grabbers are single- or two-function tools with grip forces around 100 N; they attach lines and hold light items, they do not lift. Anything heavy is brought up by a separate line or by hand-hauling vehicle and object together.

### Cited Findings
- Blue Robotics Newton gripper: grip force about 97 N at the tip and 124 N mid-jaw, from a user comparison post [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/newton-gripper-grip-stregnth-and-failsafe/11164/2)
- Stated uses of the Newton gripper on a Blueye: retrieve objects, attach recovery lines, free a snagged tether [snippet] — [Blueye Newton gripper](https://www.blueyerobotics.com/products/newton-gripper)
- Deep Trekker two-function grabber: open/close plus rotation in both directions. Deep Trekker recommends bringing object and ROV up from the surface by hand to avoid tether damage, or using a grappling hook if that is not feasible [snippet] — [Deep Trekker manipulators support page](https://support.deeptrekker.com/accessories/manipulators)
- Deep Trekker Revolution manipulator arm rated for up to 31.7 kg, with a tether able to pull up to 136 kg to the surface [snippet] — [Janes](https://www.janes.com/defence-news/news-detail/xponential-2019-deep-trekker-unveils-revolution-rov)
- A Deep Trekker lift kit rated 5500 lb (about 2500 kg) is sold as an accessory [snippet] — [MoveSea lift kit listing](https://movesea.com/products/lift-kit-5500lb-deep-trekker)
- Reach Alpha-type electric manipulator: lift capacity 2500 g, maximum closing force 600 N [snippet] — [Reach Robotics](https://quote.reachrobotics.com/?p=676)
- A manipulator, or failing that the vehicle skid, can be used to work a snagged tether free [fetched] — [VideoRay emergency snag response](https://download.videoray.com/documentation/mss/html/emergency_snag.html)
- A manipulator can carry a descent weight and drop it at depth [fetched] — [VideoRay piloting in deep water](https://download.videoray.com/documentation/v1_7_0/html/pro4/pilot_deep.html)
- In the Lake Michigan recovery, a second ROV attached a cable to the lost vehicle so it could be raised [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)

### Inferences
- The realistic recovery loop for a simulator is: locate, grip or hook a line on, back away, and let the surface haul. Vertical thrust, not grip, limits what a small vehicle can carry.
- Holding an object shifts trim and adds drag; the 31.7 kg arm rating applies to a much larger vehicle than a 10 kg class ROV.

### Gaps
- No rated in-water lift figure for the Newton gripper or for a BlueROV2-class vehicle's vertical thrust margin.
- The lift-kit listing was not opened; how the kit works (lift bag or line) is unconfirmed.
- No sourced public-safety procedure for body or evidence recovery.

## 7. Pilot errors, equipment failures and incidents

### Takeaway
The documented losses share one chain: current or a snag traps the vehicle, the crew pulls or waits, the tether chafes or tightens, and tracking fails. Two incidents below have enough detail to rebuild as scenarios.

### Cited Findings

**Incident A: ROV lost in a platform jacket (IMCA Safety Flash 02/23)**
- During a routine jacket inspection the ROV became trapped inside the structure in strong tidal current. The tether was damaged and the vehicle lost power and telemetry [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)
- Attempts to free the slightly positively buoyant vehicle by careful pulling failed. The vessel was needed elsewhere, so the tether was cut and tied off to the jacket [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)
- Next day the damaged tether parted during a new attempt and the ROV drifted away. Its beacon signal was lost after a few hours; a work-class ROV search did not find it [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)
- What went wrong: emergency procedures did not cover the case; the workboat was not launched in time during the short interval the ROV was at the surface; two operators where three were needed; beacon interrogation rate set too high, exhausting its battery [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)
- Direct cause: tether parted through abrasion on the jacket. Root causes: insufficiently detailed instructions, risk assessment and recovery procedures; understaffing. Actions: procedures revised to include environmental limits and a recovery scenario; current reading added to the pilot GUI [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

**Incident B: ROV snagged on a wreck for eight years (Lake Michigan, 2014-2022)**
- In 2014, at about 134 m (440 ft) on the wreck of the freighter Senator, a SEAMOR ROV tangled in the ship's copper depth-sounder line. The team pulled on the tether, which tightened the knot, described as "the classic mistake" [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)
- After three or four hours the owner cut the tether, sealed the end with epoxy and hose clamps, coiled it and sank it with six pounds of weight. He left no buoy for fear a passing freighter would cut it [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)
- A later grappling attempt cut the tether and moved the vehicle. In 2021 a second ROV found it by sonar within 10 minutes; the tether was raised from 131 m to 79 m before snagging again, and a cutting attempt failed. A further three hours of grappling in 1 m waves failed [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)
- In 2022 the second ROV attached a cable and the vehicle was raised to 79 m, where a diver cut the fouling line in about one minute; it was then hauled aboard by hand. After cleaning it powered on with no visible leaks; the gripper and one light needed replacing [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)

**Incident C: slack line into a vessel propeller (IMCA Safety Flash 33/21)**
- During a subsea mooring job an ROV lost control of a synthetic pull-in rope; slack built up subsea into a catenary near the vessel's port propeller and the rope was drawn in. Causes cited: insufficient monitoring of the rope over the stern rollers and a vessel heading unfavourable to the current. This is a work-class case and the line was a rope, not the ROV tether [snippet] — [IMCA SF 33/21](https://imca-int.com/resources/safety/safety-flashes/3321-uhmpe-pull-in-rope-damaged-during-mooring-connection-to-buoy)

**Work-class launch and recovery incidents (for contrast)**
- 2024: the umbilical was damaged just above the docking bullet on the TMS, then sheared by the A-frame docking-head latch; the ROV dropped to the seabed [snippet] — [IMCA SF 13/24](https://imca-int.com/resources/safety/safety-flashes/1324-rov-dropped-to-seabed)
- 2019: main ROV lift wire, umbilical and bullet parted [snippet] — [IMCA SF 27/19](https://imca-int.com/resources/safety/safety-flashes/2719-main-rov-lift-wire-umbilical-and-bullet-parted)
- 2017: a crew member was fatally crushed between the TMS and the snubber ring [snippet] — [IMCA SF 25/17](https://imca-int.com/resources/safety/safety-flashes/2517-fatality-crew-member-crushed-between-tms-and-snubber-ring)
- 2011: dropped ROV and TMS, leading to a recommended engineering review of launch and recovery systems [snippet] — [IMCA SF 11/11](https://www.imca-int.com/resources/safety/safety-flashes/1111-equipment-damage-dropped-rovtether-management-system-tms)

**Routine failure modes and operator guidance**
- Too much tether out may result in snags, tangles or propeller cuts [fetched] — [VideoRay Pro 4 tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html)
- Thruster fouling: weed can jam thrusters; after touching a sandy bottom, stop and let the vehicle float up so sand stays out of the vertical thrusters [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Loss of power or topside connection during a dive: haul the tether in at a moderate pace, not as fast as possible [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Battery limits (4S lithium): recover at 12.5 V; below 12.0 V risks permanent damage. There is no power switch, the vehicle is live when the battery is connected [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Battery options: 14.8 V 18 Ah lithium-ion or 14.8 V 10 Ah lithium-polymer. Staff estimate of run time: 2-3 hours for a standard BlueROV2, less with the heavy configuration [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/), [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)
- Leak detection: an onboard leak sensor is part of the BlueROV2 configuration; users also report vacuum tests that fail to hold [fetched for sensor, snippet for user reports] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/), [Blue Robotics forum](https://discuss.bluerobotics.com/t/vacuum-pump-is-not-holding/14345)
- Heat: a vehicle out of the water for more than 15 minutes should be shaded [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Heading-hold runaway near steel (vehicle spinning on a steel wreck) [snippet] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/rov-problem-spinning-around/10680)

### Inferences
- Scenario A (jacket): rising tidal current, a pilot GUI with no current read-out, a two-person crew, tether chafing on steel with progressive loss of power and telemetry, and a brief surface window in which a workboat must be ready. Teaching points: set an environmental abort limit, keep the tether off steel, rehearse the recovery.
- Scenario B (wreck): thin line invisible on camera, snag at depth, and a tension meter that makes the knot worse when the tender hauls. Teaching points: stop, turn, trace the tether, do not pull, mark the position before abandoning.
- The 12.5 V recover and 12.0 V damage thresholds give a simple, sourced battery model for a 4S vehicle.
- "Haul in at a moderate pace" after comms loss implies a dead vehicle that is near neutral and can be recovered by hand, provided the tether is not fouled.

### Gaps
- No documented incident found of a small-ROV tether cut by the support boat's own propeller, although vendor documentation names it as a standing hazard.
- No documented small-ROV flooding incident with cause and sequence.
- No documented case of pilot disorientation in zero visibility.
- No incident statistics (rates by cause) for observation-class operations.
- The IMCA work-class flashes other than 02/23 were read only as search summaries; sequence details are thin.

## 8. Environmental conditions operators plan for

### Takeaway
Current is the planning driver: one vendor defines "strong" as above 1.5 kn, and practice is to work at slack water, start up-current, and use structures for shelter. Usable current depends on thrust and tether length more than on vehicle top speed.

### Cited Findings
- VideoRay defines strong current as anything above 1.5 kn [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- Plan for available thrust of roughly twice the vehicle's mass (rule of thumb) [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- Tactics: fly into the current where possible; otherwise crab diagonally across it; start upstream and work downstream on a short leash; shelter in eddies behind hulls, bridge footings and wrecks [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- Slack water: time operations as close to slack as possible and do not rely on general tide tables alone; slack can shift 30-60 minutes over a short distance from the reference port, so be ready about an hour early. Neap and spring tides change the usable window. Have a backup plan [fetched] — [VideoRay strong-current tips](https://videoray.com/?p=13174)
- VideoRay Pro 4 Ultra rated speed is 4.2 kn, and the vendor states tactics allow work in current above the vehicle's own top speed [snippet] — [VideoRay Pro 4 Ultra FAQ](https://download.videoray.com/documentation/pro_4_ultra/html/intro_faq.html)
- BlueROV2 anecdotes: control authority up to about 1 m/s with tether drag manageable to about 50 m depth; manufacturer's own testing only at about 0.5 kn [snippet and fetched] — [Blue Robotics forum](https://discuss.bluerobotics.com/t/the-maximum-sea-speed-current/3529), [Blue Robotics forum](https://discuss.bluerobotics.com/t/900ft-tether-against-2kt-current-will-it-work/4404)
- Shore launch is ruled out in heavy surf [fetched] — [Blue Robotics BlueROV2 Operation](https://bluerobotics.com/learn/bluerov2-operation/)
- Recovery attempts on Lake Michigan were abandoned in 1 m waves and repeatedly delayed by weather [fetched] — [Ocean News](https://www.oceannews.com/news/subsea-and-survey/shipwreck-hunter-recovers-his-seamor-rov-after-8-years-at-the-bottom-of-lake-michigan)
- Sound speed varies with temperature, salinity and depth and must be set manually for sonar ranging [fetched] — [Blue Robotics scanning sonar guide](https://bluerobotics.com/learn/understanding-and-using-scanning-sonars/)
- DVL performance at long range depends on seabed type and salinity [snippet] — [Deep Trekker DVL page](https://deeptrekker.com/shop/products/dvl-waterlinked)
- Tidal current was the initiating factor in the IMCA jacket loss, and "environmental limitations" were added to procedures afterwards [fetched] — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

### Inferences
- A tide model with a slack window that arrives 30-60 minutes off the published time, and a current read-out the trainee must watch, reproduces both the VideoRay advice and the IMCA corrective action.
- Sensible simulator defaults from these sources: up to 0.5 kn easy, 0.5-1.5 kn workable with tether discipline, above 1.5 kn needs clump weight, shelter and short leash, around 2 kn the practical limit for a BlueROV2-class vehicle on a short tether.

### Gaps
- No sourced per-class current limits (for example for a Falcon-class 60-100 kg vehicle or a light work-class vehicle with TMS).
- No sourced treatment of near-surface surge and wave-induced motion on a small ROV, or of thermoclines and their effect on buoyancy or sonar.
- No sourced operating temperature limits or cold-water battery derating.
- No sourced sea-state limits for launch and recovery.
