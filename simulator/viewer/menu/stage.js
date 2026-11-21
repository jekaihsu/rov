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
import { applyPose, makePerson, POSES as CREW_POSES } from '../figures.js';

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
  group.traverse(function release(object) {
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) material?.dispose();
  });
  group.clear();
}

/** Drop loose seabed rocks from the journal shot so piles and the vehicle stay the subject. */
function journalWorld(world) {
  const obstacles = (world.obstacles || []).filter(function keep(obstacle) {
    if (obstacle.kind === 'habitat') return false;
    if (obstacle.type === 'snag' && obstacle.item === 'rock') return false;
    if (obstacle.kind === 'toe_rock' || obstacle.kind === 'scour_rock') return false;
    return true;
  });
  const habitat = world.habitat ? {
    ...world.habitat,
    entities: (world.habitat.entities || []).filter(function living(entity) {
      return entity.kind !== 'rock';
    }),
  } : world.habitat;
  return {...world, obstacles, habitat};
}

function workCable(from, to) {
  const curve = new THREE.CatmullRomCurve3([
    from.clone(),
    from.clone().lerp(to, 0.35).add(new THREE.Vector3(0.2, 0.35, -0.4)),
    from.clone().lerp(to, 0.7).add(new THREE.Vector3(-0.15, 0.15, -0.2)),
    to.clone(),
  ]);
  return new THREE.Mesh(
    new THREE.TubeGeometry(curve, 20, 0.018, 6, false),
    new THREE.MeshStandardMaterial({color: 0xb8893d, roughness: 0.85, metalness: 0.05}),
  );
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
  const umbilical = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, .1, 0), new THREE.Vector3(-.4, .35, -.8),
    new THREE.Vector3(-1.4, 1.2, -3), new THREE.Vector3(-2.5, 8, -7),
  ]);
  const tether = new THREE.Mesh(new THREE.TubeGeometry(umbilical, 24, .014, 5, false),
    new THREE.MeshStandardMaterial({color: 0xc99443, roughness: .8}));
  scene.add(tether);
  tether.visible = false;
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
  function dressJournal(world) {
    disposeTree(dressing);
    if (!journal) return;
    const piles = (world.obstacles || []).filter(function pile(obstacle) {
      return obstacle.type === 'cylinder' && (!obstacle.kind || obstacle.kind === 'pile');
    });
    if (piles.length) {
      const first = P(piles[0].p0).lerp(P(piles[0].p1), 0.35);
      const second = piles[1]
        ? P(piles[1].p0).lerp(P(piles[1].p1), 0.4)
        : first.clone().add(new THREE.Vector3(2, 0, 1));
      const cable = workCable(first.clone().add(new THREE.Vector3(0.1, 0.2, 0)), second);
      dressing.add(cable);
      const deck = (world.obstacles || []).find(function jetty(obstacle) {
        return obstacle.kind === 'deck';
      });
      if (deck?.center) {
        const crew = makePerson({suit: 0x243746, vest: 0xff6a13, helmet: 0xf4f4ef});
        applyPose(crew.j, CREW_POSES.stand);
        crew.root.position.copy(P(deck.center));
        crew.root.position.y += 0.05;
        crew.root.rotation.y = Math.PI * 0.65;
        crew.root.traverse(function shade(object) {
          if (object.isMesh) {
            object.castShadow = true;
            object.receiveShadow = true;
          }
        });
        dressing.add(crew.root);
      }
    } else {
      // Indoor pool: a tender on the pool deck at the waterline, plus a spare umbilical loop in frame.
      const crew = makePerson({suit: 0x2a3a48, vest: 0xff7a2f, helmet: 0xf2f2f0});
      applyPose(crew.j, CREW_POSES.stand);
      crew.root.position.set(anchor.x + 1.2, 0.02, anchor.z - 4.5);
      crew.root.rotation.y = Math.PI;
      dressing.add(crew.root);
      const loop = workCable(
        anchor.clone().add(new THREE.Vector3(-0.3, 0.05, 0.2)),
        anchor.clone().add(new THREE.Vector3(1.6, 0.4, -1.8)),
      );
      dressing.add(loop);
    }
  }
  // entry: a scene_previews.json entry; showcase: frame it as the title backdrop (SHOWCASE) instead.
  function setScene(entry, { showcase: hero = false, journal: chapter = '' } = {}) {
    if (!entry || disposed) return;
    if (state.sceneKey === entry.key && hero === showcase && journal === chapter) return;
    journal = chapter;
    tether.visible = !!journal;
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
    tether.position.copy(anchor);
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
    disposeTree(dressing);
    tether.geometry.dispose();
    tether.material.dispose();
    scene.remove(tether);
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
