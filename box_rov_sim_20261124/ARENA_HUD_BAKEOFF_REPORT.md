# `/arena` 3-Candidate HUD & Underwater Scene Bakeoff Report (`ROV-01` `#80`)

## 1. Phase A — Frame & Evaluation Rubric

- **Target Artifact**: `/workspace/rov_sim/box_run/viewer/arena_hud_themes.js` wired into `/workspace/rov_sim/box_run/viewer/wave1_hud.js` (and mirrored to `/workspace/rov_sim/viewer_out/`).
- **Mission Scope**: Provide an industry-grade B2B subsea inspection HUD and an engaging B2C Steam pilot cockpit for the original self-designed **`ROV-01` 3-Layer Sandwich Open-Frame ROV**, supporting live `F2` / HUD Preset Pill switching across all 3 candidate themes (`TACTICAL_SONAR`, `INDUSTRIAL_P260`, `STEAM_DIEGETIC`).
- **Evaluation Rubric (5 Criteria × 10 pts = 50 pts max)**:
  1. **C1 — 6DoF & 6-Thruster Spatial Situational Awareness (10 pts)**: Instant readability of `T1..T6` thrust allocation, resultant horizontal/vertical force vector, and `#EF4444` jammed-thruster sector alerts in dark/turbid water.
  2. **C2 — B2B Subsea Inspection & UT Gauging Telemetry (10 pts)**: Real-time Ultrasonic Thickness (UT) pulse-echo A-scan waveform preview (`mm` thickness + `<3°` perpendicular coupling lock `#22D3EE`/`#F59E0B`/`#10B981`) and tether catenary tension meter (`N` vs `250 N` warning / `2942 N` breaking load).
  3. **C3 — B2C Steam Gameplay Immersion & Time-Trial Pacing (10 pts)**: Diegetic pilot helmet/console bezel, 6-thruster acoustic RPM spectrum bars synced with `rovAudio`, and 4-gate split-timer (`G1..G4`) with Gold medal delta tracking for `M4` Pipeline Time-Trial.
  4. **C4 — Underwater Optical & Post-Processing Realism (10 pts)**: Cohesive coupling between HUD color palette and Three.js water surface/deep fog attenuation, directional/hemisphere lighting, and particulate backscatter without washing out the `ROV-01` 3-layer sandwich mesh (`#F59E0B` syntactic foam, `#1E293B` frame, `#0F172A` pressure hull, `#EA580C` Kort nozzles).
  5. **C5 — Brand-Neutrality (`CORR-ROV-01`) & Runtime Maintainability (10 pts)**: 0 third-party brand tokens, 100% procedural Canvas/CSS rendering (zero external image dependencies), clean state boundary, and deterministic `F2` / pill / API switching.

---

## 2. Phase B & C — Candidate Comparison Table & Cross-Judge Scoring

