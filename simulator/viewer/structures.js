// Inspection structures drawn from the simulator's collision obstacles, one builder per obstacle kind.
//
// The server's obstacle list is the single source of truth: every mesh that a vehicle or the tether could touch
// is generated inside (or on the surface of) the collision shape it belongs to, so what the pilot sees is what
// the physics hits. Fine dressing that is not in the physics (weld-node cans, mussel lumps, panel joints, hull
// zinc blocks) stays within SCENE_TOLERANCE of the surface; tests/test_scene_consistency.py builds these meshes in
// Node and checks every vertex against the Python shapes. Above-water fittings (cope, platform, deck furniture)
// are drawn as well; the vehicle cannot reach them.
//
//   const set = buildStructures(world, {detail: structureDetail()});
//   scene.add(set.group);  set.entries: Map(name -> {mesh, ob});  set.highlight(hotNames);  set.dispose();
//
// Each mesh carries userData.colliders (obstacle names it is drawn for) and userData.role:
//   'solid'     the collision shape itself (vertices on or inside it)
//   'attached'  thin dressing on a collider's surface (within SCENE_TOLERANCE outside it)
//   'above'     above the waterline, out of the vehicle's reach
import * as THREE from 'three';
import {chainSegment, harborStructures} from './harbor.js';
import {buildPenPart, penMaterial} from './aquaculture.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {aftEnd, halfBreadth, obstacleDistance, shipHullParams, snagCapsule} from './structure_sdf.js';
import {structureMaterial} from './structure_materials.js';
import {automaticSceneDetail} from './render_quality.js';
import {siteRockColor} from './seabed.js';
import {upgradeArmourRocks} from './scan_materials.js';

export const SCENE_TOLERANCE = 0.1;           // m a visual surface may stand proud of its collision shape
// fittings drawn as one merged mesh per material (labels keep per-obstacle anchors; a snag lights the group)
const BATCH_KINDS = new Set(['anode', 'anode_strap', 'mudmat', 'boat_landing', 'j_tube', 'cable_protection',
  'fender', 'bollard', 'ladder', 'tyre', 'debris_block', 'debris_pipe', 'shaft', 'deck', 'mast', 'snag']);
const UP = new THREE.Vector3(0, 1, 0);
const DETAIL = {
  low: {radial: 12, rockDetail: -1, lumps: 0, hullX: 40, hullZ: 8},
  medium: {radial: 16, rockDetail: -1, lumps: 0, hullX: 40, hullZ: 8},
  high: {radial: 28, rockDetail: 0, lumps: 90, hullX: 140, hullZ: 22},
};

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);

/**
 * Scene detail tier from the render-quality setting: performance -> low, high -> high, medium -> medium.
 * Automatic quality uses medium, or low when ``renderer`` is drawn in software (no GPU) or on an integrated /
 * entry-level GPU, where shading cost grows with every texture read (render_quality.js automaticSceneDetail).
 */
export function structureDetail(renderer = null) {
  let mode = 'auto';
  try {
    mode = globalThis.localStorage?.getItem('rov.quality') || 'auto';
  } catch {
    mode = 'auto';
  }
  if (mode === 'performance') return 'low';
  if (mode === 'high') return 'high';
  if (mode === 'auto' && renderer) return automaticSceneDetail(renderer);
  return 'medium';
}

function seeded(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  let a = h >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── geometry helpers (all return geometry already placed in three world space) ──────────────────────────
function prepared(geometry) {
  const g = geometry.index ? geometry.toNonIndexed() : geometry;
  if (g !== geometry) geometry.dispose();
  if (!g.attributes.uv) {
    g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
  }
  if (!g.attributes.normal) g.computeVertexNormals();
  for (const name of Object.keys(g.attributes)) {
    if (!['position', 'normal', 'uv'].includes(name)) g.deleteAttribute(name);
  }
  return g;
}

function merged(list) {
  const parts = list.filter(Boolean).map(prepared);
  const out = mergeGeometries(parts, false);
  for (const g of parts) g.dispose();
  return out;
}

/** Cylinder of radius r from a to b (three vectors), optionally open, with UVs in metres. */
function tube(a, b, r, radial, open = false, rTop = r) {
  const length = a.distanceTo(b);
  const g = new THREE.CylinderGeometry(rTop, r, length, radial, Math.max(1, Math.round(length / 4)), open);
  const uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 2 * Math.PI * r, uv.getY(i) * length);
  const q = new THREE.Quaternion().setFromUnitVectors(UP, b.clone().sub(a).normalize());
  g.applyQuaternion(q);
  g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
  return g;
}

function boxAt(center, size, yawRad, extraTilt = null) {
  const g = new THREE.BoxGeometry(size.x, size.y, size.z);
  if (extraTilt) g.applyQuaternion(extraTilt);
  g.rotateY(yawRad);
  g.translate(center.x, center.y, center.z);
  return g;
}

/** Deformed icosahedron with every vertex inside the unit sphere (scale = bounding radius). */
const rockCache = new Map();
function unitRock(seed, detail) {
  const key = `${seed}:${detail}`;
  if (rockCache.has(key)) return rockCache.get(key);
  // detail -1: an octahedron (8 faces) for distant armour on the low and medium tiers
  const g = detail < 0 ? new THREE.OctahedronGeometry(1, 0) : new THREE.IcosahedronGeometry(1, detail);
  const p = g.attributes.position;
  const v = new THREE.Vector3();
  let maxR = 0;
  const R = seeded(key);
  const lobes = [0, 1, 2].map(() => new THREE.Vector3(R() - .5, R() - .5, R() - .5).normalize());
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    let k = 0.8;
    for (const lobe of lobes) k += Math.max(0, v.dot(lobe)) * 0.18;
    k += (R() - 0.5) * 0.12;
    v.multiplyScalar(k);
    v.y *= 0.72;
    maxR = Math.max(maxR, v.length());
    p.setXYZ(i, v.x, v.y, v.z);
  }
  g.scale(1 / maxR, 1 / maxR, 1 / maxR);
  g.computeVertexNormals();
  rockCache.set(key, g);
  return g;
}

