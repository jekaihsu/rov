import * as THREE from 'three';

/**
 * Original Self-Designed ROV-01 Open-Frame Industrial 3D Mesh (CORR-ROV-01 + Non-Orange Cyber-Cyan & Titanium Spec)
 * Strictly original industrial ROV geometry — zero external commercial shell assets, zero consumer orange hull.
 *
 * Viewer body coordinate convention (NED):
 *   x = forward (+bow / -stern)
 *   y = starboard (+right / -port)
 *   z = down (+keel / -top)
 *
 * 3-Layer Sandwich Spec mapped to NED (Non-Orange Deep-Sea Titanium & Sonar-Cyan Hull Palette):
 *   Top Layer (z: -0.17 .. -0.06): 45° chamfered syntactic buoyancy blocks in High-Visibility Marine Cyber Cyan #06B6D4 / #22D3EE
 *   Middle Layer (z: -0.06 .. +0.08): Matte Carbon Black #0F172A cylindrical pressure hull + Ø18mm Deep-Sea Titanium Slate #1E293B tubular crash frame
 *   Bottom Layer (z: +0.08 .. +0.17): Skid frame + Bottom DVL sonar array (#0F172A with 4 #B45309 bronze transducer windows)
 *   6 Thruster Shrouds: Anodized Subsea Aluminum Trim #38BDF8 Kort nozzles + Graphite Steel #334155 3-blade rotors
 *   Reflective Engineering Strips: #F8FAFC high-contrast corner & buoyancy alignment strips
 *   Payload: 316L Stainless #CBD5E1 UT Probe with tri-color UT_Status_Ring (#22D3EE / #F59E0B / #10B981) + Dual LED floodlights (#E0F2FE / #BAE6FD)
 */
export const ROV01_LIVERY_PALETTES = {
  cyber_cyan: {
    id: 'cyber_cyan',
    label: 'Deep-Sea Cyber Cyan & Subsea Titanium',
    buoyancyHex: 0x06B6D4,      // #06B6D4 high-visibility marine cyan syntactic foam
    buoyancyEmissive: 0x22D3EE, // #22D3EE sonar cyan subtle edge glow
    buoyancyEmissiveIntensity: 0.14,
    nozzleTrimHex: 0x38BDF8,    // #38BDF8 anodized aluminum trim & Kort nozzles
    frameHex: 0x1E293B,         // #1E293B carbon-titanium open frame
    hullHex: 0x0F172A,          // #0F172A matte carbon-black pressure hull
    stripeHex: 0xF8FAFC,        // #F8FAFC reflective engineering strips
  },
  arctic_white: {
    id: 'arctic_white',
    label: 'Arctic White Research & Anodized Cyan',
    buoyancyHex: 0xF8FAFC,      // #F8FAFC polar white syntactic foam
    buoyancyEmissive: 0x38BDF8,
    buoyancyEmissiveIntensity: 0.08,
    nozzleTrimHex: 0x06B6D4,    // #06B6D4 marine cyan anodized Kort nozzles
    frameHex: 0x1E293B,         // #1E293B carbon-titanium open frame
    hullHex: 0x0F172A,
    stripeHex: 0x22D3EE,        // #22D3EE high-contrast sonar cyan strip
  },
  stealth_titanium: {
    id: 'stealth_titanium',
    label: 'Stealth Subsea Titanium & Sonar Cyan',
    buoyancyHex: 0x1E293B,      // #1E293B dark titanium syntactic foam
    buoyancyEmissive: 0x06B6D4,
    buoyancyEmissiveIntensity: 0.10,
    nozzleTrimHex: 0x22D3EE,    // #22D3EE sonar cyan anodized Kort nozzles
    frameHex: 0x0F172A,         // #0F172A carbon-titanium frame
    hullHex: 0x0F172A,
    stripeHex: 0xF8FAFC,        // #F8FAFC reflective engineering strips
  },
};

export function resolveRov01Livery(livery = 'cyber_cyan') {
  const key = String(livery || 'cyber_cyan').toLowerCase().trim();
  if (key === 'arctic' || key === 'arctic_white') return ROV01_LIVERY_PALETTES.arctic_white;
  if (key === 'stealth' || key === 'stealth_titanium' || key === 'titanium') return ROV01_LIVERY_PALETTES.stealth_titanium;
  return ROV01_LIVERY_PALETTES.cyber_cyan;
}

