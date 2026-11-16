// The live 3D background behind every menu screen: the chosen dive site, the chosen vehicle on a turntable,
// and one camera pose per screen that the camera glides between. Owns the menu's WebGL renderer.
import * as THREE from 'three';
import { Environment } from '../environment.js';
import { buildStructures } from '../structures.js';
import { createVehicleModel } from '../vehicle_models.js';
import { loadGLTF } from '../glb.js';
import { applyVehicleSticker } from '../vehicle_stickers.js';
import { configureRenderQuality, updateRenderQuality } from '../render_quality.js';
import { createFrameGate } from '../prefs/display.js';

// Camera per screen: eye offset from the vehicle (metres, three.js axes); shift moves the vehicle right of
// the screen centre by that many metres (the menus sit on the left), lift raises the look point.
const POSES = {
  title: { eye: [-3.6, 1.1, 4.6], shift: 1.4, lift: 0.35, orbit: 0.03 },
  main: { eye: [-2.2, 0.7, 2.8], shift: 1.0, lift: 0.15, orbit: 0 },
  modes: { eye: [-1.6, 2.0, 3.2], shift: 0, lift: -0.8, orbit: 0 },
  hangar: { eye: [0.9, 0.35, 1.5], shift: 0.42, lift: 0, orbit: 0 },
  // Overview of the site itself: eye direction scaled by the site's extent, looking at its structures.
  sites: { eye: [-0.55, 0.42, 0.72], shift: 0, lift: -0.22, orbit: 0.02, site: true },
  preview: { eye: [-0.55, 0.42, 0.72], shift: 0, lift: 0, orbit: 0, site: true },
  training: { eye: [2.4, 0.8, 2.6], shift: 1.2, lift: 0.1, orbit: 0 },
  briefing: { eye: [-1.3, 0.5, -1.9], shift: 0.8, lift: 0.05, orbit: 0 },
  multiplayer: { eye: [-2.6, 1.2, 3.2], shift: 1.4, lift: 0.1, orbit: 0 },
  settings: { eye: [-3.0, 1.4, 3.8], shift: 1.7, lift: 0.1, orbit: 0 },
  launch: { eye: [-0.25, 0.12, -0.55], shift: 0, lift: -0.2, orbit: 0 },
  new_game_assisted: { eye: [-4.2, 1.6, 5.2], shift: 1.8, lift: 0.2, orbit: 0.02 },
  new_game_standard: { eye: [-1.2, 0.35, 1.6], shift: 1.5, lift: 0.05, orbit: 0 },
  new_game_real: { eye: [-0.35, 0.12, 0.55], shift: 1.4, lift: 0, orbit: 0 },
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
    // New-game difficulty previews: same site, vehicle framed on the right half of the screen.
    new_game_assisted: { eye: [2.4, 1.1, -4.2], shift: 1.8, lift: 0.35, orbit: 0.02 },
    new_game_standard: { eye: [0.6, 0.25, -1.4], shift: 1.6, lift: 0.15, orbit: 0 },
    new_game_real: { eye: [0.15, 0.08, -0.55], shift: 1.5, lift: 0.05, orbit: 0 },
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
  group.traverse(function release(object) {
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) material?.dispose();
  });
  group.clear();
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
  for (const [position, power, color] of [[[3, 7, 6], 3, 0xffffff], [[-4, 2, -1], 2, 0x64c4dc]]) {
    const light = new THREE.DirectionalLight(color, power);
    light.position.set(...position);
    scene.add(light);
  }
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.domElement.className = 'menu-canvas';
  host.prepend(renderer.domElement);
  configureRenderQuality(renderer, quality);
  const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.02, 5000);
  const structures = new THREE.Group();
  scene.add(structures);
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
  // Large vehicles push the hangar camera back so they are never cropped (1 = the size the poses were set for).
  let modelScale = 1;
  let last = performance.now();
  const state = { modelReady: false, sceneReady: false, modelId: '', sceneKey: '' };

  function resize() {
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  }
  async function setModel(id) {
    if (state.modelId === id && model) return;
    state.modelId = id;
    state.modelReady = false;
    const ticket = ++modelTicket;
    const next = await createVehicleModel(id);
    if (ticket !== modelTicket) {
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
    modelScale = fitScale(model.root);
    model.root.position.copy(anchor);
    model.updateArm({ joints: [0, -15, 30, -15], grip: 0.7 });
    applyVehicleSticker(model, sticker);
    state.modelReady = true;
  }
  function setSticker(preset) {
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
    siteFocus.y = Math.max(seabed + 1.5, Math.min(-2, siteFocus.y));
    let spread = 0;
    for (const point of points) spread = Math.max(spread, point.distanceTo(siteFocus));
    siteExtent = Math.max(8, Math.min(26, spread * 1.3 + 6));
  }
  function placeAnchor(world) {
    if (showcase) {
      anchor.copy(P(SHOWCASE.anchor));
      return;
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
    scene.background.set(color);
    scene.fog.color.set(color);
    scene.fog.near = near;
    scene.fog.far = far;
  }
  // entry: a scene_previews.json entry; showcase: frame it as the title backdrop (SHOWCASE) instead.
  function setScene(entry, { showcase: hero = false } = {}) {
    if (!entry) return;
    if (state.sceneKey === entry.key && hero === showcase) return;
    showcase = hero;
    lamps.visible = hero;
    setPose(poseName);
    setSea(hero ? SHOWCASE.fog : SEA);
    if (state.sceneKey === entry.key) {
      placeAnchor(entry.world);
      snapped = false;
      return;
    }
    state.sceneKey = entry.key;
    const ticket = ++sceneTicket;
    const world = entry.world;
    environment?.dispose();
    environment = new Environment(scene, world, { detail: hero ? 'high' : 'medium' });
    disposeTree(structures);
    // the same dressed structures as the dive (low tier), so the site cards and the background match the game
    structures.add(buildStructures(world, { detail: 'low' }).group);
    for (const obstacle of world.obstacles || []) {
      if (obstacle.type === 'model') {
        loadGLTF(obstacle.model).then(function placeModel(gltf) {
          if (ticket !== sceneTicket) return;
          const heading = obstacle.heading_deg * Math.PI / 180;
          gltf.scene.position.copy(P(obstacle.origin));
          gltf.scene.rotation.y = Math.atan2(-Math.cos(heading), -Math.sin(heading));
          structures.add(gltf.scene);
        }).catch(function ignoreMissingModel() {});
      }
    }
    placeAnchor(world);
    placeSiteFocus(world);
    snapped = false;
    state.sceneReady = true;
  }
  function setPose(name) {
    poseName = name;
    pose = (showcase && SHOWCASE.poses[name]) || POSES[name] || POSES.main;
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
    if (skipFrame(now)) {
      requestAnimationFrame(frame);
      return;
    }
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
    if (!snapped || reduced) {
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
    environment?.update(dt, camera, new THREE.Vector3(0.1, 0, 0));
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  resize();
  addEventListener('resize', resize);
  requestAnimationFrame(frame);
  return {
    renderer,
    state,
    setModel,
    setScene,
    setSticker,
    setPose,
    rotate,
    configureQuality(mode) {
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
