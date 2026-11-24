/*
 * NVIDIA Omniverse SimReady OpenUSD (.usda) Loader & @huggingface/usd-web-viewer Bridge for ROV-01
 * Converts OpenUSD ASCII stages + UsdPhysics schemas (PhysicsRigidBodyAPI, PhysicsMassAPI,
 * PhysicsCollisionAPI, PhysicsMaterialAPI) into Three.js 3D industrial assemblies with
 * toggleable #22D3EE Collision Wireframes, #F59E0B Center-of-Mass (CoM) gizmos, and UT beacons.
 */

export const USD_WEB_VIEWER_META = {
  package: '@huggingface/usd-web-viewer',
  version: '0.2.0',
  vendorModuleUrl: './vendor/usd-web-viewer/dist/esm/index.js',
  vendorWasmUrl: './vendor/usd-web-viewer/dist/wasm/usd_wasm_bg.wasm',
  sourceDataset: 'https://huggingface.co/datasets/nvidia/simready-assets',
  sourceSpace: 'https://huggingface.co/spaces/nvidia/simready-central',
  changelogUrl: 'https://huggingface.co/changelog/openusd-viewer-and-simready-asset-previews',
};

// NED [N, E, D] -> Three.js Y-up [E, -D, -N]
export function nedToThreeVec(THREE, ned) {
  const n = Number(ned?.[0] || 0);
  const e = Number(ned?.[1] || 0);
  const d = Number(ned?.[2] || 0);
  return new THREE.Vector3(e, -d, -n);
}

export function parseUsdaStageText(usdaText = '') {
  const grabStr = (re, defVal = '') => {
    const m = usdaText.match(re);
    return m ? m[1] : defVal;
  };
  const grabNum = (re, defVal = 0) => {
    const m = usdaText.match(re);
    return m ? Number(m[1]) : defVal;
  };
  const grabVec3 = (re, defVal = [0, 0, 0]) => {
    const m = usdaText.match(re);
    return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : defVal;
  };

  const schemasMatch = usdaText.match(/prepend\s+apiSchemas\s*=\s*\[([^\]]+)\]/);
  const apiSchemas = schemasMatch
    ? schemasMatch[1].split(',').map((s) => s.trim().replace(/^"|"$/g, '')).filter(Boolean)
    : ['PhysicsCollisionAPI', 'PhysicsMassAPI', 'PhysicsMaterialAPI'];

  const extentMatch = usdaText.match(
    /extent\s*=\s*\[\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)\s*,\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)\s*\]/
  );

  return {
    defaultPrim: grabStr(/defaultPrim\s*=\s*"([^"]+)"/, 'SimReadyPrim'),
    upAxis: grabStr(/upAxis\s*=\s*"([^"]+)"/, 'Z'),
    metersPerUnit: grabNum(/metersPerUnit\s*=\s*([0-9.+-eE]+)/, 1.0),
    assetId: grabStr(/simready:assetId\s*=\s*"([^"]+)"/, 'SR-IND-01'),
    hfPackage: grabStr(/simready:hfPackage\s*=\s*"([^"]+)"/, 'industrial_asset'),
    hfRootUsd: grabStr(/simready:hfRootUsd\s*=\s*"([^"]+)"/, ''),
    missionId: grabStr(/simready:missionId\s*=\s*"([^"]+)"/, 'mission_1_pool'),
    missionCode: grabStr(/simready:missionCode\s*=\s*"([^"]+)"/, 'M1'),
    titleZh: grabStr(/simready:titleZh\s*=\s*"([^"]+)"/, 'SimReady 工業資產'),
    titleEn: grabStr(/simready:titleEn\s*=\s*"([^"]+)"/, 'SimReady Industrial Asset'),
    shapeArchetype: grabStr(/simready:shapeArchetype\s*=\s*"([^"]+)"/, 'calibration_rack'),
    pbrColorHex: grabStr(/simready:pbrColorHex\s*=\s*"([^"]+)"/, '#38BDF8'),
    secondaryColorHex: grabStr(/simready:secondaryColorHex\s*=\s*"([^"]+)"/, '#1E293B'),
    utCheckpointId: grabStr(/subsea:utCheckpointId\s*=\s*"([^"]+)"/, '') || null,
    utNominalMm: grabNum(/subsea:utNominalWallMm\s*=\s*([0-9.+-eE]+)/, 14.0),
    utActualMm: grabNum(/subsea:utActualWallMm\s*=\s*([0-9.+-eE]+)/, 13.2),
    displacementM3: grabNum(/subsea:displacementM3\s*=\s*([0-9.+-eE]+)/, 0.04),
    apiSchemas,
    massKg: grabNum(/physics:mass\s*=\s*([0-9.+-eE]+)/, 220.0),
    centerOfMass: grabVec3(/physics:centerOfMass\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)/, [0, 0, -0.1]),
    staticFriction: grabNum(/physics:staticFriction\s*=\s*([0-9.+-eE]+)/, 0.65),
    dynamicFriction: grabNum(/physics:dynamicFriction\s*=\s*([0-9.+-eE]+)/, 0.52),
    restitution: grabNum(/physics:restitution\s*=\s*([0-9.+-eE]+)/, 0.16),
    nedPos: grabVec3(/xformOp:translate\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)/, [4, 0, 5]),
    scale: grabVec3(/xformOp:scale\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)/, [1, 1, 1]),
    extentMin: extentMatch
      ? [Number(extentMatch[1]), Number(extentMatch[2]), Number(extentMatch[3])]
      : [-1, -1, -1],
    extentMax: extentMatch
      ? [Number(extentMatch[4]), Number(extentMatch[5]), Number(extentMatch[6])]
      : [1, 1, 1],
  };
}