/** Hemispherical caps for capsule ends that are under water, above the seabed and not inside another shape. */
function exposedCaps(world, ob, radius, radial) {
  const caps = [];
  const others = (world.obstacles || []).filter((o) => o !== ob && o.kind !== 'habitat' && o.type !== 'model');
  for (const [end, other] of [[ob.p0, ob.p1], [ob.p1, ob.p0]]) {
    if (end[2] < 0.05 || end[2] > (world.seabed_depth ?? 30) - 0.05) continue;
    if (others.some((o) => obstacleDistance(end, o) < 0.05)) continue;
    const cap = new THREE.SphereGeometry(radius, radial, 6, 0, Math.PI * 2, 0, Math.PI / 2);
    const out = P(end).sub(P(other)).normalize();
    cap.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(UP, out));
    const at = P(end);
    cap.translate(at.x, at.y, at.z);
    caps.push(cap);
  }
  return caps;
}

// ── the set ─────────────────────────────────────────────────────────────────────────────────────────────
class StructureSet {
  constructor(world, detail, makeMaterial) {
    this.world = world;
    this.detailName = DETAIL[detail] ? detail : 'medium';
    this.detail = DETAIL[this.detailName];
    this.makeMaterial = makeMaterial;
    this.group = new THREE.Group();
    this.group.name = 'structures';
    this.entries = new Map();
    this.seabedY = -(world.seabed_depth ?? 30);
    this.rocks = [];
  }

  /** Add one mesh drawn for the named colliders; the first name owns the mesh for snag highlighting. */
  add(geometry, kind, names, role = 'solid', obs = []) {
    if (!geometry) return null;
    if (BATCH_KINDS.has(obs[0]?.kind)) {
      return this.addBatched(`${kind}:${role}`, geometry, kind, names, role, obs);
    }
    return this.addMesh(geometry, kind, names, role, obs);
  }

  addMesh(geometry, kind, names, role, obs) {
    const material = this.makeMaterial(kind);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.paintable = true;
    mesh.userData.colliders = names;
    mesh.userData.role = role;
    this.group.add(mesh);
    names.forEach((name, i) => {
      if (!this.entries.has(name) && obs[i]) this.entries.set(name, {mesh, ob: obs[i]});
    });
    return mesh;
  }

  /**
   * Queue small repeated parts (anodes, mud mats, fenders, weld cans...) and draw each material as one merged
   * mesh, so the draw-call count stays close to the plain primitives on every tier.
   */
  addBatched(batch, geometry, kind, names, role, obs) {
    if (!this.batches) this.batches = new Map();
    if (!this.batches.has(batch)) this.batches.set(batch, {kind, role, parts: [], names: [], obs: []});
    const entry = this.batches.get(batch);
    entry.parts.push(geometry);
    entry.names.push(...names);
    entry.obs.push(...obs);
    return null;
  }

  flushBatches() {
    for (const entry of (this.batches || new Map()).values()) {
      const mesh = this.addMesh(merged(entry.parts), entry.kind, entry.names, entry.role, []);
      for (const ob of entry.obs) this.anchor(ob, mesh);
    }
    this.batches = null;
  }

  /** An anchor for colliders drawn by shared instanced meshes (labels need a position). */
  anchor(ob, mesh) {
    const at = new THREE.Object3D();
    if (ob.type === 'cylinder') at.position.copy(P(ob.p0).lerp(P(ob.p1), 0.5));
    else if (ob.type === 'box' || ob.type === 'ship_hull') at.position.copy(P(ob.center));
    else if (ob.type === 'wall' || ob.type === 'snag') at.position.copy(P(ob.point));
    at.material = mesh.material;
    this.entries.set(ob.name, {mesh: at, ob, drawnBy: mesh});
  }

  highlight(hot) {
    const lit = new Set();
    for (const [name, entry] of this.entries) {
      if (hot.has(name)) lit.add((entry.drawnBy || entry.mesh).material);
    }
    this.group.traverse((o) => {
      if (o.isMesh && o.material?.emissive) o.material.emissive.setHex(lit.has(o.material) ? 0x4a0a10 : 0x000000);
    });
  }

  raycastMeshes() {
    return this.group.children.filter((o) => o.isMesh && o.userData.role !== 'above');
  }

