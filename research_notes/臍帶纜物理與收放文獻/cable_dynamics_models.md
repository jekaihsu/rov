# Numerical modelling of underwater cables and ROV tethers for real-time simulation

Scope note: full texts actually read (extracted to text and checked line by line) were: von Benzon et al. 2022 (BlueROV2 + lumped-mass tether, JMSE 10:1898, AAU repository copy); Palm & Eskilsson 2020 (bending stiffness and snap loads, JMSE 8:795, Chalmers repository copy); Driscoll 1999 PhD thesis (UVic, ROPOS deep-sea ROV tether, contains the Driscoll/Lueck/Nahon 2000 lumped-mass paper as an appendix); Buckham 2003 PhD thesis (UVic, low-tension ROV tethers with bending and torsion); MoorDyn "Troubleshooting" documentation page; Stonefish cable documentation; arXiv 2508.02264 (Gazebo tether). Items marked **[snippet]** come only from search-result snippets/abstracts and were not verified in full text. mdpi.com returned HTTP 403 and nrel.gov was not reachable from this session, so the MoorDyn theory papers (Hall & Goupee 2015; Hall et al. 2020 bending) and DNV-RP-C205 were not read in full.

## 1. Modelling approaches and their trade-offs (lumped mass, finite difference, FE, ANCF, catenary, PBD)

### Takeaway
The lumped-mass-and-spring (LM) method is the predominant ROV-tether method because it stays numerically well-posed when tension goes to zero and is cheap; finite-difference continuum schemes (Ablow & Schechter 1983) treat tension as an unknown and become singular in slack; FE/cubic-spline/DG methods add bending/torsion and allow larger elements at higher per-element cost. Real-time tether models reported in the literature are LM (often with implicit or Generalized-α integration) or game-engine constraint/segment chains; quasi-static/catenary models are known to under-predict dynamic loads.