function makeLabelSprite(THREE, asset) {
  if (typeof document === 'undefined') return null;
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  ctx.fillStyle = 'rgba(7, 16, 30, 0.88)';
  ctx.strokeStyle = asset.ut_checkpoint_id ? '#10B981' : '#22D3EE';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.roundRect(6, 6, 500, 116, 14);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#22D3EE';
  ctx.font = 'bold 24px monospace';
  const utTag = asset.ut_checkpoint_id ? ` · [${asset.ut_checkpoint_id}]` : '';
  ctx.fillText(`${asset.asset_id} [${asset.mission_code || 'USD'}]${utTag}`, 22, 42);

  ctx.fillStyle = '#F8FAFC';
  ctx.font = 'bold 22px sans-serif';
  ctx.fillText((asset.title_zh || asset.title_en || '').slice(0, 18), 22, 76);

  const phys = asset.usd_physics || {};
  const mass = phys.mass_kg ?? asset.mass_kg ?? 200;
  const mu = phys.dynamic_friction ?? asset.dynamic_friction ?? 0.5;
  const rest = phys.restitution ?? asset.restitution ?? 0.15;
  ctx.fillStyle = '#94A3B8';
  ctx.font = '18px monospace';
  ctx.fillText(`UsdPhysics: ${mass}kg | μ=${mu} | e=${rest}`, 22, 106);

  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(2.4, 0.6, 1.0);
  sprite.renderOrder = 12;
  return sprite;
}