  dispose() {
    this.group.removeFromParent();
    this.group.traverse((o) => {
      if (o.geometry && !rockCacheHas(o.geometry)) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
  }
}

function rockCacheHas(geometry) {
  for (const g of rockCache.values()) if (g === geometry) return true;
  return false;
}

// ── tubulars: legs, braces, piles, masts ────────────────────────────────────────────────────────────────
function braceNodes(world, leg) {
  const a = new THREE.Vector3(...leg.p0);
  const b = new THREE.Vector3(...leg.p1);
  const ab = b.clone().sub(a);
  const nodes = [];
  for (const ob of world.obstacles || []) {
    if (ob.type !== 'cylinder' || ob.kind !== 'brace') continue;
    for (const end of [ob.p0, ob.p1]) {
      const p = new THREE.Vector3(...end);
      const t = p.clone().sub(a).dot(ab) / ab.lengthSq();
      const closest = a.clone().addScaledVector(ab, Math.min(1, Math.max(0, t)));
      if (closest.distanceTo(p) < leg.radius * 0.5 && !nodes.some((n) => Math.abs(n - t) < 0.01)) nodes.push(t);
    }
  }
  return nodes;
}

function steelTube(set, ob, kind = 'steel') {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const radial = set.detail.radial;
  const parts = [tube(a, b, ob.radius, radial, false), ...exposedCaps(set.world, ob, ob.radius, radial)];
  set.add(merged(parts), kind, [ob.name], 'solid', [ob]);
  if (ob.kind === 'jacket_leg' && set.detailName !== 'low') {
    // weld-node cans: thicker wall sections where the braces join, 0.04 m proud of the leg
    const cans = braceNodes(set.world, ob).map((t) => {
      const c = a.clone().lerp(b, t);
      const dir = b.clone().sub(a).normalize();
      return tube(c.clone().addScaledVector(dir, -0.7), c.clone().addScaledVector(dir, 0.7), ob.radius + 0.04,
        radial, true);
    });
    if (cans.length) set.addBatched('weld-cans', merged(cans), kind, [ob.name], 'attached', []);
  }
  if (set.detail.lumps && ['jacket_leg', 'pile', 'monopile', 'brace'].includes(ob.kind)) musselLumps(set, ob);
}

/** Mussel and barnacle clumps on the upper part of a tubular, at most 0.05 m proud of the steel. */
function musselLumps(set, ob) {
  const R = seeded(ob.name);
  const a = P(ob.p0);
  const b = P(ob.p1);
  const dir = b.clone().sub(a).normalize();
  const side = new THREE.Vector3().crossVectors(dir, Math.abs(dir.y) > .9 ? new THREE.Vector3(1, 0, 0) : UP)
    .normalize();
  const other = new THREE.Vector3().crossVectors(dir, side).normalize();
  const length = a.distanceTo(b);
  const count = Math.round(set.detail.lumps * (ob.kind === 'brace' ? 0.25 : 1) * Math.min(1, length / 30));
  const q = new THREE.Quaternion();
  let n = 0;
  if (!set.lumps) set.lumps = {matrices: [], names: []};
  for (let i = 0; i < count * 3 && n < count; i++) {
    const t = R();
    const p = a.clone().addScaledVector(dir, t * length);
    const depth = -p.y;
    if (depth < 0.3 || R() > Math.exp(-depth / 9)) continue;
    const ang = R() * Math.PI * 2;
    const normal = side.clone().multiplyScalar(Math.cos(ang)).addScaledVector(other, Math.sin(ang));
    const size = 0.06 + R() * 0.07;
    p.addScaledVector(normal, ob.radius + 0.005);
    q.setFromUnitVectors(UP, normal);
    const scale = new THREE.Vector3(size, 0.045, size * (0.7 + R() * 0.5));
    set.lumps.matrices.push(new THREE.Matrix4().compose(p, q, scale));
    n++;
  }
  if (n) set.lumps.names.push(ob.name);
}

/** All mussel lumps of the site as one instanced mesh. */
function flushLumps(set) {
  if (!set.lumps?.matrices.length) return;
  const mesh = new THREE.InstancedMesh(unitRock(3, 0), set.makeMaterial('steel'), set.lumps.matrices.length);
  set.lumps.matrices.forEach((m, i) => mesh.setMatrixAt(i, m));
  mesh.instanceMatrix.needsUpdate = true;
  mesh.userData.colliders = set.lumps.names;
  mesh.userData.role = 'attached';
  mesh.computeBoundingSphere();
  set.group.add(mesh);
  set.lumps = null;
}

// ── anodes ──────────────────────────────────────────────────────────────────────────────────────────────
function anodeBar(set, ob, straps) {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const dir = b.clone().sub(a).normalize();
  const r = ob.radius - 0.02;
  const body = tube(a.clone().addScaledVector(dir, -0.05), b.clone().addScaledVector(dir, 0.05), r, 6, false);
  const taperA = tube(a.clone().addScaledVector(dir, -0.11), a.clone().addScaledVector(dir, -0.05), r * 0.6, 6,
    false, r);
  const taperB = tube(b.clone().addScaledVector(dir, 0.05), b.clone().addScaledVector(dir, 0.11), r, 6, false,
    r * 0.6);
  const parts = [body, taperA, taperB];
  for (const strap of straps) parts.push(tube(P(strap.p0), P(strap.p1), strap.radius - 0.005, 6, false));
  set.addBatched('anode', merged(parts), 'anode', [ob.name, ...straps.map((s) => s.name)], 'solid', [ob, ...straps]);
}

// ── monopile fittings ───────────────────────────────────────────────────────────────────────────────────
function transitionPiece(set, ob) {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const r = ob.radius;
  const top = a.y > b.y ? a : b;
  const bottom = a.y > b.y ? b : a;
  const radial = set.detail.radial + 8;
  const parts = [tube(top, bottom, r, radial, false)];
  // grouted skirt: follows the capsule's lower cap down onto the pile
  const pile = (set.world.obstacles || []).find((o) => o.kind === 'monopile');
  const pileR = pile ? pile.radius : r - 0.3;
  const drop = Math.sqrt(Math.max(r * r - pileR * pileR, 0));
  const lathe = [];
  for (let i = 0; i <= 8; i++) {
    const h = drop * i / 8;
    lathe.push(new THREE.Vector2(Math.sqrt(Math.max(r * r - h * h, pileR * pileR)) - 0.005, -h));
  }
  const skirt = new THREE.LatheGeometry(lathe, radial);
  skirt.translate(bottom.x, bottom.y, bottom.z);
  parts.push(skirt);
  set.add(merged(parts), 'transition', [ob.name], 'solid', [ob]);
  // access platform and railing above the water: a grating ring on radial beams (open underneath)
  const deck = new THREE.RingGeometry(r, r + 2.2, radial, 1);
  deck.rotateX(-Math.PI / 2);
  deck.translate(top.x, top.y + 0.32, top.z);
  const uv = deck.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    uv.setXY(i, deck.attributes.position.getX(i), -deck.attributes.position.getZ(i));    // metres
  }
  set.add(deck, 'grating', [], 'above');
  const beams = [];
  for (let i = 0; i < 12; i++) {
    const beam = new THREE.BoxGeometry(2.2, 0.25, 0.12);
    beam.translate(r + 1.1, top.y + 0.18, 0);
    beam.rotateY(i / 12 * Math.PI * 2);
    beam.translate(top.x, 0, top.z);
    beams.push(beam);
  }
  beams.push(tube(new THREE.Vector3(top.x, top.y + 0.05, top.z), new THREE.Vector3(top.x, top.y + 0.45, top.z),
    r + 2.2, radial, true));
  const rails = [];
  for (let i = 0; i < 24; i++) {
    const ang = i / 24 * Math.PI * 2;
    const p = new THREE.Vector3(top.x + Math.cos(ang) * (r + 2.1), top.y + 0.3, top.z + Math.sin(ang) * (r + 2.1));
    rails.push(tube(p, p.clone().add(new THREE.Vector3(0, 1.1, 0)), 0.03, 5));
  }
  set.add(merged([...beams, ...rails]), 'transition', [], 'above');
}

function simpleTube(set, ob, kind, inset = 0.005, radialScale = 0.6) {
  const radial = Math.max(8, Math.round(set.detail.radial * radialScale));
  const parts = [tube(P(ob.p0), P(ob.p1), ob.radius - inset, radial),
    ...exposedCaps(set.world, ob, ob.radius - inset, radial)];
  set.add(merged(parts), kind, [ob.name], 'solid', [ob]);
}

function bellmouth(set, ob) {
  const radial = Math.max(10, Math.round(set.detail.radial * 0.6));
  set.add(tube(P(ob.p0), P(ob.p1), 0.18, radial, true, ob.radius - 0.01), 'steel', [ob.name], 'solid', [ob]);
}

function cableProtection(set, ob) {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const length = a.distanceTo(b);
  const dir = b.clone().sub(a).normalize();
  const parts = [tube(a, b, ob.radius - 0.04, 10), ...exposedCaps(set.world, ob, ob.radius - 0.04, 10)];
  for (let s = 0.4; s + 0.35 < length; s += 0.9) {
    const c = a.clone().addScaledVector(dir, s);
    parts.push(tube(c, c.clone().addScaledVector(dir, 0.35), ob.radius - 0.005, 10));
  }
  set.add(merged(parts), 'rubber', [ob.name], 'solid', [ob]);
}

// ── rock armour (scour protection, quay toe) ─────────────────────────────────────────────────────────────
/** Rocks packed inside horizontal capsule colliders, crowns touching the envelope, drawn as one instanced mesh. */
function rockArmour(set, colliders, kind) {
  if (!colliders.length) return;
  const R = seeded(colliders[0].name + kind);
  const items = [];
  for (const ob of colliders) {
    const a = P(ob.p0);
    const b = P(ob.p1);
    const length = a.distanceTo(b);
    const axis = b.clone().sub(a).normalize();
    const side = new THREE.Vector3().crossVectors(axis, UP).normalize();
    // the armour crown: rows of rocks along the capsule, each touching the collision envelope from inside
    const base = set.detailName === 'high' ? 0.62 : 0.75;
    const step = base * Math.min(1, ob.radius / 0.95);
    const bury = P(ob.p0).lerp(P(ob.p1), 0.5).y - set.seabedY;
    const reach = Math.acos(Math.max(-1, Math.min(1, bury / ob.radius)));
    const arcSteps = Math.max(2, Math.ceil(2 * reach * ob.radius / step));
    const span = length + 1.9 * ob.radius;
    const rows = Math.ceil(span / step);
    for (let row = 0; row <= rows; row++) {
      const s = -0.95 * ob.radius + span * row / rows;
      const beyond = s < 0 ? -s : Math.max(0, s - length);
      const local = Math.sqrt(Math.max(ob.radius ** 2 - beyond ** 2, 0));
      if (local < bury + 0.05) continue;
      const localReach = Math.acos(Math.max(-1, Math.min(1, bury / local)));
      for (let k = 0; k <= arcSteps; k++) {
        const size = 0.4 + R() * 0.08;
        const rho = Math.min(local * 0.45, ob.radius * size, Math.max(0.08, (local - bury) * 0.8));
        const ang = (-reach + 2 * reach * k / arcSteps) * localReach / reach + (R() - 0.5) * 0.1;
        const shell = Math.sqrt(Math.max(0, (ob.radius - 0.85 * rho) ** 2 - beyond ** 2));
        const along = s;
        const centre = a.clone().addScaledVector(axis, along)
          .addScaledVector(UP, Math.cos(ang) * shell).addScaledVector(side, Math.sin(ang) * shell);
        if (centre.y + rho < set.seabedY) continue;
        items.push({centre, rho, ob});
      }
    }
  }
  const geo = unitRock(kind === 'toe_rock' ? 7 : 5, set.detail.rockDetail);
  const mesh = new THREE.InstancedMesh(geo, set.makeMaterial('rock'), items.length);
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  items.forEach((item, i) => {
    q.setFromEuler(e.set(R() * 6.3, R() * 6.3, R() * 6.3));
    m.compose(item.centre, q, new THREE.Vector3(item.rho, item.rho, item.rho));
    mesh.setMatrixAt(i, m);
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.userData.colliders = colliders.map((ob) => ob.name);
  mesh.userData.role = 'solid';
  mesh.userData.paintable = true;
  mesh.computeBoundingSphere();
  set.group.add(mesh);
  for (const ob of colliders) set.anchor(ob, mesh);
  upgradeArmourRocks(mesh, kind, set.detailName).catch(() => false);
}

// ── quay and pool walls ──────────────────────────────────────────────────────────────────────────────────
function wallFrame(ob) {
  const a = ob.normal_deg * Math.PI / 180;
  const normal = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a));
  const along = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
  return {normal, along, origin: P([ob.point[0], ob.point[1], 0])};
}

function quayWall(set, ob) {
  const {normal, along, origin} = wallFrame(ob);
  const top = -ob.top;
  const bottom = set.seabedY - 0.5;
  const height = top - bottom;
  const yaw = Math.atan2(normal.x, normal.z);
  // face panels: a plane on the collision face with UVs in panel units (5 m wide, 3 m high)
  const face = new THREE.PlaneGeometry(ob.width, height, Math.round(ob.width / 5), Math.round(height / 3));
  const uv = face.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * ob.width / 5, uv.getY(i) * height / 3);
  face.rotateY(yaw);
  face.translate(origin.x, (top + bottom) / 2, origin.z);
  set.add(face, 'concrete', [ob.name], 'solid', [ob]);
  // the quay's end faces (the body behind the face is inside the wall's half-space and never seen from the water)
  const depth = 20;
  const centre = origin.clone().addScaledVector(normal, -depth / 2 - 0.01);
  const ends = [-1, 1].map((sign) => {
    const end = new THREE.PlaneGeometry(depth, height);
    end.rotateY(yaw + sign * Math.PI / 2);
    const at = centre.clone().addScaledVector(along, sign * ob.width / 2);
    end.translate(at.x, (top + bottom) / 2, at.z);
    return end;
  });
  set.add(merged(ends), 'concrete', [ob.name], 'solid');
  const cope = boxAt(new THREE.Vector3(centre.x, top + 0.05, centre.z), new THREE.Vector3(ob.width, 0.1, depth), yaw);
  const nosing = tube(origin.clone().addScaledVector(along, -ob.width / 2).setY(top),
    origin.clone().addScaledVector(along, ob.width / 2).setY(top), 0.06, 6);
  set.add(merged([cope, nosing]), 'ladder', [], 'above');
}