| Criterion (0–10) | Candidate A: `TACTICAL_SONAR` | Candidate B: `INDUSTRIAL_P260` | Candidate C: `STEAM_DIEGETIC` | **Synthesized Winner (`GRAFTED_v3`)** |
| :--- | :---: | :---: | :---: | :---: |
| **Primary Palette & Optical Mood** | `#22D3EE` Sonar Cyan + `#10B981` Phosphor Green on `#04111D` | `#F59E0B` Safety Amber + `#38BDF8` Calib Cyan on `#0F172A` Slate | `#06B6D4` Neon Aqua + `#FACC15` Speedrun Gold on `#090D16` | **Dynamic Theme Vars + Live `F2` / Pill Switcher** |
| **C1: 6-Thruster Vector & Fault Readability** | **9.6 / 10** *(Best: 6-Axis Hex-Radar + resultant force vector + `#EF4444` sector alert)* | 7.8 / 10 *(Numeric percentage bars only)* | 8.2 / 10 *(RPM acoustic bars, lacks 2D vector direction)* | **9.8 / 10** *(Grafted Candidate A `canvas#arenaHexRadar`)* |
| **C2: B2B UT A-Scan & Tether Catenary Telemetry** | 7.4 / 10 *(Text status only, no waveform oscilloscope)* | **9.7 / 10** *(Best: Live RF envelope UT A-Scan + gate bar + Tether Catenary `N` meter)* | 7.2 / 10 *(Minimal engineering diagnostics)* | **9.8 / 10** *(Grafted Candidate B `canvas#arenaUtAScan` + `#arenaTetherBarFill`)* |
| **C3: B2C Steam Diegetic & Speedrun Engagement** | 8.0 / 10 *(Tactical sonar feel, no gate split-timer)* | 7.5 / 10 *(Pure engineering console)* | **9.6 / 10** *(Best: Chamfered visor corners, RPM spectrum, `G1..G4` Gold split-timer)* | **9.7 / 10** *(Grafted Candidate C `#arenaSplitTimer` + `#arenaRpmSpectrum` + visor)* |
| **C4: Underwater Lighting & Fog Coupling** | 9.1 / 10 *(High-contrast deep-sea scatter, `fogScale: 0.90`)* | **9.3 / 10** *(High-CRI inspection clarity, `fogScale: 1.12`)* | 9.0 / 10 *(Cinematic radial vignette + `fogScale: 1.05`)* | **9.6 / 10** *(Per-preset Three.js `scene.fog` & `scene.background` live lerp)* |
| **C5: `CORR-ROV-01` & Maintainability** | 9.5 / 10 | **9.7 / 10** *(Cleanest non-occluding rack dock layout)* | 9.2 / 10 | **10.0 / 10** *(0 brand hits, single-module `installArenaHudThemes`)* |
| **Total Score (Max 50)** | **43.6 / 50** | **44.0 / 50 (Picked Base)** | **43.2 / 50** | **48.9 / 50 (Shipped Synthesis)** |

---

## 3. Phase D & E — Base Selection & Graft Synthesis

1. **Selected Base Architecture — Candidate B (`INDUSTRIAL_P260`, 44.0/50)**:
   - Selected as the structural base because its side-rack telemetry dock (`#arenaLeftGraft` + `#arenaRightGraft`) leaves the center 3D viewport 100% unobstructed for inspecting the `ROV-01` 3-layer sandwich mesh, tether catenary, and subsea structures.
2. **Graft 1 from Candidate A (`TACTICAL_SONAR`)**:
   - Ported the **6-Thruster Hex-Vector Radar (`drawHexRadar` on `canvas#arenaHexRadar`)** into the left tactical dock, plotting real-time `T1..T6` thrust polygon lobes, the resultant horizontal surge/sway velocity vector arrow, total thrust magnitude in Newtons, and `#EF4444` critical coral sector markers when `T3` (or any thruster) jams.
3. **Graft 2 from Candidate B (`INDUSTRIAL_P260`)**:
   - Ported the **Live Ultrasonic Thickness (UT) A-Scan Waveform Oscilloscope (`drawUtAScan` on `canvas#arenaUtAScan`)** with initial pulse, interface echo, gated backwall echo peak (`measured_mm`), and tri-color coupling status (`#22D3EE` searching / `#F59E0B` aligning / `#10B981` coupled `<3°`), paired with the **Tether Catenary Tension Meter (`#arenaTetherTensionText` & `#arenaTetherBarFill`)** calibrated against the `250 N` warning threshold.
4. **Graft 3 from Candidate C (`STEAM_DIEGETIC_COCKPIT`)**:
   - Ported the **4-Gate Speedrun Split-Timer (`#arenaSplitTimer`, `G1..G4` with `-0.84s GOLD` pace badge)**, the **6-Thruster Acoustic RPM Spectrum (`#arenaRpmSpectrum`)**, and the **Diegetic Visor Corner Reticle & Subtle Radial Vignette (`#arenaDiegeticFrame`)**.
5. **Live Switching (`F2` Hotkey / `#w1ArenaPresetPill` / `#arenaThemeTabs`)**:
   - Pilots and evaluators can press **`F2`**, click the top banner pill (`#w1ArenaPresetPill`), click the `A / B / C` theme tabs, or invoke `window.__wave1.setHudTheme('TACTICAL_SONAR' | 'INDUSTRIAL_P260' | 'STEAM_DIEGETIC')` to switch live between all 3 presets while retaining all grafted telemetry widgets.