function buildArchetypeGeometry(THREE, archetype, primaryMat, secondaryMat, accentMat) {
  const meshGroup = new THREE.Group();
  meshGroup.name = `SimReadyArchetype_${archetype}`;

  if (archetype === 'calibration_rack') {
    // Heavy industrial calibration rack with corner pillars, crossbars, and calibration target plates
    const base = new THREE.Mesh(new THREE.BoxGeometry(2.1, 0.16, 1.5), secondaryMat);
    base.position.set(0, -1.05, 0);
    meshGroup.add(base);

    for (const sx of [-0.92, 0.92]) {
      for (const sz of [-0.62, 0.62]) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.2, 12), primaryMat);
        post.position.set(sx, 0, sz);
        meshGroup.add(post);
      }
    }
    for (const y of [-0.4, 0.35, 1.02]) {
      const beam = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.08, 1.38), primaryMat);
      beam.position.set(0, y, 0);
      meshGroup.add(beam);
    }
    const panel = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.55, 0.06), accentMat);
    panel.position.set(0, 0.35, 0.68);
    meshGroup.add(panel);
  } else if (archetype === 'drum_array') {
    // 4-drum subsea containment pallet array
    const skid = new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.18, 1.75), secondaryMat);
    skid.position.set(0, -0.82, 0);
    meshGroup.add(skid);

    for (const dx of [-0.42, 0.42]) {
      for (const dz of [-0.42, 0.42]) {
        const drum = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 1.45, 20), primaryMat);
        drum.position.set(dx, -0.02, dz);
        meshGroup.add(drum);

        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.35, 0.025, 10, 24), accentMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(dx, 0.32, dz);
        meshGroup.add(ring);
      }
    }
  } else if (archetype === 'valve_manifold') {
    // High-pressure subsea gate valve & flange manifold (UT-SR-01)
    const skid = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.16, 1.55), secondaryMat);
    skid.position.set(0, -0.88, 0);
    meshGroup.add(skid);

    const mainPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, 1.95, 24), primaryMat);
    mainPipe.rotation.z = Math.PI / 2;
    mainPipe.position.set(0, -0.1, 0);
    meshGroup.add(mainPipe);

    for (const fx of [-0.82, 0, 0.82]) {
      const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.09, 24), secondaryMat);
      flange.rotation.z = Math.PI / 2;
      flange.position.set(fx, -0.1, 0);
      meshGroup.add(flange);
    }

    const riser = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.26, 0.85, 20), primaryMat);
    riser.position.set(0, 0.38, 0);
    meshGroup.add(riser);

    const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.38, 0.045, 12, 28), accentMat);
    wheel.rotation.x = Math.PI / 2;
    wheel.position.set(0, 0.85, 0);
    meshGroup.add(wheel);
  } else if (archetype === 'pump_housing') {
    // Centrifugal pump volute & turbine housing (UT-SR-02)
    const base = new THREE.Mesh(new THREE.BoxGeometry(2.15, 0.22, 1.7), secondaryMat);
    base.position.set(0, -0.76, 0);
    meshGroup.add(base);

    const volute = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.58, 28), primaryMat);
    volute.rotation.x = Math.PI / 2;
    volute.position.set(-0.28, 0.05, 0);
    meshGroup.add(volute);

    const motor = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 0.95, 22), secondaryMat);
    motor.rotation.z = Math.PI / 2;
    motor.position.set(0.48, 0.02, 0);
    meshGroup.add(motor);

    const discharge = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.75, 18), accentMat);
    discharge.position.set(-0.28, 0.55, 0.22);
    meshGroup.add(discharge);
  } else if (archetype === 'manipulator_arm') {
    // Articulated 6-axis subsea manipulator & intervention stand
    const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.58, 0.65, 20), secondaryMat);
    pedestal.position.set(0, -0.95, 0);
    meshGroup.add(pedestal);

    const shoulder = new THREE.Mesh(new THREE.SphereGeometry(0.24, 18, 18), accentMat);
    shoulder.position.set(0, -0.52, 0);
    meshGroup.add(shoulder);

    const link1 = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.13, 0.95, 16), primaryMat);
    link1.position.set(0.18, -0.08, 0);
    link1.rotation.z = -0.38;
    meshGroup.add(link1);

    const elbow = new THREE.Mesh(new THREE.SphereGeometry(0.18, 16, 16), accentMat);
    elbow.position.set(0.36, 0.36, 0);
    meshGroup.add(elbow);

    const link2 = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.10, 0.78, 16), primaryMat);
    link2.position.set(0.08, 0.68, 0.12);
    link2.rotation.z = 0.62;
    meshGroup.add(link2);

    const gripper = new THREE.Mesh(new THREE.TorusGeometry(0.18, 0.035, 10, 20, Math.PI * 1.35), accentMat);
    gripper.position.set(-0.22, 0.92, 0.15);
    meshGroup.add(gripper);
  } else if (archetype === 'power_skid') {
    // Subsea high-voltage power junction box & generator skid
    const skid = new THREE.Mesh(new THREE.BoxGeometry(2.35, 0.20, 1.8), secondaryMat);
    skid.position.set(0, -0.92, 0);
    meshGroup.add(skid);

    const cabinet = new THREE.Mesh(new THREE.BoxGeometry(1.55, 1.25, 1.15), primaryMat);
    cabinet.position.set(-0.2, -0.18, 0);
    meshGroup.add(cabinet);

    for (const y of [-0.35, 0.05, 0.42]) {
      const busbar = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.65, 14), accentMat);
      busbar.rotation.z = Math.PI / 2;
      busbar.position.set(0.78, y, 0);
      meshGroup.add(busbar);
    }
  } else if (archetype === 'pipe_truss_portal') {
    // Modular subsea pipe bridge & structural truss portal gate
    const leftCol = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 2.8, 18), primaryMat);
    leftCol.position.set(-1.35, 0, 0);
    meshGroup.add(leftCol);

    const rightCol = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 2.8, 18), primaryMat);
    rightCol.position.set(1.35, 0, 0);
    meshGroup.add(rightCol);

    const topBeam = new THREE.Mesh(new THREE.BoxGeometry(3.1, 0.28, 0.95), secondaryMat);
    topBeam.position.set(0, 1.32, 0);
    meshGroup.add(topBeam);

    const pipeSpan = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 3.1, 24), accentMat);
    pipeSpan.rotation.z = Math.PI / 2;
    pipeSpan.position.set(0, 0.85, 0);
    meshGroup.add(pipeSpan);
  } else {
    // Heavy harbor pier bollard & stainless IBC containment tank (SR-IND-08)
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.28, 2.2), secondaryMat);
    plinth.position.set(0, -1.12, 0);
    meshGroup.add(plinth);

    const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.78, 0.78, 1.65, 28), primaryMat);
    tank.position.set(-0.22, -0.15, 0);
    meshGroup.add(tank);

    const bollard = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.28, 1.45, 20), accentMat);
    bollard.position.set(0.75, -0.25, 0.55);
    meshGroup.add(bollard);

    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.26, 0.18, 20), secondaryMat);
    cap.position.set(0.75, 0.52, 0.55);
    meshGroup.add(cap);
  }

  return meshGroup;
}

