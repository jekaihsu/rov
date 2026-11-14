# ROV Tether / Umbilical Physical Properties and Real-World Behaviour (as of Nov 2026)

Scope: observation-class tethers (vehicles up to ~150 kg: FIFISH X1, BlueROV2/Fathom, VideoRay, Deep Trekker, Blueye), with heavier work-class umbilicals noted separately. All manufacturer numbers are **manufacturer claims** unless marked otherwise. "[snippet]" = seen only in a search-result summary, not on a fetched page. "[derived]" = my calculation from cited inputs.

---

## 1. Construction, diameter, weight and buoyancy

### Takeaway
Small-ROV tethers are 3.5–12 mm cables: copper twisted pairs (or fibre) + an aramid (Kevlar) or Vectran strength member + a foamed polyurethane/polyethylene jacket that sets bulk density near water. "Neutral" tethers are almost always specified as neutral in **fresh** water and therefore **slightly positive in seawater**; negative (non-foamed) tethers are thinner per conductor size, carry more power, and sink.

### Cited Findings
**Blue Robotics Fathom (BlueROV2)** — [Blue Robotics product page](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/)
- Standard: Ø 7.6 mm; 4 unshielded twisted pairs 26 AWG (0.14 mm²); weight in air 0.043 kg/m; DC resistance 0.127 Ω/m; 300 VDC rating; insulation >1640 MΩ/km @500 VDC.
- Slim: Ø 4.0 mm; 1 twisted pair 26 AWG; 0.012 kg/m in air; 0.146 Ω/m.
- Buoyancy (both): "Neutral" in freshwater, "Slightly Positive" in saltwater; jacket is "polyurethane foam" that "provides neutral buoyancy".
- Core: "Kevlar strands for strength and Dacron fibers for space filling", impregnated with water-blocking compound "to block any leaks caused by nicks or rips in the cable".
- Max link distance with Fathom-X interface: 300 m (standard), 200 m (slim).
- Max rated depth 950 m / 1000 m and design life "three years or 500 cycles to rated depth" [snippet, sources disagree on depth] — [RobotShop listing](https://robotshop.com/products/bluerobotics-fathom-rov-tether-200m).

**QYSEA FIFISH X1** — [myROVs X1 page (distributor)](https://www.myrovs.com/fifish-x1/)
- Tether 350 m, Ø 9.5 mm, tensile strength 300 kgf; spool 600×430×540 mm, 53 kg (spool + tether, IP66); direct power supply 700–800 V DC in → 29.2 V out, 1.8 kW max.
- Vehicle ≤30 kg; thrust fwd 30 kgf / rev 24 / lateral 15 / vertical 21 kgf; speed fwd 4.5 kn; "current resistance up to 4.0 knots (2.0 m/s)".
- Vendor pages disagree on vehicle mass (30/27/23 kg) [snippet] — [search summary of retailer pages incl. Terra Drone, 9tenthsco](https://store.terra-drone.com.sa/product/fifish-x1/).
- No published X1 tether weight, buoyancy, conductor/fibre count, or bend radius found.

**Other QYSEA tethers** (consumer/prosumer) [snippet]
- V6 100 m tether: Ø 3.5 mm, 80 kgf breaking, neutral — [Wellbots](https://www.wellbots.com/products/qysea-fifish-100-meter-tether-and-spool).
- 300 m spool tether: Kevlar-reinforced, ~100 kgf — [QYSEA store](https://store.qysea.com/products/300m-984ft-tether-spool); 3 m tether Ø 4 mm, 100 kgf — [QYSEA store](https://store.qysea.com/products/3m-9-8ft-tether).
- E-GO: Ø 4.6 mm 120 kgf vs another reseller Ø 4.0 mm 130 kgf (conflict) — [scuba.com](https://www.scuba.com/p-qyfishege20a/qysea-fifish-e-go-e200a-underwater-rov-kit-with-robotic-arm-and-200m-tether).

**VideoRay (Mission Specialist)** — [VideoRay MSS tether specs](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html)
| Type | Ø mm | Min bend radius | Buoyancy | Breaking |
|---|---|---|---|---|
| Negative | 8.51 ± 0.38 | 88.9 mm | no foam, sinks | 450 kg |
| Neutral | 11.18 ± 0.50 | 114 mm | foam, ~neutral fresh | 450 kg |
| Performance | 8.18 ± 0.50 | 82.5 mm | foam, ~neutral fresh | 450 kg |
| FB Neutral (2018+) | 12.2 ± 0.25 | – | – | 450 kg |
| FB Performance | 9.1 ± 0.25 | – | – | 450 kg |
- Conductor sizes: power pairs 2×16 AWG (negative), 2×20 AWG (neutral), 2×24 AWG (performance) — thinner conductors are the price of foam buoyancy at a given OD.
- Newer comparison sheet: Neutral 11.7 mm, 457 kg; Performance ~9–10 mm, 635 kg; fibre 4.5 mm, 300 kg, "~neutral (-2/-3 kg/km seawater weight)"; hybrid 12–17 mm, 730 kg [snippet] — [VideoRay MS Tether Comparison Sheet](https://videoray.com/wp-content/uploads/2023/09/Mission-Specialist-Tether-Comparison-Sheet-1.1.1.pdf).
- "Neutral tether is neutral in fresh water (slightly buoyant in salt water), but has thinner conductors"; negative "has larger conductors, so longer lengths can be used without reducing power" — [VideoRay Pro4 tether management](https://download.videoray.com/documentation/pro_4/html/universal_tether.html).

**Deep Trekker REVOLUTION** — neutrally buoyant, Ø 4.5–6.5 mm, min breaking 90 kg (200 lb) [snippet] — [Deep Trekker spec sheet](https://www.deeptrekker.com/learn/revolution-rov-spec-sheet); 1000 m DPK & fibre tether Ø 4.5 mm, 300 lb break [snippet] — [Deep Trekker shop](https://www.deeptrekker.com/shop/products/1000m-dpk-and-fiber-system). (200 vs 300 lb conflict unresolved.)

**Blueye** 150 m replacement tether: breaking strength 100 kg; 1 twisted pair 26 AWG copper (no diameter/buoyancy given) — [Blueye spec sheet BYE-TETH-150](https://www.blueyerobotics.com/specsheet/BYE-TETH-150/pdf).

**Linden Photonics ROV fibre tether** — Ø 3.5 ± 0.127 mm; 9.52 g/m in air; specific gravity 0.99; 750 lb tensile (page intro also says ">350 kg"); recommended SWL 15% (113 lb); bend radius guideline 70 mm; "torque-balanced Vectran strength members"; LCP/TPU/aramid braid/LDPE layers + low-density outer jacket — [Linden Photonics](https://www.lindenphotonics.com/lindens-rov-fiber-optic-tether).

**Saab Seaeye Falcon tether (measured, academic)** — 4 large stranded copper power conductors, 2 fibres, 2 signal wires, Vectran braided strength lining, two polyethylene jacket layers; measured density 1025 kg/m³, Ø 14 mm, length 350 m — [Zand, UVic MASc thesis, Table 2-1 & App. B](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf).

**Falmat / Winchester Interconnect, South Bay Cable, DeRegt, JDR, Novacavi, Teledyne/Kongsberg**: Falmat (now Winchester) offers neutrally buoyant excursion tethers and Xtreme-Net Ethernet cable with "Xtreme" PU jacket, but no numbers retrieved (PDFs returned 403) [snippet] — [oceannews Falmat brochure](https://oid.oceannews.com/media/com_jbusinessdirectory/attachments/companies/139/ROV_Tether_Cable_1710767635-1719433552.pdf). Winchester Xtreme-Light fibre: hydrostatically tested to 15 kpsi, 10 km depth, customizable to neutral buoyancy [snippet] — [Winchester datasheet](https://www.winconn.com/wp-content/uploads/2022/10/Xtreme-Light-Marine-Fiber.pdf). Bofan (CN) neutral tethers in 100/300/400 kg Kevlar grades [snippet] — [bofan-cable.com](https://bofan-cable.com/?p=14732).

**Heavier (work-class) for reference** [snippet]
- Sub-Atlantic TMS: tether Ø 25–39 mm (Type 6a); 1500 m of 27 mm tether = 1028 kg in air (≈0.69 kg/m); 1029 m of 35 mm = 1132 kg (≈1.10 kg/m); Type 5c line pull 330 kgf — [FET TMS Type 6 datasheet](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-6.pdf), [TMS Type 5](https://f-e-t.com/wp-content/uploads/2019/10/tms-type-5.pdf).
- WHOI/Oceanworks lifting tether: MBS 45,000 lb; heavy section 0.5–3 lb/ft wet in seawater; buoyant section 0.15–0.5 lb/ft buoyancy [snippet] — [WHOI Oceanworks](https://oceanworks.whoi.edu/innovation/?p=42672).
- Patent: aramid umbilical SWL >30,000 lb, MBL 2–3× SWL [snippet] — [USPTO 9855999](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9855999).

### Inferences
- [derived] Displaced water per metre = π/4·d²·ρ: Ø7.6 mm → 45.4 g/m fresh / 46.5 g/m sea; Ø9.5 mm → 70.9 / 72.7 g/m; Ø11.7 mm → 107.5 / 110.2 g/m; Ø14 mm → 153.9 / 157.8 g/m. Fathom at 43 g/m in air is thus ≈ −2.4 g/m (buoyant) in fresh and ≈ −3.5 g/m in sea — "neutral/slightly positive" is a few g/m, i.e. ~±5% of displaced mass.
- [derived] Fresh vs. salt difference is ~2.5% of displaced mass (ρ 1000 vs 1025). A tether exactly neutral in fresh is ~+1.8 g/m buoyant in sea at 9.5 mm (≈0.6 kgf upward per 350 m). Simulator: model net wet weight w = (m_air/L − ρ_water·A)·g, with ρ_water switching per environment; default X1 tether could be set "neutral in fresh" with m_air ≈ 0.071 kg/m (assumption, not published). A 350 m × 0.071 kg/m ≈ 25 kg tether is plausible within the 53 kg spool figure (assumption).
- Manufacturing tolerance on OD (±0.25–0.5 mm, VideoRay) alone changes displacement by ~±5–10%, so real "neutral" tethers vary by several g/m along their length; a simulator may add small per-segment buoyancy noise.

### Gaps
- No published X1 tether weight in air/water, conductor or fibre layout, buoyancy class, or bend radius. Needs X1 measurement (docs/reference/x1-measurement-checklist.md).
- No retrieved numeric datasheets for Falmat, South Bay Cable, DeRegt, JDR, Novacavi, Teledyne, Kongsberg (pages 403 or not found).
- Dyneema/Spectra use in ROV tethers not documented in sources found.

---

## 2. Mechanical properties (strength, SWL, elongation, EA, bend, torsion, crush)

### Takeaway
Breaking strengths range 80–635 kgf for small tethers; manufacturers derate heavily (Fathom 23%, VideoRay ≤50%, Linden 15%). Connectors/terminations are far weaker than the cable (VideoRay connector 80 kg, locking collar 35 kg). Measured small-tether bending stiffness is ~0.5 N·m², torsional ~0.5 N·m²/rad; EA estimates for aramid-reinforced tethers are ~10⁴–10⁵ N.

### Cited Findings
- Fathom: breaking 155 kgf (342 lb; marketing text says 350 lb), working 35 kgf (77 lb) → SWL ≈ 23% of break; min working bend **diameter** 75 mm (standard) / 25 mm (slim) — [Blue Robotics](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/).
- VideoRay: "The tether should not be subjected to a working strength greater than one half of the breaking strength"; Kevlar rated 450 kg; connector breaking 80 kg (175 lb); strain relief cable and connectors 136 kg (300 lb); "strain relief cable should be used to avoid separation of the tether connectors and loss of the ROV" — [VideoRay MSS specs](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html). Connector locking collars 35 kg (75 lb) — [VideoRay tether care](https://download.videoray.com/documentation/mss/html/mnt_handling_tethers.html).
- Min bend radius VideoRay 82.5–114 mm for Ø8–11 mm (≈10 × OD) — [VideoRay MSS specs](https://download.videoray.com/documentation/mss/html/equip_tether_specs.html); Linden 70 mm for Ø3.5 mm (20 × OD) — [Linden](https://www.lindenphotonics.com/lindens-rov-fiber-optic-tether). Generic rule "static ≥8× OD, dynamic (reeling) ≥12× OD" from a low-reliability buying guide [snippet, unverified] — [Alibaba buying guide](https://electronics.alibaba.com/buyingguides/rov-tether-guide-how-to-choose-the-right-one).
- Falcon tether measured (Ø14 mm, Vectran): bending stiffness EI = 0.54 N·m² average (0.40 ramp-up, 0.67 ramp-down; 3-point bend over 0.5 m span); torsional stiffness GJ ≈ 0.5 N·m² (0.39–0.66 N·m/(rad/m)) with strong hysteresis "due to strong tether damping … unbonded nature of the internal wires and plasticity of the polyethylene jackets"; EA = 4.3×10⁴ N, but **derived from EI**, and the author warns it "may contain inaccuracies" — [Zand thesis, App. B](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf).
- Kevlar 49 yarn: ~885 g/d modulus, ~2.4% elongation at break [snippet from DuPont-derived table] — [Kevlar Technical Guide (scribd)](https://www.scribd.com/document/401192485/Kevlar-Technical-Guide); Kevlar 29/49 creep negligible up to high % of UTS — [NASA 1976](https://ntrs.nasa.gov/api/citations/19760007949/downloads/19760007949.pdf); Vectran HS creeps ~4× slower than similar Kevlar 49 but is not zero-creep — [NASA Goddard Vectran report](https://ntrs.nasa.gov/api/citations/20050040773/downloads/20050040773.pdf).
- Torque balance: Linden uses contra-helical "torque-balanced Vectran strength members" — [Linden](https://www.lindenphotonics.com/lindens-rov-fiber-optic-tether). Fathom described as "flexible enough to give plenty of freedom … stiff enough that it does not become tangled easily" — [Blue Robotics](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/).
- Twist: "Do not drive the vehicle in repeated circles, which can twist the tether"; coiling in one direction "will result in twists that are hard to remove" — [VideoRay tether care](https://download.videoray.com/documentation/mss/html/mnt_handling_tethers.html), [VideoRay tether management](https://download.videoray.com/documentation/pro_4/html/universal_tether.html).
- Crush: "Do not crush the tether, including closing it in a lid or stepping or driving on it" (no numeric rating) — [VideoRay tether care](https://download.videoray.com/documentation/mss/html/mnt_handling_tethers.html).
- No research known on aramid tethers under small-radius bends (1997) — [CMU Dante II tether paper](https://publications.ri.cmu.edu/storage/publications/pub_files/pub1/krishna_murali_1997_1/krishna_murali_1997_1.pdf).

### Inferences
- [derived] Assuming the strength member dominates axial load and fails at ~2.4% strain (Kevlar 49, linear): EA ≈ F_break/0.024 → Fathom ≈ 1520 N/0.024 ≈ 6×10⁴ N; X1 (300 kgf) ≈ 1.2×10⁵ N; VideoRay (450 kg) ≈ 1.8×10⁵ N. Real cables add constructional stretch, so true EA is likely lower (the Falcon 4.3×10⁴ N is the same order). Elongation at Fathom working load ≈ 35/155 × 2.4% ≈ 0.5%; over 300 m that is ~1.6 m — negligible for gameplay but means a simulator can treat the tether as nearly inextensible (stiff spring; use EA ~5×10⁴–1×10⁵ N with damping for stability).
- EI ~0.5 N·m² gives a bending length (EI/w)^(1/3) of ~0.5–1 m for wet weights of a few g/m — bending matters only near terminations/strain relief, so a simulator can neglect EI except for rendering and to prevent sub-MBR loops.
- Suggested X1 parameters (assumptions until measured): break 300 kgf (published), SWL ~50% (VideoRay practice) to ~25% (Fathom practice), MBR ≈10×OD ≈ 95 mm static.
- Connector/termination is the realistic failure point under snag loads (VideoRay connector 80 kg < cable 450 kg) — simulator snag events should fail at termination or trigger "strain relief" rather than mid-cable.

### Gaps
- No directly measured axial EA or load-elongation curve for any small ROV tether found.
- No numeric crush rating for any small tether found.
- No source specifically on hockling thresholds for ROV tethers.

---

## 3. Hydrodynamic drag (normal/tangential), fairings, strumming

### Takeaway
Use normal drag coefficient C_n ≈ 1.2 (bare cylinder) to 1.65–2.0 (measured on real ROV tethers; higher when strumming). Tangential coefficients are ~two orders smaller but no ROV-specific measured value was found. Tether drag dominates vehicle drag for long lays and can exceed an observation ROV's thrust in currents ≥0.5 m/s.

### Cited Findings
- Falcon tether model C_D (normal) = 1.65, based on steady-state inclination of a towed cable at several speeds in ocean tests — [Zand thesis Table 2-1](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf).
- Kojima et al. (ROV '86) field-measured the MARCAS ROV tether with acoustic transponders; normal C_D "much larger than the theoretical value of 1.2"; ≈2.0 per secondhand forum citation — [Springer chapter](https://link.springer.com/chapter/10.1007/978-94-009-4207-3_5); [Blue Robotics forum](https://discuss.bluerobotics.com/t/tether-drag-on-rov/9092).
- Cable C_d: 1.2 unfaired, 0.5–0.6 hair-faired, 0.1–0.2 faired (quoted from ScienceDirect topic page); Blue Robotics has not measured Fathom's C_d and suggests 1.2 — [Blue Robotics forum](https://discuss.bluerobotics.com/t/tether-drag-on-rov/9092).
- Bare stationary cable C_d 0.5–1.2; bare **strumming** cable 1.5–3.5; fairings suppress strumming but raise tangential drag — [Wikipedia: Cable fairing](https://en.wikipedia.org/wiki/Cable_fairing).
- Strum results from vortex shedding from a cable at an angle to the flow [snippet] — [USPTO 8773954](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8773954).
- Simulated Falcon (350 m neutral tether, ship 26 m lead): tether force on ROV at 0.2 m/s: 8 N heave / 23 N surge (vs 25 N vehicle drag); at 0.67 m/s: 84 N / 255 N; at 1.0 m/s: 188 N / 568 N (vehicle drag 273 N). Falcon surge thrust limit 401 N, so max sustained transit with neutral tether ≈0.67 m/s; conventional tending produced disturbances up to 43 N in a 0.2 m/s transect once all tether paid out — [Zand thesis Table 2-2](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf).
- VideoRay: thinner (Performance) tether "has less drag"; in swift current use minimal tether, weights may be required — [VideoRay tether management](https://download.videoray.com/documentation/pro_4/html/universal_tether.html).

### Inferences
- [derived] Normal drag of a straight X1 tether (Ø9.5 mm, C_n 1.2, ρ 1025) per 100 m fully across the flow: 36 N at 0.25 m/s, 146 N at 0.5 m/s, 584 N at 1.0 m/s. X1 forward thrust 30 kgf ≈ 294 N, so ~100 m of tether broadside to a 0.7 m/s current saturates the vehicle — far below the advertised 2.0 m/s "current resistance" (which presumably assumes little tether in the flow). Fathom Ø7.6 mm: 117 N per 100 m at 0.5 m/s. These are upper bounds (catenary and tangential alignment reduce them, cf. Falcon numbers).
- For simulation use Morison-style split: f_n = ½ρ C_n d |v_n| v_n, f_t = ½ρ C_t π d |v_t| v_t with C_n 1.2 (default) to 1.65 (realistic/strumming), C_t ≈ 0.01–0.03 (commonly used in cable-dynamics literature; not verified for ROV tethers here — treat as assumption).

### Gaps
- No measured tangential drag coefficient for an ROV tether found; DTIC cable reports (e.g. [ADA113478](https://apps.dtic.mil/sti/pdfs/ADA113478.pdf)) define C_t on wetted area but values not extracted.
- No data on effect of foam-jacket surface texture on drag.

---

## 4. Operational effects of buoyancy choice and recommended practice

### Takeaway
Neutral/slightly positive tether keeps line off the seabed but floats loops up near the surface and toward propellers; negative tether sinks, snags on the bottom, but allows bigger conductors. Standard practice: neutral (or thin performance) tether near the ROV, negative tether near the surface/console, minimum payout, launch up-current, and add clump weights or floats to shape the catenary.

### Cited Findings
- "Use Performance or Neutral tether at the ROV and if more tether is needed use Negative at the control panel"; recommended max lengths e.g. 229 m Neutral, 305 m Negative + 76 m Neutral (381 m), 40 m PPT alone — [VideoRay tether management](https://download.videoray.com/documentation/pro_4/html/universal_tether.html).
- Deploy "up-current of the work zone with a direct line of sight to avoid snags"; "too little will affect piloting – too much may result in snags, tangles or propeller cuts" — same source.
- Typical conventional tending keeps low surface tension (simulated 20 N), paying out when tension rises; once tether runs out, disturbance rises quickly; a depressor (clump) weight was analysed as an alternative tether-management scheme — [Zand thesis §2.2, §2.5](https://dspace.library.uvic.ca/bitstream/handle/1828/1964/ZandThesis.pdf).
- Tethers designed for seawater are "very slightly negative in freshwater" (forum claim) [snippet] — [Blue Robotics forum, third-party umbilicals](https://discuss.bluerobotics.com/t/third-party-umbilicals/11828). (Note: Fathom and VideoRay neutral tethers are the opposite — neutral in fresh, positive in salt.)
- Use a pulley/sheave when deploying other than by hand — [VideoRay tether care](https://download.videoray.com/documentation/mss/html/mnt_handling_tethers.html).

### Inferences
- Simulator should expose buoyancy class as a per-segment wet weight: a slightly positive tether in seawater should rise toward the surface at slack, creating surface loops (wave/boat-prop hazard); a negative one should lie on the seabed and be checked for snag contacts. Clump weight = point mass on tether; floats = point buoyancy.
- Tether in a current pulls the ROV downstream; with neutral tether the pull is mostly horizontal, with negative tether there is also a downward/aft component — consistent with Falcon heave vs surge loads.

### Gaps
- No quantitative guidance (from sources) on how many floats/weights to add or at what spacing for small ROVs.

---

## 5. Damage modes, inspection, retirement

### Takeaway
Common failures: abrasion/cut against structures, kinks and sub-MBR bends, twist from circling, crushing, connector damage/corrosion, water ingress after nicks. Manufacturers give handling rules but almost no numeric retirement criteria; Fathom gives a design life of 3 years / 500 dives to rated depth [snippet].

### Cited Findings
- VideoRay rules: don't crush, tie or kink; respect MBR; avoid rough surfaces, sharp edges, pinch points; coil over-under or figure-8; don't circle repeatedly; caps on connectors; clean, lubricate with silicone, rinse connectors in fresh water after every disconnection; inspect connectors periodically for corrosion/damage (no interval) — [VideoRay tether care](https://download.videoray.com/documentation/mss/html/mnt_handling_tethers.html).
- Cut/nicked tether: power off, retrieve, remove tether from water ASAP to prevent water ingress; can be spliced; field repairs with hot glue or silicone/RTV must be made permanent later [snippet] — [VideoRay emergency: cut tether](https://download.videoray.com/documentation/mss/html/_page_emergency_cut.html).
- IMCA incident: tether parted due to abrasion against jacket structure, ROV lost with no comms [snippet] — [IMCA safety flash 0223](https://www.imca-int.com/resources/safety/safety-flashes/0223-lost-rov-incident/?pdf). Work-class main-lift umbilical failure: internal strand damage consistent with prior water ingress (rust), no lubricant in core; lesson: examine parts not visually accessible [snippet] — [IMCA umbilical failure](https://legacy.imca-int.com/?p=978).
- Fathom water-blocking compound limits leak propagation after nicks — [Blue Robotics](https://bluerobotics.com/store/cables-connectors/cables/fathom-rov-tether-by-the-meter/).
- Routine inspection for abrasion, cuts, fatigue recommended (vendor blog) [snippet] — [Linden Photonics](https://www.lindenphotonics.com/top-5-challenges-in-managing-long-rov-tethers-underwater).

### Inferences
- Training-sim damage model candidates: abrasion accumulator on contact segments; event when local bend radius < MBR; twist counter from cumulative yaw (warn after N turns); termination failure at connector rating; water ingress → comms/power degradation after a cut.

### Gaps
- No numeric retirement criteria (insulation resistance thresholds, max cuts, diameter loss) from any small-tether manufacturer found.
- No published turn-count limit for twist.
