# Ocean currents, waves and water motion as they affect small ROV operations (physics notes for the simulator)

Scope note: these notes were compiled from roughly 25 searches and fetches. Primary sources whose full text was read: the HR Wallingford SR 360 report (it reproduces Soulsby's z0 table), the NOAA Tidal Current Tables 2018 (Pacific Coast) explanatory text and Tables 3 to 5, Milne, Sharma and Flay (2016) on Sound of Islay turbulence, Togneri and Masters (2016) on Ramsey Sound turbulence, VideoRay operator guidance, LibreTexts Coastal Dynamics (Bosboom and Stive), and the Wikipedia article on potential flow around a cylinder. DNV-RP-C205 could not be fetched (the HVL mirror returns 404 and the current edition is paywalled), so its current-profile formulas are **not verified** here; see Gaps. Formulas marked "standard result / inference" are textbook physics that I derived or recalled and could not cite to a fetched page. They are listed under Inferences, not Cited Findings.

## 1. Vertical current profiles (tidal, wind-driven, sheared, stratified)

### Takeaway
Tidal flow near the bed follows a logarithmic law, u(z) = (u*/κ) ln(z/z0), with κ ≈ 0.4 and z0 between about 0.005 cm (silt/sand) and 0.6 cm (rippled sand). In strong tidal channels the boundary layer fills most of the water column: it was 40 to 50 m thick in about 55 m of water at Islay. Wind drift adds a surface current of about 1 to 3% of wind speed, which decays with depth. For a simulator, a 1/7 power law over the depth plus a wind-drift layer near the surface is a reasonable default. The 1/7 exponent and the DNV formula are unverified here.

### Cited Findings
- **Log law (von Kármán–Prandtl)**: near-bed tidal flow follows u(z) = (u*/κ) ln(z/z0). Here u(z) is the velocity at height z above the bed, κ ≈ 0.4 is von Kármán's constant, u* is the friction velocity, and z0 is the roughness length, the height where the fitted profile extrapolates to zero. — [HR Wallingford SR 360](https://eprints.hrwallingford.com/348/1/SR360.pdf)
- **z0 regimes**: in smooth turbulent flow (Re* < 3.5), z0 ≈ ν/(9 u*). In rough turbulent flow (Re* > 68), z0 = d/c3, where d is the grain size d50 and c3 is between 15 and 30 depending on the experimenter. — [HR Wallingford SR 360](https://eprints.hrwallingford.com/348/1/SR360.pdf)
- **Typical z0 and C100 by seabed (Soulsby 1990, as reproduced in Table 1)**. C100 is the drag coefficient referenced to the velocity 1 m above the bed. — [HR Wallingford SR 360](https://eprints.hrwallingford.com/348/1/SR360.pdf)

  | Bottom type | z0 (cm) | C100 |
  |---|---|---|
  | Mud | 0.02 | 0.0022 |
  | Mud/sand | 0.07 | 0.0030 |
  | Silt/sand | 0.005 | 0.0016 |
  | Sand (unrippled) | 0.04 | 0.0026 |
  | Sand (rippled) | 0.6 | 0.0061 |
  | Sand/shell | 0.03 | 0.0024 |
  | Sand/gravel | 0.03 | 0.0024 |
  | Mud/sand/gravel | 0.03 | 0.0024 |
  | Gravel | 0.3 | 0.0047 |
- z0 on rippled sand is about 15 times larger than on unrippled sand, because form drag over the bedforms adds to the grain roughness. In the field, z0 is highly variable. In the Solent (coarse sand and gravel with dunes) the mean was 0.15 cm with a range of 0.001 to 5 cm. In Puget Sound (rock, shell, gravel, sand) the mean was 0.1 cm with a range of 10⁻⁵ to 10¹ cm. At one site z0 swung from about 0.01 cm to about 5 cm over 1.5 tidal cycles. — [HR Wallingford SR 360](https://eprints.hrwallingford.com/348/1/SR360.pdf)
- **Boundary-layer thickness in a strong tidal channel**: the Sound of Islay is about 55 m deep and 800 m wide, with a seabed of boulders, rock and gravel. There the boundary layer (taken as the height where U = 99% of the maximum) was at least 50 m at peak flood and up to about 40 m on the ebb. At maximum ebb it shrank to about 25 m. The layer was thicker while the flow decelerated than while it accelerated, which means large eddies persist after peak flow. The profile was roughly log-linear up to about 10 m above the bed. The log law is considered applicable only for z/h < 0.15 to 0.2. Bed stress fitted with the log law exceeded the stress measured directly by about 25%. — [Milne, Sharma & Flay 2016, AFMC](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf)
- Islay flow direction was near-uniform through the water column, the water was well mixed, and there were no strong secondary subsurface currents. Peak speed was about 2.5 m/s at spring tide and about 1.5 m/s at neap. Significant wave height (Hs) was generally below 1 m. — [Milne et al. 2016](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf)
- **Wind drift**: with a steady wind, the surface current is generally 1 to 3% of wind speed. — [LibreTexts, Intro to Ocean Sciences (Segar)](https://geo.libretexts.org/Courses/American_Meteorological_Society/Introduction_to_Ocean_Sciences_6e_(Segar)/08%3A_Ocean_Circulation/8.02%3A_Wind-Driven_Currents). Bowditch gives about 2% or a little less in deep water after at least 12 h of steady wind. — [Bowditch Ch. 36 (snippet only)](https://thenauticalalmanac.com/2019_Bowditch-_American_Practical_Navigator/Volume-_1/11-%20Part%209-%20Oceanography/Chapter%2036-%20Ocean%20Currents.pdf). NASA TN D-7771 says up to 3% in deep water. — [NASA NTRS (snippet only)](https://ntrs.nasa.gov/api/citations/19750004465/downloads/19750004465.pdf)
- Undrogued surface drifters move at about 3.4 to 6.0% of wind speed, deflected about 5 to 55° to the right of the wind in the northern hemisphere. Their surface velocity includes Stokes drift and windage, so it is not the same as the Eulerian current. — [Ocean Science 15, 1627 (2019) (snippet only)](https://os.copernicus.org/articles/15/1627/2019/os-15-1627-2019.pdf)
- The wind-driven current decreases with depth and is confined to the upper 100 to 200 m of the ocean, often much less. It is not expected to be significant below about 0.7 times the Ekman depth. — [LibreTexts](https://geo.libretexts.org/Courses/American_Meteorological_Society/Introduction_to_Ocean_Sciences_6e_(Segar)/08%3A_Ocean_Circulation/8.02%3A_Wind-Driven_Currents); [Ardhuin et al. 2009 (snippet only)](https://data-ww3.ifremer.fr/BIB/Ardhuin_etal_JPO2009.pdf)
- **Stratification**: at the Gemini offshore wind farm (North Sea, about 80 km north of Schiermonnikoog), ADCP data showed maximum tidal currents in summer, not winter, because stratification influenced tidal currents more than wind did. — [TU Delft repository (snippet only)](https://repository.tudelft.nl/record/uuid:a210fc5f-a2e2-43f0-b754-b41e8740d487)
- At FINO1 / alpha ventus (North Sea, about 30 m deep), bottom-mounted 5-beam ADCPs measured current and turbulence profiles as 2-min averages every 10 min, in 1 m cells. — [Ocean Dynamics 2018 (snippet only)](https://link.springer.com/article/10.1007/s10236-017-1109-5)
- VideoRay notes that current profiles "may vary significantly throughout the depth range", which matters for tether shape. — [VideoRay, A deep dive on diving deep](https://videoray.com/a-deep-dive-on-diving-deep/)

### Inferences
- **Recommended simulator profile (standard result, not verified against DNV)**: the total current is a tidal part plus a wind part, U(z) = U_tide(z) + U_wind(z).
  - Tidal part: U_tide(z) = U_tide,0 · ((d + z)/d)^α, with α = 1/7, z ≤ 0 measured from the surface, and d the water depth. This is the commonly quoted DNV-RP-C205 form.
  - Wind part: U_wind(z) = U_wind,0 · (d0 + z)/d0 for −d0 ≤ z ≤ 0, otherwise 0, with U_wind,0 = k·U10, k ≈ 0.015 to 0.03, and d0 ≈ 50 m (or the full depth if shallower).
  - These match the memory-based DNV form; the k range is consistent with the cited 1 to 3% wind-drift values. **Verify against DNV-RP-C205 §4.1 before writing them into code.**
- For a log-law bottom layer joined to the depth average (a Soulsby-style relation): ū = (u*/κ)(ln(h/z0) − 1), so u* = κ ū / (ln(h/z0) − 1). Example: h = 20 m and z0 = 0.3 cm (gravel) give ln(h/z0) ≈ 8.8 and u* ≈ 0.051 ū. At ū = 1 m/s the speed at 0.5 m above the bed is u ≈ (0.051/0.4) · ln(0.5/0.003) ≈ 0.65 m/s. A small ROV sitting on or near the bottom therefore sees roughly 60 to 70% of the depth-averaged current. This is pedagogically important: "get down low to escape the current".
- For two-layer, stratified flows such as harbours with river outflow or a summer thermocline, model the layers as separate speed and direction vectors joined across a shear interface of a few metres. Directions can differ between the layers (for example, outflowing fresh water on top of an inflowing salt wedge). The shear across a thermocline or halocline also suppresses vertical mixing, so turbulence should be lower below the interface. There is no quantitative source here; treat it as an assumption.

### Gaps
- DNV-RP-C205's exact current-profile equations, its k factor and its d0 could not be read: the HVL mirror PDF returns 404 and the 2025 edition is paywalled. The 1/7 exponent is unverified from a primary source in this session.
- No open, quantitative profile data were found for harbours, quay walls or wrecks. The North Sea metocean reports (Energinet North Sea I / Energy Island, Fugro TNW) were located but are over 10 MB and were not read: [ens.dk 5777](https://ens.dk/media/5777/download), [ens.dk 5778](https://ens.dk/media/5778/download), [RVO TNW Fugro](https://offshorewind.rvo.nl/file/download/3b2f655f-af72-4bf5-9754-a7d2d2e6dc6c/tnw_20220118_mc_fugro_report-f.pdf).
- No Ekman spiral rotation rates or eddy viscosity values were gathered.

## 2. Time variation: tidal cycles, slack water, rotary vs rectilinear

### Takeaway
A rectilinear (reversing) tidal current runs about 6 h in each direction with four slacks per day, and its speed follows roughly a sinusoid between slack and maximum. Slack water is only momentary. For a 1-knot maximum, the current stays below 0.1 kn for about 23 min, and the window shrinks roughly as 1/Umax. Slack does not coincide with high or low water: in rivers and bays it can be offset by 1 to 3 h. Offshore rotary currents never reach true slack.

### Cited Findings
- **Slack definition**: "Slack" is the predicted instant when the current has stopped setting one way and is about to set the other. "Offshore, where the current is rotary, slack water denotes the time of minimum current." There are usually four slacks and four maxima a day. Where the diurnal inequality is large, some days have only two of each. — [NOAA Tidal Current Tables 2018](https://tidesandcurrents.noaa.gov/tidetables/2018/pcct2018FullBook.pdf)
- **Timing offset**: the time of slack "does not generally coincide with the time of high or low water". In a tidal river or bay it may differ by 1 to 3 hours from high or low water. Actual slack can differ from the prediction by up to 30 min, rarely up to 1 h. More than 90% of observed slacks fall within ±30 min of the prediction, so plan to arrive at least 30 min early. Wind and river discharge disturb the timing. — [NOAA Tidal Current Tables 2018](https://tidesandcurrents.noaa.gov/tidetables/2018/pcct2018FullBook.pdf)
- **Speed at intermediate times (Table 3)**: speed = factor × maximum speed. Worked example: with 3 h 06 m from slack to maximum and 1 h 41 m elapsed since slack, the factor is 0.8, so a 3.2 kn maximum gives 2.56 kn. For intervals longer than 5 h 40 m, enter the table with half-intervals. — [NOAA Tidal Current Tables 2018](https://tidesandcurrents.noaa.gov/tidetables/2018/pcct2018FullBook.pdf)
- **Duration of slack (Table 4A, normal stations)**: minutes with speed at or below each threshold, centred on the slack, half before and half after. — [NOAA Tidal Current Tables 2018](https://tidesandcurrents.noaa.gov/tidetables/2018/pcct2018FullBook.pdf)

  | Max current (kn) | ≤0.1 kn | ≤0.2 | ≤0.3 | ≤0.4 | ≤0.5 |
  |---|---|---|---|---|---|
  | 1.0 | 23 | 46 | 70 | 94 | 120 |
  | 1.5 | 15 | 31 | 46 | 62 | 78 |
  | 2.0 | 11 | 23 | 35 | 46 | 58 |
  | 3.0 | 8 | 15 | 23 | 31 | 38 |
  | 4.0 | 6 | 11 | 17 | 23 | 29 |
  | 5.0 | 5 | 9 | 14 | 18 | 23 |
  | 6.0 | 4 | 8 | 11 | 15 | 19 |
  | 8.0 | 3 | 6 | 9 | 11 | 14 |
  | 10.0 | 2 | 5 | 7 | 9 | 11 |

  Table B, for constricted narrows such as Seymour Narrows or Deception Pass, has shorter windows. For example, a 2.0 kn maximum gives 6/13/20/28/36 min. When the flood and ebb maxima differ, average the two durations.
- **Rotary currents (Table 5)**: inside bays and rivers the current reverses, setting about 6 h in one direction, stopping momentarily, then setting about 6 h the other way. Offshore currents "change direction continually and never slow to a true slack". Over the 12½ h cycle they set toward every compass direction. A minimum follows a maximum by about 3 h. Notes for individual stations include "Current is rotary, turning clockwise. Minimum current about 0.1 knot". — [NOAA Tidal Current Tables 2018](https://tidesandcurrents.noaa.gov/tidetables/2018/pcct2018FullBook.pdf)
- **Spring/neap**: at the Sound of Islay, peak speed was about 2.5 m/s at spring tide and about 1.5 m/s at neap, a ratio of about 1.7. Flow was asymmetric, with a stronger southerly ebb. — [Milne et al. 2016](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf)
- **Operator practice**: time dives as close to slack as possible. Moving a short distance from the port that the tide tables refer to can shift slack by 30 to 60 min, so check local predictions. — [VideoRay (search snippet of operator tips)](https://videoray.com/introducing-insights-a-new-go-to-resource-for-rov-operators-2/)

### Inferences
- NOAA Table 4A matches a pure sinusoid, U(t) = Umax sin(2π t / T) with T = 12.42 h (the M2 period). For |U| ≤ u_th the half-window is t ≈ (T/2π)·asin(u_th/Umax). Check: Umax = 1 kn and u_th = 0.1 kn give 2 × 11.9 = 23.8 min, against 23 in the table. The simulator can therefore use U(t) = Umax(t)·sin(ωt + φ), with a spring-neap modulation Umax(t) = Ū[1 + m cos(2π t / 14.77 d)] and m ≈ 0.25 to 0.3 (from the Islay 2.5/1.5 ratio). Flood and ebb can have different Umax to represent ebb–flood asymmetry.
- For rotary currents, use a tidal ellipse: U(t) = (U_major cos ωt, U_minor sin ωt), rotated by the ellipse orientation. The minimum current equals U_minor, which is not zero.
- Training scenario idea: give the pilot a 23-min "below 0.1 kn" window at a 1-kn site, versus 6 min at a 4-kn site, so they learn why planning around slack matters.

### Gaps
- The numeric cells of NOAA Table 3 (the factor grid) were not extracted; it rendered as an image or empty text. The sinusoidal approximation above reproduces Table 4.

## 3. Spatial variation around structures (piles, jackets, wrecks, quays)

### Takeaway
In potential flow the surface speed on a cylinder is 2U·sinθ, so the flow is twice the free stream at the sides and stagnates at the front and rear. Real flow separates and leaves a turbulent wake that sheds vortices at f = St·U/D, with St ≈ 0.2. At the base a horseshoe vortex forms, and together with the side acceleration it drives scour.

### Cited Findings
- **Potential flow around a cylinder** of radius R in free stream U: V_r = U(1 − R²/r²)cosθ and V_θ = −U(1 + R²/r²)sinθ. On the surface the speed is 2U sinθ: zero at the stagnation points and 2U on the sides. The surface pressure coefficient is Cp = 1 − 4 sin²θ, ranging from +1 to −3. Real viscous flow separates and forms a wake, so the ideal solution does not hold behind the cylinder. — [Wikipedia: Potential flow around a circular cylinder](https://en.wikipedia.org/wiki/Potential_flow_around_a_circular_cylinder)
- **Strouhal number**: an empirical fit for a monopile is St ≈ 0.198(1 − 19.7/Re_D), which approaches about 0.2 at high Re. The shedding frequency is f_s = St·U∞/D. For Re > 2000 the wake is essentially turbulent but keeps traces of periodic structure. — [arXiv 2503.13860 (snippet only)](https://arxiv.org/pdf/2503.13860)
- **Scour**: scour begins under the flow acceleration at the sides of the cylinder and the horseshoe vortex at its upstream base. The horseshoe vortex grows in size and lifespan with increasing Keulegan–Carpenter number. Horseshoe vortices also increase entrainment between the main flow and the wake downstream. — [arXiv 2503.13860 and related results (snippet only)](https://arxiv.org/pdf/2503.13860)
- **Natural features**: in Ramsey Sound, the gross mean flow did not vary at scales below about 50 m except in the wake of large surface-piercing features. A turbulent kinetic energy (TKE) maximum about 5 m above the bed was attributed to flow separating off a rough outcrop, and ebb TKE varied by 140% between points less than 50 m apart. — [Togneri & Masters 2016, Ramsey Sound](https://cronfa.swansea.ac.uk/Record/cronfa23511/Download/0023511-20072016150754.pdf)

### Inferences
- **Practical numbers (standard results, not verified here)**:
  - For a 6 m monopile in 1 m/s current, f_s ≈ 0.2 × 1 / 6 ≈ 0.033 Hz (period about 30 s). A small ROV in the near wake would feel a lateral oscillation with a period of about 30 s.
  - For a 0.5 m jacket leg in the same current, f_s ≈ 0.4 Hz, which feels like buffeting.
- **Wake deficit**: there is no cited formula. A common far-wake similarity result for a 2-D cylinder is that the centreline deficit decays as ΔU/U ∝ (x/(C_D D))^(−1/2) and the wake half-width grows as ∝ (C_D D x)^(1/2). A reasonable simulator approximation:
  - just behind the cylinder (x < 2D) the flow is a recirculation zone with mean u of about 0 to slightly negative;
  - at x ≈ 5 to 10 D the deficit is roughly 30 to 50%;
  - by x ≈ 20 D or more it is under 10–20%.
  - Treat this as an assumption to be tuned.
- **Lee shelter for the pilot**: the lee is real but unsteady. It is calm in the mean but has large periodic side loads at f_s. The accelerated flow on the sides (up to 2U in theory, typically about 1.3 to 1.6U in real separated flow, not verified here) is the worst place to station-keep.
- **Jackets, hulls, wrecks and quay walls**: no quantitative open source was found. Plausible modelling:
  - Treat a jacket as a porous blockage with a shielding factor, which DNV-RP-C205 is believed to give for jackets (unverified).
  - Treat a wreck hull as a bluff body with a separated lee, plus upwelling and downwelling over the hull.
  - At quay walls, the flow runs parallel to the wall, with a no-slip boundary layer and eddies at the corners.
  - At channel and harbour entrances, the flow jets through the gap: speed ≈ Q/(width × depth), with eddies forming on both sides on the ebb or flood.

### Gaps
- Sumer & Fredsøe and Roshko wake-deficit data were not fetched. There are no measured values for velocity deficit against x/D, for the real separated-flow side speed-up on piles at high Re, or for jacket blockage factors.
- No ADCP data around monopiles or wrecks was found.

## 4. Turbulence: intensity, scales, spectra, synthesis, coherence

### Takeaway
Strong tidal channels show a streamwise turbulence intensity (TI) of about 10 to 15% (Islay 12 to 13% at 5 m above the bed). Integral length scales are of order 10 m up to the water depth (Islay 11 to 14 m; Alderney Race 2 to 3 times the depth; Fall of Warness eddies over 30 m). Turbulence is anisotropic: σv/σu ≈ 0.75 and σw/σu ≈ 0.55. TI falls as mean speed rises, because TKE grows more slowly than U². Turbulence varies strongly over tens of metres.

### Cited Findings
- **Islay**: an ADV 5 m above the bed in a mean flow up to 2.5 m/s measured a length scale of about 11 to 14 m and a streamwise TI of about 12 to 13%, with little difference between ebb and flood. — [search-result summary of a review citing Milne et al. (snippet only)](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf)
- **Islay (full text)**:
  - Anisotropy away from slack: σv/σu = 0.75 and σw/σu = 0.55. Laboratory open-channel values are 0.71 and 0.55; atmospheric values are 0.80 and 0.68.
  - −σuw/q² = 0.12 (Puget Sound 0.14; laboratory 0.14), where q² = 0.5(σu² + σv² + σw²).
  - The peak Reynolds stress has a median of about 0.014 m²/s², with short-term variation on scales under 15 min.
  - The streamwise spectrum peaks at k_z = 2π f z/U ≈ 0.4, which corresponds to a length scale of about the channel depth. Lateral and vertical spectra peak at k_z ≈ 2 and 4 respectively. Vertical eddies are confined by the free surface.
  - [Milne, Sharma & Flay 2016](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf)
- **Ramsey Sound** (swept-bedrock channel, depth up to 70 m; bed-mounted 600 kHz ADCP sampling at 2 Hz in 1 m bins): TKE density scaled linearly, not quadratically, with mean speed, so TI decreases as the flow gets faster even though the turbulence is more energetic. Ebb TKE varied by 140% between points less than 50 m apart, and there was a large flood–ebb asymmetry. Integral length scales were about 5 to 15 m (Fig. 8), and the estimates from different beams differed by up to 68%. — [Togneri & Masters 2016](https://cronfa.swansea.ac.uk/Record/cronfa23511/Download/0023511-20072016150754.pdf)
- **Alderney Race**: the integral length scale is 2 to 3 times the local water depth. Removing wave and Doppler-noise bias is crucial. — [search summary of Thiébaut et al. (snippet only)](https://scite.ai/authors/maxime-thiebaut-5zWDR)
- **Fall of Warness (EMEC, Orkney)**: eddies larger than 30 m. Results were highly sensitive to ADCP make and model. — [Greenwood et al. 2019, Energies 12(4):672 (snippet only)](https://econpapers.repec.org/RePEc:gam:jeners:v:12:y:2019:i:4:p:672-:d:207291); [UHI Pure (snippet only)](https://pure.uhi.ac.uk/en/publications/on-the-variation-of-turbulence-in-a-high-velocity-tidal-channel/)
- **Puget Sound** (Admiralty Head and Nodule Point): large-scale, anisotropic eddies dominate the spectra, possibly because the sites are close to headlands. Normalised TI was consistent across sites and instruments. A public dataset is available. — [PNNL 2012 listing (snippet only)](https://www.pnnl.gov/publications/measurements-turbulence-two-tidal-energy-sites-puget-sound-wa); [data.gov dataset](https://data.amerigeoss.org/en/dataset/admiralty-inlet-wa-tidal-current-turbulence-b456b)
- **LES of tidal turbulence**: anisotropic, with longer length scales along the flow than across it. Simulated TI was lower than the ADCP-derived TI. — [EWTEC paper (snippet only)](https://submissions.ewtec.org/proc-ewtec/article/download/566/283/3067)

### Inferences
- **Real-time gust synthesis (standard methods, not cited)**: per axis i ∈ {u, v, w}, use an Ornstein–Uhlenbeck process
  `du_i' = −(u_i'/T_i) dt + σ_i √(2/T_i) dW`, discretised exactly as `u' ← a·u' + σ√(1−a²)·N(0,1)` with `a = exp(−Δt/T_i)`.
  - Parameters: σ_u = TI·U with TI ≈ 0.10 to 0.15 in tidal channels and about 0.05 in quiet harbours (assumed); σ_v = 0.75 σ_u and σ_w = 0.55 σ_u (Islay).
  - Integral time scale T_u ≈ L_u/U. With L_u ≈ 10 m and U = 1 m/s, T_u ≈ 10 s; T_v and T_w are shorter, about L/U with L about 0.5 and 0.3 times L_u. L_u can be taken as about min(depth, 15 m), and should be smaller near the bed (L grows roughly as κz near the wall).
  - Because measured TKE scales about linearly with U, make σ_u ∝ √U, not ∝ U, for physical fidelity.
  - An OU process gives a Lorentzian spectrum (slope −2). For a −5/3 inertial range, sum 2 or 3 OU processes, or use spectral synthesis from a von Kármán spectrum, S_u(f) = 4σ²(L/U) / [1 + 70.8 (fL/U)²]^(5/6).
- **Coherence over the vehicle and tether**: a small ROV of about 0.5 m is much smaller than L (about 10 m), so the turbulence is effectively uniform over the hull and can be applied as one velocity at the centre of gravity. Along a 50 to 100 m tether, the segments are separated by more than L. Each tether segment should therefore take turbulence from a spatially correlated field, for example a frozen-turbulence field advected with the mean flow (Taylor hypothesis), or independent OU processes per node with correlation exp(−Δs/L).
- **Pedagogy**: TI is lowest at peak flow but absolute gusts (σ) are largest. Near slack the turbulence decays, but eddies persist into deceleration (Islay).

### Gaps
- No primary source in this session gave "10–15%" across sites. Islay gives 12 to 13%. Admiralty Inlet values of about 10% are commonly quoted but could not be verified (the PNNL PDFs returned 403).
- No von Kármán fit parameters were obtained from a tidal paper. The coherence-versus-separation numbers from Thomson et al. (Admiralty Inlet, rotor-scale coherence) were not obtained.

## 5. Surface waves: orbital velocities, depth decay, ROV motion

### Takeaway
Linear (Airy) wave theory gives an orbital velocity of u = ωa·cosh k(h+z)/sinh kh, which in deep water reduces to ωa·e^{kz}. At a depth of half a wavelength the orbits are only about 4% of their surface size. Short wind sea dies out within a few metres, but long swell reaches tens of metres, so a small ROV near the surface surges and heaves with the waves.

### Cited Findings
- Horizontal orbital velocity amplitude: û(z) = ωa · cosh k(h+z) / sinh kh, with ω = 2π/T, a the amplitude (H/2), k = 2π/L, h the depth, and z positive upward from the surface. In shallow water (kh < π/10) û = ωa/(kh) = c·a/h = √(gh)·H/(2h), uniform over the depth. The orbital excursion is ξ̂ = û/ω. — [LibreTexts, Coastal Dynamics (Bosboom & Stive) §5.4.1](https://geo.libretexts.org/Bookshelves/Oceanography/Coastal_Dynamics_(Bosboom_and_Stive)/05%3A_Coastal_hydrodynamics/5.04%3A_Wave_orbital_velocity_pressure_and_bed_shear_stress/5.4.01%3A_Wave_orbital_velocities)
- "In deep water the orbital diameter has been reduced to only 4% of the value at the surface at a depth of half a wavelength." Deep water means depth greater than L/2. Orbital velocities attenuate exponentially with depth, and faster for shorter waves. — [LibreTexts](https://geo.libretexts.org/Bookshelves/Oceanography/Coastal_Dynamics_(Bosboom_and_Stive)/05%3A_Coastal_hydrodynamics/5.04%3A_Wave_orbital_velocity_pressure_and_bed_shear_stress/5.4.01%3A_Wave_orbital_velocities); [Nortek, Subsurface wave properties (snippet only)](https://support.nortekgroup.com/hc/en-us/articles/21694249619484-Subsurface-wave-properties)
- Airy theory is accurate for small wave height relative to wavelength. — [Wikipedia: Airy wave theory (snippet only)](https://www.wikipedia.org/wiki/Airy_wave_theory)
- At Islay, Hs was mostly below 1 m and the site was sheltered. Wave bias must be removed from ADCP turbulence estimates. — [Milne et al. 2016](https://people.eng.unimelb.edu.au/imarusic/proceedings/20/544%20Paper.pdf); [Thiébaut et al. (snippet only)](https://scite.ai/authors/maxime-thiebaut-5zWDR)

### Inferences
- **Deep-water formulas (standard, derived from the above)**:
  - Dispersion: ω² = gk tanh kh, so in deep water ω² = gk, L = gT²/(2π) ≈ 1.56 T² m, and c = gT/(2π).
  - Velocities: u = ωa e^{kz} cos(kx − ωt) and w = ωa e^{kz} sin(kx − ωt). The magnitude decays as e^{kz}, and the e-folding depth is L/(2π).
  - Vertical displacement of a fluid particle: a·e^{kz}.
- **Worked numbers (H = 1 m, so a = 0.5 m)**:

  | Sea | T (s) | L (m) | û surface (m/s) | 2 m | 5 m | 10 m | 20 m |
  |---|---|---|---|---|---|---|---|
  | Short wind chop | 4 | 25 | 0.79 | 0.48 | 0.23 | 0.06 | ≈0 |
  | Wind sea | 6 | 56 | 0.52 | 0.42 | 0.30 | 0.17 | 0.05 |
  | Swell | 10 | 156 | 0.31 | 0.29 | 0.26 | 0.21 | 0.14 |
  | Long swell | 14 | 306 | 0.22 | 0.22 | 0.20 | 0.18 | 0.15 (h-limited) |

  These are computed from e^{kz}. Velocities scale linearly with H.
- **When waves become negligible for a small ROV**: take the threshold as the depth where û falls below about 0.05 m/s, roughly the turbulence level. Solving û(z) = ωa·e^{kz} = 0.05 m/s gives z = ln(0.05/(ωa))/k. For H = 1 m this is about 10 m for a 4-s chop, about 20 m for a 6-s wind sea, and 40 m or more for a 10-s swell (in shallow water, swell reaches the bed). This is why ROVs launched from small boats "get pumped" during launch, recovery and the first few metres, and why swell can be felt even at 20 to 30 m on a shallow shelf.
- **Wave-induced vehicle response**: a small ROV (L about 0.5 m) is much shorter than the wavelength. The wave acts on it mainly through Morison-type forces: drag ½ρC_dA|u_r|u_r plus fluid inertia (1 + C_a)ρV·du/dt. In deep water the acceleration amplitude is ω²a·e^{kz}. The result is surge and heave orbits that the vehicle largely follows, with only a little pitch, because the velocity gradient over the vehicle is small. The tether and the surface boat (heave of the launch point) add a jerk through the tether near the surface.
- **Sea states for small-boat ROV operations**: no source was found. Assume Hs ≤ 1 to 1.5 m (sea state 2 to 3) as typical for small-boat inspection class operations. Swell has T of about 8 to 16 s and is long-crested; wind sea has T of about 3 to 7 s and is short-crested. Synthesise the sea as a sum of JONSWAP- or Pierson–Moskowitz-distributed components, each with its own e^{kz} decay.
- **Stokes drift**, u_s = ωka²·e^{2kz}, gives a small mean down-wave drift near the surface (standard result).

### Gaps
- No ROV-operator source quantified Hs limits or the depth at which wave pumping stops for small ROVs. DNV-RP-C205 wave kinematics (including Wheeler stretching) were not read.

## 6. Effects on the ROV and tether: loads, practical limits, piloting strategy

### Takeaway
Drag scales with U², so doubling the current quadruples the load. In current, tether drag usually dominates the vehicle's own drag once tens of metres of tether are exposed. A third-party calculator gives about 615 N for 100 m in 0.5 m/s, but its inputs imply a roughly 40 mm cable; see Inferences. Real practice is therefore to minimise the length of tether in the water, use clump weights, head into the current, deploy up-current, and dive at slack. Manufacturer claims of "up to 4 kn" refer to the vehicle alone. VideoRay treats anything above 1.5 kn as "strong current".

### Cited Findings
- Tether in the water "will act like a sail and pull on the ROV": keep it short. When working from shore, reposition the control box rather than paying out tether. Drag increases when working perpendicular to the current. A thinner tether reduces drag, especially over long lengths. VideoRay organises its operator advice around strong currents above 1.5 kn. Above 3 kn, live-boat with the engine facing upstream and deploy the ROV from the bow, downstream. Time dives near slack. — [VideoRay operator tips (search snippet)](https://videoray.com/introducing-insights-a-new-go-to-resource-for-rov-operators-2/)
- **Slant range**: current means using at least 25 to 75% more tether than the vertical depth. As the slant angle grows, vertical thrust may not be enough to keep descending. Remedies are a thinner tether, more ballast, or fibre instead of copper. In strong current, position the vessel up-current of the work site. — [VideoRay, A deep dive on diving deep](https://videoray.com/a-deep-dive-on-diving-deep/)
- **Clump weights**: attach the clump weight a short distance behind the ROV; that distance sets the working radius. Effective up to about 50 kg (110 lb). "It is best to maintain the ROV heading into the current and let the weight drag it down." This keeps tension on the slack tether and prevents wrapping. Auto-heading counters torque steer from a single vertical thruster, which would otherwise put turns into the tether. — [VideoRay, A deep dive on diving deep](https://videoray.com/a-deep-dive-on-diving-deep/)
- **Tether drag estimate**: 100 m of tether fully perpendicular to a 0.5 m/s current gives about 615 N. This is conservative and comes from a third-party calculator, so treat it as preliminary. — [ROV Tether Drag Power Calculator](https://agentcalc-cloudflare-public.pages.dev/rov-tether-drag-power-calculator)
- **Industry speeds**: traditional work-class ROVs were limited to about 1.5 to 2 kn. A high-speed design (vendor claim) reaches up to 5 kn and kept station in currents above 2.6 kn at a wind farm. — [Offshore Magazine (vendor piece)](https://www.offshore-mag.com/renewable-energy/article/14206590/oceaneering-new-work-class-rov-can-operate-in-harsh-tidal-environments). Open-frame vehicles are "useful for free-swimming in light currents (less than 4 knots based upon manufacturer specifications)". — [Wikipedia ROV (mirror, snippet only)](https://en.wikipedia.com/wiki/ROUV)
- A tether management system shortens or lengthens the tether to minimise cable drag in current. Required thrust must exceed current drag plus tool loads plus a margin. — [Rigzone (snippet only)](https://www.rigzone.com/insights/how-it-works-3/how-do-rovs-work-1148); [Melon Robotics wiki (snippet only)](https://melon-robotics.github.io/melon-wiki/subsea-robotics/rov-systems/)

### Inferences
- **Drag law (standard)**:
  - Vehicle: F = ½ρC_d A |U_r| U_r, with ρ ≈ 1025 kg/m³ for seawater and U_r the velocity relative to the water.
  - Tether, per unit length: f_n = ½ρC_n d |U_n| U_n, where C_n ≈ 1.0 to 1.2 for a cylinder at subcritical Re and U_n is the normal component; the tangential coefficient is much smaller (about 0.01 to 0.03).
  - Back-check of the calculator: 615 N = 100 m × d × ½ × 1025 × 1.2 × 0.5² implies d ≈ 40 mm (or a larger C_n with a thinner cable). That is much thicker than a small-ROV tether, so the calculator's default inputs are not representative. For a 6 to 8 mm tether, 100 m fully normal to 0.5 m/s gives only about 90 to 125 N, but the load rises as U²: about 370 to 490 N at 1 m/s.
- **Why a "4-knot" claim is optimistic**:
  - A small ROV with A ≈ 0.08 m² and C_d ≈ 0.9 in 2 m/s (3.9 kn) of current needs F ≈ ½ × 1025 × 0.9 × 0.08 × 4 ≈ 148 N on the vehicle alone. Typical small-ROV forward thrust is of order 50 to 150 N (assumption, not cited).
  - Add a 6 mm tether with 30 m exposed: ≈ ½ × 1025 × 1.2 × 0.006 × 30 × 4 ≈ 440 N, about three times the vehicle drag.
  - So "holds station in X kn" is only possible with a very short tether, and only along the thrust axis. Because thrust is spread over vectored thrusters, lateral and vertical capability is less than forward capability.
  - Simulator default: let real-mode station-keeping saturate (`assist.limited = true` per the AGENTS.md contract) as soon as the required force exceeds the available thrust per axis.
- **Crab angle and heading**: to hold a track across the current, head into the current by the crab angle β = asin(U_c⊥ / U_vehicle,max). Pointing the bow (smallest frontal area, strongest thrust axis) into the current minimises drag, which is why operators "fly into the current" and approach targets from down-current, moving up-current. The vehicle then drifts away from the target, not into it, if thrust is lost.
- **Tether shape in current**: catenary-like with a "belly" downstream. The slant range grows with U². Use a lumped-mass tether with per-node relative-velocity drag and a depth-varying current profile, so that shear (for example a stronger surface current) visibly bows the upper tether.
- **Using structure lee**: lee shelter reduces mean drag but adds periodic loads at the shedding frequency (see §3). The pilot should hold position close downstream of a pile, at x/D ≲ 1 to 2, or behind a large hull, and avoid the accelerated flanks.

### Gaps
- No IMCA or manufacturer document with published operational current limits for observation-class ROVs was read. VideoRay's ">1.5 kn = strong" and ">3 kn = live-boat" thresholds are the best operator-level numbers found.
- No ROV current-logging datasets (DVL water-track or ADCP from ROV operations) were found.
- Small-ROV thrust values and tether diameters belong to the separate X1 measurement checklist. Per AGENTS.md, do not treat these assumed numbers as X1 facts.