export function buildSimReadyAssetGroup(THREE, asset, options = {}) {
  const showCollider = options.showCollider !== undefined ? options.showCollider : true;
  const showCoM = options.showCoM !== undefined ? options.showCoM : true;

  const root = new THREE.Group();
  root.name = `SimReady_${asset.asset_id}`;
  root.userData.simreadyAsset = asset;

  const primaryMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(asset.pbr_color_hex || '#38BDF8'),
    roughness: 0.34,
    metalness: 0.68,
  });
  const secondaryMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(asset.secondary_color_hex || '#1E293B'),
    roughness: 0.45,
    metalness: 0.55,
  });
  const accentMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(asset.ut_checkpoint_id ? '#10B981' : '#22D3EE'),
    emissive: new THREE.Color(asset.ut_checkpoint_id ? '#064E3B' : '#083344'),
    emissiveIntensity: 0.45,
    roughness: 0.28,
    metalness: 0.72,
  });

  const visualGroup = buildArchetypeGeometry(
    THREE,
    asset.shape_archetype || 'calibration_rack',
    primaryMat,
    secondaryMat,
    accentMat
  );
  root.add(visualGroup);

  // UsdPhysics.CollisionAPI Bounding Box Wireframe (#22D3EE)
  const emin = asset.extent_min || [-1, -1, -1];
  const emax = asset.extent_max || [1, 1, 1];
  const bw = Math.max(0.4, Math.abs(emax[0] - emin[0]));
  const bh = Math.max(0.4, Math.abs(emax[2] - emin[2]));
  const bd = Math.max(0.4, Math.abs(emax[1] - emin[1]));

  const boxGeo = new THREE.BoxGeometry(bw, bh, bd);
  const edgesGeo = new THREE.EdgesGeometry(boxGeo);
  const wireMat = new THREE.LineBasicMaterial({
    color: 0x22d3ee,
    transparent: true,
    opacity: 0.88,
  });
  const collisionWireframe = new THREE.LineSegments(edgesGeo, wireMat);
  collisionWireframe.name = 'UsdPhysics_CollisionWireframe';
  collisionWireframe.visible = !!showCollider;
  root.add(collisionWireframe);
  root.userData.collisionWireframe = collisionWireframe;

  // UsdPhysics.MassAPI Center-of-Mass (CoM) Gizmo (#F59E0B)
  const comGizmo = new THREE.Group();
  comGizmo.name = 'UsdPhysics_CenterOfMassGizmo';
  const comVec = asset.usd_physics?.center_of_mass || asset.center_of_mass || [0, 0, -0.1];
  comGizmo.position.set(
    Number(comVec[1] || 0),
    -Number(comVec[2] || 0),
    -Number(comVec[0] || 0)
  );
  const comSphere = new THREE.Mesh(
    new THREE.SphereGeometry(0.13, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xf59e0b })
  );
  comGizmo.add(comSphere);
  const axes = new THREE.AxesHelper(0.48);
  comGizmo.add(axes);
  comGizmo.visible = !!showCoM;
  root.add(comGizmo);
  root.userData.comGizmo = comGizmo;

  // UT Inspection Target Beacon Ring for M2 SimReady assets (UT-SR-01 / UT-SR-02)
  if (asset.ut_checkpoint_id) {
    const utRing = new THREE.Mesh(
      new THREE.TorusGeometry(0.52, 0.032, 12, 36),
      new THREE.MeshBasicMaterial({ color: 0x10b981 })
    );
    utRing.position.set(-bw * 0.48, 0.1, 0);
    utRing.rotation.y = Math.PI / 2;
    utRing.name = `UT_Beacon_${asset.ut_checkpoint_id}`;
    root.add(utRing);
    root.userData.utBeacon = utRing;
  }

  // Floating Label Sprite
  const labelSprite = makeLabelSprite(THREE, asset);
  if (labelSprite) {
    labelSprite.position.set(0, bh * 0.5 + 0.55, 0);
    root.add(labelSprite);
    root.userData.labelSprite = labelSprite;
  }

  // Position in Three.js world space from NED
  if (asset.ned_pos) {
    root.position.copy(nedToThreeVec(THREE, asset.ned_pos));
  }

  return root;
}