function buildChamferedBuoyancyGeometry(length = 0.56, width = 0.16, height = 0.105, chamfer = 0.028) {
  // Cross-section in (y, z) plane with 45° top chamfer, extruded along x (forward)
  const hw = width / 2;
  const hh = height / 2;
  const c = Math.min(chamfer, hw * 0.45, hh * 0.45);
  const shape = new THREE.Shape();
  shape.moveTo(-hw, -hh);
  shape.lineTo(hw, -hh);
  shape.lineTo(hw, hh - c);
  shape.lineTo(hw - c, hh);
  shape.lineTo(-hw + c, hh);
  shape.lineTo(-hw, hh - c);
  shape.closePath();

  const geom = new THREE.ExtrudeGeometry(shape, {
    steps: 1,
    depth: length,
    bevelEnabled: true,
    bevelThickness: 0.012,
    bevelSize: 0.012,
    bevelSegments: 1,
  });
  geom.center();
  // Rotate so extrusion axis (originally Z) aligns with X (forward), and shape Y aligns with -Z (up)
  geom.rotateY(Math.PI / 2);
  geom.rotateX(Math.PI);
  return geom;
}

export function createRov01IndustrialMesh({ frame = 'ned', livery = 'cyber_cyan' } = {}) {
  let activePalette = resolveRov01Livery(livery);
  const root = new THREE.Group();
  root.name = 'ROV01_Root';

  // Locked PBR Materials (Non-Orange Deep-Sea Titanium & Cyber-Cyan Spec)
  const matBuoyancy = new THREE.MeshStandardMaterial({
    name: 'ROV01_Buoyancy_SyntacticFoam',
    color: activePalette.buoyancyHex, // Default 0x06B6D4 Deep-Sea Cyber Cyan
    emissive: activePalette.buoyancyEmissive, // 0x22D3EE Sonar Cyan highlight
    emissiveIntensity: activePalette.buoyancyEmissiveIntensity,
    metalness: 0.08,
    roughness: 0.58,
  });
  const matAnodizedTrim = new THREE.MeshStandardMaterial({
    name: 'ROV01_Anodized_Aluminum_Trim',
    color: 0x38BDF8, // Anodized Subsea Aluminum Trim #38BDF8
    metalness: 0.68,
    roughness: 0.28,
  });
  const matFrameSlate = new THREE.MeshStandardMaterial({
    name: 'ROV01_Frame_TitaniumSlate',
    color: 0x1E293B, // Deep-Sea Titanium Slate #1E293B
    metalness: 0.78,
    roughness: 0.32,
  });
  const matHullBlack = new THREE.MeshStandardMaterial({
    name: 'ROV01_PressureHull_Carbon',
    color: 0x0F172A, // Matte Carbon Black #0F172A
    metalness: 0.85,
    roughness: 0.30,
  });
  const matNozzleCyan = new THREE.MeshStandardMaterial({
    name: 'ROV01_KortNozzle_AnodizedTrim',
    color: activePalette.nozzleTrimHex, // Default 0x38BDF8 Anodized Aluminum Trim
    metalness: 0.42,
    roughness: 0.36,
  });
  const matRotorGraphite = new THREE.MeshStandardMaterial({
    color: 0x334155, // Graphite Steel #334155
    metalness: 0.80,
    roughness: 0.35,
  });
  const matHubSteel = new THREE.MeshStandardMaterial({
    color: 0x94A3B8,
    metalness: 0.88,
    roughness: 0.25,
  });
  const matStainless316 = new THREE.MeshStandardMaterial({
    color: 0xCBD5E1, // 316L Stainless #CBD5E1
    metalness: 0.90,
    roughness: 0.25,
  });
  const matDomeGlass = new THREE.MeshPhysicalMaterial({
    color: 0x020617,
    metalness: 0.10,
    roughness: 0.05,
    transmission: 0.85,
    transparent: true,
    opacity: 0.72,
    ior: 1.5,
  });
  const matLensCyan = new THREE.MeshStandardMaterial({
    color: 0x38BDF8,
    emissive: 0x0284C7,
    emissiveIntensity: 0.55,
    metalness: 0.5,
    roughness: 0.2,
  });
  const matBronzeDvl = new THREE.MeshStandardMaterial({
    color: 0xB45309, // Bronze acoustic transducer window #B45309
    metalness: 0.70,
    roughness: 0.30,
  });
  const matEngineeringStripe = new THREE.MeshStandardMaterial({
    name: 'ROV01_Reflective_Stripe',
    color: 0xF8FAFC, // Reflective Engineering Strip #F8FAFC
    emissive: 0xE2E8F0,
    emissiveIntensity: 0.22,
    metalness: 0.15,
    roughness: 0.35,
  });

  // 1. TOP LAYER: 45° Chamfered Syntactic Buoyancy Blocks (High-Visibility Marine Cyan #06B6D4 / #22D3EE)
  const buoyGeom = buildChamferedBuoyancyGeometry(0.56, 0.16, 0.105, 0.028);
  const buoyL = new THREE.Mesh(buoyGeom, matBuoyancy);
  buoyL.name = 'Buoyancy_TopBlock_L';
  buoyL.position.set(0.0, -0.145, -0.115);
  buoyL.castShadow = true;
  buoyL.receiveShadow = true;
  root.add(buoyL);

  const buoyR = new THREE.Mesh(buoyGeom, matBuoyancy);
  buoyR.name = 'Buoyancy_TopBlock_R';
  buoyR.position.set(0.0, 0.145, -0.115);
  buoyR.castShadow = true;
  buoyR.receiveShadow = true;
  root.add(buoyR);

  // Top anodized aluminum bridge plates & lifting lugs (#38BDF8 trim + #1E293B frame)
  for (const bx of [-0.22, 0.0, 0.22]) {
    const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.14, 0.022), matAnodizedTrim);
    bridge.position.set(bx, 0, -0.155);
    root.add(bridge);
  }
  for (const side of [-1, 1]) {
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.005, 0.026), matEngineeringStripe);
    stripe.position.set(0.02, side * 0.232, -0.115);
    root.add(stripe);
  }

  // 2. MIDDLE & BOTTOM LAYER: Open Tubular Carbon-Titanium Crash Frame + Skid Frame (#1E293B)
  const frameCage = new THREE.Group();
  frameCage.name = 'Frame_Cage';
  const tubeRadius = 0.009; // Ø18mm tubular frame

  // 4 longitudinal Ø18mm rails (length 0.64m)
  const longRailGeom = new THREE.CylinderGeometry(tubeRadius, tubeRadius, 0.64, 12);
  longRailGeom.rotateZ(Math.PI / 2);
  for (const sy of [-0.23, 0.23]) {
    for (const sz of [-0.06, 0.08]) {
      const rail = new THREE.Mesh(longRailGeom, matFrameSlate);
      rail.position.set(0, sy, sz);
      frameCage.add(rail);
    }
  }
  // 8 vertical stanchions connecting top, middle, and bottom skid
  const vertPostGeom = new THREE.CylinderGeometry(tubeRadius, tubeRadius, 0.24, 10);
  vertPostGeom.rotateX(Math.PI / 2);
  const tapeBandGeom = new THREE.CylinderGeometry(tubeRadius * 1.14, tubeRadius * 1.14, 0.022, 12);
  tapeBandGeom.rotateX(Math.PI / 2);
  const matReflectiveTape = new THREE.MeshStandardMaterial({
    color: 0xF8FAFC,
    emissive: 0xE2E8F0,
    emissiveIntensity: 0.35,
    metalness: 0.15,
    roughness: 0.22,
  });
  for (const sx of [-0.30, -0.10, 0.10, 0.30]) {
    for (const sy of [-0.23, 0.23]) {
      const post = new THREE.Mesh(vertPostGeom, matFrameSlate);
      post.position.set(sx, sy, 0.04);
      frameCage.add(post);
      // Corner vertical posts get two #F8FAFC reflective engineering tape bands
      if (Math.abs(sx) > 0.25) {
        for (const tz of [-0.015, 0.095]) {
          const band = new THREE.Mesh(tapeBandGeom, matReflectiveTape);
          band.name = 'Corner_Reflective_Tape';
          band.position.set(sx, sy, tz);
          frameCage.add(band);
        }
      }
    }
  }
  // Top aqua rim light to separate #1E293B outer frame from #0F172A inner pressure hull in dark water
  const topAquaRimLight = new THREE.PointLight(0x22D3EE, 1.4, 1.85, 1.5);
  topAquaRimLight.name = 'Top_Aqua_Rim_Light';
  topAquaRimLight.position.set(0.0, 0.0, -0.28);
  frameCage.add(topAquaRimLight);
  // Lateral cross-members
  const crossBeamGeom = new THREE.CylinderGeometry(tubeRadius, tubeRadius, 0.46, 10);
  for (const sx of [-0.30, 0.0, 0.30]) {
    for (const sz of [-0.06, 0.08, 0.155]) {
      const cross = new THREE.Mesh(crossBeamGeom, matFrameSlate);
      cross.position.set(sx, 0, sz);
      frameCage.add(cross);
    }
  }
  // Bottom Layer: Twin CNC Titanium-Aluminum Skids (width 0.38m, z = +0.155m) with #38BDF8 trim rails
  const skidBarGeom = new THREE.BoxGeometry(0.62, 0.028, 0.026);
  for (const sy of [-0.19, 0.19]) {
    const skid = new THREE.Mesh(skidBarGeom, matFrameSlate);
    skid.position.set(0, sy, 0.155);
    frameCage.add(skid);
  }
  root.add(frameCage);

  // 3. MIDDLE LAYER: Cylindrical Pressure Hull (Matte Carbon Black #0F172A, Ø0.14m, L=0.42m)
  const hullGroup = new THREE.Group();
  hullGroup.name = 'PressureHull_Center';
  const hullCylGeom = new THREE.CylinderGeometry(0.07, 0.07, 0.42, 24);
  hullCylGeom.rotateZ(Math.PI / 2);
  const hullBody = new THREE.Mesh(hullCylGeom, matHullBlack);
  hullBody.position.set(-0.01, 0, 0.0);
  hullGroup.add(hullBody);

  // Rear anodized heatsink fins on pressure hull
  for (let i = 0; i < 4; i++) {
    const fin = new THREE.Mesh(
      new THREE.CylinderGeometry(0.076, 0.076, 0.008, 20),
      i === 0 ? matAnodizedTrim : matFrameSlate
    );
    fin.rotation.z = Math.PI / 2;
    fin.position.set(-0.16 - i * 0.018, 0, 0.0);
    hullGroup.add(fin);
  }
  root.add(hullGroup);

  // 4. PAYLOADS: Optical Dome Camera, Dual LED Floodlights, 316L Stainless UT Probe, Bottom DVL Sonar
  const payloads = new THREE.Group();
  payloads.name = 'Payloads';

  // 4a. Main Optical Dome at bow (0.28, 0.0, -0.01)
  const cameraAnchor = new THREE.Group();
  cameraAnchor.name = 'Optical_Dome_Camera';
  cameraAnchor.position.set(0.28, 0.0, -0.01);
  const flange = new THREE.Mesh(
    new THREE.CylinderGeometry(0.062, 0.062, 0.018, 20).rotateZ(Math.PI / 2),
    matFrameSlate
  );
  const lensRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.036, 0.005, 10, 20).rotateY(Math.PI / 2),
    matLensCyan
  );
  lensRing.position.x = 0.012;
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(0.055, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.55),
    matDomeGlass
  );
  dome.rotation.z = -Math.PI / 2;
  dome.position.x = 0.006;
  cameraAnchor.add(flange, lensRing, dome);
  payloads.add(cameraAnchor);

  // 4b. Dual LED Subsea Floodlights (#E0F2FE, emissive #BAE6FD, intensity 3.5)
  const lampAnchors = [];
  for (const [idx, sy] of [[-0.14, 0], [0.14, 1]]) {
    const side = idx;
    const lampGroup = new THREE.Group();
    lampGroup.name = sy === 0 ? 'LED_Light_L' : 'LED_Light_R';
    lampGroup.position.set(0.29, side, -0.06);
    lampGroup.rotation.y = 8 * (Math.PI / 180); // 8° downward tilt to reduce backscatter

    const lampHousing = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.06, 0.04), matFrameSlate);
    const lampLens = new THREE.Mesh(
      new THREE.CylinderGeometry(0.016, 0.016, 0.008, 16).rotateZ(Math.PI / 2),
      new THREE.MeshStandardMaterial({
        color: 0xE0F2FE,
        emissive: 0xBAE6FD,
        emissiveIntensity: 3.5,
        roughness: 0.1,
      })
    );
    lampLens.position.x = 0.026;
    lampGroup.add(lampHousing, lampLens);
    payloads.add(lampGroup);
    lampAnchors.push(lampGroup);
  }

  // 4c. Forward 316L Stainless UT Ultrasonic Thickness Gauging Probe Assembly
  const utAssembly = new THREE.Group();
  utAssembly.name = 'UT_Probe_Assembly';
  utAssembly.position.set(0.30, 0.0, 0.09);

  const utMountBlock = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.065, 0.036), matFrameSlate);
  utAssembly.add(utMountBlock);
  // Dual 316L stainless spring guide rods extending 0.18m forward
  for (const ry of [-0.018, 0.018]) {
    const rod = new THREE.Mesh(
      new THREE.CylinderGeometry(0.0055, 0.0055, 0.18, 12).rotateZ(Math.PI / 2),
      matStainless316
    );
    rod.position.set(0.09, ry, 0);
    utAssembly.add(rod);
  }
  const utHead = new THREE.Mesh(
    new THREE.CylinderGeometry(0.016, 0.018, 0.038, 16).rotateZ(Math.PI / 2),
    matStainless316
  );
  utHead.position.set(0.18, 0, 0);
  utAssembly.add(utHead);

  // Tri-color UT Coupling Status Glow Ring (#22D3EE searching / #F59E0B aligning / #10B981 coupled)
  const utStatusMat = new THREE.MeshStandardMaterial({
    color: 0x22D3EE,
    emissive: 0x22D3EE,
    emissiveIntensity: 2.2,
    roughness: 0.2,
  });
  const utStatusRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.018, 0.0045, 10, 20).rotateY(Math.PI / 2),
    utStatusMat
  );
  utStatusRing.name = 'UT_Status_Ring';
  utStatusRing.position.set(0.198, 0, 0);
  utAssembly.add(utStatusRing);
  payloads.add(utAssembly);

  // 4d. Bottom DVL & Multibeam Sonar Module (Ø0.12m #0F172A disc + 4 #B45309 bronze windows)
  const dvlGroup = new THREE.Group();
  dvlGroup.name = 'Bottom_DVL_Sonar';
  dvlGroup.position.set(-0.04, 0.0, 0.14);
  const dvlDisc = new THREE.Mesh(
    new THREE.CylinderGeometry(0.06, 0.06, 0.032, 20).rotateX(Math.PI / 2),
    matHullBlack
  );
  dvlGroup.add(dvlDisc);
  for (const [dx, dy] of [[0.026, 0.026], [0.026, -0.026], [-0.026, 0.026], [-0.026, -0.026]]) {
    const xducer = new THREE.Mesh(
      new THREE.CylinderGeometry(0.013, 0.013, 0.006, 14).rotateX(Math.PI / 2),
      matBronzeDvl
    );
    xducer.position.set(dx, dy, 0.015);
    dvlGroup.add(xducer);
  }
  payloads.add(dvlGroup);
  root.add(payloads);

  // 5. Rear Subsea Cyan Tether Strain Relief (#38BDF8)
  const tetherAnchor = new THREE.Group();
  tetherAnchor.name = 'Tether_Mount';
  tetherAnchor.position.set(-0.32, 0.0, -0.04);
  const tetherBoot = new THREE.Mesh(
    new THREE.ConeGeometry(0.022, 0.075, 12).rotateZ(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0x38BDF8, roughness: 0.35, metalness: 0.35 })
  );
  tetherAnchor.add(tetherBoot);
  root.add(tetherAnchor);

  const armMount = new THREE.Group();
  armMount.name = 'anchor_arm_mount';
  armMount.position.set(0.28, 0.0, 0.12);
  root.add(armMount);

  // 6. 6 THRUSTER SHROUDS (Anodized Subsea Aluminum Trim #38BDF8 Kort Nozzles + Graphite #334155 3-Blade Rotors)
  // Coordinates aligned with physics Thrusters 0..5
  const thrusterGroup = new THREE.Group();
  thrusterGroup.name = 'Thrusters';
  root.add(thrusterGroup);

  const thrusterSpecs = [
    { name: 'Thruster_FL', pos: [0.22, -0.20, 0.01], dir: [0.7071, 0.7071, 0] },
    { name: 'Thruster_FR', pos: [0.22, 0.20, 0.01], dir: [0.7071, -0.7071, 0] },
    { name: 'Thruster_RL', pos: [-0.22, -0.20, 0.01], dir: [0.7071, -0.7071, 0] },
    { name: 'Thruster_RR', pos: [-0.22, 0.20, 0.01], dir: [0.7071, 0.7071, 0] },
    { name: 'Thruster_VL', pos: [0.00, -0.11, -0.08], dir: [0, 0, -1] },
    { name: 'Thruster_VR', pos: [0.00, 0.11, -0.08], dir: [0, 0, -1] },
  ];

  const rotors = [];
  const thrusterVisuals = [];

  for (let i = 0; i < thrusterSpecs.length; i++) {
    const spec = thrusterSpecs[i];
    const tNode = new THREE.Group();
    tNode.name = spec.name;
    tNode.position.set(spec.pos[0], spec.pos[1], spec.pos[2]);

    const dirVec = new THREE.Vector3(spec.dir[0], spec.dir[1], spec.dir[2]).normalize();
    tNode.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), dirVec);

    // Anodized Aluminum #38BDF8 Kort Nozzle Guard (Ø0.105m, length 0.08m)
    const shroudMat = matNozzleCyan.clone();
    const shroud = new THREE.Mesh(
      new THREE.CylinderGeometry(0.0525, 0.0525, 0.08, 20, 1, true).rotateZ(Math.PI / 2),
      shroudMat
    );
    const frontLip = new THREE.Mesh(
      new THREE.TorusGeometry(0.0525, 0.006, 10, 20).rotateY(Math.PI / 2),
      shroudMat
    );
    frontLip.position.x = 0.038;
    const rearLip = frontLip.clone();
    rearLip.position.x = -0.038;

    // 3 radial protective struts
    for (let s = 0; s < 3; s++) {
      const a = (s * Math.PI * 2) / 3;
      const strut = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.005, 0.008), matFrameSlate);
      strut.position.set(0, Math.cos(a) * 0.038, Math.sin(a) * 0.038);
      strut.rotation.x = a;
      tNode.add(strut);
    }

    // Motor pod + Graphite Steel #334155 3-blade rotor + #94A3B8 stainless hub cap
    const motorPod = new THREE.Mesh(
      new THREE.CylinderGeometry(0.018, 0.018, 0.068, 12).rotateZ(Math.PI / 2),
      matRotorGraphite
    );
    const rotor = new THREE.Group();
    rotor.name = `Propeller_Rotor_${i}`;
    rotor.userData = { role: 'rotor', thruster_index: i };
    const hubCap = new THREE.Mesh(
      new THREE.ConeGeometry(0.014, 0.022, 12).rotateZ(-Math.PI / 2),
      matHubSteel
    );
    hubCap.position.x = 0.028;
    rotor.add(hubCap);
    for (let b = 0; b < 3; b++) {
      const blade = new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.042, 0.016), matRotorGraphite);
      const angle = (b * Math.PI * 2) / 3;
      blade.position.set(0.008, Math.cos(angle) * 0.022, Math.sin(angle) * 0.022);
      blade.rotation.x = angle + 0.42;
      rotor.add(blade);
    }

    // Hydrodynamic thrust plume cone (#22D3EE Sonar Cyan normal / #EF4444 Critical Coral when jammed)
    const plumeMat = new THREE.MeshBasicMaterial({
      color: 0x22D3EE,
      transparent: true,
      opacity: 0.0,
      depthWrite: false,
    });
    const plume = new THREE.Mesh(
      new THREE.ConeGeometry(0.042, 0.18, 12, 1, true).rotateZ(Math.PI / 2),
      plumeMat
    );
    plume.position.x = -0.11;

    tNode.add(shroud, frontLip, rearLip, motorPod, rotor, plume);
    thrusterGroup.add(tNode);
    rotors.push(rotor);
    thrusterVisuals.push({ shroudMat, plume, plumeMat });
  }

  function setLivery(nextLivery = 'cyber_cyan') {
    activePalette = resolveRov01Livery(nextLivery);
    matBuoyancy.color.setHex(activePalette.buoyancyHex);
    matBuoyancy.emissive.setHex(activePalette.buoyancyEmissive);
    matBuoyancy.emissiveIntensity = activePalette.buoyancyEmissiveIntensity;
    matBuoyancy.userData.rovOriginalColor = matBuoyancy.color.clone();
    matFrameSlate.color.setHex(activePalette.frameHex);
    matEngineeringStripe.color.setHex(activePalette.stripeHex);
    for (const vis of thrusterVisuals) {
      vis.shroudMat.color.setHex(activePalette.nozzleTrimHex);
    }
    return activePalette.id;
  }

  function updateThrusters(motor = [], dt = 0.016, health = null, utCoupledState = 'searching') {
    for (let i = 0; i < rotors.length; i++) {
      const cmd = Number(motor[i] || 0);
      const h = Array.isArray(health) && health[i] !== undefined ? Number(health[i]) : 1.0;
      const isFault = h < 0.99;
      const effectiveCmd = cmd * h;

      rotors[i].rotation.x += dt * effectiveCmd * 42.0;

      const vis = thrusterVisuals[i];
      if (isFault) {
        vis.shroudMat.color.setHex(0xEF4444); // Critical Coral #EF4444 fault highlight
        vis.shroudMat.emissive.setHex(0xEF4444);
        vis.shroudMat.emissiveIntensity = 0.75;
        vis.plumeMat.color.setHex(0xEF4444);
        vis.plumeMat.opacity = 0.25;
      } else {
        vis.shroudMat.color.setHex(activePalette.nozzleTrimHex); // Anodized Trim #38BDF8 / #06B6D4 normal shroud
        vis.shroudMat.emissive.setHex(0x000000);
        vis.shroudMat.emissiveIntensity = 0.0;
        const mag = Math.min(1, Math.abs(effectiveCmd));
        vis.plumeMat.color.setHex(effectiveCmd >= 0 ? 0x22D3EE : 0x38BDF8);
        vis.plumeMat.opacity = mag * 0.38;
        vis.plume.scale.set(0.6 + mag * 1.1, 1, 1);
      }
    }
    if (utCoupledState === 'coupled' || utCoupledState === 'ut_coupled_lock') {
      utStatusMat.color.setHex(0x10B981);
      utStatusMat.emissive.setHex(0x10B981);
      utStatusMat.emissiveIntensity = 2.4;
    } else if (utCoupledState === 'aligning' || utCoupledState === 'ut_aligning') {
      utStatusMat.color.setHex(0xF59E0B);
      utStatusMat.emissive.setHex(0xF59E0B);
      utStatusMat.emissiveIntensity = 2.2;
    } else {
      utStatusMat.color.setHex(0x22D3EE);
      utStatusMat.emissive.setHex(0x22D3EE);
      utStatusMat.emissiveIntensity = 2.2;
    }
  }

  // Map internal FRD (x=fwd, y=stbd, z=down) -> Three.js Y-up body frame: three(x,y,z) = (-y_frd, -z_frd, x_frd)
  // Top layer (#06B6D4 / #22D3EE cyber_cyan buoyancy) is +Y, Bottom layer (skids + DVL) is -Y, Bow (Camera + LED + UT Probe) is +Z
  const wrapper = new THREE.Group();
  wrapper.name = 'ROV01_ThreeBody_Root';
  const basis = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(0, 0, 1),   // +x_frd (forward) -> +Z
    new THREE.Vector3(-1, 0, 0),  // +y_frd (starboard) -> -X
    new THREE.Vector3(0, -1, 0)   // +z_frd (down) -> -Y (so -z_frd top is +Y!)
  );
  root.quaternion.setFromRotationMatrix(basis);
  wrapper.add(root);

  return {
    root: wrapper,
    rotors,
    thrusterVisuals,
    livery: activePalette.id,
    setLivery,
    updateThrusters,
    updateThrusterVisuals: (m, h, dt = 0.016) => updateThrusters(m, dt, h, 'coupled'),
    anchors: {
      camera: cameraAnchor,
      lamps: lampAnchors,
      tether: tetherAnchor,
      armMount,
      utProbe: utStatusRing,
    },
  };
}
