// The live 3D background behind every menu screen: the chosen dive site, the chosen vehicle on a turntable,
// and one camera pose per screen that the camera glides between. Owns the menu's WebGL renderer.
import * as THREE from 'three';
import { Environment } from '../environment.js';
import { buildStructures } from '../structures.js';
import { createVehicleModel } from '../vehicle_models.js';
import { placeSceneModelLow } from '../scene_models.js';
import { applyVehicleSticker } from '../vehicle_stickers.js';
import { automaticSceneDetail, configureRenderQuality, updateRenderQuality } from '../render_quality.js';
import { createFrameGate } from '../prefs/display.js';
import { Humanoid } from '../humanoid.js';
// Camera per screen: eye offset from the vehicle (metres, three.js axes); shift moves the vehicle right of
// the screen centre by that many metres (the menus sit on the left), lift raises the look point.
const POSES = {
  title: { eye: [-3.6, 1.1, 4.6], shift: 1.4, lift: 0.35, orbit: 0.03 },
  main: { eye: [-2.2, 0.7, 2.8], shift: 1.0, lift: 0.15, orbit: 0.019 },
  modes: { eye: [-2.3, 0.45, 3.0], shift: 0.9, lift: -0.3, orbit: 0 },
  hangar: { eye: [0.9, 0.35, 1.5], shift: 0.42, lift: 0, orbit: 0 },
  // Overview of the site itself: eye direction scaled by the site's extent, looking at its structures.
  sites: { eye: [-0.55, 0.42, 0.72], shift: 0, lift: -0.22, orbit: 0.02, site: true },
  preview: { eye: [-0.55, 0.42, 0.72], shift: 0, lift: 0, orbit: 0, site: true },
  training: { eye: [2.4, 0.8, 2.6], shift: 1.2, lift: 0.1, orbit: 0 },
  briefing: { eye: [-1.3, 0.5, -1.9], shift: 0.8, lift: 0.05, orbit: 0 },
  multiplayer: { eye: [-2.6, 1.2, 3.2], shift: 1.4, lift: 0.1, orbit: 0 },
  settings: { eye: [-3.0, 1.4, 3.8], shift: 1.7, lift: 0.1, orbit: 0 },
  shop: { eye: [0.9, 0.35, 1.5], shift: 0.42, lift: 0, orbit: 0 },
  launch: { eye: [-0.25, 0.12, -0.55], shift: 0, lift: -0.2, orbit: 0 },
};
const NARROW = 850;
// The title and main menu backdrop: the vehicle with its lamps on beside a lit jacket structure, a darker and
// more distant sea than the site previews. Anchor in NED metres; poses here replace the screen's own eye.
export const SHOWCASE = {
  scene: 'jacket_inspection',
  anchor: [6.5, 1.0, 12.5],
  fog: ['#05202b', 4, 30],
  poses: {
    title: { eye: [1.6, 0.4, -3.6], shift: 1.3, lift: 0.5, orbit: 0.012 },
    main: { eye: [1.3, 0.3, -2.9], shift: 1.0, lift: 0.5, orbit: 0 },
    // YX 裝備部: the vehicle close up, where the equipment goes.
    shop: { eye: [0.9, 0.3, -1.7], shift: 0.5, lift: 0.1, orbit: 0 },
  },
};

const P = function nedToThree(p) {
  return new THREE.Vector3(-p[1], -p[2], p[0]);
};

// Reference half-diagonal of the vehicle the menu poses were framed for, in metres.
const FRAMED_RADIUS = 0.42;

function fitScale(root) {
  const size = new THREE.Box3().setFromObject(root).getSize(new THREE.Vector3());
  const radius = size.length() / 2;
  return Math.max(1, Math.min(3, radius / FRAMED_RADIUS));
}

function disposeTree(group) {
  const geometries = new Set();
  const materials = new Set();
  group.traverse(function release(object) {
    if (object.geometry) geometries.add(object.geometry);
    const list = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of list) {
      if (material) materials.add(material);
    }
  });
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
  group.clear();
}