function poolWall(set, ob) {
  const {normal, origin} = wallFrame(ob);
  const top = -ob.top + 0.4;
  const bottom = set.seabedY - 0.1;
  const height = top - bottom;
  const yaw = Math.atan2(normal.x, normal.z);
  const face = new THREE.PlaneGeometry(ob.width, height, 4, 2);
  const uv = face.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * ob.width / 2, uv.getY(i) * height / 2);
  face.rotateY(yaw);
  face.translate(origin.x, (top + bottom) / 2, origin.z);
  set.add(face, 'tiles', [ob.name], 'solid', [ob]);
  const coping = boxAt(origin.clone().addScaledVector(normal, -0.6).setY(top), new THREE.Vector3(ob.width, 0.15, 1.2),
    yaw);
  set.add(coping, 'concrete', [], 'above');
}

function fender(set, ob) {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const parts = [tube(a, b, ob.radius - 0.02, 16), ...exposedCaps(set.world, ob, ob.radius - 0.02, 16)];
  set.add(merged(parts), 'rubber', [ob.name], 'solid', [ob]);
}

function bollard(set, ob) {
  const a = P(ob.p0);
  const b = P(ob.p1);
  const low = a.y < b.y ? a : b;
  const high = a.y < b.y ? b : a;
  const post = tube(low, high, ob.radius - 0.03, 14);
  const cap = tube(high, high.clone().add(new THREE.Vector3(0, 0.08, 0)), ob.radius + 0.06, 14);
  set.add(merged([post, cap]), 'ladder', [ob.name], 'above', [ob]);
}