### Cited Findings
- **Lumped mass (LM) formulation used in a recent ROV simulator (BlueROV2, Simulink):** cable idealised as n+1 lumped masses joined by n weightless cylinders; p0 = base (possibly moving), pn = ROV attachment. Equation of motion `M_t v̇_t + D_t v_t + k_t = 0`; node mass `M_t,i = ½(M_{i-1} + M_i + M_a,i-1 + M_a,i)` (structural + added mass of the two adjacent cylinders); internal damping `P_i = C_t ((v_i − v_{i−1})·r_i/|r_i|) r_i/|r_i|`; tension `T_i = E_t A_t,i / l0,i · r_i (1 − l0,i/|r_i|)`; the tether force on the ROV is the end-node axial tension; tether assumed neutrally buoyant so external force is only drag — [von Benzon et al. 2022, JMSE 10:1898](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- Same paper: "An implicit solver is recommended due to stiffness in the system of equations, e.g., ode15s in Simulink"; tether lengths in examples 15 m and 35 m; it notes that Gazebo's UUV Simulator and similar simulators neglect the tether force — [von Benzon et al. 2022](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- Note: the drag expressions in that paper (eqs. 31–32) are written as `½ ρ d C v|v| |r_i|` for both normal and tangential components, i.e. the tangential term uses diameter×length rather than wetted perimeter πd×length. Some other references define Ct on wetted area (see §3). Unit table A1 values for the tether were not extractable from the PDF text — [von Benzon et al. 2022](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- **Finite difference (Ablow & Schechter 1983):** equations for a differential segment written in a body-fixed frame with compatibility relations; FD in both space and time; Newton–Raphson for velocity, orientation and tension at knots; implicit in time, which increased allowable time step. Because tension is an unknown, "when the cable enters a slack regime of motion and the cable tension goes to zero, the algebraic equations ... become singular" (Howell; Triantafyllou & Howell showed adding bending stiffness removes the singularity; Burgess FD with bending for cable laying) — [Buckham 2003 thesis, §1.3.2 and §2](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- In LM, tension is an explicit function of node positions, so at zero tension "the calculated tension is simply zero and no constraint forces are applied"; LM "is numerically stable during low-tension instances"; Huang & Vassalos used a bi-linear (no-compression) EA for alternating taut/slack — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- But for **extended low tension**, Buckham reports the plain LM results "suffer dramatically" despite bi-linear EA, motivating bending terms (Banerjee & Do rotational springs; Buckham's discrete bending model; then a twisted cubic-spline higher-order element) — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- LM vs finite segment (rigid links with distributed mass and rotational equations): Ketchman and Kamman & Huston found LM gave equivalent accuracy at significant computational savings, attributed to the large ratio of hydrodynamic to inertial terms underwater — [Buckham 2003, §1.4.2](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Buckham's higher-order (cubic) element allows element size increases of 35–50 % over the revised linear LM and cuts execution time by up to 70 %; it halves the state variables needed — [Buckham 2003 abstract](https://dspace.library.uvic.ca/handle/1828/3644)
- Driscoll's FE-derived LM: consistent-mass matrix replaced by a lumped-mass matrix to uncouple accelerations; RK4(5) adaptive integration; the continuous (analytical) model "is invalid for slack tether and inherently unable to predict snap loads", whereas the discrete model reproduced snap loads — [Driscoll 1999 thesis](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- Palm & Eskilsson list bending-capable solvers in the literature: finite differences, lumped masses, linear FE, curved elements, cubic splines and iso-geometric mapping; they add bending as a rotation-free nested local DG term in the hp-adaptive DG solver "Moody" with explicit 3rd-order SSP Runge–Kutta — [Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- **Quasi-static vs dynamic:** Hall & Goupee (2015) found a quasi-static mooring model significantly under-predicts mooring loads, especially fatigue loads; their lumped-mass MoorDyn was judged suitable — **[snippet/abstract]** [Hall & Goupee 2015 record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_osti_scitechconnect_1459757). (Mooring application, heavy lines.)
- **Catenary hybrid in Gazebo:** arXiv 2508.02264 uses an inextensible catenary `z(x)=a cosh((x−c)/a) − a cosh(c/a)`, with `L = a[sinh((D−c)/a)+sinh(c/a)]`, for static shape, plus a Gazebo chain of buoyant spheres joined by ball joints (joint_damping = 0.05, joint limits ±1.5 rad) for dynamics; no drag coefficients, stiffness or validation reported — [arXiv 2508.02264](https://arxiv.org/html/2508.02264v1)
- **Stonefish:** cable is a soft body between two ends divided into `number_of_segments` (example 100) with `diameter` (example 0.01 m), material density, `stretch_factor` in [0,1] that is "not a physical quantity" and must be tuned to update rate and attached masses; no cable–cable or self-collision; drag model not documented — [Stonefish docs](https://stonefish.readthedocs.io/en/latest/cables.html)
- **Game-engine / PBD:** an Unreal Engine 4 underwater-cable paper uses constraints / position-based models (Jakobsen-style Verlet) for a long many-segment cable to reach real time — **[snippet]** (PDF returned 503) [Ganoni, ZČU](https://dspace.zcu.cz/bitstream/11025/34656/1/Ganoni.pdf)
- **Real-time LM in an ROV training simulator:** COBEM 2009 paper built an ROV training simulator in MSC.Adams with the tether discretised into 200 pieces — **[snippet]** [COBEM 2009](https://www.abcm.org.br/anais/cobem/2009/pdf/COB09-0141.pdf)

### Inferences
- For a host-authoritative 0.01 s fixed-step simulator, LM with tension-only springs is the literature-standard choice; what distinguishes "good" implementations is (a) explicit handling of slack, (b) a small bending term for low-tension shape, (c) axial stiffness/integration chosen so the axial mode is stable, and (d) normal/tangential Morison drag with relative velocity.
- ANCF was not covered by any source I could read; no ROV-tether ANCF validation was found (see Gaps).

### Gaps
- Ablow & Schechter (1983) original equations not read in full; only described via Buckham.
- No full text found on ANCF applied to ROV tethers, nor on XPBD/PBD tether accuracy versus LM.
- Hall & Goupee (2015) and Hall et al. (2020, MoorDyn bending) full texts were unreachable (nrel.gov blocked; MDPI 403).

## 2. Governing physics: EA, EI, torsion, slack, internal damping; typical small-tether values

### Takeaway
Axial stiffness dominates when taut, but small ROV tethers live at low tension, where transverse (bending) forces are of the same order as tension and bending/torsion change the shape and ROV disturbance. Measured small-tether values: EA ≈ 23.5–217 kN, EI ≈ 0.12–0.25 N·m², GJ ≈ 0.11 N·m² for 13.6–19 mm tethers; tension-only (bi-linear) elasticity is universal.

### Cited Findings
- **Small ROV tether, pool test (Buckham):** d = 0.0136 m, ρc = 1643 kg/m³, length 3.70 m, EA = 23.5 kN, EI = 0.1241 N·m², normal Cd = 1.25 (fitted; Cd between 1.0 and 2.0 "produced minimal variation") — [Buckham 2003, Table 3.4](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- **Small ROV tether, 3D manoeuvre (Buckham, FALMAT TPE-sheathed tether):** d = 0.019 m, L = 6.55 m, EA = 217 kN, EI = 0.25 N·m², GJ = 0.11 N·m², viscous damping C_ID = 437 N·s; tether density 1000 kg/m³ (neutral); normal Cd = 1.649. EI and GJ were computed from the sheath only because conductors slipped inside the sheath; a Hydrocable tether with tighter packing suggested higher torsional stiffness on other platforms — [Buckham 2003, Tables 5.1, 5.3, §5.6](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Torsion: "Inclusion of a non-zero torsional stiffness produced a resolution of significant tether motions" not captured by previous models; however the real ROV behaved more like GJ = 0 because the termination at the ROV (connector) was flexible in twist — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Low-tension cables: Buckham et al. showed transverse and axial forces are of the same magnitude; "Cable model developers generally agree that models require bending stiffness to produce accurate and stable simulations of the low-tension cable position" — [Palm & Eskilsson 2020, §1](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Bending as shear force: moment `M = GIp Ω1 î + î × (EI κ + ξ_b κ̇)`; tension law `T(ε, ε̇) = EA·max(ε, 0) + ξ ε̇` (no compression); torsion excluded in their simulations — [Palm & Eskilsson 2020, eqs. 18, 22](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Implicit schemes' Jacobian becomes singular in free-fall slack; "a small artificial bending stiffness is often recommended" for chains; explicit simulations typically stay stable in slack but time step can become prohibitive for very stiff cables — [Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Bending effect magnitude in a heavy tether (ROPOS, d = 30 mm, EI* = 2.62 kN·m² assuming solid section): no noticeable effect at L = 975 m and 1730 m; small but increasing effect at 500 m and 200 m, with larger EI increasing snap-load magnitude and delaying its arrival — [Palm & Eskilsson 2020, §6.2](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Swinging neoprene cable (Koh et al. experiment; d = 25 mm, E = 3.14 MPa, EA = 1541 N, EI = 0.060 N·m², γ0 = 0.702 kg/m, Lc = 2.022 m): with EI = 0 the free end "whips" and tension at t = 2 s is significantly over-estimated; including EI and bending damping ξ_b = 0.020 N·m²·s reproduces experiments well — [Palm & Eskilsson 2020, Table 2, §5](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- **Heavy armoured tether (ROPOS, measured):** d = 3 cm, 4200 m, weight 30.5 N/m in air, MWL 200 kN, breaking 550 kN; calibrated m = 3.01 ± 0.06 kg/m, wet weight W = 25.4 ± 0.5 N/m, EA = 45.5 ± 1.4 MN (obtained from strain-wave speed measured during snap loads; consistent with c = 3870 m/s, since √(45.5e6/3.01) ≈ 3890 m/s), tangential Cd = 0.02 — [Driscoll 1999, Table 4.1, §2](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download); [Palm & Eskilsson 2020, Table 3](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf) (heavy umbilical, not a small tether)
- Internal damping: MoorDyn segment model `m = wL/N, k = 4EA·N/L`(as printed), `c = 4BA·N/L`; damping ratio `ζ = BA·(N/L)·√(1/(EA·w))`, so `BA = ζ(L/N)√(EA·w)`; recommended segment damping "approaching the critical value (ζ = 1)" to damp artificial segment resonances; entering a negative BA in MoorDyn means "−ζ" — [MoorDyn troubleshooting](https://moordyn.readthedocs.io/en/latest/troubleshooting.html)
- Armoured-cable effective modulus 77.5 GPa (Laura et al.) used for a 33.2 mm towcable (ρ = 3121 kg/m³, Cd = 1.649, damping 10 N·s), modelled with six 50 m elements and matched experimental tow profiles "very well" — [Buckham 2003, Table 2.2](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download) (heavy towcable)

### Inferences
- Axial wave speed c = √(EA/m_eff) for a small tether: with Buckham's 13.6 mm tether (m ≈ 1643·π/4·0.0136² ≈ 0.24 kg/m, EA 23.5 kN) c ≈ 310 m/s, i.e. very stiff relative to a 0.01 s step on 1–10 m segments (see §6). These are my calculations from cited values.
- EI ≈ 0.1–0.25 N·m² gives a bending length scale √(EI/T); at T = 1 N that is ~0.3–0.5 m, so bending matters within roughly half a metre of the vehicle gland or obstacles and near loops at low tension — derived, not measured.
- A twist/torsion state is only worth modelling if the ROV-end termination is twist-stiff; Buckham's pool observation suggests a flexible termination makes GJ≈0 realistic.

### Gaps
- No published EA/EI/GJ found for 5–10 mm thin observation-class tethers (Kevlar-braided, near-neutral). Values above are 13.6–19 mm research tethers.
- Twist accumulation (hockling) over many yaw turns: no quantitative source read.

## 3. Hydrodynamic loading: Morison normal/tangential drag, Cdn, Cdt, added mass, current, VIV

### Takeaway
Standard practice is independent-component Morison drag on relative velocity: normal Cdn ≈ 1.0–1.7 (fitted values 1.25–1.65 for small tethers; 1.70 measured for double-armoured cables), tangential Cdt ≈ 0.002–0.02 (skin-friction, roughness-dependent) or ~0.02 calibrated; normal added-mass coefficient 1.0, tangential 0. Strumming (VIV) amplifies effective normal drag; formula constants were not verified.

### Cited Findings
- Drag (Palm & Eskilsson): `f_d = 0.5 d ρf √le (Cd_t |v*_t| v*_t + Cd_n |v*_n| v*_n)` with v* = fluid − cable velocity; added mass + Froude–Krylov `f_a = ρf A (a_w,n + Cm_t a*_t + Cm_n a*_n)`; buoyancy `f_b = A g (ρf − ρc) ẑ` — [Palm & Eskilsson 2020, eqs. 13, 14, 17](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- ROPOS tether coefficients: CDn = 1.0, CDt = 0.02, CMn = 1, CMt = 0 — [Palm & Eskilsson 2020, Table 3](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf); Driscoll's calibration gives tangential Cd 0.02 — [Driscoll 1999, Table 4.1](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- Small tether normal Cd fitted 1.25 (sensitivity small between 1.0 and 2.0); 1.649 used for 19 mm tether and 33.2 mm towcable — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- At-sea tests on two double-armoured bare cables: normal Cd = 1.70 independent of Reynolds number — **[snippet]** [DTIC reports (search set)](https://apps.dtic.mil/sti/pdfs/ADA113478.pdf)
- A constant Cn independent of Re fits measured towing data well; Cn and Ct defined on wetted area with separate normal/tangential Reynolds numbers; Casarella & Parsons (1970) show the sine-law/angle model agrees with experiments for round cables — **[snippet]** [DTIC ADA113478 / related](https://apps.dtic.mil/sti/pdfs/ADA113478.pdf)
- Tangential friction drag coefficient "lie[s] within the limits 0.002 and 0.02, depending on roughness, for diameter Reynolds numbers greater than 10³" — **[snippet/abstract]** [ASCE J. Hydraulics Div.](https://ascelibrary.com/doi/10.1061/JYCEAJ.0000873)
- Stranded (helical) cables produce side force/lift when yawed; tests at Re 5,000–50,000; Pode's sine-squared law for normal force — **[snippet]** [DTIC search set](https://apps.dtic.mil/sti/tr/pdf/ADA191535.pdf)
- VIV: vortex-induced drag on vibrating structures is "amplified substantially" above the stationary case; NRL drag-amplification model implemented in NATFREQ for strumming cables — **[snippet]** [DTIC AD0654906](https://apps.dtic.mil/sti/pdfs/AD0654906.pdf), [BSEE TAP report](https://www.bsee.gov/sites/bsee.gov/files/tap-technical-assessment-program//074af.pdf). The commonly quoted form `C_D = C_D0 (1 + k (A/D)^b)` (Vandiver-type) was reported only by a search summary and is **unverified**.
- Current in the BlueROV2 benchmark: constant irrotational current (e.g. [0.21, 0.21, 0] m/s, [0.3536, 0.3536, 0] m/s); with a 35 m tether during a monopile inspection the tether force averaged 21.1 N (25 % of max thrust) in x, 19.3 N in y, 12.2 N in z, with the top 5 % averaging 31.9 / 28.7 / 21.2 N (38 / 34 / 18 % of max thrust) — [von Benzon et al. 2022, Table 9](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf) (simulated, not measured)

### Inferences
- Because drag on a long tether dominates over inertia for small ROVs (Kamman & Huston argument), Cdn and the current profile are the parameters that most change the ROV disturbance; Cdt matters mainly for long tethers and snap damping.
- If the simulator writes tangential drag as ½ρ d Cdt v|v| ℓ (projected-area convention) a literature Cdt defined on wetted area must be multiplied by π.

### Gaps
- DNV-RP-C205 drag/added mass tables (roughness-dependent Cd vs Re) not read in full.
- No verified quantitative VIV drag-amplification formula or factor for small jacketed tethers.

## 4. Snap loads

### Takeaway
Snap loads occur when a slack section is rapidly re-tensioned while the end mass and cable move apart; they appear as a strain wave travelling at c = √(EA/m) with reflections. Continuous/FD tension-unknown models cannot represent slack; LM/DG with tension-only elasticity can, but threshold events are very sensitive to forcing amplitude.

### Cited Findings
- Mechanism and signature (ROPOS, measured at sea): at the instant slack disappears, cage inertia induces large strain; the wave propagates at the longitudinal sound speed and reflects at the ends, giving regularly spaced jerks at the cage and delayed tension spikes at the ship; the cage was accelerated by up to 0.5 g; the peak tension did not exceed working limit, but tether was bent beyond minimum bend radius at the cage termination (likely fibre damage) — [Driscoll 1999, §2.3](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- Snap loads occurred in < 1 % of motion cycles; the calibrated model did not reproduce them with recorded ship motion; increasing ship motion by 10 % reproduced snap loads "and all the associated characteristics" — [Driscoll 1999, §4.2](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download). Palm & Eskilsson needed +20 % amplitude with DG and changed cage vertical Cd from 2.3 to 2.7 — [Palm & Eskilsson 2020, §6.1](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Propagation: L/c = 0.445 s for 1730 m, c = 3870 m/s; snap is damped by internal damping ξ (45.5 kN·s/m used) and tangential drag; simulated peaks were longer-lived than measured, suggesting higher damping; tension peaks in Fig. 4 reach roughly 140–150 kN at the ship (read from plot axes) — [Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Slack-snap occurred for a 2 m-radius circular fairlead orbit at 0.2 and 0.25 Hz but not at 0.1 Hz, confirming Driscoll's analytical criterion — [Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- Compliance eliminates snaps: a passive compensator made re-tensioning gradual and "eliminated all snap loads" in simulated operating conditions — [Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)

### Inferences
- For a small near-neutral ROV tether driven by a light vehicle, snap peaks scale with vehicle momentum × c; with softened EA in a game simulator, c drops and snap peaks drop correspondingly, so peak-tension events (and "tether break" scoring) will be under-predicted unless compensated.

### Gaps
- No measured snap magnitudes for small (≤ 20 mm) observation-class ROV tethers found.

## 5. Contact and friction: seabed, structures, capstan, entanglement

### Takeaway
Published ROV/mooring codes model seabed contact as a vertical spring-damper with regularised Coulomb friction; tether-structure contact in ROV simulators is mostly a normal repulsion without friction. No source read applies the capstan equation to ROV tethers.

### Cited Findings
- Seabed contact (Moody/DG): vertical bilinear spring-damper `f_c,z = √le K_g d δ − ξ 2√(K_g d γ0) v_z` (K_g ground bulk modulus, ξ = 1 critical); horizontal friction `f_c,xy = −√le μ tanh(π|v_xy|/v_μ) (v_xy/|v_xy|) min(f_b,z, 0)` (regularised Coulomb up to threshold speed v_μ) — [Palm & Eskilsson 2020, eqs. 15–16](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf) (sign conventions as printed in the paper)
- UNB/UVic tethered-vehicle simulation: collision detection of tether with environment and with itself via global combinatorial then local optimisation for closest points; a separating force is applied at the contact site; no friction mentioned — [UNB RAM lab page](https://ram.ext.unb.ca/research/simulation/tethered_vehicles_simulations.html)
- Continuous collision detection for cubic-spline tethers in ROV simulations applies a contact force and ignores tangential (friction) forces — **[snippet]** [CCD of cubic-spline tethers](https://www.bohrium.com/paper-details/continuous-collision-detection-of-cubic-spline-based-tethers-in-rov-simulations/811830082652864514-97764)
- Entanglement-aware planning (REACT) uses a signed-distance-field tether model of taut configurations around structures — **[snippet]** [arXiv 2507.10204](https://arxiv.org/html/2507.10204v1)
- Stonefish cables collide with bodies/links but not with themselves or other cables — [Stonefish docs](https://stonefish.readthedocs.io/en/latest/cables.html)

### Inferences
- A per-node contact with Coulomb friction (μ) on a densely discretised LM chain reproduces capstan behaviour (T_out/T_in = e^{μθ}) only if node spacing is small relative to the wrap radius; this is standard mechanics, not taken from a cited tether paper.

### Gaps
- No ROV-specific measured friction coefficients (tether jacket on steel/concrete/seabed) found; no validated entanglement model found.

## 6. Numerical stability: time step, implicit vs explicit, real-time strategies

### Takeaway
The axial segment mode sets the explicit limit: ω_n = 2(N/L)√(EA/w) (MoorDyn), so Δt must be well below 2π/ω_n; small-tether research codes used 0.1–1 ms with RK4. Implicit/Generalized-α allows 10–50× larger steps but Jacobian cost grows with element count. Game engines use constraint/PBD chains with non-physical stiffness parameters.

### Cited Findings
- MoorDyn: "Δt < 2π/ω_n", Δt "should be significantly smaller than the natural period", chosen from the shortest natural period of any line; `ω_n = √(k/m) = 2(N/L)√(EA/w)`; near-critical segment damping recommended — [MoorDyn troubleshooting](https://moordyn.readthedocs.io/en/latest/troubleshooting.html)
- Buckham 3.70 m tether with 0.2–0.29 m elements needed Δt = 0.4 ms; 60 s manoeuvre took 129 s CPU on a PIII 700 MHz ("to capture the entire bandwidth of node motion produced by the high stiffness of the shortest tether elements") — [Buckham 2003, §3.5.4](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Equal-accuracy step sizes, 6.55 m tether: RK4 1.0 / 0.5 / 0.4 / 0.25 / 0.2 / 0.1 ms vs Generalized-α 22.5 / 20 / 15 / 12.5 / 10 / 5 ms for N = 5 / 10 / 15 / 20 / 25 / 30 elements; Generalized-α ran ~2× faster up to 20 elements, but at 30 elements Jacobian cost erased the gain; real time was reached only up to ~10 elements of 0.655 m on a 1.0 GHz Athlon — [Buckham 2003, Table 5.4, §5.5](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Radanovic & Driscoll: Generalized-α ran in one fifth of the RK-Fehlberg time for a towed system and achieved real time with up to 27 elements of 2–10 m — [cited in Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Generalized-α was the only integrator (vs backward differences, trapezoidal) giving bounded solutions for the hanging chain in FD models (Gobat & Grosenbaugh) — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Burgess found elements of 1 % of total scope were required in a FD low-tension model — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- Stonefish's elasticity is a soft-body `stretch_factor` that must be tuned against update rate and attached mass (i.e. stiffness is not physical) — [Stonefish docs](https://stonefish.readthedocs.io/en/latest/cables.html)

### Inferences
- Worked example (my calculation from cited formula): w = 0.24 kg/m (plus added mass ≈ ρπd²/4 ≈ 0.15 kg/m → 0.39 kg/m), EA = 23.5 kN, 1 m segments: ω_n ≈ 2√(23500/0.39) ≈ 490 rad/s, natural period ≈ 13 ms. A 10 ms explicit step is unstable; symplectic Euler needs Δt < 2/ω_n ≈ 4 ms, so ~4–10 substeps per 0.01 s step, or EA softened. Softening EA by factor s lowers c and ω_n by √s, raising static stretch by s; that error is negligible under ~10–100 N tension for EA ≥ ~1 kN but distorts snap peaks (§4).
- Near-critical per-segment damping (MoorDyn rule BA = ζ(L/N)√(EA·w)) is a principled replacement for ad-hoc damping constants.

### Gaps
- No published error quantification of PBD/XPBD tethers against LM or experiments was found.

## 7. Validation against experiments

### Takeaway
Validated agreement for tether models is typically qualitative-to-~10–20 %: Driscoll's LM within ~11 % for cage motion (RMS-like), the analytical model within 20 %; Buckham's small-tether profiles match pool video "very well"; MoorDyn matches tank data and OrcaFlex closely. Constant Cd/added-mass assumptions limit accuracy for oscillating end bodies.

### Cited Findings
- ROPOS (sea trial, 1730 m): FE/LM model accurately predicted cage motion, ship-end tension and natural frequencies, with a "small (~11 %) disagreement between the real and predicted cage motion" not explainable by parameter uncertainty; adding a wake (history) model made the transfer functions "nearly identical within the wave-band" — [Driscoll 1999, §4.2](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- Driscoll's analytical model: displacement and tension "generally agree ... within 20 % error"; LM better "but with less than a factor of 2 improvement" — **[snippet]** [wavelet paper page](https://www.bohrium.com/paper-details/a-wavelet-for-predicting-the-time-domain-response-of-vertically-tethered-systems/811176071788494848-3885); fitted continuous-model non-dimensional parameters differed by 14 % and 16.5 % from empirical values — [Driscoll 1999](https://dspace.library.uvic.ca/bitstreams/344a09ed-0d13-4b3f-8997-b3562f915d69/download)
- Buckham small-tether planar manoeuvre: trailing-end motion at 2 s intervals "matches the simulation output very well"; 3D pool manoeuvre in 12.7 × 9.0 × 4.6 m pool with USBL at ~0.23 Hz and 6.8 m ShapeTape (bend/twist sensing drifted) — [Buckham 2003](https://dspace.library.uvic.ca/bitstreams/2ea4fde6-8013-4cc8-ac1d-eec31d9db23f/download)
- MoorDyn vs DeepCwind tank data and vs OrcaFlex: "largely equivalent" to OrcaFlex (Wendt et al.); Paduano et al. 2020 found good agreement for a floating WEC when fairlead motions imposed — **[snippet]** [NREL 65822](https://www.nrel.gov/docs/fy16osti/65822.pdf), [JMSE 2020 record](https://doaj.org/article/38c1adef99994ab0a202ff57cc75dffd) (mooring application)
- Palm & Eskilsson DG: Koh swinging-cable experiment reproduced well with EI; mesh error in tension < 1 % between N = 7 and 10 — [Palm & Eskilsson 2020](https://research.chalmers.se/publication/520017/file/520017_Fulltext.pdf)
- BlueROV2 benchmark validated the vehicle hydrodynamics (pool 1.15 m deep, 6.1 m diameter; pitch/yaw error 10 % / 12 %) but the tether model itself was not validated experimentally — [von Benzon et al. 2022](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- A 2017 Japanese study (JASNAOE) compared an LM tether estimate with tank experiments — **[snippet]**, results not read [J-STAGE](https://www.jstage.jst.go.jp/article/jjasnaoe/25/0/25_143/_article/-char/ja/)

### Inferences
- A realistic acceptance target for a training simulator tether is shape/tension trends within ~10–20 % against tank data; tighter claims are not supported by published ROV-tether validations.
- Relevant to this repository: `simulator/qysim/tether.py` already implements the literature-standard elements (tension-only springs with axial damping, normal/tangential drag with depth-dependent current, added mass, wet weight); its provisional values (9.5 mm, 350 m, 300 kgf) are reseller figures, not measurements, consistent with AGENTS.md.

### Gaps
- No experimental validation for thin (<10 mm) observation-ROV tethers at lengths of 100–300 m was found.
- Driscoll, Lueck & Nahon (2000) numerical tension error statistics only available qualitatively.