/** Drop habitat clutter and loose rocks from the journal shot so piles / walls and the vehicle stay the subject. */
function journalWorld(world) {
  const obstacles = (world.obstacles || []).filter(function keep(obstacle) {
    if (obstacle.kind === 'habitat') return false;
    if (obstacle.type === 'snag' && obstacle.item === 'rock') return false;
    if (obstacle.kind === 'toe_rock' || obstacle.kind === 'scour_rock') return false;
    return true;
  });
  // Kelp and seagrass read as flat green slabs under soft lighting; keep fish only.
  const habitat = world.habitat ? {
    ...world.habitat,
    entities: (world.habitat.entities || []).filter(function living(entity) {
      return !['rock', 'kelp', 'seagrass', 'seastar'].includes(entity.kind);
    }),
  } : world.habitat;
  return {...world, obstacles, habitat};
}

// Journal main shot stays on the vehicle, a little higher so the cable and floor gear sit in frame.
const JOURNAL_MAIN = { eye: [-2.7, 1.45, 3.15], shift: 1.15, lift: -0.72, orbit: 0.008 };
const CABLE = 0xc99443;

function cableMaterial() {
  return new THREE.MeshStandardMaterial({color: CABLE, roughness: 0.84, metalness: 0.04});
}

function cableMesh(points) {
  const curve = new THREE.CatmullRomCurve3(points);
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, points.length * 2, 0.009, 5, false), cableMaterial());
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

// Slack umbilical: a short catenary onto the floor, then a loose run lying on it.
function drapePoints(from, floorY, touch, end, side) {
  const points = [];
  const fall = 14;
  for (let i = 0; i <= fall; i += 1) {
    const t = i / fall;
    const ease = Math.sin(t * Math.PI / 2);
    const point = from.clone().lerp(touch, t);
    point.y = from.y + (floorY - from.y) * ease;
    point.addScaledVector(side, Math.sin(t * Math.PI) * 0.38);
    points.push(point);
  }
  const run = 10;
  for (let i = 1; i <= run; i += 1) {
    const t = i / run;
    const point = touch.clone().lerp(end, t);
    point.y = floorY + 0.012;
    point.addScaledVector(side, Math.sin(t * Math.PI) * 0.22);
    points.push(point);
  }
  return points;
}

function floorLoop(center, floorY, right, toward) {
  const points = [];
  const steps = 18;
  for (let i = 0; i <= steps; i += 1) {
    const angle = (i / steps) * Math.PI * 1.7;
    const point = center.clone();
    point.addScaledVector(right, Math.cos(angle) * 0.36);
    point.addScaledVector(toward, Math.sin(angle) * 0.24);
    point.y = floorY + 0.012;
    points.push(point);
  }
  return points;
}

function shadeProp(object) {
  object.traverse(function mark(child) {
    if (!child.isMesh) return;
    child.castShadow = true;
    child.receiveShadow = true;
  });
  return object;
}

function cableReel(position) {
  const group = new THREE.Group();
  group.position.copy(position);
  const steel = new THREE.MeshStandardMaterial({color: 0x6a726e, roughness: 0.55, metalness: 0.4});
  const wound = new THREE.MeshStandardMaterial({color: CABLE, roughness: 0.8, metalness: 0.05});
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.32, 12), wound);
  drum.rotation.z = Math.PI / 2;
  const flange = new THREE.CylinderGeometry(0.36, 0.36, 0.03, 16);
  const left = new THREE.Mesh(flange, steel);
  left.rotation.z = Math.PI / 2;
  left.position.x = -0.17;
  const right = left.clone();
  right.position.x = 0.17;
  const legGeo = new THREE.BoxGeometry(0.06, 0.34, 0.06);
  const legA = new THREE.Mesh(legGeo, steel);
  legA.position.set(-0.17, -0.2, 0.16);
  const legB = legA.clone();
  legB.position.z = -0.16;
  const legC = legA.clone();
  legC.position.x = 0.17;
  const legD = legB.clone();
  legD.position.x = 0.17;
  group.add(drum, left, right, legA, legB, legC, legD);
  return shadeProp(group);
}