/** Box obstacle frame: local x along yaw (north at yaw 0), y across, z down. */
function boxFrame(ob) {
  const yaw = -ob.yaw_deg * Math.PI / 180;
  return {centre: P(ob.center), yaw, hx: ob.half[0], hy: ob.half[1], hz: ob.half[2]};
}

function ladder(set, ob) {
  const {centre, yaw, hx, hy, hz} = boxFrame(ob);
  const fwd = new THREE.Vector3(0, 0, 1).applyAxisAngle(UP, yaw);
  const across = new THREE.Vector3(-1, 0, 0).applyAxisAngle(UP, yaw);
  const parts = [];
  for (const s of [-1, 1]) {
    const base = centre.clone().addScaledVector(across, s * (hy - 0.05)).addScaledVector(fwd, hx * 0.3);
    parts.push(tube(base.clone().setY(centre.y + hz), base.clone().setY(centre.y - hz), 0.03, 6));
  }
  for (let y = centre.y - hz + 0.3; y < centre.y + hz; y += 0.3) {
    const c = centre.clone().addScaledVector(fwd, hx * 0.3).setY(y);
    parts.push(tube(c.clone().addScaledVector(across, -hy + 0.05), c.clone().addScaledVector(across, hy - 0.05),
      0.022, 6));
  }
  set.add(merged(parts), 'ladder', [ob.name], 'solid', [ob]);
}

function tyre(set, ob) {
  const {centre, hx, hz} = boxFrame(ob);
  const tube = hz;
  const g = new THREE.TorusGeometry(hx - tube, tube - 0.005, 10, 24);
  g.rotateX(Math.PI / 2);
  g.translate(centre.x, centre.y, centre.z);
  set.add(g, 'rubber', [ob.name], 'solid', [ob]);
}

function plainBox(set, ob, kind, inset = 0.01) {
  const {centre, yaw, hx, hy, hz} = boxFrame(ob);
  const g = new THREE.BoxGeometry(2 * hy - inset, 2 * hz - inset, 2 * hx - inset, 1, 1, 1);
  const uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * Math.max(hx, hy) / 5, uv.getY(i) * hz / 1.25);
  g.rotateY(yaw);
  g.translate(centre.x, centre.y, centre.z);
  const role = centre.y - hz > 0 ? 'above' : 'solid';
  set.addBatched(`box:${ob.kind}:${kind}:${role}`, g, kind, [ob.name], role, [ob]);
}

/** Rudder section: round nose, then flat sides tapering to a blunt trailing edge, inside the rudder box. */
function rudderThickness(t, half) {
  if (t < 0.1) return half * Math.sqrt(t / 0.1);
  return half * (1 - 0.55 * (t - 0.1) / 0.9);
}

function rudder(set, ob) {
  const {centre, yaw, hx, hy, hz} = boxFrame(ob);
  const shape = new THREE.Shape();
  const n = 20;
  const half = hy - 0.03;
  shape.moveTo(hx - 0.01, 0);
  for (let i = 1; i <= n; i++) {
    const t = (i / n) ** 1.5;
    shape.lineTo(hx - 0.01 - (2 * hx - 0.02) * t, rudderThickness(t, half));
  }
  for (let i = n; i >= 1; i--) {
    const t = (i / n) ** 1.5;
    shape.lineTo(hx - 0.01 - (2 * hx - 0.02) * t, -rudderThickness(t, half));
  }
  const g = new THREE.ExtrudeGeometry(shape, {depth: 2 * hz - 0.02, bevelEnabled: false});
  g.translate(0, 0, -(hz - 0.01));
  g.rotateX(-Math.PI / 2);         // extrusion along +y (up); shape x = forward, shape y = across
  g.rotateY(-Math.PI / 2);         // shape x -> three +z (forward at yaw 0)
  g.rotateY(yaw);
  g.translate(centre.x, centre.y, centre.z);
  set.add(g, 'steelPlate', [ob.name], 'solid', [ob]);
}

