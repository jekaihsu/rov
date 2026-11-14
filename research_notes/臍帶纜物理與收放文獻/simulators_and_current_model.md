# ROV tether models: existing simulators vs. this repository's tether model

Scope: (A) how open-source and commercial ROV/marine simulators model tethers and topside handling; (B) exactly how `simulator/qysim/tether.py` works today; (C) ranked gaps. Repository facts are cited as `file:line` (paths relative to `/home/user/rov/`). Web facts carry links. Anything marked **[inferred]** is my own reasoning or calculation, not a sourced fact. Numbers labelled **[local run]** come from a throw-away script run against the unmodified repo (`/tmp/claude-0/.../scratchpad/exp.py`). No repository file was modified.

## Q1. How do open-source simulators and physics engines model tethers and cables?

### Takeaway
The engineering reference is the lumped-mass, Morison-drag model used by MoorDyn. It is the same family as this repository's model, but MoorDyn adds near-critical per-segment damping set from EA, CFL-based time-step selection, optional bending stiffness, a seabed pressure/friction model and actuated line length. Its v1 formulation is validated against tank tests. The robotics simulators are much weaker. UUV Simulator's "umbilical" is a single drag force on the vehicle. Stonefish uses a Bullet soft-body rope whose stretch factor is not physical. Gazebo tether work uses ball-jointed rigid links. I found no tether model documented for DAVE or HoloOcean. Chrono offers proper FEA cables (ANCF), with torsion available only in other beam elements. Game PBD/XPBD ropes need extra "long range attachment" constraints to stay inextensible over long lengths.

### Cited Findings