function toolBox(position) {
  const group = new THREE.Group();
  group.position.copy(position);
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.58, 0.26, 0.32),
    new THREE.MeshStandardMaterial({color: 0xb4531f, roughness: 0.66, metalness: 0.08}),
  );
  const lid = new THREE.Mesh(
    new THREE.BoxGeometry(0.58, 0.05, 0.32),
    new THREE.MeshStandardMaterial({color: 0x8a3e16, roughness: 0.72, metalness: 0.06}),
  );
  lid.position.y = 0.155;
  const handle = new THREE.Mesh(
    new THREE.TorusGeometry(0.09, 0.012, 6, 10, Math.PI),
    new THREE.MeshStandardMaterial({color: 0x24282a, roughness: 0.4, metalness: 0.55}),
  );
  handle.rotation.z = Math.PI;
  handle.position.y = 0.22;
  group.add(body, lid, handle);
  return shadeProp(group);
}

function viewBasis() {
  const toward = new THREE.Vector3(JOURNAL_MAIN.eye[0], 0, JOURNAL_MAIN.eye[2]);
  if (toward.lengthSq() < 1e-6) toward.set(0, 0, 1);
  toward.normalize();
  const right = new THREE.Vector3(toward.z, 0, -toward.x);
  return { toward, right };
}