/** Flat blade between its two edge capsules (names "... blade <k>a" / "<k>b"). */
function bladeGeometry(edgeA, edgeB) {
  const hub = P(edgeA.p0).add(P(edgeB.p0)).multiplyScalar(0.5);
  const tip = P(edgeA.p1).add(P(edgeB.p1)).multiplyScalar(0.5);
  const chord = P(edgeB.p0).sub(P(edgeA.p0));
  const maxHalf = chord.length() / 2 + edgeA.radius - 0.04;
  chord.normalize();
  const radial = tip.clone().sub(hub);
  const reach = radial.length() + edgeA.radius - 0.05;
  radial.normalize();
  const normal = new THREE.Vector3().crossVectors(radial, chord).normalize().multiplyScalar(0.025);
  const rows = [];
  const n = 10;
  for (let i = 0; i <= n; i++) {
    const s = 0.3 + (reach - 0.3) * i / n;
    const halfChord = maxHalf * (0.55 + 0.45 * Math.sin(Math.PI * (0.25 + 0.6 * i / n))) * (i === n ? 0.35 : 1);
    const c = hub.clone().addScaledVector(radial, s);
    rows.push([c.clone().addScaledVector(chord, -halfChord), c.clone().addScaledVector(chord, halfChord)]);
  }
  const positions = [];
  for (const sign of [-1, 1]) {
    for (let i = 0; i < n; i++) {
      const [a0, a1] = rows[i].map((p) => p.clone().addScaledVector(normal, sign));
      const [b0, b1] = rows[i + 1].map((p) => p.clone().addScaledVector(normal, sign));
      positions.push(...a0.toArray(), ...a1.toArray(), ...b1.toArray(), ...a0.toArray(), ...b1.toArray(),
        ...b0.toArray());
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.computeVertexNormals();
  return g;
}

function propeller(set, obs) {
  const hub = obs.find((o) => o.name.endsWith('hub'));
  if (!hub) return;
  const edges = obs.filter((o) => o.name.includes('blade'));
  const parts = [tube(P(hub.p0), P(hub.p1), hub.radius - 0.02, 16),
    ...exposedCaps(set.world, hub, hub.radius - 0.02, 16)];
  for (const a of edges.filter((o) => o.name.endsWith('a'))) {
    const b = edges.find((o) => o.name === a.name.slice(0, -1) + 'b');
    if (b) parts.push(bladeGeometry(a, b));
  }
  const mesh = set.add(merged(parts), 'bronze', [hub.name, ...edges.map((o) => o.name)], 'solid', [hub, ...edges]);
  mesh.material.side = THREE.DoubleSide;
}

function bilgeKeel(set, ob, hull) {
  // a flat plate standing out radially from the turn of the bilge, inside the capsule envelope
  const a = P(ob.p0);
  const b = P(ob.p1);
  const hp = shipHullParams(hull);
  const local = shipLocalFrame(hull);
  const starboard = ob.name.endsWith('starboard') ? 1 : -1;
  const rb = hp.bilge;
  const inward = local.across.clone().multiplyScalar(-starboard * Math.SQRT1_2).addScaledVector(UP, Math.SQRT1_2);
  const inner = inward.clone().multiplyScalar(ob.radius + 0.1);
  const outer = inward.clone().multiplyScalar(-(ob.radius - 0.03));
  const thick = local.across.clone().multiplyScalar(starboard * Math.SQRT1_2).addScaledVector(UP, Math.SQRT1_2)
    .cross(b.clone().sub(a).normalize()).normalize().multiplyScalar(0.015);
  const corners = [a.clone().add(inner), a.clone().add(outer), b.clone().add(outer), b.clone().add(inner)];
  const positions = [];
  for (const sgn of [-1, 1]) {
    const c = corners.map((p) => p.clone().addScaledVector(thick, sgn));
    positions.push(...c[0].toArray(), ...c[1].toArray(), ...c[2].toArray(), ...c[0].toArray(), ...c[2].toArray(),
      ...c[3].toArray());
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.computeVertexNormals();
  const mesh = set.add(g, 'hull', [ob.name], 'solid', [ob]);
  mesh.material.side = THREE.DoubleSide;
  void rb;
}

// ── ship hull ───────────────────────────────────────────────────────────────────────────────────────────
function shipLocalFrame(ob) {
  const a = ob.yaw_deg * Math.PI / 180;
  const toWorld = (x, y, z) => P([ob.center[0] + x * Math.cos(a) - y * Math.sin(a),
    ob.center[1] + x * Math.sin(a) + y * Math.cos(a), ob.center[2] + z]);
  const across = toWorld(0, 1, 0).sub(toWorld(0, 0, 0));
  return {toWorld, across};
}

function keelDepth(x, hp) {
  const inside = (z) => {
    const {hb, fwdEnd} = halfBreadth(x, z, hp);
    return hb >= 0 && x <= fwdEnd && x >= aftEnd(z, hp);
  };
  if (!inside(hp.top)) return null;
  if (inside(hp.draft)) return hp.draft;
  let lo = hp.top;
  let hi = hp.draft;
  for (let i = 0; i < 26; i++) {
    const mid = (lo + hi) / 2;
    if (inside(mid)) lo = mid;
    else hi = mid;
  }
  return lo;
}

/** Stations along the hull: cosine-spaced (dense at bow and stern) plus 0.1 m steps through the aperture. */
function hullStations(hp, detail) {
  const xs = [];
  for (let i = 0; i < detail.hullX; i++) {
    xs.push(-hp.length / 2 + hp.length * (1 - Math.cos(Math.PI * i / (detail.hullX - 1))) / 2);
  }
  for (let x = -hp.length / 2; x < -hp.length / 2 + hp.aperture + 1; x += 0.1) xs.push(x);
  return dedupe(xs);
}

/** Waterlines: cosine-spaced between deck and keel plus 0.1 m steps where the stern closes under the counter. */
function hullRows(hp, detail) {
  const zs = [];
  for (let j = 0; j < detail.hullZ; j++) {
    zs.push(hp.top + (hp.draft - hp.top) * (1 - Math.cos(Math.PI * j / (detail.hullZ - 1))) / 2);
  }
  for (let z = hp.counter - 0.1; z < hp.counter + hp.fair + 0.1; z += 0.1) zs.push(z);
  return dedupe(zs);
}

function dedupe(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  return sorted.filter((v, i) => i === 0 || v - sorted[i - 1] > 0.02);
}

/** Hull surface from the shared half-breadth function: two sides, flat bottom and deck (one closed hull). */
export function shipHullGeometry(ob, detail = DETAIL.medium) {
  const hp = shipHullParams(ob);
  const {toWorld} = shipLocalFrame(ob);
  const pieces = [];
  {
    const stations = hullStations(hp, detail);
    const rows = hullRows(hp, detail);
    const nz = rows.length;
    const columns = [];
    for (const x of stations) {
      const zb = keelDepth(x, hp);
      if (zb === null) continue;
      // shared absolute rows, clamped at the keel: neighbouring stations never form skewed quads
      columns.push(rows.map((row) => {
        const z = Math.min(zb, row);
        return {x, z, hb: Math.max(0, halfBreadth(x, z, hp).hb)};
      }));
    }
    const positions = [];
    const uvs = [];
    const zMid = (hp.top + hp.draft) / 2;
    // one triangle in hull-local coordinates (x forward, y starboard, z down; right-handed like the world),
    // wound so its normal points away from the hull's centre line: the hull can then be drawn front faces only
    const triangle = (a, b, c) => {
      const pa = [a[0].x, a[1] * a[0].hb, a[0].z];
      const pb = [b[0].x, b[1] * b[0].hb, b[0].z];
      const pc = [c[0].x, c[1] * c[0].hb, c[0].z];
      const u = [pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]];
      const v = [pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]];
      const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
      const centre = [(pa[0] + pb[0] + pc[0]) / 3, (pa[1] + pb[1] + pc[1]) / 3, (pa[2] + pb[2] + pc[2]) / 3];
      const out = [centre[0] * 0.02, centre[1], centre[2] - zMid];
      const order = n[0] * out[0] + n[1] * out[1] + n[2] * out[2] >= 0 ? [pa, pb, pc] : [pa, pc, pb];
      for (const q of order) {
        positions.push(...toWorld(q[0], q[1], q[2]).toArray());
        uvs.push(q[0] / 10, q[2] / 2.5);
      }
    };
    const quad = (p00, p01, p10, p11, s00, s01, s10, s11) => {
      triangle([p00, s00], [p10, s10], [p11, s11]);
      triangle([p00, s00], [p11, s11], [p01, s01]);
    };
    for (let i = 0; i < columns.length - 1; i++) {
      const c0 = columns[i];
      const c1 = columns[i + 1];
      for (let j = 0; j < nz - 1; j++) {
        quad(c0[j], c0[j + 1], c1[j], c1[j + 1], 1, 1, 1, 1);
        quad(c0[j], c1[j], c0[j + 1], c1[j + 1], -1, -1, -1, -1);
      }
      const b0 = c0[nz - 1];
      const b1 = c1[nz - 1];
      quad(b0, b1, b0, b1, 1, 1, -1, -1);
      quad(c0[0], c0[0], c1[0], c1[0], 1, -1, 1, -1);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    g.computeVertexNormals();
    pieces.push(g);
  }
  return merged(pieces);
}

function shipHull(set, ob) {
  set.add(shipHullGeometry(ob, set.detail), 'hull', [ob.name], 'solid', [ob]);
  // zinc anodes welded flush on the hull near the stern, 0.06 m proud
  const hp = shipHullParams(ob);
  const {toWorld} = shipLocalFrame(ob);
  const zincs = [];
  for (const side of [-1, 1]) {
    for (let k = 0; k < 4; k++) {
      const x = -hp.length / 2 + hp.stern + 0.3 + k * 1.2;
      const z = hp.draft * 0.55;
      const hb = halfBreadth(x, z, hp).hb;
      if (hb <= 0.3) continue;
      const c = toWorld(x, side * (hb - 0.005), z);
      const yaw = -ob.yaw_deg * Math.PI / 180;
      zincs.push(boxAt(c, new THREE.Vector3(0.05, 0.12, 0.6), yaw));
    }
  }
  if (zincs.length) set.add(merged(zincs), 'anode', [ob.name], 'attached');
}

// ── dispatcher ──────────────────────────────────────────────────────────────────────────────────────────
function shipFor(world, ob) {
  return (world.obstacles || []).find((o) => o.type === 'ship_hull' && ob.name.startsWith(o.name));
}

/** Small snaggable seabed item (world.SnagFeature): a rock, a debris block or a rope coil inside its capsule. */
function snagItem(set, ob) {
  const cap = snagCapsule(ob);
  const base = P(cap.p0);
  const top = P(cap.p1);
  const r = ob.radius;
  const R = seeded(ob.name);
  let geometry;
  let kind = 'rock';
  if (ob.item === 'rope') {
    const coils = [0, 1].map((k) => {
      const g = new THREE.TorusGeometry(r * 0.62, r * 0.18, 6, 20);
      g.rotateX(Math.PI / 2 + (R() - 0.5) * 0.3);
      g.translate(base.x + (R() - 0.5) * r * 0.2, base.y + r * 0.18 + k * r * 0.3, base.z + (R() - 0.5) * r * 0.2);
      return g;
    });
    geometry = merged(coils);
    kind = 'rubber';
  } else if (ob.item === 'debris') {
    const tall = top.y - base.y + r * 0.6;
    geometry = new THREE.BoxGeometry(r * 1.4, Math.max(tall, r * 0.6), r * 1.2);
    geometry.rotateY(R() * Math.PI);
    geometry.rotateZ((R() - 0.5) * 0.3);
    geometry.translate(base.x, base.y + Math.max(tall, r * 0.6) / 2 - 0.05, base.z);
    kind = 'steelPlate';
  } else {
    // rock or boulder: a rock in each sphere of the capsule
    const rocks = [base, top].map((c, k) => {
      const g = unitRock(11 + k, 1).clone();
      g.scale(r * 0.98, r * 0.98, r * 0.98);
      g.rotateY(R() * Math.PI * 2);
      g.translate(c.x, c.y, c.z);
      return g;
    });
    geometry = merged(base.distanceTo(top) > 0.05 ? rocks : rocks.slice(0, 1));
  }
  set.add(geometry, kind, [ob.name], 'solid', [ob]);
}

function buildOne(set, ob, consumed) {
  if (consumed.has(ob.name)) return;
  const world = set.world;
  if (ob.kind?.startsWith('pen_')) {
    buildPenPart(set, ob);
    return;
  }
  if (ob.type === 'snag') {
    snagItem(set, ob);
    return;
  }
  if (ob.type === 'ship_hull') {
    shipHull(set, ob);
    return;
  }
  if (ob.type === 'wall') {
    if (ob.kind === 'quay') quayWall(set, ob);
    else poolWall(set, ob);
    return;
  }
  if (ob.type === 'box') {
    if (ob.kind === 'ladder') ladder(set, ob);
    else if (ob.kind === 'tyre') tyre(set, ob);
    else if (ob.kind === 'rudder') rudder(set, ob);
    else if (ob.kind === 'wreck') plainBox(set, ob, 'wreck');
    else if (ob.kind === 'deck' || ob.kind === 'debris_block' || ob.kind === 'mudmat') plainBox(set, ob, 'concrete');
    else plainBox(set, ob, 'steelPlate');
    return;
  }
  if (ob.type !== 'cylinder') return;
  const kind = ob.kind;
  if (kind === 'mooring_chain') {
    chainSegment(set, ob);
  } else if (kind === 'hawser') {
    simpleTube(set, ob, 'rubber', 0);
  } else if (kind === 'anode') {
    const straps = (world.obstacles || []).filter((o) => o.kind === 'anode_strap' && o.name.startsWith(ob.name));
    for (const s of straps) consumed.add(s.name);
    anodeBar(set, ob, straps);
  } else if (kind === 'anode_strap') {
    simpleTube(set, ob, 'anode');
  } else if (kind === 'transition_piece') transitionPiece(set, ob);
  else if (kind === 'boat_landing') simpleTube(set, ob, 'transition', 0.005, 0.7);
  else if (kind === 'j_tube' && ob.name.endsWith('bellmouth')) bellmouth(set, ob);
  else if (kind === 'j_tube') simpleTube(set, ob, 'steel');
  else if (kind === 'cable_protection') cableProtection(set, ob);
  else if (kind === 'fender') fender(set, ob);
  else if (kind === 'bollard') bollard(set, ob);
  else if (kind === 'debris_pipe') set.add(tube(P(ob.p0), P(ob.p1), ob.radius - 0.01, 12, true), 'steelPlate',
    [ob.name], 'solid', [ob]);
  else if (kind === 'shaft') simpleTube(set, ob, 'steelPlate');
  else if (kind === 'bilge_keel') {
    const hull = shipFor(world, ob);
    if (hull) bilgeKeel(set, ob, hull);
    else simpleTube(set, ob, 'hull');
  } else if (kind === 'propeller') {
    const group = (world.obstacles || []).filter((o) => o.kind === 'propeller' && o.name.split(' propeller')[0]
      === ob.name.split(' propeller')[0]);
    for (const o of group) consumed.add(o.name);
    propeller(set, group);
  } else if (kind === 'brace') steelTube(set, ob, 'brace');
  else if (kind === 'pile' && (world.obstacles || []).some((o) => o.kind === 'quay')) {
    steelTube(set, ob, 'pileConcrete');                        // harbour piles are concrete
  } else steelTube(set, ob, kind === 'monopile' ? 'monopileSteel' : 'steel');
}

/**
 * Build the visible structures for a world message. Habitat colliders and GLB models are left to the caller.
 * ``makeMaterial(kind)`` defaults to the procedural structure materials (browser only).
 */
export function buildStructures(world, {detail = 'medium', makeMaterial} = {}) {
  const rockHex = siteRockColor(world);
  const baseMaterial = makeMaterial || ((kind) => structureMaterial(kind, detail));
  const paint = (kind) => {
    const material = kind.startsWith('pen_') ? penMaterial(kind) : baseMaterial(kind);
    // The high tier has a charcoal rubber map. Supply the same base tone on tiers without it.
    if (kind === 'rubber' && world.scenario?.key === 'harbor_inspection' && !material.map) {
      material.color.setHex(0x353732);
    }
    // Rock armour and snag rocks share the site's seabed sand/mud tint.
    if (kind === 'rock' && material.color?.setHex) material.color.setHex(rockHex);
    return material;
  };
  const set = new StructureSet(world, detail, paint);
  const consumed = new Set();
  const obstacles = (world.obstacles || []).filter((ob) => ob.kind !== 'habitat' && ob.type !== 'model' && !ob.embedded);
  if (world.scenario?.key === 'harbor_inspection') harborStructures(set, obstacles, consumed, seeded, boxAt);
  rockArmour(set, obstacles.filter((ob) => ob.kind === 'scour_rock'), 'scour_rock');
  rockArmour(set, obstacles.filter((ob) => ob.kind === 'toe_rock'), 'toe_rock');
  for (const ob of obstacles) {
    if (ob.kind === 'scour_rock' || ob.kind === 'toe_rock') continue;
    buildOne(set, ob, consumed);
  }
  set.flushBatches();
  flushLumps(set);
  if (set.detailName !== 'high') mergeByMaterial(set);
  return set;
}

/**
 * Low and medium tiers: one mesh per material kind and role for the whole site (geometry is already in world
 * space). Labels keep per-obstacle anchors; a snag highlight then lights every part of that material.
 */
function mergeByMaterial(set) {
  const groups = new Map();
  for (const mesh of set.group.children) {
    if (!mesh.isMesh || mesh.isInstancedMesh || mesh.material.side !== THREE.FrontSide) continue;
    const key = `${mesh.material.userData.structureKind}:${mesh.userData.role}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(mesh);
  }
  for (const meshes of groups.values()) {
    if (meshes.length < 2) continue;
    const geometry = merged(meshes.map((m) => m.geometry));
    const mesh = new THREE.Mesh(geometry, meshes[0].material);
    mesh.userData = {...meshes[0].userData, colliders: meshes.flatMap((m) => m.userData.colliders || [])};
    set.group.add(mesh);
    const gone = new Set(meshes);
    for (const old of meshes) {
      old.removeFromParent();
      if (old.material !== mesh.material) old.material.dispose();
    }
    for (const [, entry] of set.entries) {
      if (gone.has(entry.mesh) || gone.has(entry.drawnBy)) set.anchor(entry.ob, mesh);
    }
  }
}