**MoorDyn (Matt Hall; MoorDyn-C v2 / MoorDyn-F)**
- Method: a line is split into N equal segments connecting N+1 nodes, indexed from the anchor. Each segment has the same unstretched length, diameter, density and Young's modulus — [MoorDyn docs, structure.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/structure.rst)
- Hydrodynamic loads are computed at the nodes, not at segment centres, "This ensures damping of transverse cable vibrations having a wavelength of twice the cable segment length". The node tangent is the average of the two adjacent segment directions — [structure.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/structure.rst). (This repo uses the same central-difference tangent, `simulator/qysim/tether.py:233-236`.)
- Hydrodynamics follow a version of the Morison equation — [MoorDyn references.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/references.rst). The line-type table carries separate normal and axial added-mass and drag coefficients (Can, Cat, Cdn, Cdt). Example nylon line: Diam 0.124, EA 2,515,288 N, BA/-zeta −0.8, Can 1.0, Cat 0.0, Cdn 1.6, Cdt 0.05 — [MoorDyn inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)
- v2 adds 6-DOF objects, non-linear tension, wave kinematics, bending stiffness, bathymetry and seabed friction — [references.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/references.rst)
- Bending stiffness (EI, N·m²) exists only in MoorDyn-C, "not yet implemented in MoorDyn-F". A line with nonzero EI is called a "cable" — [structure.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/structure.rst). EI implementation and verification: Hall, Sirnivas & Yu, ASME IOWTC 2021 — [references.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/references.rst)
- Non-linear and visco-elastic axial stiffness is supported. Fibre ropes can have static and dynamic EA, with `EA_d = EA_Dc + EA_D_Lm * mean_load`. Stress–strain and stress–strain-rate lookup tables are also available — [inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst), [structure.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/structure.rst)
- Internal damping and stability: the highest axial mode of the lumped chain has m = wL/N, k = 4EA·N/L and ω_n = 2(N/L)·√(EA/w). A damping ratio "approaching the critical value (ζ=1) is recommended" to kill this non-physical segment resonance. Entering a negative BA makes MoorDyn compute BA = ζ(L/N)√(EA·w) per line. For stability "Δt < 2π/ω_n", and the time step is global, so it is set by the stiffest line — [MoorDyn troubleshooting.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/troubleshooting.rst)
- Time integration: the default is RK2 in both C and F. MoorDyn-C also offers Euler, local-time-step Euler, Heun, RK3/4, AB2–4 and implicit schemes (BEuler, Midpoint, ACA, Wilson). The docs note explicit schemes are simpler but "more unstable" — [MoorDyn tschemes.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/tschemes.rst). Default dtM is 0.001 s in the classic input format. MoorDyn-C can instead derive dt from a CFL factor (default 0.5) and uses the smaller of the two — [inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)
- Seabed contact is a penalty pressure. kBot = 3.0e6 Pa/m and cBot = 3.0e5 Pa·s/m are applied over d·l of each contacting segment, giving a vertical force. Friction is set by FrictionCoefficient (default 0), FricDamp (200; ramps from zero friction at zero velocity to full friction at large velocity) and StatDynFricScale (static/dynamic ratio). Bathymetry comes from SeafloorFile — [inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst). Friction theory: Hall EWTEC 2017, Devries & Hall 2018, Housner et al. (bathymetry and friction) — [references.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/references.rst)
- Initial conditions come from dynamic relaxation with drag scaled by CdScaleIC (5.0), or from MoorDyn-C's newer stationary solver, until tensions converge (threshIC 0.001, TmaxIC 120 s) — [inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)
- Variable length / payout: MoorDyn-F active tension control lets ServoDyn/Simulink drive line length through deltaL and deltaLdot control channels assigned to lines — [inputs.rst "Control"](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst). Line failure (disconnection at points) is also supported — [inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)
- Validation: the v1 lumped-mass formulation was validated against DeepCwind semisubmersible model-test data (Hall & Goupee, Ocean Engineering 104:590–603, 2015) — [references.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/references.rst), [ScienceDirect](http://www.sciencedirect.com/science/article/pii/S0029801815002279) (full text 403 to me; agreement metrics not read)

**von Benzon et al. 2022, BlueROV2 benchmark (MATLAB/Simulink, open source)**
- The tether is "n + 1 lumped masses connected together by n weightless cylinders". p0 is the base (possibly time-varying, p0 = p_b(t)) and p_n is attached to the ROV. Node mass is the average of adjacent masses plus added mass. Internal damping is Ct·(relative velocity projected on the segment). Tension is Ti = Et·(At/l0)·ri·(1 − l0/|ri|), and the tether is "assumed to be neutrally buoyant", so the only external force is normal plus tangential quadratic drag. The tether acts on the ROV as the end-node axial tension — [von Benzon et al., JMSE 10:1898, §6](https://doi.org/10.3390/jmse10121898) ([AAU PDF](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf))
- The published tension equation has no `max(0,·)`, so it would also push in compression. **[inferred from Eq. 36]** That differs from MoorDyn and from this repo, which are tension-only.
- Passive test: 15 m tether, current [0.3536, 0.3536, 0] m/s. The tether straightens after about 30 s, the ROV is near the surface after about 100 s, and forces are constant after 150 s, peaking around 30 N — [same, Figs. 8–9](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- Inspection case study: current [0.21, 0.21, 0] m/s and 35 m tether. Mean absolute tether force is x 21.1 N (25% of max thrust), y 19.3 N (23%), z 12.2 N (10%). The mean of the top 5% is 31.9 N (38%) in x. These are model results; only the vehicle hydrodynamics were tank-validated — [same, Tables 8–9](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)
- The paper says Gazebo/UUV-Simulator tether models are user-defined, which makes them "challenging to use as a benchmark", and that many simulators "neglect the tether force" — [same, §1](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)

**UUV Simulator (Gazebo) `UmbilicalPlugin`**
- The plugin reads `umbilical_model` and `flow_velocity_topic` from the SDF. The only registered model is `"Berg"`. Its `OnUpdate` computes the relative flow at the connector link and applies `F = 0.25·1.2·ρ·(u|u|, v|v|, 0)` to that link — [UmbilicalModel.cc (raw source)](https://raw.githubusercontent.com/uuvsimulator/uuv_simulator/master/uuv_gazebo_plugins/uuv_gazebo_plugins/src/UmbilicalModel.cc), [UmbilicalPlugin.cc](https://raw.githubusercontent.com/uuvsimulator/uuv_simulator/master/uuv_gazebo_plugins/uuv_gazebo_plugins/src/UmbilicalPlugin.cc)
- The code reads `diameter` and computes depth `h`, but neither appears in the force line. So the "umbilical" is a horizontal drag force on the vehicle only, with no cable geometry, no tension, no contact and no payout **[inferred from source]**. The plugin header also links segments for a visual chain — [UmbilicalPlugin.hh docs](https://docs.ros.org/en/kinetic/api/uuv_gazebo_plugins/html/UmbilicalPlugin_8hh_source.html) (page blocked by bot protection for me; segment detail unverified).

**Project DAVE / HoloOcean**
- DAVE is built on UUV Simulator and WHOI ds_sim. Its model list covers ROVs, gliders and UUV Simulator vehicles — [DAVE docs](https://field-robotics-lab.github.io/dave.doc). I found no DAVE tether plugin beyond the UUV Simulator umbilical it inherits.
- A 2025 review of underwater simulators (Stonefish, DAVE, HoloOcean, MARUS, UNav-Sim) reports no tether modelling for any of them — [Aldhaheri et al., arXiv 2504.06245](https://arxiv.org/html/2504.06245v1) (as cited in `docs/reference/real-rov-research.md:130`)

**Gazebo tethered multi-robot work (2025)**
- The tether is "a series of buoyant spheres (or buoy segments) connected by ball joints" with near-neutral buoyancy. Example joint limits are ±1.5 rad and joint_damping 0.05. It is assumed "inextensible and flexible", with an analytic catenary for the static shape. No winch or payout; lengths tested were 5, 10 and 15 m. The authors say accurate tether modelling in Gazebo "requires significant customization" — [arXiv 2508.02264](https://arxiv.org/html/2508.02264v1)

**Stonefish (Bullet-based)**
- A cable is a soft body between two world points, "divided into a specified number of segments" (example: 100). Mass comes from diameter and material. Elasticity is a `stretch_factor` in [0,1] "passed directly to the soft body configuration of the physics engine". The docs say this is not a physical stretch fraction and must be tuned for the update rate and attached masses. Ends can be free, attached to the world or attached to a dynamic body; robot links need an intermediate body. Cables collide with bodies and links, but "cable-to-cable and self-collisions are not supported". Bending and hydrodynamic details are not documented beyond `physics="submerged"` and `buoyant="true"` — [Stonefish docs: Cables](https://stonefish.readthedocs.io/en/latest/cables.html)

**Project Chrono (FEA)**
- `ChElementCableANCF` is "a fast element for the simulation of thin beams (cables, wires, ropes)". It is an ANCF large-displacement element with position-plus-gradient nodes and a section of A, I, E, density and damping. It "Does not model torsional stiffness". `ChElementBeamEuler` (corotational, G and J) or `ChElementBeamIGA` (Cosserat) are used when torsion matters — [Chrono FEA elements manual](https://api.projectchrono.org/manual_fea_elements.html). `ChBuilderCableANCF::BuildBeam(mesh, section, N, A, B)` builds N elements between two points — [API](https://api.projectchrono.org/classchrono_1_1fea_1_1_ch_builder_cable_a_n_c_f.html). An ANCF validation report exists — [Chrono ANCF validation](https://www.projectchrono.org/assets/validations/FEA/ancfBeamValidation.pdf)

**Game physics: PBD / XPBD ropes**
- Long range attachments (LRA) constrain the distance from attachment points to particles. They are an efficient way to enforce global inextensibility in PBD, starting from the single-rope case — [Kim, Chentanez & Müller 2012](https://matthias-research.github.io/pages/publications/sca2012cloth.pdf)
- Local constraint solves propagate corrections slowly, which hurts convergence for long chains — [Eurographics CGF 2024](https://diglib.eg.org/bitstream/handle/10.1111/cgf15186/v43i8_cgf15186.pdf). A Jacobi XPBD rope struggles to satisfy distance constraints as it nears tension; a Thomas (tridiagonal) direct solve keeps the length exact — [Liu et al. 2022, arXiv 2202.09714](https://arxiv.org/pdf/2202.09714). "Cable Joints" (Müller et al. 2018) models cables wrapping over rigid bodies as joints rather than particles — [Eurographics](https://diglib.eg.org:443/handle/10.1111/cgf13507)

### Inferences
- Typical choices across tools: MoorDyn uses tens of segments per line with dt ≈ 1 ms, RK2 and ζ near 1. Stonefish's example uses 100 segments. Gazebo uses rigid links with joint damping. **[inferred]**
- None of the open robotics simulators I could read models payout or a winch with dynamics. MoorDyn-F does, through deltaL/deltaLdot control.
- The repository's approach (lumped mass, tension-only spring, normal/tangential Morison drag, node contact) is closer to MoorDyn and von Benzon than any robotics simulator. Its gaps are in parameter choice, stiffness softening, contact and topside handling, not in the basic method.

### Gaps
- I could not read Hall & Goupee 2015 (403), so I have no quantitative validation metrics or segment counts from it. MoorDyn line-line contact is not documented in the pages I read; I found no evidence it exists in general form.
- I could not read the HoloOcean docs directly. The "no tether" claim rests on the 2025 review.
- PhysX/Bullet-specific cable APIs (PhysX articulation-based ropes, Bullet btSoftBody rope parameters) were not researched beyond Stonefish's Bullet usage.

## Q2. What do commercial ROV training simulators say about tether, TMS, winch, tension display and entanglement?

### Takeaway
Vendors market "dynamic tether", tether collision and entanglement, TMS and vessel/crane coupling, and instructor-controlled tether effects. I found no published method, segment count, time step or validation data for any of them. Their observable feature set is the benchmark for training realism: TMS and winch payout coupled to crane and vessel, current acting on the tether, collision and snagging, instructor fault injection, and replay.

### Cited Findings
- Forum VMAX: product claims include a "dynamic cable system", "realistic object hydro dynamic physics", in-scenario vessel and crane dynamics, adjustable friction, and a scenario library for "tether management, access evaluation and manipulator control" — [Forum/FET VMAX](https://f-e-t.com/?p=2974) (now 404; content via search snippet and `docs/reference/real-rov-research.md:130`). Forum also sells TMS hardware, which "stores and deploys the ROV tether cable" and decouples the ROV from vessel motion — [Forum TMS](https://f-e-t.com/?p=2929)
- Fugro DeepWorks (with Kongsberg): umbilical payout from the launch-system sim "is passed to DeepWorks ROV, which simulates lowering the TMS". If the crane operator "winches in the ROV umbilical unexpectedly, the pilot sees his ROV pulled in response". It also offers 3D current profiles that change mid-mission and act on the tether, plus whole-world rewind — [Hart Energy / E&P](https://hartenergy.com/exclusives/rov-simulation-training-tool-cuts-operational-costs-and-risks-18642) (403 to me; quotes via search snippet and the repo's earlier research)
- GRi VROV: its GRiP physics engine provides dynamic tether modelling and collision detection and interaction. It has offered "fully interactive tether dynamics since 1999", and its reputation rests partly on "interactive tether collision and dynamics". It claims IMCA Class A and DNV GL certification. The instructor console changes current, turbidity and tether effects and injects faults — [GRi VROV overview](https://grisim.kayako.com/article/19-virtual-remotely-operated-vehicle-overview) (404 now; via search snippet), [Inspenet](https://inspenet.com/en/?p=320302), [MarineTechnologyNews](https://www.marinetechnologynews.com/news/seabot-maritime-simulations-frontier-661007)
- ROVsim O&G (Marine Simulation): the ROV is deployed by a TMS cage from a simulated support ship. The instructor controls the environment, ship and cage — [Hydro International 2009](https://www.hydro-international.com/content/news/rov-simulator)
- Real topside winch tension displays (research vessels) provide a tension bar graph plus configurable high-tension and low-payout alarms — [UNOLS RVTEC doc](https://www.unols.org/sites/default/files/201011rvtap21b.pdf) (via search snippet)
- Real small-ROV tether data (VideoRay MSS): tether breaking strength is 450 kg (Kevlar), but **connectors break at 80 kg** and the strain relief at 136 kg. Working load should not exceed half the breaking strength. Neutral and Performance tethers are "near neutral buoyancy in fresh water"; the Negative tether sinks and connectors sink slightly. Minimum bend radius is 82.5–114 mm — [VideoRay tether specs](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html)
- Operator practice: use the shortest tether; excess tether "acts like a sail"; a coiled tether keeps twist, and each twist puts torque on the vehicle; never pull a snagged tether, fly back to the snag point instead — [VideoRay tether management](https://download.videoray.com/documentation/pro_4/html/oper_tether.html), [VideoRay snag procedure](https://download.videoray.com/documentation/mss/html/emergency_snag.html) (as summarised in `docs/reference/real-rov-research.md:96`). IMCA SF 02/23: the tether chafed on a jacket, lost power, then parted the next day — [IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)

### Inferences
- For an observation-class ROV with a manual reel (the X1 per the reseller, `docs/reference/real-rov-research.md:11`), the analogue of "TMS/winch" is a human tether handler. The realism target is handler latency, rate and feel, plus the handler's own vessel or quay motion, not a hydraulic winch. **[inferred]**
- The VideoRay connector-versus-tether strength gap suggests the realistic failure is at the gland or connector, at loads well below cable breaking strength. **[inferred]**

### Gaps
- No vendor publishes model equations, segment counts, time steps or validation. All commercial claims are marketing or trade-press, 2009–2026.
- No public evidence on how commercial simulators display tension or entanglement in the HUD.

## Q3. Exactly how does this repository's tether model work today?

### Takeaway
The tether is a fixed 40-segment lumped-mass chain from a fixed spool point (node 0) to a kinematic gland (node 40) on the ROV. It uses tension-only springs with stiffness min(EA/l0, 9000 N/m) and ζ=0.6 axial damping, node-wise normal/tangential quadratic drag in the local current, small wet weight and Ca=1 added mass. Integration is semi-implicit Euler with 10 substeps per 10 ms tick. Contact is node-only position projection with a velocity-reducing friction rule. Wraps are measured by winding angle around near-vertical cylinders. Auto payout runs at 1 m/s when spool tension exceeds 45 N. Manual payout is instantaneous. The cable breaks above 2943 N and warns above 250 N. There is no bending, torsion, segment-edge contact, reel dynamics or vessel motion.

### Cited Findings (repository, `file:line`)

**Discretisation and mass**
- Segment count is fixed at `segments` = 40, flagged as an engineering assumption (`simulator/qysim/vehicles.py:77`). Rest length per segment is `length/segments` (`simulator/qysim/tether.py:78-80`), so segment length grows with deployed length: 350 m gives 8.75 m segments **[calc]**.
- Node mass = `mass_per_m·l + ρ·π(d/2)²·l`, i.e. dry mass plus Ca=1 added mass, applied isotropically including along the cable axis (`simulator/qysim/tether.py:148-151`). End nodes get the same mass as interior nodes. ρ = `RHO` (`simulator/qysim/tether.py:25`); the compiled path hard-codes 1025 for drag (`simulator/qysim/_cable_accel.py:43`).
- X1 values: diameter 0.0095 m and max length 350 m are reseller figures. Breaking load 2943 N (300 kgf) is also from the reseller. mass_per_m 0.12 kg/m and wet_weight_per_m 0.004 kg/m are estimates (`simulator/qysim/vehicles.py:78-82,89-94`).
- The displaced water mass of a 9.5 mm cable is ≈0.0727 kg/m. With 0.12 kg/m the wet weight would be ≈0.047 kg/m, not 0.004. `mass_per_m` (inertia) and `wet_weight_per_m` (gravity) are therefore independent and mutually inconsistent unless the cable has foam of larger diameter **[inferred/calc]**.

**Axial model**
- Tension-only spring-damper: `f = k·stretch + c·rel_v` only when stretch > 0, clipped to [0, 2·breaking_n] and NaN-sanitised (`simulator/qysim/tether.py:217-226`; compiled `simulator/qysim/_cable_accel.py:27-39`). The comment states the clip exists "so a violent yank breaks the cable instead of blowing up the explicit integrator" (`tether.py:223-224`).
- Stiffness `k = min(EA/l0, k_max)` with EA = 20000 N and k_max = 9000 N/m, both estimates (`simulator/qysim/tether.py:198`, `:169`; `simulator/qysim/vehicles.py:83-84`).
- Consequence **[calc]**: for L ≤ 88.9 m (l0 ≤ 2.22 m) the cap is active. The whole-cable series stiffness is then a constant 9000/40 = 225 N/m regardless of length, i.e. an effective EA of 225·L (2,250 N at 10 m; 9,000 N at 40 m). Beyond 88.9 m the effective EA is 20,000 N (100 N/m at 200 m). At breaking load the nominal strain would be 2943/20000 ≈ 15%.
- Damping is `c = 2·ζ·√(k·m)` with ζ = 0.6 per segment (`simulator/qysim/tether.py:199`; `simulator/qysim/vehicles.py:85`). MoorDyn recommends ζ approaching 1 and defines the mode as k = 4EA·N/L — [MoorDyn troubleshooting](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/troubleshooting.rst).
- The paper benchmark parameters (`BENCHMARK_TETHER_PARAMETERS`: d .0075, mass .043, Cdn 1.2, Cdt .01) explicitly do not reproduce the paper's axial stiffness, 6.437e10 Pa (`simulator/qysim/tether.py:342-350`; `docs/reference/t20-validation.md:19-20`).

**Bending and torsion**
- None. There is no EI term, no torsional DOF, no twist accounting and no twist torque on the ROV. The force on the ROV is pure axial tension at the gland, plus the moment of that force about the CG (`simulator/qysim/tether.py:186-191`).

**Hydrodynamics, buoyancy, current**
- Relative flow `vr = current − v` per node. Tangent = central difference (`x[i+1] − x[i−1]`), with end nodes using the adjacent segment. Normal/tangential split; drag `0.5·ρ·d·l0·(Cdn·vn|vn| + Cdt·vt|vt|)` (`simulator/qysim/tether.py:231-241`; `simulator/qysim/_cable_accel.py:43-57`). End nodes use the full `d·l0` area rather than half **[inferred from code]**.
- Cdn = 1.2 and Cdt = 0.02 are estimates (`simulator/qysim/vehicles.py:86-87`). For comparison, von Benzon uses 1.2/0.01 and the MoorDyn example nylon line uses 1.6/0.05.
- Wet weight is `wet_weight_per_m·l0·g` in +z (NED, down) (`simulator/qysim/tether.py:242`). Nodes above the waterline are not treated specially: drag and buoyancy apply even if z < 0 **[inferred: no surface check in `step`/`_substep`]**.
- Current is sampled per node every tick with `world.current.sample_many(x, seabed, t)`. The sample is held constant over the 10 substeps (`simulator/qysim/tether.py:161`). The profile is depth-dependent (surface/mid/bottom blend with a 1 m bottom boundary layer) plus gust state (`simulator/qysim/world.py:261-311`).
- Initial shape is a quadratic Bézier "bight" of arc length = `max(5, 1.25·span)` (capped at max_length), bowed down-current and 0.6 deeper (`simulator/qysim/tether.py:62-64, 96-137`). It is then relaxed for 2 s with auto payout off and velocities zeroed (`simulator/qysim/tether.py:139-146`; `simulator/qysim/engine.py:102-103`).

**Integration**
- The engine tick is dt = 0.01 s (AGENTS.md). `h = dt/substeps` with substeps = 10, so h = 1 ms (`simulator/qysim/tether.py:159`; `simulator/qysim/vehicles.py:96`). Each substep is semi-implicit (symplectic) Euler: `v += F/m·h; x += v·h` (`simulator/qysim/tether.py:244-245`; `simulator/qysim/_cable_accel.py:58-61`).
- Boundary conditions: node 0 is pinned to `spool` with v = 0. Node N is reset to `gland`/`gland_vel` at every substep (`simulator/qysim/tether.py:212-215`; `_cable_accel.py:18-22`). The gland position is computed once per tick from the ROV pose at tick start (`tether.py:158`) and is not interpolated across substeps. The cable sees the ROV move in 10 ms jumps; at 2 m/s that is 2 cm per tick **[inferred from code]**.
- Stability **[calc]**: with k = 9000 and m ≈ 0.193 kg/m · l0, the highest chain mode is ≈2√(k/m). For L = 10 m (m ≈ 0.048 kg), ω·h ≈ 0.87 < 2, which is stable; this is evidently why k_max exists.

**Numba acceleration**
- `_cable_accel.advance` is the same force law, JIT-compiled with `njit(cache=True)` and no fastmath (`simulator/qysim/_cable_accel.py:1-5, 65`). `advance_batch` runs all substeps and contact in one compiled call using a cached tangent-plane contact. It returns `False` if any node moves more than `contact_cache_m` = 0.01 m from the anchor, and the tick is then rolled back and redone in the NumPy reference loop (`simulator/qysim/_cable_accel.py:68-109`; `simulator/qysim/tether.py:165-184`).
- 99.39% of ticks complete in the compiled batch in the 3-vehicle benchmark. Tether stepping was ~32% of room time before optimisation (`docs/physics-performance.md:14,18`). The startup line names which path is active (`_cable_accel.py:123-130`). Equivalence is tested to 1e-8 (`simulator/tests/test_ecology.py:144-161`).

**Contact (structures, seabed)**
- Node-only contact against the world SDF: a flat seabed plane or terrain, plus capsule/cylinder, box and mesh proxies (`simulator/qysim/world.py:476-500`). Candidates are obstacles near the cable's AABB with 2 m margin (`simulator/qysim/tether.py:162`).
- Penetration is resolved by projection: `pen = min(node_radius − dist, 0.05)`, `x += n·pen` (node_radius 0.03 m), at most 5 cm per substep. Normal velocity into the surface is zeroed, so contact is fully inelastic (`simulator/qysim/tether.py:268-278`).
- Friction is a velocity-reduction rule: `v_t *= clip(1 − μ·(|v_n,into| + 0.05)/|v_t|, 0, 1)` with μ = 0.6 (`simulator/qysim/tether.py:279-282`; `simulator/qysim/vehicles.py:95`). It depends on the impact velocity plus a constant 0.05 m/s, not on normal force or tension. There is no explicit capstan T₂ = T₁e^{μθ} behaviour; any capstan-like holding emerges only indirectly from repeated re-penetration **[inferred]**. Seabed and structures share the same μ.
- Endpoints are excluded from contact while attached (`tether.py:271-273`). There is no segment-edge contact, cable-cable contact or self-contact. With 40 nodes, segments longer than the obstacle diameter plus 2·node_radius can pass through thin piles between nodes **[inferred]**. Example: at 350 m deployed, 8.75 m segments versus a 1.6 m pile.
- Contact geometry is cached on a local tangent plane until any node moves 1 cm (`tether.py:259-268`). This is tested against exact queries: < 2 cm position and < 1 N mean tension difference (`simulator/tests/test_ecology.py:126-142`).

**Snag, wrap, entanglement detection**
- `contact_nodes` counts nodes within node_radius + 2 cm of a surface. `snag_names` lists the obstacles touched (`simulator/qysim/tether.py:292-297`). "Snag" means contact, with no notion of being pinned.
- `wraps`: for each near-vertical cylinder (axis within ~45° of vertical, excluding `habitat`), the code sums the signed angle change between consecutive nodes that are within the cylinder's z-range ±0.5 m and radius + 2.5 m. Turns = total/2π, reported if |turns| ≥ 0.25 (`simulator/qysim/tether.py:300-323`). Horizontal members, boxes and wrecks are not checked.
- Test: driving the ROV 1.5 turns around a pile yields 1.5 ± 0.2 turns and a snag on P1 (`simulator/tests/test_core.py:129-145`). The `tether_untangle` scenario pre-wraps 1.25 turns with a helical layout (`simulator/qysim/scenarios.py:154-161`; `simulator/qysim/engine.py:115-134`); its test is at `simulator/tests/test_core.py:243-246`.

**Payout / haul-in**
- Auto payout: if `auto_payout` is on, the cable is not broken and `tension_spool > payout_threshold_n` (45 N), then `length += payout_rate·0.01` once per tick, i.e. 1.0 m/s (`simulator/qysim/tether.py:286-287`; `simulator/qysim/vehicles.py:95-96`). There is no automatic haul-in or slack take-up. The rate is a hard step with no acceleration, reel inertia, brake or handler delay. The 0.01 is hard-coded rather than using `dt` **[inferred: wrong if dt ≠ 0.01]**.
- Manual: the `payout` message carries `metres`, clamped to ±100 m per message. Viewer buttons send −5/−1/+1/+5 m (`simulator/qysim/server.py:581-587`; `simulator/viewer/index.html:207`; `simulator/viewer/app.js:734-735`). `payout()` clamps the length to [2.0, max_length] (`simulator/qysim/tether.py:82-83`).
- Payout is applied instantly by rescaling every segment's rest length (`seg_len = length/40`). New cable appears uniformly along the whole line, not at the spool **[inferred from code]**. Auto payout is toggled with the `auto_payout` message (`server.py:586-587`).
- **[local run]**: an instant −2 m haul on a hanging 10 m cable, ROV held fixed, peaked at 1631 N (55% of breaking) and settled at 1066 N. On 40 m the peak was 449 N; on 200 m, 205 N.
- **[local run]**: ROV kinematically pulled away from a taut 20 m line at 1 m/s with auto payout on. The spool tension saturated at about 45 N, the line paid out about 2.05 m in 3 s, and ROV-end tension was 22 N.

**Breaking, warning, scoring**
- Break when `tension_max > breaking_n` = 2943 N, where `tension_max` is the maximum over segments in the last substep. It logs a `tether_break` event (`simulator/qysim/tether.py:288-291`). After a break the ROV end is freed (`tether.py:214, 272-273`), the wrench is zeroed (`tether.py:186-188`), and the RC is locked: `locked = rc.rc_lock == 1 or self.tether.broken` (`simulator/qysim/engine.py:164`). This represents loss of power and comms.
- Warn when `tension_max > warn_n` = 250 N, an estimate (`simulator/qysim/tether.py:332`; `simulator/qysim/vehicles.py:94`). The scorer deducts 10 points per over-tension episode (`simulator/qysim/scenarios.py:455-458`). By contrast, the VideoRay working limit is half of breaking, which would be ≈1471 N for 2943 N — [VideoRay](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html).
- There is no separate weaker connector or gland strength, no fatigue or abrasion accumulation, and no damage-from-chafe model.

**Coupling to the vehicle**
- Force on the ROV = `−f_seg[-1]`, the last segment's tension vector from the last substep only, not averaged over substeps (`simulator/qysim/tether.py:252`; `_cable_accel.py:62`). It is converted to body frame and the moment is `gland_body × F` (`tether.py:189-191`). It is applied via `v.step(dt, thr, w_tether + w_contact + …)` (`simulator/qysim/engine.py:196-202`).
- The coupling is explicit and staggered: the cable uses the ROV state at tick start, and the ROV sees the end-of-tick cable force. Gland position is per vehicle definition (`engine.py:97-99`). Room respawn translates all nodes and re-pins the spool (`simulator/qysim/room.py:117-120`).

**Spool / topside**
- `spool` is a fixed NED point from the scenario, e.g. (−3, 0, 0) (`simulator/qysim/scenarios.py:59`). There is no vessel or quay motion, waves, reel inertia, brake, slip ring, tether handler model or TMS.

**State / HUD**
- `state()` exposes `nodes` (all 41 positions), `length`, `tension_rov`, `tension_spool`, `tension_max`, `warn`, `broken`, `contact_nodes`, `snagged_on`, `wraps`, `auto_payout` and `max_length` (`simulator/qysim/tether.py:325-339`; `simulator/qysim/engine.py:786`). Per-segment tensions (`_seg_tension`) are not exported.
- The viewer shows ROV and spool tension bars, an auto-pay checkbox, payout buttons, a wraps list and a warn banner ("纜線張力 N N, 減少拉扯、檢查纏繞"). The cable is coloured by **linear interpolation between spool and ROV tension**, not by per-segment tension (`simulator/viewer/app.js:316-353, 934-946, 981, 1022-1023`). The instructor view receives `tension_rov` and `wraps` (`simulator/qysim/instructor.py:173`).

**Tests touching the tether**
- `test_core.py:129` (wrap and snag), `test_core.py:243` (untangle scenario), `test_ecology.py:126` (contact cache), `test_ecology.py:144` (Numba equals NumPy), `test_examples.py:38` (only that peak tension ≥ 0), and `test_instructor.py:153-166` (payout message permissions).
- None checks tension or shape against an analytic or published reference (catenary, a drag-loaded straight cable, the von Benzon passive test) **[inferred from test list]**.

### Inferences
- The architecture matches the MoorDyn/von Benzon class, but EA is softened twice. Nominal EA (20 kN) is roughly 5× softer than an aramid tether of this strength **[inferred: 2943 N at ~3% break strain gives EA ≈ 1e5 N; strain at break for the strength member is an assumption]**, and the k_max cap makes short deployments up to ~40× softer still. The model is therefore a stretchy cord: 225 N/m whole-cable stiffness for any L < 89 m. Snap loads, the "tether goes hard" feel and tension rise rates are understated, while sudden rest-length changes create artificial loads (see the local runs).

### Gaps
- No X1 tether measurement exists (`vehicles.py` source strings; `docs/reference/real-rov-research.md:148`). EA, wet weight, Cd and the reel are all unknown.
- I did not trace the viewer's interpolation and smoothing of nodes (`tetherDisp`), or the multiplayer serialisation cost of 41 nodes per vehicle.

## Q4. Concrete gaps, ranked by impact on training realism

### Takeaway
The biggest realism gaps are topside and contact behaviour, not missing exotic physics. The ranking is: (1) payout and haul-in semantics (instant rest-length rescale, a 1 m/s threshold auto-payout and no handler or reel); (2) node-only contact with a fixed 40 nodes, so long tethers tunnel through piles, plus friction that does not depend on tension; (3) length-dependent softened EA; (4) no twist; (5) no surface/vessel motion and a fixed spool; (6) thresholds and failure modes; (7) missing bending; (8) parameter inconsistencies and drag coefficients.

### Cited Findings and ranking (each item cites the repo behaviour from Q3 and the practice from Q1/Q2)

1. **Payout/haul-in model is non-physical (high impact: it is the operator's main tether control).**
   - Repo: manual payout rescales all 40 segments instantly, ±100 m per message (`tether.py:82-83`, `server.py:581-585`). **[local run]** A −2 m haul on 10 m gave a 1631 N spike.
   - Repo: auto payout is a 45 N threshold at a constant 1 m/s with no inertia, brake or delay (`tether.py:286-287`).
   - Practice: MoorDyn-F drives length through deltaL and deltaLdot, i.e. rate-controlled ([inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)). DeepWorks couples crane and winch payout so an unexpected haul pulls the ROV ([Hart Energy](https://hartenergy.com/exclusives/rov-simulation-training-tool-cuts-operational-costs-and-risks-18642)). Real small-ROV practice uses a human tether handler who pays out and reports length ([VideoRay field ops](https://download.videoray.com/documentation/pro_4_ultra/html/pm_operations.html)).
   - Fix direction **[inferred]**: add or remove length only at the spool segment (variable-length first segment with node insertion and removal), apply a rate-limited handler/reel command with first-order lag and a brake, and expose deployed length to the HUD as a handler readout.
2. **Contact fidelity for snag and wrap training (high).**
   - Repo: contact is node-only with fixed N = 40, so segments up to 8.75 m long can tunnel through 0.8 m-radius piles. Friction is velocity-based, independent of tension and wrap angle (`tether.py:254-282`). Wrap detection works only for near-vertical cylinders (`tether.py:300-323`). There is no line-line or self-contact.
   - Practice: GRi's selling point is "interactive tether collision". Stonefish also lacks cable-cable contact ([Stonefish docs](https://stonefish.readthedocs.io/en/latest/cables.html)). MoorDyn models friction as normal-force based with static/dynamic scaling ([inputs.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst)). Wrapped cables obey capstan friction **[general mechanics; no source fetched]**. "Cable Joints" handles wrapping over rigid bodies ([Müller et al. 2018](https://diglib.eg.org:443/handle/10.1111/cgf13507)).
   - Fix direction **[inferred]**: segment-capsule contact (closest point on segment), a minimum node density near obstacles or adaptive segments, and friction scaled by the contact normal force.
3. **Softened, length-dependent axial stiffness (medium-high).**
   - Repo: whole-cable stiffness is a constant 225 N/m for L < 89 m; effective EA is 2–20 kN against an estimated real ~1e5 N **[inferred]** (`tether.py:198`, `vehicles.py:83-84`). Taut-line snap loads, the jolt at full length and the rate of tension build are understated. Short tethers feel the most rubbery, although they should be the stiffest.
   - Practice: MoorDyn keeps the physical EA and lowers dt or raises ζ via CFL instead ([troubleshooting.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/troubleshooting.rst)). PBD uses LRA or direct solves for inextensibility ([Kim et al. 2012](https://matthias-research.github.io/pages/publications/sca2012cloth.pdf); [Liu et al. 2022](https://arxiv.org/pdf/2202.09714)).
   - Fix direction **[inferred]**: implicit or tridiagonal axial solve, or more substeps with ζ≈1, so k_max can be removed. The softening matters less than items 1–2 because loads are mostly drag-dominated and quasi-static.
4. **No torsion/twist (medium).**
   - Repo: no twist state or torque.
   - Practice: VideoRay notes each twist puts torque on the vehicle and pilots watch a turns counter ([VideoRay tether mgmt](https://download.videoray.com/documentation/pro_4/html/oper_tether.html), via `real-rov-research.md:96`). Chrono's cable element also omits torsion, and torsion requires Cosserat or Euler beams ([Chrono manual](https://api.projectchrono.org/manual_fea_elements.html)).
   - Cheap fix **[inferred]**: track net yaw turns of the ROV relative to the tether (heading integral), apply a small restoring yaw torque, and show a HUD turns counter. This needs no rod model.
5. **Fixed spool, no surface/vessel/quay motion or waterline (medium).**
   - Repo: spool is a fixed point (`scenarios.py:59`); there is no surface check for nodes.
   - Practice: von Benzon allows a time-varying p0 ([paper §6](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)). VMAX and DeepWorks simulate vessel and crane dynamics ([VMAX](https://f-e-t.com/?p=2974); [Hart Energy](https://hartenergy.com/exclusives/rov-simulation-training-tool-cuts-operational-costs-and-risks-18642)). The IMCA case involved a support vessel and current ([IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)).
   - Relevance is lower for a quay-launched observation ROV, but wave-driven surface bight motion and boat drift matter for boat ops **[inferred]**.
6. **Thresholds and failure modes (medium).**
   - Repo: a single break at 2943 N on any segment, a warning at 250 N, and no connector, gland, chafe or fatigue model (`tether.py:288-291, 332`).
   - Practice: connectors are much weaker than the cable (80 kg versus 450 kg), and working load is ≤ half of breaking ([VideoRay specs](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html)). Chafe on structure caused the IMCA loss ([IMCA SF 02/23](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/)).
   - Fix direction **[inferred]**: a gland/connector limit, cumulative chafe on contact nodes with tension × slip, and a cumulative-overload log.
7. **No bending stiffness (low-medium for a ~10 mm soft tether).**
   - Practice: MoorDyn-C adds EI for power cables ([structure.rst](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/structure.rst)); minimum bend radius is ~0.1 m ([VideoRay](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html)).
   - **[inferred]** For a soft 9.5 mm tether, EI mainly affects kink and loop formation near the gland and slack coils on the seabed. Visual plausibility of slack loops (they currently fold at nodes) matters more than force accuracy. Low priority.
8. **Parameter consistency and hydrodynamic details (low-medium).**
   - mass_per_m 0.12 versus wet_weight 0.004 is inconsistent for d = 9.5 mm **[calc]**. Added mass is applied axially (MoorDyn example Cat = 0). End nodes have full drag area. Current is frozen across substeps. ζ = 0.6 is below MoorDyn's near-1 advice. Cdn 1.2 and Cdt 0.02 are in the range used by von Benzon (1.2/0.01) and MoorDyn examples (1.6/0.05) ([MoorDyn inputs](https://github.com/FloatingArrayDesign/MoorDyn/blob/master/docs/inputs.rst); [von Benzon Table A1](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)), so drag is not the main problem. Vortex-induced vibration is absent, which is acceptable.
9. **Coupling and HUD details (low).**
   - The ROV force is taken from the last substep, not averaged. The gland is not interpolated within the tick (a 2 cm jump at 2 m/s) **[inferred; magnitude unverified]**.
   - The HUD colour interpolates spool-to-ROV tension instead of using per-segment `_seg_tension`, which hides mid-span peaks at snags (`app.js:1022-1023`). There is no handler-style "deployed length" callout or turns counter.
10. **No validation test against a reference (process gap).**
    - The tests only check wrap counting, cache and Numba equivalence, and tension ≥ 0. No test checks a catenary, a uniform-current drag-loaded line, or the von Benzon passive test (15 m, 0.5 m/s resultant current: straight in ~30 s, ROV at the surface in ~100 s, ~30 N steady) ([paper](https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf)). MoorDyn's practice is to validate against tank data ([Hall & Goupee 2015](http://www.sciencedirect.com/science/article/pii/S0029801815002279)).

### Inferences
- The ranking weighs operator-facing behaviour (what a trainee does with the tether: pay out, avoid snags, unwrap, read tension) above force-model accuracy. The reason is that the repo's drag-dominated quasi-static loads are already in the right family. **[inferred judgement]**
- Steam "fun" and training "truth" diverge most on item 1 (an instant ±5 m button is a game convenience). Per AGENTS.md this belongs in an assist layer that can be turned off, with a rate-limited handler model as the real-mode default. **[inferred]**

### Gaps
- No public stiffness, wet weight or Cd data for the X1 tether, so items 3 and 8 cannot be quantified beyond order of magnitude.
- No public data on commercial simulators' tension HUDs or payout control UIs.
- The capstan-friction claim and the aramid break-strain estimate (~3%) are general engineering knowledge; I did not fetch a source for them in this session.