export function createStage(host, { quality = 'auto' } = {}) {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const scene = new THREE.Scene();
  const SEA = ['#0c3342', 7, 36];
  scene.background = new THREE.Color(SEA[0]);
  scene.fog = new THREE.Fog(SEA[0], SEA[1], SEA[2]);
  // The vehicle's lamps, switched on for the showcase backdrop only.
  const lamps = new THREE.Group();
  for (const side of [-0.16, 0.16]) {
    const lamp = new THREE.SpotLight(0xfff0d8, 60, 22, 0.42, 0.55, 1.4);
    lamp.position.set(side, 0.05, 0.3);
    lamp.target.position.set(side * 4, -0.6, 6);
    lamps.add(lamp, lamp.target);
  }
  lamps.visible = false;
  scene.add(new THREE.HemisphereLight(0xc9eeff, 0x29362b, 2));
  const keyLight = new THREE.DirectionalLight(0xffffff, 3);
  keyLight.position.set(3, 7, 6);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  keyLight.shadow.camera.near = 1;
  keyLight.shadow.camera.far = 60;
  keyLight.shadow.camera.left = -18;
  keyLight.shadow.camera.right = 18;
  keyLight.shadow.camera.top = 18;
  keyLight.shadow.camera.bottom = -18;
  scene.add(keyLight);
  const fill = new THREE.DirectionalLight(0x64c4dc, 2);
  fill.position.set(-4, 2, -1);
  scene.add(fill);
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.className = 'menu-canvas';
  host.prepend(renderer.domElement);
  configureRenderQuality(renderer, quality);
  let qualityMode = quality;
  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.02, 5000);
  const structures = new THREE.Group();
  scene.add(structures);
  const dressing = new THREE.Group();
  scene.add(dressing);
  const anchor = new THREE.Vector3(0, -12, 0);
  const siteFocus = new THREE.Vector3(0, -12, 0);
  let siteExtent = 10;
  let seabed = -12;
  const eye = new THREE.Vector3();
  const look = new THREE.Vector3();
  const targetEye = new THREE.Vector3();
  const targetLook = new THREE.Vector3();
  let pose = POSES.title;
  let poseName = 'title';
  let snapped = false;
  let model = null;
  let environment = null;
  let modelTicket = 0;
  let sceneTicket = 0;
  let elapsed = 0;
  let spin = 0.45;
  let spinVelocity = 0;
  let sticker = 'none';
  let showcase = false;
  let journal = '';
  let still = false;
  let disposed = false;
  let raf = 0;
  let crewLib = null;
  let crewTicket = 0;
  // The fog set by setSea (SEA or SHOWCASE.fog); site cards widen it per frame and other poses restore it.
  let sea = SEA;
  // Large vehicles push the hangar camera back so they are never cropped (1 = the size the poses were set for).
  let modelScale = 1;
  let last = performance.now();
  const state = { modelReady: false, sceneReady: false, modelId: '', sceneKey: '' };

  function resize() {
    if (disposed) return;
    still = false;
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  }
  async function setModel(id) {
    if (disposed) return;
    if (state.modelId === id && model) return;
    state.modelId = id;
    state.modelReady = false;
    const ticket = ++modelTicket;
    const next = await createVehicleModel(id);
    if (ticket !== modelTicket || disposed) {
      next.dispose();
      return;
    }
    if (next.loadError) {
      next.dispose();
      throw next.loadError;
    }
    model?.root.removeFromParent();
    model?.dispose();
    model = next;
    scene.add(model.root);
    model.root.add(lamps);
    model.root.traverse(function shade(object) {
      if (object.isMesh) object.castShadow = true;
    });
    modelScale = fitScale(model.root);
    model.root.position.copy(anchor);
    model.updateArm({ joints: [0, -15, 30, -15], grip: 0.7 });
    applyVehicleSticker(model, sticker);
    state.modelReady = true;
    still = false;
  }
  function setSticker(preset) {
    still = false;
    sticker = preset;
    if (model) applyVehicleSticker(model, preset);
  }
  // Where a site's interest is: its structures, else the living patch nearest the vehicle; and how far it spreads.
  function placeSiteFocus(world) {
    const points = [];
    for (const obstacle of world.obstacles || []) {
      if (obstacle.kind === 'habitat') continue;
      if (obstacle.type === 'cylinder') points.push(P(obstacle.p0).lerp(P(obstacle.p1), 0.5));
      else if (obstacle.type === 'box' || obstacle.type === 'ship_hull') points.push(P(obstacle.center));
      else if (obstacle.type === 'model') points.push(P(obstacle.origin));
    }
    if (!points.length) {
      const living = (world.habitat?.entities || []).filter(function showcase(entity) {
        return ['coral', 'seagrass', 'kelp'].includes(entity.kind);
      }).map(function position(entity) {
        return P(entity.pos);
      }).sort(function nearest(a, b) {
        return a.distanceTo(anchor) - b.distanceTo(anchor);
      });
      points.push(...living.slice(0, 12));
    }
    if (!points.length) points.push(anchor.clone());
    siteFocus.set(0, 0, 0);
    for (const point of points) siteFocus.add(point);
    siteFocus.divideScalar(points.length);
    seabed = -world.seabed_depth;
    // Lift the look point off the sand so a half-buried wreck's deck stays in frame.
    siteFocus.y = Math.max(seabed + 4, Math.min(-2, siteFocus.y + 3));
    let spread = 0;
    for (const point of points) spread = Math.max(spread, point.distanceTo(siteFocus));
    // Single authored models need a mid-hull overview inside the menu fog far plane.
    const floor = spread > 1 ? 8 : 14;
    siteExtent = Math.max(floor, Math.min(26, spread * 1.3 + 6));
  }
  function placeAnchor(world) {
    if (showcase) {
      anchor.copy(P(SHOWCASE.anchor));
      return;
    }
    seabed = -world.seabed_depth;
    if (journal) {
      // Frame the working piles / walls, not a stray habitat patch that pulls the shot onto a rock.
      const piles = (world.obstacles || []).filter(function pile(obstacle) {
        return obstacle.type === 'cylinder' && (!obstacle.kind || obstacle.kind === 'pile');
      });
      if (piles[0]) {
        const pile = piles[0];
        const mid = P(pile.p0).lerp(P(pile.p1), 0.55);
        const out = new THREE.Vector3(mid.x, 0, mid.z).normalize();
        if (!Number.isFinite(out.x)) out.set(0, 0, -1);
        anchor.copy(mid).addScaledVector(out, -(pile.radius || 0.65) - 2.2);
        anchor.y = Math.max(seabed + 1.6, Math.min(-2.5, mid.y));
        return;
      }
      const wall = (world.obstacles || []).find(function pool(obstacle) {
        return obstacle.kind === 'pool_wall' || obstacle.type === 'wall';
      });
      if (wall?.p0) {
        anchor.copy(P(world.start_pos || [0, 0, 3]));
        // Sit the vehicle just off the pool floor so the spare cable reads as a short drape, not a pole.
        anchor.y = seabed + 1.35;
        return;
      }
    }
    anchor.copy(P(world.start_pos || [0, 0, 0]));
    anchor.y = -world.seabed_depth + 1.4;
    const living = (world.habitat?.entities || []).filter(function showcase(entity) {
      return ['coral', 'seagrass', 'kelp'].includes(entity.kind);
    }).sort(function nearest(a, b) {
      return Math.hypot(a.pos[0], a.pos[1]) - Math.hypot(b.pos[0], b.pos[1]);
    });
    if (living[0]?.pos) {
      anchor.copy(P(living[0].pos));
      anchor.y += 1.5;
    }
  }
  function setSea([color, near, far]) {
    sea = [color, near, far];
    scene.background.set(color);
    scene.fog.color.set(color);
    scene.fog.near = near;
    scene.fog.far = far;
  }
  function placeCrew(position, yaw) {
    if (!crewLib) return;
    const crew = new Humanoid(crewLib, {
      shirt: 0x2b3f55, pants: 0x2a2f36, vest: 0xff6a13, helmet: 0xf4f4ef,
    });
    crew.root.position.copy(position);
    crew.root.rotation.y = yaw;
    crew.play('Idle', {at: 0.4});
    crew.root.traverse(function shade(object) {
      if (object.isMesh) object.castShadow = true;
    });
    dressing.add(crew.root);
    dressing.userData.crew = crew;
  }
  function clearDressing() {
    const crew = dressing.userData.crew;
    if (crew) {
      crew.root.removeFromParent();
      dressing.userData.crew = null;
    }
    disposeTree(dressing);
  }
  // Spare umbilical, reel and toolbox on the floor behind the vehicle, where the main shot looks down.
  function layWorksite(floorY) {
    const { toward, right } = viewBasis();
    const back = toward.clone().multiplyScalar(-1);
    const gland = anchor.clone();
    gland.y += 0.02;
    gland.addScaledVector(back, 0.35);
    const touch = anchor.clone();
    touch.y = floorY;
    touch.addScaledVector(back, 1.35);
    touch.addScaledVector(right, 0.15);
    const end = touch.clone().addScaledVector(back, 0.45).addScaledVector(right, 0.7);
    dressing.add(cableMesh(drapePoints(gland, floorY, touch, end, right)));
    dressing.add(cableMesh(floorLoop(end, floorY, right, back)));
    const reelPos = touch.clone().addScaledVector(right, -0.85);
    reelPos.y = floorY + 0.37;
    const reel = cableReel(reelPos);
    reel.rotation.y = Math.atan2(back.x, back.z);
    dressing.add(reel);
    const boxPos = end.clone().addScaledVector(right, 0.15).addScaledVector(back, 0.15);
    boxPos.y = floorY + 0.13;
    const box = toolBox(boxPos);
    box.rotation.y = reel.rotation.y + 0.5;
    dressing.add(box);
  }
  function dressJournal(world) {
    clearDressing();
    const ticket = ++crewTicket;
    if (!journal) return;
    const floorY = seabed + 0.03;
    layWorksite(floorY);
    const deck = (world.obstacles || []).find(function jetty(obstacle) {
      return obstacle.kind === 'deck';
    });
    if (deck?.center) {
      const spot = P(deck.center);
      spot.y += 0.02;
      placeCrew(spot, Math.PI * 0.7);
    }
    // Humanoid loads asynchronously; refresh dressing once when the library arrives.
    if (!crewLib && deck?.center) {
      Humanoid.load('models/worker.glb').then(function ready(lib) {
        if (disposed || ticket !== crewTicket) return;
        crewLib = lib;
        dressJournal(world);
      }).catch(function ignored() {});
    }
  }
  // entry: a scene_previews.json entry; showcase: frame it as the title backdrop (SHOWCASE) instead.
  function setScene(entry, { showcase: hero = false, journal: chapter = '' } = {}) {
    if (!entry || disposed) return;
    if (state.sceneKey === entry.key && hero === showcase && journal === chapter) return;
    journal = chapter;
    still = false;
    keyLight.color.set(journal === 'prologue' ? 0xffbf89 : journal === 'ch2' ? 0xb4cad4 : 0xffffff);
    showcase = hero;
    lamps.visible = hero;
    setPose(poseName);
    const seas = {prologue: ['#3d5a62', 4, 26], ch1: ['#284a4b', 4, 34], ch2: ['#15383f', 2, 22]};
    setSea(seas[journal] || (hero ? SHOWCASE.fog : SEA));
    if (state.sceneKey === entry.key) {
      placeAnchor(entry.world);
      dressJournal(journal ? journalWorld(entry.world) : entry.world);
      snapped = false;
      return;
    }
    state.sceneKey = entry.key;
    const ticket = ++sceneTicket;
    const source = journal ? journalWorld(entry.world) : entry.world;
    environment?.dispose();
    environment = new Environment(scene, source, { detail: backdropDetail(hero) });
    disposeTree(structures);
    // Journal shots use medium structures so piles read as round concrete with fouling, not flat green plates.
    const structureDetail = journal ? 'medium' : 'low';
    const built = buildStructures(source, { detail: structureDetail });
    built.group.traverse(function shade(object) {
      if (!object.isMesh) return;
      object.castShadow = true;
      object.receiveShadow = true;
    });
    structures.add(built.group);
    for (const obstacle of source.obstacles || []) {
      if (obstacle.type === 'model') {
        // Menu background loads one reduced authored LOD (scene_models.js placeSceneModelLow), never the full mesh.
        placeSceneModelLow(obstacle, structures, P, function current() {
          return ticket === sceneTicket && !disposed;
        });
      }
    }
    placeAnchor(source);
    placeSiteFocus(source);
    dressJournal(source);
    snapped = false;
    state.sceneReady = true;
  }
  // Backdrop detail follows the quality setting: the low scene wherever the dive uses it (performance, or automatic
  // quality on software / integrated / entry-level GPUs), medium for medium. Otherwise the title scene keeps its high
  // detail (structure life: two instanced draws) and the site cards medium.
  function backdropDetail(hero) {
    if (qualityMode === 'performance' || qualityMode === 'low') return 'low';
    if (qualityMode === 'auto' && automaticSceneDetail(renderer) === 'low') return 'low';
    if (qualityMode === 'medium') return 'medium';
    return hero ? 'high' : 'medium';
  }
  function setPose(name) {
    still = false;
    poseName = name;
    if (journal && name === 'main') pose = JOURNAL_MAIN;
    else pose = (showcase && SHOWCASE.poses[name]) || POSES[name] || POSES.main;
    dressing.visible = Boolean(journal) && name === 'main';
  }
  // value: −1..1 from the stick or a pointer drag; turns the turntable with a little momentum.
  function rotate(value, dt) {
    spinVelocity = value * 2.4;
    spin += spinVelocity * dt;
  }
  function poseTargets() {
    const narrow = innerWidth < NARROW;
    const orbit = reduced ? 0 : elapsed * pose.orbit;
    const up = new THREE.Vector3(0, 1, 0);
    const offset = new THREE.Vector3(...pose.eye).applyAxisAngle(up, orbit);
    if (narrow) offset.multiplyScalar(1.3);
    const fit = pose === POSES.hangar ? modelScale : 1;
    offset.multiplyScalar(fit);
    const forward = offset.clone().negate().normalize();
    const right = new THREE.Vector3().crossVectors(forward, up).normalize();
    const shift = narrow ? 0 : pose.shift * fit;
    const lift = narrow ? pose.lift + 0.45 : pose.lift;
    if (pose.site) {
      targetEye.copy(siteFocus).addScaledVector(offset, siteExtent);
      targetEye.y = Math.max(seabed + 1, Math.min(-1, targetEye.y));
      targetLook.copy(siteFocus).addScaledVector(up, pose.lift * siteExtent);
      return;
    }
    targetEye.copy(anchor).add(offset);
    targetLook.copy(anchor).addScaledVector(right, -shift).addScaledVector(up, lift);
  }
  const skipFrame = createFrameGate();
  function frame(now) {
    if (disposed) return;
    raf = requestAnimationFrame(frame);
    if (still || skipFrame(now)) return;
    const seconds = (now - last) / 1000;
    const dt = Math.min(0.05, seconds);
    last = now;
    updateRenderQuality(renderer, seconds, { suspended: !state.modelReady || !state.sceneReady });
    if (!reduced) elapsed += dt;
    if (model) {
      model.root.position.copy(anchor);
      model.root.position.y += Math.sin(elapsed * 0.6) * 0.07;
      if (!reduced && Math.abs(spinVelocity) < 0.01 && pose === POSES.hangar) spin += dt * 0.12;
      spinVelocity *= Math.exp(-dt * 4);
      // The showcase vehicle faces the camera three-quarters on, lamps towards the viewer and the jacket.
      const facing = showcase ? Math.PI * -0.1 : spin;
      model.root.rotation.y = facing + (pose === POSES.hangar ? 0 : Math.sin(elapsed * 0.18) * 0.18);
    }
    poseTargets();
    const holdShot = journal && poseName === 'main' && backdropDetail(false) === 'low';
    if (!snapped || reduced || holdShot) {
      eye.copy(targetEye);
      look.copy(targetLook);
      snapped = true;
    } else {
      // Real elapsed time, not the capped frame step, so a slow renderer still arrives at the pose.
      const blend = 1 - Math.exp(-Math.min(1, seconds) * 2.6);
      eye.lerp(targetEye, blend);
      look.lerp(targetLook, blend);
    }
    camera.position.copy(eye);
    camera.lookAt(look);
    // Site overview cards need a longer fog reach than the hangar turntable.
    if (pose.site) {
      scene.fog.near = Math.max(4, siteExtent * 0.35);
      scene.fog.far = Math.max(40, siteExtent * 3);
    } else {
      scene.fog.near = sea[1];
      scene.fog.far = sea[2];
    }
    environment?.update(dt, camera, new THREE.Vector3(0.1, 0, 0));
    dressing.userData.crew?.update?.(dt);
    renderer.render(scene, camera);
    still = holdShot && state.modelReady;
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(raf);
    removeEventListener('resize', resize);
    environment?.dispose();
    environment = null;
    model?.root.removeFromParent();
    model?.dispose();
    model = null;
    disposeTree(structures);
    clearDressing();
    // dispose() drops GPU objects but keeps the WebGL context. A second context on the dive page
    // then doubles software-GL frame time and the cold-open pilot flies into the jacket.
    renderer.forceContextLoss();
    renderer.dispose();
    renderer.domElement.remove();
  }
  resize();
  addEventListener('resize', resize);
  raf = requestAnimationFrame(frame);
  return {
    renderer,
    scene,
    camera,
    state,
    setModel,
    setScene,
    setSticker,
    setPose,
    rotate,
    dispose,
    configureQuality(mode) {
      still = false;
      qualityMode = mode;
      configureRenderQuality(renderer, mode);
    },
    get showcase() {
      return showcase;
    },
    get stickerMeshes() {
      return model?.stickerGroup?.children.length || 0;
    },
  };
}