export class SimReadySceneManager {
  constructor() {
    this.catalog = null;
    this.assets = [];
    this.group = null;
    this.assetNodes = new Map();
    this.showCollider = true;
    this.showCoM = true;
    this.showAllMissions = false;
    this.activeMissionId = null;
  }

  async loadCatalog() {
    if (this.catalog) return this.catalog;
    try {
      const res = await fetch('/api/simready/catalog');
      if (res.ok) {
        this.catalog = await res.json();
        this.assets = this.catalog.assets || [];
        return this.catalog;
      }
    } catch {}
    const fallback = await fetch('./simready_usd/simready_catalog.json');
    this.catalog = await fallback.json();
    this.assets = this.catalog.assets || [];
    return this.catalog;
  }

  ensureSceneGroup(viewer) {
    if (!viewer || !viewer.THREE || !viewer.scene) return null;
    if (!this.group) {
      this.group = new viewer.THREE.Group();
      this.group.name = 'SimReadyOpenUSDStageGroup';
      viewer.scene.add(this.group);
    } else if (this.group.parent !== viewer.scene) {
      viewer.scene.add(this.group);
    }
    return this.group;
  }

  syncMissionAssets(viewer, missionId) {
    if (!viewer || !viewer.THREE || !this.assets.length) return;
    this.ensureSceneGroup(viewer);
    const targetMission = missionId || 'mission_1_pool';
    this.activeMissionId = targetMission;

    while (this.group.children.length) {
      this.group.remove(this.group.children[0]);
    }
    this.assetNodes.clear();

    const filtered = this.showAllMissions
      ? this.assets
      : this.assets.filter((a) => a.mission_id === targetMission);
    const toSpawn = filtered.length ? filtered : this.assets.slice(0, 2);

    for (const asset of toSpawn) {
      const node = buildSimReadyAssetGroup(viewer.THREE, asset, {
        showCollider: this.showCollider,
        showCoM: this.showCoM,
      });
      this.group.add(node);
      this.assetNodes.set(asset.asset_id, node);
    }
  }

  setColliderVisible(visible) {
    this.showCollider = !!visible;
    for (const node of this.assetNodes.values()) {
      if (node.userData.collisionWireframe) {
        node.userData.collisionWireframe.visible = this.showCollider;
      }
    }
  }

  setCoMVisible(visible) {
    this.showCoM = !!visible;
    for (const node of this.assetNodes.values()) {
      if (node.userData.comGizmo) {
        node.userData.comGizmo.visible = this.showCoM;
      }
    }
  }

  setShowAllMissions(showAll, viewer) {
    this.showAllMissions = !!showAll;
    if (viewer) {
      this.syncMissionAssets(viewer, this.activeMissionId);
    }
  }
}
