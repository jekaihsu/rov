# Real handling, control modes and dynamics of observation-class / light work-class ROVs (BlueROV2, BlueROV2 Heavy, Saab Seaeye Falcon; VideoRay, Deep Trekker, FIFISH for comparison)

Research date: 2026-11-14. Conventions: "MFR" = manufacturer claim; "MEAS" = independently measured / identified;
"SNIPPET" = taken from a search-result summary only, the page itself could not be opened, so treat as lower confidence.
1 kgf = 9.81 N; 1 knot = 0.514 m/s.

## 1. Vehicle specs (mass, geometry, thrust, speed, depth, payload, stability)

### Takeaway
BlueROV2 is an ~11-12 kg, 6-thruster (4 vectored + 2 vertical) vehicle with MFR 9 kgf forward/lateral bollard thrust;
the Heavy adds 2 vertical thrusters (14 kgf vertical, 6-DOF) with the same horizontal thrust. The Falcon is a 60 kg
(100 kg DR), 5-thruster (4 vectored + 1 vertical) vehicle with 42-50 kgf forward thrust and ">3 knots". Independent pool
measurements put the BlueROV2 Heavy top speed at only ~0.7 m/s, about half the MFR 1.5 m/s figure for the standard vehicle.

### Cited Findings

BlueROV2 (standard), MFR:
- Mass in air 11-12 kg with ballast and battery; 9-10 kg without. Length 457 mm, width 338 mm, height 254 mm.
  6 thrusters (4 vectored, 2 vertical). — [Blue Robotics BlueROV2 page](https://bluerobotics.com/store/rov/bluerov2/)
- Forward bollard thrust (45 deg vectored) 9 kgf; lateral 9 kgf; vertical 7 kgf. Max forward speed 1.5 m/s (3 knots).
  — [Blue Robotics BlueROV2 page](https://bluerobotics.com/store/rov/bluerov2/)
- Depth 100 m (acrylic tubes) / 300 m (aluminium tubes). Payload 1.2 kg (4 lights) to 1.4 kg (no lights) = net buoyancy
  available without ballast. Battery ~2 h normal use, ~4 h light use (15.6 Ah).
  — [Blue Robotics BlueROV2 page](https://bluerobotics.com/store/rov/bluerov2/)
- Tether: 7.6 mm standard (25-300 m) or 4.0 mm slim (50-200 m); working strength 35 kgf, breaking 155 kgf; neutral in
  fresh water, slightly positive in salt water. — [Blue Robotics BlueROV2 page](https://bluerobotics.com/store/rov/bluerov2/)
- CONFLICT on top speed: the older BlueROV2 datasheet (rev3) lists maximum forward speed 1 m/s (2 knots) (SNIPPET)
  — [BlueROV2 datasheet rev3](https://bluerobotics.com/wp-content/uploads/2017/03/br_bluerov2_datasheet_rev3-bleed.pdf);
  Blue Robotics staff restate 1.5 m/s as the specified figure but note internally that one person thinks ~1 m/s is more
  realistic — [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)
- Standard BlueROV2 has 5 controllable DOF (no pitch authority); Heavy has 6 DOF (SNIPPET)
  — [Blue Robotics Technical Reference](https://bluerobotics.com/?p=145836)

BlueROV2 Heavy, MFR:
- 8 thrusters: 4 vectored horizontal + 4 vertical, verticals moved to the outside of the frame "improving flight
  stability"; forward 9 kgf, lateral 9 kgf, vertical 14 kgf (SNIPPET)
  — [Heavy retrofit kit](https://bluerobotics.com/store/rov/bluerov2-upgrade-kits/brov2-heavy-retrofit)
- No published Heavy top speed. Staff: same forward thrusters, slightly larger cross-section, so below 1.5 m/s; the
  1.5 m/s figure assumes forward-only command (adding yaw / lateral / vertical demand lowers it).
  — [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)

BlueROV2 Heavy, MEAS (von Benzon et al., Aalborg Univ., J. Mar. Sci. Eng. 2022, pool tests with SBL positioning):
- Mass 13.5 kg (experimental); displaced volume 0.0134 m^3 (so buoyancy 13.4 kg in fresh water, i.e. ~0.1 kg negative
  as tested). Ix 0.26, Iy 0.23, Iz 0.37 kg m^2 (CAD). Centre of gravity (0,0,0), centre of buoyancy (0,0,-0.01) m,
  i.e. CB only 10 mm above CG (CAD value). — [von Benzon et al. 2022, Table A1](https://doi.org/10.3390/jmse10121898)
- Overall L x H x W = 0.46 x 0.38 x 0.58 m; projected areas Au 0.0877 m^2 (frontal), Av 0.1131 m^2 (side),
  Aw 0.2049 m^2 (top). — [von Benzon et al. 2022, Table 5](https://doi.org/10.3390/jmse10121898)
- Measured maxima (Table 4): surge 0.72 m/s at 85 N; sway 0.63 m/s at 85 N; heave 0.71 m/s at 120 N; max moments roll
  26 N m, pitch 14 N m, yaw 22 N m; max angular rates listed as 5.2 (roll), 4.9 (pitch), 3.6 (yaw) - the table prints
  "m/s" for these, presumably rad/s. — [von Benzon et al. 2022, Table 4](https://doi.org/10.3390/jmse10121898)

Saab Seaeye Falcon / Falcon DR, MFR:
- Falcon: depth 300 m; L 1000 mm, H 500 mm, W 600 mm; 60 kg in air; payload 14 kg; speed >3 knots.
  Falcon DR: depth 1000 m; L 1055 mm, H 555 mm, W 600 mm; 100 kg; payload 15 kg; speed >3 knots.
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)
- Thrust per 2020 brochure (both variants): forward 50 kgf, lateral 28 kgf, vertical 13 kgf.
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf);
  CONFLICT: the current Saab Seaeye web page lists forward 42 kgf, lateral 25 kgf, vertical 13 kgf for the 60 kg Falcon
  — [Saab Seaeye Falcon page](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon). Record range: 42-50 kgf
  forward, 25-28 kgf lateral, 13 kgf vertical.
- Thrusters: type S1-MCT01, 4 horizontal (vectored) + 1 vertical, "magnetically coupled propellers ... integral drive
  for precise vehicle control". No auto pitch/roll (vehicle relies on passive stability). Power: single-phase
  110/230 VAC surface supply. Optional fibre upgrade allows up to 1100 m tether.
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)

Comparison vehicles, MFR:
- VideoRay Mission Specialist Defender: 4 vectored horizontal + 3 vertical brushless thrusters; thrust ~23.6 kgf
  forward, 15.0 kgf reverse, 8.6 kgf lateral, 9.5 kgf lift; ~3.8 knots forward, 0.8 m/s vertical, 0.9 knots sway
  (as extracted; lateral speed figure looks low and should be re-checked); depth 300 m std / 1000 m optional (SNIPPET)
  — [VideoRay Defender spec sheet 2025](https://videoray.com/wp-content/uploads/2025_SpecSheet_Defender-2.0.1.pdf)
- Deep Trekker REVOLUTION: 26 kg in air; 717 x 440 x 235 mm; 6 magnetically coupled thrusters; 305 m; 22.2 V battery,
  up to 6 h. Page gives no thrust or speed numbers.
  — [Deep Trekker REVOLUTION spec page](https://www.deeptrekker.com/learn/revolution-rov-spec-sheet)
- QYSEA FIFISH V6 / V6 Expert: ~3.9 kg / ~4.6 kg; 383 x 331 x 143 mm; 100 m depth; omnidirectional; "AI Vision Station
  Lock" listed for both (SNIPPET) — [QYSEA store FIFISH V6](https://store.qysea.com/fifish-v6.html)

### Inferences
- Thrust-to-weight (forward bollard / mass in air): BlueROV2 9/11.5 = ~0.78; Falcon 42-50/60 = 0.70-0.83; Falcon DR
  42-50/100 = 0.42-0.50; Defender figure not computable (no mass found). So BlueROV2 and Falcon are similar in
  normalised horizontal authority; the Falcon's vertical authority is weak (13 kgf / 60 kg = 0.22) versus Heavy
  (14 kgf / ~12-13.5 kg = ~1.0-1.2). A simulator should make a Falcon-like vehicle noticeably sluggish in heave.
- Falcon lumped drag: if 3 knots (1.54 m/s) is reached at 42-50 kgf (412-490 N), quadratic drag coefficient
  k = F/v^2 = ~173-207 N s^2/m^2 (upper bound, since speed is ">3 knots").
- BlueROV2 MFR 1.5 m/s vs MEAS 0.72 m/s (Heavy): with quadratic drag, 1.5 m/s at 88 N implies k = ~39 N s^2/m^2, while
  the Heavy identification gives 141 N s^2/m^2. The Heavy has a larger frontal area, but not 3.6x; the MFR figure is
  best treated as optimistic. A realistic tuning range for a BlueROV2-class top speed is 0.7-1.0 m/s (Heavy)
  and 1.0-1.5 m/s (standard).
- Passive stability of BlueROV2 Heavy per the von Benzon CAD values is very low: righting moment = W * BG * sin(angle)
  = 132.6 N * 0.01 m = ~1.3 N m/rad (~0.023 N m/deg). Actual vehicles with bottom ballast and top foam will have larger
  BG; this CAD figure should be treated as a lower bound.

### Gaps
- No published BG (metacentric height) or righting-moment figure from Blue Robotics or Saab Seaeye was found.
- Falcon lateral and vertical maximum speeds are not published in the sources opened; only ">3 knots" forward.
- Falcon mass in water / trim and the reason for the 50 -> 42 kgf revision are not documented in the sources found.
- Deep Trekker and FIFISH thrust and speed figures were not obtained (QYSEA spec page returned 404).
- The Ng (2024) MS thesis hosted by Blue Robotics, which collects BlueROV2 Heavy parameter tables from several papers,
  exceeded the fetch size limit and could not be read:
  [Ng thesis PDF](https://bluerobotics.com/wp-content/uploads/2025/01/ng_patrick_ms_thesis_2024.pdf).

## 2. Thruster characteristics (T200; Falcon thrusters)

### Takeaway
A T200 gives 5.25 kgf forward / 4.1 kgf reverse at 16 V (reverse is ~78% of forward), with a +/-25 us PWM deadband
around 1500 us and an effective response lag on the order of 0.1 s. Falcon thrusters are brushless, magnetically coupled
units with integral drive electronics; no thrust-curve data is public.

### Cited Findings
- T200 full-throttle thrust forward/reverse (MFR): 3.71/2.92 kgf at 12 V (17 A, 205 W); 5.25/4.1 kgf at 16 V (24 A,
  390 W); 6.7/5.05 kgf at 20 V (32 A, 645 W). Operating voltage 7-20 V. Minimum thrust 0.02 kgf. Propeller 76 mm.
  Mass 427 g in air, 239 g in water. FAQ estimates ~3075 rpm at 12 V and ~3600 rpm at 16 V at full throttle.
  — [Blue Robotics T200 page](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/)
- PWM: 1100 us full reverse, 1500 us stop, 1900 us full forward; deadband +/-25 us (1475-1525 us) (SNIPPET, from a
  Blue Robotics listing and forum answer) — [BR forum: basic T200 control setup](https://discuss.bluerobotics.com/t/basic-t200-control-setup/2111)
- Basic ESC accepts 1100-1900 us pulses at up to 400 Hz. Staff-estimated command-to-ESC delay ~31-40 ms at 100 Hz and
  ~24-25 ms at 400 Hz update rate. The ESC applies an input low-pass filter governed by a "Startup Power" setting,
  default 50%. — [BR forum: T200 response time](https://discuss.bluerobotics.com/t/response-time-and-minimum-rotation-speed-for-t200-with-basic-esc/11112)
- User measurement (MEAS, single user): ~110 ms (+/-10 ms) from command to output change for a 1500 -> 1700 us step.
  — [BR forum: T200 response time](https://discuss.bluerobotics.com/t/response-time-and-minimum-rotation-speed-for-t200-with-basic-esc/11112)
- Identified thruster dynamics (MEAS, from MathWorks-published test data): unity-DC-gain transfer function
  K(s) = (6136 s + 108700) / (s^3 + 89 s^2 + 9258 s + 108700).
  — [von Benzon et al. 2022, Eq. 19](https://doi.org/10.3390/jmse10121898)
- Identified static thrust curve (MEAS), normalised input V in [-1, 1], force in N:
  F(V) = -140.3 V^9 + 389.9 V^7 - 404.1 V^5 + 176.0 V^3 + 8.9 V. Thruster deadzone means vehicle tests started at 20%
  input. — [von Benzon et al. 2022, Eq. 18 and Sec. 4.2](https://doi.org/10.3390/jmse10121898)
- T200 thrust is "not quite quadratic" in ESC input, so 75% input gives slightly more than 75% of top speed (staff).
  — [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)
- Falcon: thruster type S1-MCT01, "high efficiency thrusters with magnetically coupled propellers for low maintenance
  and integral drive for precise vehicle control" (MFR).
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)

### Inferences
- Evaluating the von Benzon polynomial at V = 1 gives ~30.4 N (~3.1 kgf) per thruster, i.e. the test vehicle was
  running at roughly 12-13 V-equivalent output. 4 x 30.4 x cos45 = 86 N matches the paper's 85 N surge/sway maximum, and
  4 x 30.4 = 122 N matches the 120 N heave maximum.
- The transfer function has a dominant real pole near s = -13.2 (time constant ~0.076 s) plus a complex pair with
  natural frequency ~91 rad/s and damping ~0.42. For a simulator, a first-order lag of 0.08-0.11 s per thruster
  reproduces both this and the forum measurement.
- Ideal geometry at 16 V would give 4 x 5.25 x cos45 = 14.8 kgf forward, more than the MFR 9 kgf vehicle figure, so the
  vehicle rating reflects lower voltage under load, reverse-direction thrusters and/or current limiting. Forward/reverse
  asymmetry of ~22% applies per thruster.

### Gaps
- Full thrust-vs-PWM tables at each voltage are only in Blue Robotics' downloadable spreadsheet, not read here.
- No public thrust curve, response time, or velocity-feedback detail for the Falcon S1-MCT01 thruster was found.

## 3. Hydrodynamics (drag, added mass, acceleration, coasting, yaw rate)

### Takeaway
The best open, experimentally validated BlueROV2 Heavy model (von Benzon et al.) gives quadratic drag of 141 (surge),
217 (sway) and 190 (heave) N s^2/m^2 with added mass of 6.4, 7.1 and 18.7 kg. This implies a vehicle that reaches top
speed and stops within roughly 0.3 m and about 1-1.5 s: it does not coast like a boat.

### Cited Findings
All from [von Benzon et al. 2022, Table A1](https://doi.org/10.3390/jmse10121898) unless noted; damping values are
"Experimental", added mass from the Eidsvik/DNV empirical method (not measured):
- Linear damping: Xu 13.7 N s/m; Yv 0 N s/m; Zw 33.0 N s/m; Kp 0; Mq 0.8 N m s/rad; Nr 0.
- Quadratic damping: Xu|u| 141.0; Yv|v| 217.0; Zw|w| 190.0 N s^2/m^2; Kp|p| 1.19; Mq|q| 0.47; Nr|r| 1.5 N m s^2/rad^2.
- Added mass: Xu_dot 6.36 kg; Yv_dot 7.12 kg; Zw_dot 18.68 kg; Kp_dot 0.189; Mq_dot 0.135; Nr_dot 0.222 kg m^2.
- Model validation: steady-state velocity error up to ~10% in surge and sway over 20-100% input; heave error 15% at 20%
  input, less at higher input. — [von Benzon et al. 2022, Sec. 4.2](https://doi.org/10.3390/jmse10121898)
- Added-mass estimates by this method carry 10-20% error in translation and 30-100% in rotation, and the Heavy violates
  the method's shape assumption (width 20% larger than length), so acceleration-phase behaviour is the least certain
  part of the model. — [von Benzon et al. 2022, Sec. 4.3](https://doi.org/10.3390/jmse10121898)
- Other BlueROV2 parameter sets exist with different values, e.g. heave linear damping 31.87 N s/m, pitch linear
  damping 44.91 N m s/rad, yaw added inertia 0.40 kg m^2 (SNIPPET; table incomplete in extraction)
  — [AquaChat++ arXiv 2508.06554](https://arxiv.org/pdf/2508.06554)
- Drag scales with speed squared, so doubling thrust yields only ~41% more speed (staff).
  — [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)

### Inferences (computed from the Table A1 values; not stated in the paper)
- Effective mass: surge 13.5 + 6.36 = 19.9 kg; sway 20.6 kg; heave 32.2 kg; yaw inertia 0.37 + 0.222 = 0.59 kg m^2.
- Consistency check: 13.7 v + 141 v^2 = 85 N gives v = 0.73 m/s (paper: 0.72); 217 v^2 = 85 gives 0.63 m/s (0.63);
  33 w + 190 w^2 = 120 gives 0.71 m/s (0.71).
- Initial acceleration from rest at full thrust: surge 85/19.9 = ~4.3 m/s^2; heave 120/32.2 = ~3.7 m/s^2 (before
  thruster lag). Time to ~90% of top speed is therefore a few tenths of a second plus ~0.1 s thruster lag.
- Coasting after stick release from 0.72 m/s in surge (thrust to zero, no tether): distance to stop
  x = (M/b) ln((a + b v0)/a) = (19.9/141) ln(115.2/13.7) = ~0.30 m; speed falls to 0.05 m/s after ~1.4 s and ~0.24 m.
  Half-speed (0.36 m/s) is reached in ~0.3 s. The last few cm/s decay slowly (linear-damping tail, time constant
  M/a = ~1.45 s).
- Sway has no linear term in this model, so pure quadratic decay: v(t) = v0 / (1 + (b v0 / M) t); from 0.63 m/s the speed
  halves in ~0.15 s but never formally reaches zero - in a simulator add a small linear term to avoid endless creep.
- Maximum yaw rate: sqrt(22 N m / 1.5) = ~3.8 rad/s (~220 deg/s), consistent with the paper's 3.6 (~206 deg/s) at full
  yaw command. At typical 50% pilot gain, quadratic scaling suggests ~150 deg/s. Yaw spin-down from 3.6 rad/s halves in
  about I/(b r0) = 0.59/(1.5 x 3.6) = ~0.11 s.
- Lateral drag is ~1.5x surge drag and vertical ~1.35x, so the vehicle is slower sideways (0.63 vs 0.72 m/s) for the
  same thrust.

### Gaps
- No independently measured step-response or stopping-distance plots were extracted; the numbers above are derived from
  identified coefficients, not directly observed.
- No published hydrodynamic coefficients for the Saab Seaeye Falcon were found.
- Wu's thesis and the Ng (2024) thesis parameter tables were not read; ranges across papers are therefore incomplete.

## 4. ArduSub flight modes, pilot gain and joystick mapping

### Takeaway
ArduSub's default piloting is direct thrust control: stick deflection scaled by pilot gain becomes thruster effort, and
only attitude/heading (Stabilize) and depth (Depth Hold) are closed-loop. Horizontal position is uncontrolled unless a
position source (DVL/USBL) enables Position Hold.

### Cited Findings
- Mode table (ArduPilot Sub docs): MANUAL "Pilot control with no stabilization"; STABILIZE "Manual angle control, manual
  depth control"; ACRO "Body-frame rate control, manual depth control"; ALT_HOLD (depth hold) "Stabilize with automatic
  depth control" (needs depth sensor); POSHOLD "Loiter with depth control and pilot overrides" (needs position + depth);
  AUTO "Automatic mission command list execution" (position + depth); GUIDED "Swim to location or velocity/direction
  using GCS" (position + depth); CIRCLE "Circle swim with depth control" (position + depth); SURFACE "Return to surface,
  pilot directional control"; SURFTRAK "Hold distance above seafloor while stabilizing" (needs rangefinder);
  MOTOR_DETECT. — [ArduPilot Sub flight modes](https://ardupilot.org/sub/docs/modes.html)
- Manual: thruster output comes only from joystick input; "There is no feedback stabilization, heading holding, or
  depth holding." — [ArduSub features while in operation](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html)
- Stabilize: roll is levelled and heading is held when the pilot is not commanding a turn; vertical control is fully
  manual. Depth Hold: same as Stabilize plus depth is held unless the pilot commands dive/ascent; releasing the
  vertical stick holds the current depth.
  — [ArduSub features while in operation](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html)
- Roll/pitch input: in Manual "a centered joystick input commands a rotation rate of zero" (rate, not angle); in
  Stabilize / Depth Hold a centred stick levels the vehicle and deflection sets a target angle limited by pilot gain and
  ANGLE_MAX (example: ANGLE_MAX 80 deg at 50% gain gives 40 deg at full stick).
  — [ArduSub features while in operation](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html)
- Pilot gain: "controls how much power is available for thruster control"; it scales input linearly (75% gain turns a
  100% input into 75%). — [ArduSub features while in operation](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html);
  [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)
- Gain parameters: JS_GAIN_DEFAULT (gain at boot, range 0.1-1.0), JS_GAIN_MIN (0.1-0.8), JS_GAIN_MAX (0.2-1.0),
  JS_GAIN_STEPS (1-10 steps between min and max; 1 = always default), JS_THR_GAIN (extra scaling of vertical input).
  — [ArduPilot Sub pilot control](https://ardupilot.org/sub/docs/pilot-control.html);
  [ArduPilot Sub parameter list](https://ardupilot.org/sub/docs/parameters.html)
- Button functions: gain_inc / gain_dec (one step), gain_toggle ("Toggle pilot gain between 50% and 100%"),
  input_hold_set ("Toggle holding current joystick axis inputs (cruise control on/off)"), trim_roll/pitch_inc/dec,
  roll_pitch_toggle (sticks switch between forward/lateral and roll/pitch), mode_* buttons (manual, stabilize, depth
  hold, poshold, auto, circle, guided, acro, surftrak), lights brighter/dimmer steps, mount_tilt_up/down. Each button has
  a primary and a shifted function; up to 32 buttons. — [ArduPilot Sub button inputs](https://ardupilot.org/sub/docs/buttons.html)
- Depth-hold vertical stick: deflection moves the depth target at a rate limited by PILOT_SPEED_UP / PILOT_SPEED_DN and
  PILOT_ACCEL_Z; THR_DZ is a throttle deadzone so small stick movements do not change the target (applies in ALT_HOLD,
  SURFTRAK, POSHOLD, CIRCLE). SURFACE_MAX_THR reduces upward thrust near the surface.
  — [ArduPilot Sub pilot control](https://ardupilot.org/sub/docs/pilot-control.html)
- Tuning note from Blue Robotics staff: raising the PILOT_SPEED parameters and lowering PILOT_ACCEL_Z makes the vertical
  stopping distance larger; these parameters affect only depth-hold and position-enabled modes (SNIPPET)
  — [BR forum: depth hold gain](https://discuss.bluerobotics.com/t/depth-hold-gain/3587)
- Yaw is a rate target in STABILIZE, ALT_HOLD, SURFTRAK, POSHOLD and SURFACE; in MANUAL all axes are direct motor
  output. — [ArduPilot Sub pilot control](https://ardupilot.org/sub/docs/pilot-control.html)

### Inferences
- Sticks centred, by mode: Manual - zero thrust, vehicle coasts to rest in ~0.3 m and then drifts freely with current,
  tether pull and any net buoyancy; heading drifts. Stabilize - heading and level attitude held, vehicle still drifts
  in x/y/z. Depth Hold - heading, attitude and depth held, drifts horizontally with current. Position Hold - all held,
  as long as the position estimate is valid.
- In Depth Hold the vertical stick is a climb-rate command (velocity control with acceleration limit), while forward,
  lateral and (effectively) yaw remain effort commands. Real BlueROV2 handling is therefore a hybrid: "drone-like" only
  in the vertical axis and heading.
- With gain_toggle semantics (50% / 100%) and quadratic drag, 50% gain gives roughly 70% of top speed; pilots typically
  inspect at low gain for finer stick resolution.

### Gaps
- Default numeric values (JS_GAIN_DEFAULT, JS_GAIN_STEPS, PILOT_SPEED_UP, PILOT_ACCEL_Z, THR_DZ, ANGLE_MAX, yaw rate
  scaling) were not shown on the pages opened; they are in the full parameter list. Unverified recollection (do not
  cite): default gain 0.5, min 0.25, max 1.0, 4 steps.
- The default gamepad layout (which function sits on which button in QGroundControl, and Cockpit's defaults) lives on
  the "Default Sub Hardware Configuration" page / as an image and was not retrieved. The old ardusub.com operators-manual
  and joystick pages return 404.
- No documented description of Surface mode ascent rate or Auto/Guided speed limits was retrieved.

## 5. Saab Seaeye Falcon control (hand controller, autopilots, iCON, behaviour in current)

### Takeaway
The Falcon is flown from a USB hand controller (or on-screen virtual controller) through the iCON control system, with
auto heading and auto depth standard and auto altitude, DVL station keeping, relative waypoints and auto speed as
options. Manufacturer material describes stability in current only qualitatively; no knots figure for current-holding is
published.

### Cited Findings
- Autopilots: "Auto heading & depth (latch and track modes)"; "Auto altitude option"; "Station keeping with fine
  position control"; "Relative waypoint control and auto speed". Spec table: auto-depth and auto-heading standard;
  auto-altitude and station keeping optional; no auto pitch/roll.
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)
- Surface unit: iCON control system, 22 inch detachable daylight-viewable touchscreen, customisable pilot display,
  "a USB hand controller and an on-screen virtual controller", live vehicle diagnostics.
  — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)
- "Five powerful thrusters provide precise control and maintain a stable platform in strong currents and turbulent
  waters." (MFR, qualitative.) — [Saab Seaeye Falcon page](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon)
- A navigation pod provides auto depth and auto heading as standard; an altimeter enables auto altitude; a DVL is the
  option "used for station keeping". — [Saab Seaeye Falcon page](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon)

### Inferences
- "Latch and track modes" most plausibly mean: latch = hold the heading/depth at the moment of engagement; track = the
  setpoint follows pilot input and re-latches on release. This reading is not confirmed by a manual.
- Without the DVL option the Falcon, like the BlueROV2, is thrust-controlled horizontally: sticks centred with auto
  heading and depth on means it holds heading and depth and drifts with current and tether pull.
- With >3 knots top speed, the usable current for station work is lower than top speed because tether drag consumes
  thrust (see section 6); the common pilot rule of working in currents up to roughly half to two-thirds of top speed is
  not sourced here.

### Gaps
- No Falcon operator manual was accessible: hand controller layout (which stick/knob does what), thruster gain or
  power-limit settings, autopilot engagement logic and loop behaviour are undocumented in these notes.
- No published or independent current-holding figure in knots, and no pilot testimonials on Falcon handling, were found.
- iCON internals (thruster velocity feedback, control rates) are not publicly described in the sources found.

## 6. Real-world handling: tether, current, trim, technique

### Takeaway
The tether is the dominant disturbance on small ROVs: in a simulated inspection with 0.5 m/s current, a BlueROV2 Heavy
spent on average ~25% and at peaks ~38% of its horizontal thrust just counteracting tether force. Pilot practice is to
minimise tether in the water, work heading into the current and crab across it.

### Cited Findings
- Simulated inspection campaign with tether and current: average absolute tether force 21.1 N in x (25% of max thrust),
  19.3 N in y (23%), 12.2 N in z (10%); mean of the largest 5%: 31.9 N (38%), 28.7 N (34%), 21.2 N (18%). The paper
  notes this is the ideal case because the same thrusters serve surge and sway. Model-based, not measured.
  — [von Benzon et al. 2022, Table 9](https://doi.org/10.3390/jmse10121898)
- Passive test in the same model: 15 m tether, current 0.354 m/s north + 0.354 m/s east (0.5 m/s total); tether lags the
  vehicle, straightens after ~30 s, and the unpowered vehicle is dragged up to the surface after ~100 s. "The tether has
  a large effect on the ROV." Tether parameters: 7.5 mm diameter, 0.043 kg/m, normal drag coefficient 1.2, tangential
  0.01. — [von Benzon et al. 2022, Sec. 6 and Table A1](https://doi.org/10.3390/jmse10121898)
- Even in a pool, tether disturbance could not be eliminated during identification tests despite manually feeding the
  tether after the vehicle. — [von Benzon et al. 2022, Sec. 4.2](https://doi.org/10.3390/jmse10121898)
- User report: a BlueROV2 on a 1 kW power-over-tether system in a fish pen has overcome currents "of up to 1 m/s ...
  (at full power)" (anecdotal, single user, configuration not fully specified).
  — [BR forum: Heavy water current speed](https://discuss.bluerobotics.com/t/bluerov2-heavy-configuration-water-current-speed/17002)
- VideoRay operator guidance (SNIPPET; page returned an error when opened): deploy as little tether as possible because
  it "will act like a sail and pull on the ROV"; drag increases when working perpendicular to the current; flying into
  the current gives the best control; take a diagonal heading and "crab" across the current rather than flying straight
  at the target; when going with the current, use the tether like a fishing line to control the force on the vehicle;
  a clump weight on the tether can help when the current keeps pushing the vehicle off station; shelter behind hulls,
  bridge footings or wrecks. — [VideoRay Mission Specialist: piloting in swift current](https://download.videoray.com/documentation/mss/html/pilot_current.html)
- Thicker tether conductors increase diameter, drag and slant angle; thin tether helps on long deployments (SNIPPET).
  — [VideoRay Insights](https://videoray.com/insights/introducing-insights-a-new-go-to-resource-for-rov-operators-2)

### Inferences
- Tether drag per metre broadside: 0.5 x 1000 x 1.2 x 0.0075 x v^2 = 4.5 v^2 N/m. At 0.5 m/s that is ~1.1 N/m, so ~75 m
  of tether broadside to a 0.5 m/s current equals the entire 85 N horizontal thrust of a BlueROV2 Heavy; at 1 m/s only
  ~19 m is needed. This is why current capability collapses with depth/tether length and why slim (4 mm) tether matters.
- Hull drag alone at 0.5 m/s is small (13.7 x 0.5 + 141 x 0.25 = ~42 N, half of available thrust), so the vehicle body
  could hold ~0.7 m/s head-on but tether limits practical working current to well below that.
- Buoyancy trim: Blue Robotics' 1.2-1.4 kg of spare buoyancy is ballasted out to near neutral; a residual of even 0.1 kg
  (1 N) gives a slow steady rise or sink in Manual/Stabilize because linear heave damping is only ~33 N s/m
  (drift ~0.03 m/s), which Depth Hold masks at the cost of constant vertical thrust.
- Because lateral drag is ~1.5x surge drag and tether side-load is largest broadside to the current, the natural
  technique of pointing the nose into the current and crabbing emerges from the physics; a simulator with correct
  anisotropic drag plus a tether model will reward it without special-casing.

### Gaps
- No sourced figures for typical inspection working speed (m/s), manual station-keeping precision, or turning technique
  were found. Christ and Wernli's "The ROV Manual" and IMCA guidance were not accessible online.
- No first-hand pilot descriptions of Falcon or BlueROV2 feel (e.g. forum testimonials on turning, overshoot) were
  retrieved within the search budget.
- The rule of thumb "about twice as much thrust as vehicle mass for strong current" appeared only in an unattributed
  search summary and is not reliably sourced.

## 7. DVL-based station keeping on small ROVs

### Takeaway
The Water Linked DVL A50 (5 cm to 50 m altitude, +/-1.01% standard or +/-0.1% performance long-term accuracy) is the
common enabler of Position Hold on BlueROV2-class vehicles, but no measured station-keeping accuracy figure was found,
and forum reports show that bottom-lock problems and EKF setup issues can cause runaway rather than hold.

### Cited Findings
- DVL A50: altitude range 5 cm to 50 m (above ~35 m depends on seabed and salinity); long-term accuracy +/-1.01%
  (standard) or +/-0.1% (performance); max velocity 3.75 m/s; velocity resolution 0.1 mm/s; 1 MHz, 4-beam convex Janus;
  300 m depth rating (600 m option) (SNIPPET, distributor pages)
  — [Blueye DVL A50 page](https://www.blueyerobotics.com/products/dvl-a50);
  [Deep Trekker DVL page](https://deeptrekker.com/shop/products/dvl-waterlinked)
- DVLs better than 1.0% accuracy are export controlled, hence the 1.01% standard variant; 0.1% is "survey grade"
  (Nortek staff). Position error from DVL dead reckoning is unbounded over time because velocity errors integrate, but
  grows more slowly than accelerometer-only integration; soft or very jagged bottoms make bottom lock harder.
  — [BR forum: DVL A50 accuracy](https://discuss.bluerobotics.com/t/dvl-a50-accuracy/14873)
- Field reports: position hold engaging but the vehicle running away with the dead-reckoned position drifting; DVL
  velocity readings scattering 5-10 s after arming, causing thrusters to push wildly (SNIPPET)
  — [BR forum: ongoing DVL A50 issues](https://discuss.bluerobotics.com/t/ongoing-dvl-a50-issues/11419);
  [BR forum: position hold not working correctly](https://discuss.bluerobotics.com/t/position-hold-mode-with-waterlinked-dvl-not-working-correctly/13235)
- Positive report: a 4-hour quarry session with the A50 on a BlueROV2 had only two small hiccups (SNIPPET).
  — [BR forum: DVL testing in quarry](https://discuss.bluerobotics.com/t/water-linked-dvl-testing-with-bluerov2-in-quarry/8255)
- Water Linked recommends fusing Underwater GPS (acoustic positioning) with the DVL to bound long-term drift.
  — [Water Linked: BlueROV integration DVL + UGPS](https://waterlinked.github.io/dvl/bluerov-integration-dvl-ugps)
- Cerulean documents the same MAVLink/BlueOS route for position hold with its DVL-75, requiring ArduSub 4.1.1 beta or
  later (SNIPPET) — [Cerulean docs: position hold on a BlueROV2](https://docs.ceruleansonar.com/c/dvl-75/using-mavlink-and-blueos-for-position-hold-on-a-bluerov2)
- Falcon station keeping is a DVL-based option. — [Saab Seaeye Falcon page](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon)

### Inferences
- With +/-1.01% of distance travelled, a vehicle holding station (little distance travelled) drifts slowly; the
  practical accuracy is set by DVL noise and control loop, plausibly decimetre-level, but this is not sourced.
- Simulator behaviour worth modelling: position hold is only available within altitude limits (below ~0.05 m and above
  ~35-50 m no lock), degrades over soft/steep bottoms or in mid-water, and on loss of lock the real system falls back to
  drifting (or misbehaves) rather than holding.

### Gaps
- No measured position-hold accuracy (cm RMS) for BlueROV2 + A50, Nortek Nucleus, or Cerulean DVL-75 was found.
- Nortek and Cerulean altitude ranges and accuracies were not retrieved (Cerulean page redirected and was not re-read).
- Official Water Linked datasheet was not opened; A50 figures above are from distributor pages.

## 8. Real vehicles versus "drone-like" velocity-controlled feel

### Takeaway
By default, real observation-class ROVs are effort-controlled in the horizontal plane: stick means thrust, release means
coast and drift. Closed loops are normally limited to heading, depth (and attitude or altitude); true velocity /
position control exists only with a DVL or similar aiding (ArduSub PosHold/Guided, Falcon station keeping option, vision
"station lock" on FIFISH).

### Cited Findings
- ArduSub Manual: no feedback at all; Stabilize adds heading + level hold; Depth Hold adds depth; horizontal translation
  axes remain direct output in these modes.
  — [ArduSub features while in operation](https://www.ardusub.com/reference/ardusub/features-while-in-operation.html);
  [ArduPilot Sub pilot control](https://ardupilot.org/sub/docs/pilot-control.html)
- Position-referenced modes (POSHOLD, AUTO, GUIDED, CIRCLE) all require a position source; GUIDED accepts
  location or velocity/direction targets from the ground station.
  — [ArduPilot Sub flight modes](https://ardupilot.org/sub/docs/modes.html)
- Falcon: auto heading and depth standard; station keeping "with fine position control", relative waypoints and auto
  speed only as options. — [Falcon brochure rev 18 (2020)](https://www.uniquegroup.com/wp-content/uploads/2022/10/falcon-rev18-s.pdf)
- FIFISH V6 / V6 Expert list an "AI Vision Station Lock" (camera-based) feature (SNIPPET).
  — [QYSEA store FIFISH V6](https://store.qysea.com/fifish-v6.html)
- ArduSub "input hold" is cruise control on stick inputs (holds effort, not speed).
  — [ArduPilot Sub button inputs](https://ardupilot.org/sub/docs/buttons.html)

### Inferences
- Differences a trainee should feel versus an aerial-drone-style velocity controller: (a) releasing the stick does not
  brake actively - the hull stops by drag in ~0.3 m in still water, then drifts at the current speed; (b) steady stick
  gives steady thrust, so ground speed varies with current, tether load and heading; (c) no automatic compensation for
  tether pull, so the vehicle weathervanes and is dragged off station; (d) lateral motion is slower than forward for the
  same stick; (e) reverse thrust is ~20% weaker than forward; (f) only the vertical axis (Depth Hold) and yaw behave
  like rate-commanded axes.
- Mapping to this project's assist levels: assist 0 corresponds to ArduSub Manual/Stabilize/Depth Hold and to a
  non-DVL Falcon; assist 1 and 2 correspond to DVL-aided velocity and position hold (ArduSub PosHold, Falcon station
  keeping option) and should inherit DVL limitations (altitude window, bottom-lock loss, thrust saturation in current).

### Gaps
- Whether VideoRay Defender and Deep Trekker REVOLUTION offer DVL station holding as standard or optional, and how their
  stick response is shaped, was not confirmed from primary sources.
- No source was found that documents commercial small ROVs offering closed-loop horizontal velocity control without a
  DVL or vision aid.
