# Thruster-induced silt-out and underwater visibility: physics, numbers, and audit of this repo's silt/visibility model

Scope note: web sources were fetched in full where possible. Items marked **[snippet-only]** come only from search-result summaries. Items marked **[computed]** are my own arithmetic, done with standard formulas in `/tmp/claude-0/-home-user-rov/c18300da-7030-5b94-b1a0-14632023d865/scratchpad/silt_physics.py`. Items marked **[assumption]** are illustrative inputs, not X1 facts. Per AGENTS.md, none of the thruster numbers below are X1 values. The X1 thruster diameter and thrust are unmeasured.

---

## Q1. Thruster wash: jet efflux velocity, decay with distance, velocity at the seabed

### Takeaway
A propeller or thruster jet leaves the disc at V0 ≈ 1.2–1.6·n·D·√Ct. Beyond about 2–3 diameters its centreline velocity decays roughly as 1/x (Fuehrer: 2.6·(x/D)⁻¹; Blaauw: 2.8·(x/D)⁻¹; Verhey: 1.275·(x/D)⁻⁰·⁷). For a small ROV thruster (D ≈ 0.09 m) [assumption], this keeps the jet at 0.1–0.3 m/s 1–3 m from the nozzle. That is enough to erode fluffy fines. A thruster pointed down can therefore disturb soft mud from 2–6 m altitude, not just from contact range.

### Cited Findings
- Efflux velocity formulas (Kadir et al. 2024, which compiles the literature) — [JMSA 2024, Ship propeller rotation threshold](https://html.rhhz.net/jmsa/html/20240408.htm):
  - Fuehrer et al. (1987): V0 = 1.59·n·Dp·√Ct
  - Hamill (1988): V0 = 1.33·n·Dp·√Ct
  - Hamill, Kee & Ryan (2015): V0 = 1.22·n^1.01·Dp^0.84·Ct^0.62
  - Stewart and Hashmi variants add pitch ratio, blade-area ratio and hub-ratio terms.
- Axial decay laws Vmax/V0 from the same source:
  - Fuehrer (1987): 2.6·(x/D)⁻¹
  - Blaauw & van de Kaa (1978): 2.8·(x/D)⁻¹
  - Verhey (1983): 1.275·(x/D)⁻⁰·⁷ for x/D > 1.5
  - Berger (1981): 1.025·(x/D)⁻⁰·⁶
  - Hashmi (1993): 0.638·exp(−0.097·x/D)
  - Linear near-field fits, for example Lam 2011: 1 − 0.1592·x/D
  - Radial profiles are Gaussian: Fuehrer exp[−22.2(r/x)²]; Blaauw exp[−15.4(r/x)²] — [JMSA 2024](https://html.rhhz.net/jmsa/html/20240408.htm)
- Efflux velocity is defined at the outlet. The zone of flow establishment ends near x ≈ 2.5·Dp. Hamill & McGarvey say their bed-velocity equations inherit an efflux equation "found to be up to 20% in error". The only empirical maximum-bed-velocity equation cited is Fuehrer et al. (1981), for twin-screw ships — [ICCE paper](https://icce-ojs-tamu.tdl.org/icce/article/download/5867/5535/24336) **[snippet-only]**
- Full-scale example (Dp = 1.5 m): at 230 rpm, measured velocity was 4, 2.5, 2 and 1.5 m/s at 0.5, 1.0, 1.5 and 2.0·Dp below the propeller. "Safe from erosion" clearance grew from Dp at 75 rpm to 2·Dp at 230 rpm — [JMSA 2024](https://html.rhhz.net/jmsa/html/20240408.htm)
- Small-thruster wake: a 2026 lab study of an 8-thruster ROV measured axial wake velocities of about 5–60 cm/s at 0.1–0.5 m from a thruster centre with PIV. The study modelled
  - velocity ∝ √(T/(ρ·A_prop)) · (r_ref/r)²
  - a cos⁴θ angular weighting, cut off at a 45° half-angle, beyond which velocity is below 10 % of the axial peak

  The model gave R² = 0.99 in the core (|θ| < 15°, r < 0.3 m) and 0.82 out to 30°. It overestimates at r > 0.4 m — [Gao et al. 2026, arXiv:2607.07139](https://arxiv.org/pdf/2607.07139)
- The same study's disturbance-aware thrust allocation cut target-surface particle velocity from 0.18 ± 0.05 m/s to 0.06 ± 0.02 m/s while hovering 0.20 m above a coral target in a 0.3 m/s flow. 3D-reconstruction RMSE fell from 8.7 to 1.9 mm. Their Fig. 7 shows "progressive water disturbance" over 0, 5 and 10 s under manual control — [Gao et al. 2026](https://arxiv.org/pdf/2607.07139)

### Inferences
- **[computed, assumption: D = 0.09 m, ρ = 1025 kg/m³, momentum efflux T = ρ·A·V0²]** Efflux V0 and Fuehrer / Verhey Vmax by distance:

  | Thrust | V0 | 0.5 m | 1 m | 2 m | 3 m | 5 m |
  |---|---|---|---|---|---|---|
  | 5 N | 0.88 m/s | 0.41 / 0.34 | 0.20 / 0.21 | 0.10 / 0.13 | — | — |
  | 10 N | 1.24 m/s | 0.58 / 0.48 | 0.29 / 0.29 | 0.14 / 0.18 | 0.10 / 0.14 | — |
  | 50 N | 2.77 m/s | 1.30 / 1.06 | 0.65 / 0.65 | 0.32 / 0.40 | 0.22 / 0.30 | 0.13 / 0.21 |

- **[computed]** Distance at which Fuehrer Vmax falls to a critical velocity U_c:

  | Thrust | U_c = 0.1 m/s | U_c = 0.2 m/s | U_c = 0.4 m/s |
  |---|---|---|---|
  | 5 N | 2.0 m | 1.0 m | — |
  | 10 N | 2.9 m | 1.5 m | 0.7 m |
  | 25 N | 4.6 m | 2.3 m | 1.2 m |
  | 50 N | 6.5 m | 3.2 m | 1.6 m |

  So the danger altitude scales with √T, not as a fixed 1.7 m cutoff. This is a free-jet estimate. Real bed velocity on impingement turns into a radial wall jet, and the extra decay is not quantified here.
- **[computed]** A horizontal (forward/aft) thruster jet spreads with a Gaussian 1/e half-width of about 0.21·x (Fuehrer). Its edge reaches a bed at altitude h after roughly x ≈ h/0.21 to h/0.3, which is about 3–5 m downstream for h = 1 m. Horizontal thrusters therefore also raise silt behind the vehicle, delayed and weaker.
- Thrust direction matters more than mean thrust level. The VideoRay guidance in Q5 (thrusting up near the bottom stirs more than thrusting down) is consistent with up-thrust jets pointing at the bed.

### Gaps
- No primary source found that measures bed velocity under a small ROV thruster (50–100 mm prop, 10–100 N) versus altitude. Liao, Wang & Wang 2015 ("In situ measurement of sediment resuspension caused by propeller wash with underwater PIV and ADV", Flow Meas. Instrum. 41:1–9) is cited by Gao et al. but was not read.
- Ct, n and D for the X1 thrusters are unknown. These belong in `x1-measurement-checklist.md`.
- PIANC propeller-wash guideline values were not retrieved.

---

## Q2. Erosion thresholds: critical shear stress and velocity for mud, silt and fine sand

### Takeaway
Non-cohesive silt and fine sand start moving at τ_cr ≈ 0.04–0.16 Pa (Soulsby–Shields). Consolidated mud and mud–sand beds need about 0.2–1.3 Pa. Freshly deposited fluff erodes far more easily than either. With a wall-jet friction coefficient Cf ≈ 0.003–0.01, 0.1 Pa corresponds to only about 0.1–0.2 m/s near-bed velocity.

### Cited Findings
- Van Rijn critical Shields parameter: θcr = 0.115·D*⁻⁰·⁵ for D* < 4, and 0.14·D*⁻⁰·⁶⁴ for 4 ≤ D* < 10, with D* = d·[g(s−1)/ν²]^(1/3). Erosion occurs when θ > θcr — [JMSA 2024](https://html.rhhz.net/jmsa/html/20240408.htm)
- Soulsby correlation: τ*_cr = 0.30/(1 + 1.2·d*) + …; the second term was truncated in the snippet. Stokes settling: ws = (s−1)·g·d²/(18ν) — [Apsley, Manchester sediment examples](https://personalpages.manchester.ac.uk/staff/david.d.apsley/lectures/hydraulics3/SedimentExamples.pdf) **[snippet-only]**
- Mud–sand beds: critical bed-shear stress is about 0.25–1.3 N/m², depending on bed density and mud fraction — [van Rijn 2017 SedNet poster](https://sednet.org/wp-content/uploads/2017/07/2017-poster8-LCvanRijn.pdf) **[snippet-only]**
- Sand with 36–60 % silt eroded in two stages, at 0.18–0.74 Pa and 1.00–1.23 Pa. Adding silt to pure sand raised τ_cr by about an order of magnitude — [TU Delft repository](https://repository.tudelft.nl/file/File_7b3a54ed-d852-4aa4-ab47-7e8cadff6a24?preview=1) **[snippet-only]**
- Grain classes and cohesion: clay is below 4 µm; fines (silt plus clay) are below 63 µm. Beds with less than 5–10 % clay behave roughly non-cohesively. Cohesive beds have separate erosion and deposition thresholds, τ_cr,sed < τ_cr,er — [Bosboom & Stive, Coastal Dynamics §6.8.2](https://geo.libretexts.org/Bookshelves/Oceanography/Coastal_Dynamics_(Bosboom_and_Stive)/06%3A_Sediment_transport/6.08%3A_Some_aspects_of_(very)_fine_sediment_transport/6.8.2%3A_Critical_shear_stress_and_settling_velocity)

### Inferences
- **[computed with the full Soulsby (1997) form, θcr = 0.30/(1+1.2D*) + 0.055(1−e^(−0.02D*)), quartz, seawater]**:

  | Grain size d | τ_cr |
  |---|---|
  | 10 µm | 0.037 Pa |
  | 20 µm | 0.061 Pa |
  | 40 µm | 0.089 Pa |
  | 63 µm | 0.108 Pa |
  | 100 µm | 0.127 Pa |
  | 200 µm | 0.157 Pa |

  Below about 63 µm, cohesion makes these lower bounds for consolidated mud, but realistic for a loose fluff layer.
- **[computed]** Bed shear τ = ρ·Cf·U², with Cf assumed in 0.003–0.01:

  | Near-bed U | τ |
  |---|---|
  | 0.1 m/s | 0.03–0.10 Pa |
  | 0.2 m/s | 0.12–0.41 Pa |
  | 0.3 m/s | 0.28–0.92 Pa |
  | 0.5 m/s | 0.77–2.6 Pa |

- Suggested simulator seabed classes [assumption, to be validated]:

  | Class | τ_cr | Silt-out risk |
  |---|---|---|
  | `fluff` | 0.03–0.08 Pa | High |
  | `silt` / `mud` | 0.1–0.4 Pa | Medium |
  | `fine sand` | about 0.15 Pa | Erodes, but settles in seconds, so produces a short burst, not a lasting cloud |
  | `gravel` / `rock` / `reef` | — | Essentially none |

### Gaps
- No authoritative number found for the erosion threshold of freshly settled organic fluff. The 0.03–0.08 Pa class above is an extrapolation from the Soulsby curve.
- Wall-jet Cf for an impinging thruster jet was not sourced.

---

## Q3. Plume behaviour: settling, how long fines stay suspended, advection, diffusion, height

### Takeaway
Fine silt (≤ 20 µm) settles at ≤ 0.3 mm/s, so a cloud 1–2 m thick takes about an hour to settle out. Clay takes days. In practice, visibility at the work site returns when the current carries the cloud away (tens of seconds to minutes at 0.1–0.5 m/s) or when flocs settle, not when grains settle individually. Plumes stay low: the highest concentrations are about 1 m above the bed.

### Cited Findings
- A 10 µm silt particle settles at about 0.1 mm/s in still water. Flocs are heavier and settle faster, but their larger size raises drag and can lead to break-up (deflocculation) — [Bosboom & Stive §6.8.2](https://geo.libretexts.org/Bookshelves/Oceanography/Coastal_Dynamics_(Bosboom_and_Stive)/06%3A_Sediment_transport/6.08%3A_Some_aspects_of_(very)_fine_sediment_transport/6.8.2%3A_Critical_shear_stress_and_settling_velocity)
- Deep-sea mining plume monitoring found most of the plume close to the seafloor. The highest concentrations were at the 1 m monitoring altitude, and background was reached at 50 m — [Sci. Rep. 2020 (s41598-020-61837-y)](https://eprints.soton.ac.uk/439733/1/s41598_020_61837_y_1_.pdf) **[snippet-only]**
- A dense suspension can behave as a gravity current: behind a nodule collector at 4,500 m it ran downslope for up to 500 m — [GEOMAR news](https://www.geomar.de/n9781) **[snippet-only]**
- Mining-plume modelling found most released sediment re-settled within about a day of the disturbance ending. Flocculation is a key control on spread — [Purkiani et al. 2021, Front. Mar. Sci.](https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2021.719463/pdf) **[snippet-only]**

### Inferences
- **[computed]** Settling velocity (Soulsby) and time to fall 1 m:

  | Grain size | Class | Settling velocity | Time to fall 1 m |
  |---|---|---|---|
  | 2 µm | clay | 0.003 mm/s | about 4 days |
  | 4 µm | — | 0.012 mm/s | about 23 h |
  | 10 µm | — | 0.075 mm/s | 3.7 h |
  | 20 µm | — | 0.30 mm/s | 56 min |
  | 40 µm | — | 1.2 mm/s | 14 min |
  | 63 µm | — | 2.95 mm/s | 5.6 min |
  | 100 µm | — | 7.3 mm/s | 2.3 min |
  | 200 µm | fine sand | 24 mm/s | 41 s |

- A real silt-out is therefore **bimodal**:
  - A sand fraction falls back within seconds to a minute.
  - A silt and clay fraction hangs for minutes to hours and leaves only by advection or floc settling.
- **[computed]** Clearing by advection: a plume of along-current size L passes a fixed camera in about L/U plus a diffusion tail. For L = 3–5 m, that is about 6–10 s at 0.5 m/s, 30–50 s at 0.1 m/s, and minutes or longer in slack water.
- Plume rise height above the bed should scale with impingement velocity and jet geometry. The Sci. Rep. altitude profile suggests most of the concentration sits below about 1–2 m in the absence of strong vertical jets.

### Gaps
- No measured floc settling velocities for coastal mud were found in fetched sources.
- No measured turbulent-diffusivity or spread rates for small-thruster plumes were found.
- No primary measurement of how long an ROV-induced cloud persists.

---

## Q4. Visibility versus concentration: SSC → beam attenuation c → visibility; backscatter

### Takeaway
Horizontal visibility of a black target is y ≈ 4.8/c(photopic or 550 nm), to within about 10 %. Particulate attenuation c_p = c*_p·SSC, with c*_p between 0.05 and 1.5 m²/g. The typical coastal value is about 0.5 m²/g. Visibility therefore falls hyperbolically with concentration: about 8 m at 1 mg/L, about 1 m at 10 mg/L, and about 0.1 m at 100 mg/L. Turbidity in NTU is only a weak proxy.

### Cited Findings
- Visibility of a black target: range = −(1/c)·ln|C_L|. The slope of visibility range against photopic c "was found to be 4.8", predicting visibility "to an accuracy of 8%". Zaneveld proposes y = 4.8/c as the standard, with c(532) or a 528 nm transmissometer as a near-substitute — [Zaneveld & Pegau 2003, Opt. Express](https://misclab.umeoce.maine.edu/ftp/classes/OO2017/readings/Zaneveld_visibility_OX2003.pdf) (full text extracted)
- Davies-Colley (1988) tested the black-disk method across 11 rivers and 8 lakes spanning a 60-fold clarity range — [scilit record](https://scilit.com/publications/6b00d2e88a2560dd79a445127c55da17) **[snippet-only]**
- NZ national reporting uses y_BD = 4.8/c(550) and prefers it over Secchi depth, which depends on lighting — [NZ MfE 9.12](https://environment.govt.nz/assets/publications/Environmental-Reporting/9.12-Suspended-sediment-water-clarity-turbidity.pdf) **[snippet-only; fetch failed]**
- Turbidity and visual clarity relate poorly for general use: sites with equal NTU can differ widely in clarity (Davies-Colley & Smith 2001) — [NALMS black disk article](https://www.nalms.org/secchidipin/monitoring-methods/the-black-disk-a-different-approach-to-measuring-water-clarity/) **[snippet-only]**
- The 4.8/c relation underestimates visibility in very turbid water. A modified theory that includes K_d fits better — [Bowers et al., core.ac.uk](https://core.ac.uk/download/322526368.pdf) **[snippet-only]**
- Mass-specific attenuation (Neukermans et al. 2012, L&O 57:124–144; full text extracted):
  - c*_p = c_p/[SPM] in the literature ranges "from 0.05 m² g⁻¹ to 1.5 m² g⁻¹". It varies about tenfold and is 77 % explained by particle apparent density.
  - Mass-specific scattering is about 0.5 m²/g in coastal waters versus about 1 m²/g in the open ocean (Babin 2003).
  - Mass-specific backscattering is 0.012 m²/g for inorganic and 0.005 m²/g for organic particles.

  [Neukermans et al. 2012 PDF](https://www.vliz.be/imisdocs/publications/ocrd/229784.pdf)
- Backscatter from the vehicle's own lights is the dominant near-field degradation. Deep Trekker tells users to dim or switch off lights in turbid water. These are cited in the repo's own research report — `docs/reference/real-rov-research.md:43`

### Inferences
- **[computed; c_w ≈ 0.07 m⁻¹ assumed for water at 550 nm]** Visibility y = 4.8/(c_w + c*_p·SSC), with c*_p = 0.5 m²/g; the bracket is c*_p from 1.5 to 0.05:

  | SSC | Visibility | Range |
  |---|---|---|
  | 0.5 mg/L | 15 m | 5.9–51 m |
  | 1 mg/L | 8.4 m | 3.1–40 m |
  | 2 mg/L | 4.5 m | — |
  | 5 mg/L | 1.9 m | — |
  | 10 mg/L | 0.95 m | — |
  | 20 mg/L | 0.48 m | — |
  | 50 mg/L | 0.19 m | — |
  | 100 mg/L | 0.10 m | — |
  | 500 mg/L | 0.02 m | — |

  A few tens of mg/L, easily reached in a thruster plume over mud, gives "functional zero" visibility. The scale is hyperbolic, so adding sediment to an already murky scene costs proportionally less.
- Contrast physics is exponential: C(y) = C0·e^(−c·y), with visibility where |C| reaches about 0.008 (e^−4.8). A renderer should use exponential fog with density ≈ c = 4.8/visibility, not linear fog.
- With artificial light, backscatter adds a veiling luminance roughly proportional to b_p and to lamp power and proximity. A silt cloud should therefore raise both fog density and fog brightness near the lights, with the colour tinted toward the lamp's colour.

### Gaps
- Direct NTU → c conversion was not sourced; it is instrument-dependent.
- No sourced table of camera (as opposed to human-eye) visibility versus c. Camera dynamic range and lighting geometry change the effective limiting contrast.

---

## Q5. Natural turbidity: typical visibilities, nepheloid layers, thermocline haze, tide and weather

### Takeaway
Visibility in harbours and coastal water changes over metres, and is worst near the bottom. Bottom nepheloid (turbid) layers several metres to tens of metres thick are normal over mud. Blooms can drop coastal visibility below 3 m. A site therefore needs a vertical turbidity profile, not one `visibility_m` number.

### Cited Findings
- In harbour and coastal regions, visibility and attenuation "can change rapidly over small scales (meters), especially near the bottom". Turbid bottom layers are common — [SPIE 9878 abstract](https://proceedings.spiedigitallibrary.org/conference-proceedings-of-spie/9878/98781I/Preliminary-results-of-algorithms-to-determine-horizontal-and-vertical-underwater/10.1117/12.2238595.full) **[snippet-only]**
- Bottom nepheloid layer (BNL) thickness:
  - South Texas shelf: thickest over muddy substrate, up to 35 m — [USGS](https://pubs.usgs.gov/publication/70012139) **[snippet-only]**
  - Ebro shelf: bottom boundary layer 3–9 m thick (up to 12 m) at stations deeper than 20 m, with maximum concentration over the mid-shelf mud belt — [Sci. Mar.](https://scientiamarina.revistas.csic.es/index.php/scientiamarina/article/download/1371/1472/1447) **[snippet-only]**
- BNL thickness scales with bottom current via k·u*/f. Detached turbid layers spread laterally (McCave) — [Oceanography 17-2, Agrawal](https://tos.org/oceanography/assets/docs/17-2_agrawal.pdf) **[snippet-only]**
- In the northern South China Sea, internal waves with vertical velocity up to 0.5 m/s resuspended sediment to about 10 m above the bed — [bohrium/arXiv summary](https://bohrium.dp.tech/paper/arxiv/89ff8f1e6ea17c85e14554c8afce44b4cfd27258721e502a40ad23f4e7dba158) **[snippet-only]**
- Strong BNLs occur where eddy kinetic energy and near-bottom dissipation are high (global comparison, 1964–2016) — [ESSOAr preprint](https://essopenarchive.org/doi/full/10.1002/essoar.10500860.1) **[snippet-only, preprint]**
- Spring algae blooms can cut coastal US visibility to below 10 ft (3 m) — [Dive Training magazine](https://dtmag.com/thelibrary/visibility-illuminating-facts-unclear-situation/) **[snippet-only, trade press]**
- In Kaipara Harbour sub-estuaries, clarity variability was mostly explained by TSS — [BL record](https://eld.bl.uk/catalog/100078893656_0x000001) **[snippet-only]**

### Inferences
- Scenario values in the repo are plausible as surface-to-mid-water visibility: harbour 7 m, reef 18 m, incident 1–4 m (`simulator/qysim/scenarios.py:273-309`). They lack a near-bed degradation layer, and they do not vary with tide or current.
- A cheap model is c(z) = c_bg + Δc_BNL·exp(−h_above_bed/H_BNL), with H_BNL of about 1–10 m [assumption], and Δc_BNL scaled with current speed relative to a threshold.

### Gaps
- No sourced table of typical visibility in metres by water type (harbour, estuary, coastal, offshore) was retrieved. Jerlov and Zaneveld figures exist but were not extracted.
- Thermocline haze was not sourced.
- Quantitative tide and spring-neap modulation of near-bed turbidity was not sourced.

---

## Q6. Operational practice for avoiding silt-outs, and recovery times

### Takeaway
Pilots move slowly, keep slightly positive buoyancy so they apply small down-thrust rather than up-thrust near the bed, avoid thrusting at silted surfaces, hold an up-current heading, and wait or climb when visibility collapses. Sonar keeps working through a silt-out. No source gives typical waiting times.

### Cited Findings
- Silt-out is defined as "visibility rapidly reduced to functional zero by disturbing fine particulate deposits". Causes are thrust towards the bottom or a silted surface, and turbulence from vehicle motion. Cameras become ineffective but sonar keeps working — [Wikipedia: Silt out](https://en.wikipedia.org/wiki/Silt_out)
- VideoRay advises ballasting slightly positive. Near the bottom, "slight vertical down thrust … is less likely to stir up the bottom than having to thrust up to keep the ROV from settling" — [VideoRay Pro 4: Piloting in deep water](https://download.videoray.com/documentation/pro_4/html/pilot_deep.html) **[snippet-only]**
- In confined spaces, move slowly and deliberately to avoid stirring silt — [VideoRay MSS: Piloting in confined spaces](https://download.videoray.com/documentation/mss/html/pilot_confined.html) **[snippet-only]**
- In current: back up to create tether slack, then rotate and thrust to set an up-current heading — [VideoRay MSS: Piloting in swift current](https://download.videoray.com/documentation/mss/html/pilot_current.html) **[snippet-only]**
- MBARI, 2013: a natural turbidity current forced repeated aborted descents. The vehicle landed about an hour later, after the flow abated — [phys.org](https://phys.org/news/2015-03-deep-sea-robot-caught-underwater-avalanche.pdf) **[snippet-only]**
- Gao et al. 2026 cite Liu et al. as qualitative evidence that thruster wakes hit sediment, and recommend avoiding downward-facing thrusters near sediment — [arXiv:2607.07139](https://arxiv.org/pdf/2607.07139)

### Inferences
- Training-relevant behaviours the simulator should reward or punish:
  - Altitude discipline.
  - Using lateral or forward thrusters rather than vertical thrusters near the bed.
  - Low-gain "cine" control near the bed.
  - Approaching from down-current, so the vehicle faces up-current and the plume drifts behind it.
  - Climbing above the plume, or backing out up-current, to recover.
  - Switching to sonar or the altimeter.
  - Dimming lights in turbid water.

### Gaps
- No sourced operational rule of thumb for minimum altitude or how long to wait after a silt-out. The X1 measurement checklist could record this: hover at 0.5, 1 and 2 m over the real site and time recovery of camera contrast.

---

## Q7 (Part B). How this repository models silt and visibility, with measured behaviour

### Takeaway
The silt model is a game-style proxy, not a physical one:
- **Source:** up to 24 Gaussian "clouds", spawned at the vehicle centre whenever altitude is under 1.7 m and mean |thrust| is above 15 %, regardless of altitude below that cutoff, thrust direction or seabed type.
- **Decay:** each cloud decays with a fixed 9 s time constant and is deleted at 35 s.
- **Rendering:** the result scales one scene-wide linear fog distance by (1 − 0.75·silt), so a full silt-out still leaves 25 % of nominal visibility.
- **Timing:** measured, a full silt-out forms in about 3 s and clears about 21 s after thrust stops, even in still water. Real fine silt in slack water should take minutes to hours.

### Cited Findings (repo, file:line)
- Contact-driven silt:
  - A scalar `World.silt` is set on seabed contact: `self.silt = min(1.0, self.silt + 0.3 + speed)` at `simulator/qysim/world.py:449`. It decays at `dt/25` at `world.py:535`.
  - Contact also emits a cloud: `emit_silt(pos, .3 + speed, …)` at `world.py:450`.
  - The scalar `World.silt` is never exported. State uses `silt_at()` (`engine.py:789`, `server.py:275`), so the scalar is dead state.
- `emit_silt` (`world.py:514-520`):
  - Rate-limited to one cloud per source per 0.35 s.
  - Initial radius 0.8 m; strength capped at 1.
  - At most 24 clouds kept (`self.silt_clouds[-24:]`).
  - Spawn position is the vehicle centre, not the seabed.
- `silt_at` (`world.py:522-525`) is the sum of `strength·exp(−|p−c|²/(2r²))`, clamped to 1. It is a dimensionless 0..1 index, not a concentration.
- Cloud evolution, every 0.1 s (`world.py:540-547`):
  - Advected by the local current.
  - Sinks at 0.025 m/s (z is depth-positive), clamped at the seabed.
  - Radius grows at 0.09 m/s.
  - Strength multiplies by exp(−dt/9).
  - Removed when strength < 0.015 or age ≥ 35 s.
  - Strength decay is independent of growth, so the integrated "mass" (strength·r³) is not conserved.
- Thruster source (`world.py:548-552`): `if self.seabed_at(p) - p[2] < 1.7 and thrust > .15: self.emit_silt(p, thrust * .4, …)`. This is a step function of altitude (vehicle centre to bed) and independent of seabed type.
- Thrust input:
  - The room passes `thrust = mean(|thrust_i|)/thruster_max`, which ignores thruster direction and whether the jet points at the bed (`simulator/qysim/room.py:200-201`).
  - The single-vehicle `Simulator.step` path passes no `thrust` key (`simulator/qysim/engine.py:204`), so thruster-induced silt never occurs there. The server uses `Room.step` (`server.py:225`), so live play is unaffected; standalone or test use is.
- Scenario base visibility is a static `visibility_m` per scenario (`simulator/qysim/scenarios.py:56`). Examples: reef 18, harbour 7, the silt incident 1, the wreck 4 (`scenarios.py:273-358`).
- The silt incident is a static 1 m visibility, not generated silt: `incident_silt` sets `visibility_m=1` (`scenarios.py:355-363`, brief at `:321`).
- Instructor `visibility` injection scales `visibility_m` by (1 − strength), with a 0.1 m floor (`simulator/qysim/instructor.py:74-117`; `PROTOCOL.md:326-332`).
- Viewer fog (`simulator/viewer/app.js:63`, `1210-1219`):
  - Fog type: `THREE.Fog` (linear).
  - Fog distances: `vis = visibility_m*(1 − .75*silt)`, `fog.near = .3`, `fog.far = vis*1.35`.
  - Colour: water colour lerps toward `siltCol #3b3a26` by `silt*0.7`.
  - Silt source: `S.silt`, the value at the vehicle position, applied to the whole scene even in third-person camera.
- The observation-camera range uses the same formula (`simulator/viewer/observation_camera.js:79`).
- The `environment.silt_clouds` list is sent in state (`world.py:530`, `PROTOCOL.md:78`), but no viewer module renders it. Grep for `silt_clouds` in `simulator/viewer` returns nothing; `environment.js:511` only reads `fish_schools`. There is no volumetric or particle silt cloud.
- The SDK mock renderer (`simulator/sdk_mock/qysea/sdk/_render.py:188-208`, `272`) uses the same `vis*(1−0.75 silt)` with a 0.5 m floor. Silt increases LED backscatter by a factor of (1 + 3·silt) and adds particles. This is the only place silt couples to lighting backscatter. The viewer does not.
- The expedition photo check refuses photos when `silt_at(pos) > .75` (`simulator/qysim/expedition.py:347`). Its range check uses unreduced `visibility_m` (`:341`).
- Tests cover only locality, advection and expiry (`simulator/tests/test_ecology.py:95-106`).
- The repo's own research report states that particle size, density, drift and settling time have "no quantitative source" (`docs/reference/real-rov-research.md:43`).

### Measured behaviour (script: `/tmp/claude-0/-home-user-rov/c18300da-7030-5b94-b1a0-14632023d865/scratchpad/silt_char.py`, driving `World.step` at dt = 0.01 s, seabed 12 m, turbulence 0)
- **Altitude response** is a step function. For altitudes of 0.5, 1.0 and 1.6 m the result is identical: thrust 0.2 gives silt 0.23 at 1 s, 0.80 at 5 s, and 1.0 by 10 s. At 1.8 m and 3.0 m, nothing happens at any thrust.
- **Thrust response:**
  - Thrust 0.1 gives no silt at any altitude.
  - Thrust 0.5 gives silt 0.57 at 1 s and 1.0 at 3 s.
  - Thrust 1.0 gives silt 1.0 at 1 s.
- **Build-up and clearing** (altitude 1 m, thrust 0.5 for 20 s, no current, base visibility 8 m):

  | Time | Silt | Visibility |
  |---|---|---|
  | 0 s | 0 | 8.0 m |
  | 1 s | 0.57 | 4.6 m |
  | 2 s | 0.89 | 2.7 m |
  | 3–25 s | 1.0 | 2.0 m (floor) |
  | 30 s | 0.95 | — |
  | 40 s | 0.14 | 7.2 m |
  | 50 s | 0 | — |

  Silt drops below 0.1 about 21 s after thrust stops. The 24-cloud cap is reached at about 10 s.
- **With 0.5 kn current:** the same run reads 0.75 at 25 s, 0.33 at 30 s and 0.05 at 40 s. Current shortens recovery only modestly, because the clouds die from the 9 s exponential and 35 s age limit anyway.
- **Single cloud, strength 1, in still water:**

  | Time | Silt at centre | Radius |
  |---|---|---|
  | 0 s | 1.0 | 0.8 m |
  | 5 s | 0.57 | — |
  | 10 s | 0.33 | 1.7 m |
  | 20 s | 0.11 | 2.6 m |
  | 30 s | 0.035 | 3.5 m |
  | 35 s | gone | — |

  The cloud sinks 0.75 m in 30 s.
- **Spatial footprint** of a fresh cloud of strength 0.2: 100 % at 0 m, 83 % at 0.5 m, 46 % at 1 m, 4.5 % at 2 m, 0 at 3 m.
- **Contact scalar** `World.silt`: from 0.5 it reaches 0 in 12.5 s. It is unused anyway.

### Inferences
- Formation speed (seconds) is roughly realistic for a thruster over mud. The source law (step at 1.7 m, direction-blind) and the clearing law (about 20 s, deterministic decay, no settling physics) are not.
- The 25 % visibility floor contradicts "functional zero" silt-outs (Wikipedia; Q4 numbers). The linear fog with `far = 1.35·vis` lets objects remain partly visible beyond the nominal visibility. Exponential fog would make contrast at y = vis about e^−4.8 ≈ 0.8 %, versus about 26 % residual in the current linear setup [computed: (vis−0.3)/(1.35·vis−0.3) ≈ 0.74 fog factor].

### Gaps
- Browser rendering was not run; this audit reads code only for the viewer path.

---

## Q8 (Part C). Ranked gaps, suggested models, and validation targets

### Takeaway
In order of training impact:
1. Replace the 1.7 m step source with a jet-impingement source driven by thrust direction and altitude, with a seabed-type threshold.
2. Replace the 9 s exponential decay with settling by size class plus advection, so slack-water silt-outs last minutes.
3. Map concentration to exponential fog, with no 25 % floor and with light-dependent backscatter.
4. Render the clouds that already exist in state.
5. Add a near-bed nepheloid layer per site.

All of these stay inside the physics and presentation layers and are additive to the protocol.

### Cited Findings
(Evidence for each gap is in Q1–Q7 above. Repo lines are cited there.)

### Inferences — ranked gaps

1. **Source term ignores jet physics and direction (high).**
   - Current behaviour (`world.py:548-552`, `room.py:200-201`): a binary 1.7 m altitude test on mean |thrust|.
   - Model: for each thruster i, take thrust T_i, axis n_i and position x_i. Find where the axis or cone (half-angle about 12–15°, Fuehrer exp[−22.2(r/x)²]) meets the seabed at distance x_b. Then:
     - V0 = √(T_i/(ρ·A_i))
     - U_b = V0·min(1, 2.6·D/x_b)·g(θ)
     - τ_b = ρ·Cf·U_b²
     - Erosion flux E = M·max(0, τ_b/τ_cr − 1), with a Partheniades-type erosion constant M [assumption].
   - Spawn mass at the impingement point on the seabed, not at the vehicle centre.
   - Include contact or skid erosion, which already exists.
   - Validation targets:
     - With D = 0.09 m and τ_cr = 0.1 Pa (U_c ≈ 0.1–0.2 m/s), the onset altitude for vertical down-thrust should be about 1 m at 5 N, 1.5–3 m at 10 N, and 3–6.5 m at 50 N (Q1 table).
     - Pure horizontal thrust at 1 m altitude should raise silt 3–5 m behind the vehicle.
     - Up-thrust (jet toward the bed) should raise more silt than down-thrust, per VideoRay.
     - X1 values need `x1-measurement-checklist.md` entries for thruster D, thrust and nozzle orientation.

2. **Clearing is too fast and not physical (high).**
   - Current behaviour (`world.py:540-547`): strength decays with a 9 s time constant, ages out at 35 s, sinks at 2.5 cm/s.
   - Model: carry 2–3 size classes per cloud, each with its own settling velocity:
     - sand: 100–200 µm, 7–25 mm/s
     - coarse silt / flocs: 0.5–1 mm/s [assumption for flocs]
     - fine silt / clay: 0.01–0.1 mm/s
   - Conserve mass. Spread by Gaussian puff diffusion (σ² = σ0² + 2·K·t, with K about 10⁻³–10⁻² m²/s [assumption]). Advect with the near-bed current. Remove mass by deposition at the bed (flux = ws·C), not by exponential decay.
   - Raise the cap above 24 puffs, or merge puffs.
   - Validation targets:
     - In slack water, a fine-silt cloud from a 10 s burst should keep visibility below 50 % of base for at least 5–10 min.
     - At 0.25–0.5 m/s current, the site should clear within about L/U + 10–30 s.
     - Sand-only beds should clear within about 1 min.

3. **Visibility mapping is wrong in shape and has a floor (high).**
   - Current behaviour (`app.js:1217-1219`, `_render.py:189`, `observation_camera.js:79`): `vis·(1−0.75·silt)`, linear fog, `far = 1.35·vis`.
   - Model: represent silt as concentration C (mg/L).
     - c = 4.8/visibility_m(base) + c*_p·C, with c*_p ≈ 0.5 m²/g (range 0.05–1.5).
     - Effective visibility = 4.8/c.
     - Use `THREE.FogExp2` with density chosen so exp(−d·y) matches exp(−c·y). Note FogExp2 uses exp(−(d·y)²), so a custom fog chunk or an approximation is needed.
   - Remove the 25 % floor. Keep the scalar `silt` 0..1 in state, and add an optional `turbidity` field (c or mg/L) per AGENTS.md compatibility rules.
   - Validation targets: 1 mg/L → about 8 m, 10 mg/L → about 1 m, 50 mg/L → about 0.2 m (Q4 table). A black object at the stated visibility should have about 1 % contrast.

4. **Lights do not interact with silt in the viewer (medium-high).**
   - The SDK renderer couples LED backscatter to silt (`_render.py:208`); the viewer does not.
   - Model: veil luminance ∝ lamp power × b_p (∝ C) × proximity term, so in turbid water a lower light level gives a better image (Deep Trekker; `real-rov-research.md:43`). This is the training point "dim the lights in silt".
   - Validation: at C = 10 mg/L, maximum LED should look worse than about 30–50 % LED in image contrast. This needs footage from X1 for a target.

5. **Silt clouds are not rendered (medium).**
   - `environment.silt_clouds` is in state (`world.py:530`) but unused by the viewer.
   - The fog uses silt at the vehicle position (`S.silt`) for the whole scene, so in third person a camera outside the cloud wrongly sees fog, and the cloud cannot be seen from outside.
   - Model: a front-end presentation module that draws billboard or volume puffs from `silt_clouds`, and samples the cloud field at the camera position for fog. It is a new module per AGENTS.md rule 3.
   - Validation: from a third-person view up-current, the plume should be visible drifting away.

6. **No near-bed nepheloid layer, tide or current dependence (medium).**
   - `visibility_m` is a single static number per scenario (`scenarios.py:56`).
   - Model: add optional scenario fields `bnl_height_m` and `bnl_delta_c`; c(z) = c_bg + Δc·exp(−h/H). Optionally scale Δc with near-bed current above a threshold.
   - Validation: in a harbour preset, visibility at 0.5 m altitude should be noticeably lower (for example 50 %) than mid-water. Sources say "changes rapidly over metres, especially near the bottom" and a BNL of 3–35 m over mud.

7. **Seabed type is ignored (medium).**
   - All biomes silt equally.
   - Model: per-biome τ_cr and size mix:
     - reef / rock: none
     - sand: fast settle
     - harbour mud: low τ_cr, fine
   - Validation: the same manoeuvre should give a large lasting cloud in the harbour, a short burst on sand, and nothing on rock.

8. **Code hygiene (low).**
   - Dead scalar `World.silt` (`world.py:350/449/535`).
   - `engine.py:204` omits `thrust`, so standalone `Simulator.step` never makes thruster silt.
   - The expedition range check uses unreduced `visibility_m` (`expedition.py:341`).
   - The incident "揚沙迷航" uses a static 1 m visibility rather than a dynamic silt-out (`scenarios.py:358`).
   - Tests only cover locality and expiry (`test_ecology.py:95`). Add tests for altitude scaling, direction, mass conservation and clearing time.

9. **Assist interaction (low, design).**
   - Speed and position assist (T01 contract) will actively fight drift near the bed. Each correction is a thruster jet.
   - Show this as a `limited`-style warning, or have the HUD flag "high near-bed thrust". The physics should not be softened.

### Gaps
- All clearing-time and altitude targets above are derived from first principles plus generic literature. None comes from ROV field measurement, because no such data was found.
- Highest-value next measurement: on the X1 over a muddy site, log altitude, thruster commands and camera contrast. Use 0.5/1/2 m altitude × 25/50/100 % vertical thrust, and time recovery with and without current.
