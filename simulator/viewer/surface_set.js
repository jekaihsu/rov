// Above-water set around a site, seen from the surface and in the deployment intro: an offshore wind farm
// (wind_farm.js), a low coastline far off where the site needs land, other vessels and navigation buoys.
//
// What appears is chosen per site from the scenario summary and the obstacles (surfacePlan): offshore wind
// sites stand inside a farm (jacket sites on jackets, monopile sites on monopiles), other open-sea sites see a
// farm several kilometres off, harbours, fish farms, reefs and fresh water get no farm, an indoor pool gets
// nothing. Everything is placed from the seeded generator the environment passes in, so a site always looks
// the same.
//
// At offshore wind sites the inspected jacket or monopile also gets its above-water part and turbine
// (site_topside.js).
//
//   const set = buildSurfaceSet(world, centre, random, {detail, time});
//   set.group      add to the scene; hide it under water
//   set.vessels    [{v, ph, speed}]  bobbing and moving forward (environment.js update)
//   set.buoys      [{b, lamp, ph}]   bobbing and flashing (environment.js update)
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {buildSiteTopside} from './site_topside.js';
import {buildWindFarm, horizonMaterial, horizonMesh, TURBINE_TYPES} from './wind_farm.js';

const HARBOUR_KINDS = new Set(['quay', 'bollard', 'fender', 'toe_rock']);
const JACKET_KINDS = new Set(['jacket_leg']);
const MONOPILE_KINDS = new Set(['monopile', 'transition_piece']);
const NO_FARM_BIOMES = new Set(['harbor', 'harbour', 'aquaculture', 'reef', 'seagrass']);

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);          // NED -> three

function obstacleKinds(world) {
  return new Set((world?.obstacles || []).map((ob) => ob.kind).filter(Boolean));
}

function anyOf(kinds, wanted) {
  for (const kind of wanted) {
    if (kinds.has(kind)) return true;
  }
  return false;
}

// Mean position of the obstacles of the given kinds (three.js, y = 0), relative to the site centre.
function anchorOf(world, wanted, centre) {
  const points = (world?.obstacles || []).filter((ob) => wanted.has(ob.kind) && (ob.p0 || ob.center))
    .map((ob) => P(ob.p0 || ob.center));
  if (!points.length) return {x: 0, z: 0};
  const sum = points.reduce((total, p) => total.add(p), new THREE.Vector3()).divideScalar(points.length);
  return {x: sum.x - centre.x, z: sum.z - centre.z};
}

/**
 * What stands round a site. Pure: decided from the world message only.
 * Returns {kind, farm: null|{type, mode, anchor?}, coast: null|{...}, vessels: [names], buoys: boolean}.
 */
export function surfacePlan(world, centre = new THREE.Vector3()) {
  const scenario = world?.scenario || {};
  const key = String(scenario.key || '');
  const kinds = obstacleKinds(world);
  if (key.includes('pool') || kinds.has('wall')) {
    return {kind: 'indoor', farm: null, coast: null, vessels: [], buoys: false};
  }
  if (scenario.water_type === 'fresh_clear') {
    return {kind: 'lake', farm: null, coast: {arc: 300, distance: [900, 1600], height: [30, 120]}, vessels: [],
      buoys: false};
  }
  if (NO_FARM_BIOMES.has(scenario.biome) || anyOf(kinds, HARBOUR_KINDS)) {
    if (scenario.biome === 'aquaculture') {
      return {kind: 'fish-farm', farm: null, coast: {arc: 120, distance: [3800, 5200], height: [60, 260]},
        vessels: ['workboat', 'fishing', 'fishing'], buoys: true};
    }
    if (scenario.biome === 'reef' || scenario.biome === 'seagrass') {
      return {kind: 'islands', farm: null, coast: {arc: 14, pieces: 2, distance: [3500, 5500], height: [40, 140]},
        vessels: ['fishing', 'fishing'], buoys: true};
    }
    // Land behind the quay: the harbour's hills, washed out by the overcast haze.
    const quay = anchorOf(world, HARBOUR_KINDS, centre);
    const toward = quay.x || quay.z ? Math.atan2(quay.z, quay.x) : null;
    return {kind: 'harbour', farm: null,
      coast: {arc: 170, distance: [800, 1300], height: [30, 90], toward},
      vessels: ['coaster', 'workboat', 'fishing'], buoys: true};
  }
  // Offshore wind farms stand roughly 10-60 km from shore: from inside one, or from open sea, no land is in
  // sight at the distances this scene can show, so these sites get open sea only.
  if (anyOf(kinds, JACKET_KINDS)) {
    return {kind: 'farm', farm: {type: 'jacket', mode: 'inside', anchor: anchorOf(world, JACKET_KINDS, centre)},
      coast: null, vessels: ['ctv', 'coaster', 'fishing'], buoys: true};
  }
  if (anyOf(kinds, MONOPILE_KINDS)) {
    return {kind: 'farm', farm: {type: 'large', mode: 'inside', anchor: anchorOf(world, MONOPILE_KINDS, centre)},
      coast: null, vessels: ['ctv', 'coaster'], buoys: true};
  }
  return {kind: 'open-sea', farm: {type: 'mid', mode: 'distant'}, coast: null,
    vessels: ['coaster', 'fishing', 'workboat'], buoys: true};
}

// Coastline ------------------------------------------------------------------------------------------------

function ridgeNoise(x, seed) {
  let sum = 0;
  let amplitude = 0.55;
  let frequency = 1;
  for (let octave = 0; octave < 3; octave++) {
    sum += amplitude * Math.sin(x * frequency * 6.1 + seed * (octave + 1.7)) *
      Math.cos(x * frequency * 3.7 - seed * 0.9 * octave);
    amplitude *= 0.5;
    frequency *= 2.1;
  }
  return sum;
}

// A ridge of land: a vertical card along an arc facing the site, its top a noisy hill profile tapering to the
// sea at both ends. Far away and hazed it reads as a low band of coast.
function ridgeGeometry(start, span, distance, height, seed, hex, steps) {
  const positions = [];
  const colours = [];
  const index = [];
  const top = new THREE.Color(hex);
  const foot = top.clone().multiplyScalar(0.8);
  for (let i = 0; i <= steps; i++) {
    const k = i / steps;
    const angle = start + span * k;
    const taper = Math.min(1, Math.sin(Math.PI * k) * 2.4) ** 0.7;
    const h = Math.max(4, height * taper * (0.62 + 0.38 * ridgeNoise(k * 3 + seed, seed)));
    const d = distance * (1 + 0.04 * ridgeNoise(k * 2 + 5, seed + 3));
    const x = Math.cos(angle) * d;
    const z = Math.sin(angle) * d;
    positions.push(x, -4, z, x, h, z);
    colours.push(foot.r, foot.g, foot.b, top.r, top.g, top.b);
    if (i < steps) {
      const a = i * 2;
      index.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
  g.setIndex(index);
  g.computeVertexNormals();
  // Light it as land facing the site, a little upward.
  const normals = g.attributes.normal;
  for (let i = 0; i < normals.count; i++) {
    const n = new THREE.Vector3(-positions[i * 3], 0, -positions[i * 3 + 2]).normalize();
    n.y = 0.45;
    n.normalize();
    normals.setXYZ(i, n.x, n.y, n.z);
  }
  return g;
}

function buildCoast(group, centre, plan, random, detail) {
  const coast = plan.coast;
  const pieces = coast.pieces || 1;
  const steps = detail === 'low' ? 40 : 90;
  const parts = [];
  const facing = Number.isFinite(coast.toward) ? coast.toward : random() * Math.PI * 2;
  for (let piece = 0; piece < pieces; piece++) {
    const span = THREE.MathUtils.degToRad(coast.arc) * (0.7 + random() * 0.3);
    const middle = facing + (pieces > 1 ? (piece - (pieces - 1) / 2) * 0.9 : 0) + (random() - 0.5) * 0.3;
    const distance = THREE.MathUtils.lerp(coast.distance[0], coast.distance[1], random());
    const height = THREE.MathUtils.lerp(coast.height[0], coast.height[1], random());
    parts.push(ridgeGeometry(middle - span / 2, span, distance, height, random() * 10, '#5c6a55', steps));
    if (detail !== 'low' && pieces === 1) {
      // A taller, paler range behind the coast; the haze makes it the faintest band.
      parts.push(ridgeGeometry(middle - span * 0.42, span * 0.84, distance * 1.25, height * 1.7, random() * 10,
        '#66735f', steps));
    }
  }
  const mesh = horizonMesh(new THREE.Mesh(mergeGeometries(parts, false), horizonMaterial()));
  for (const part of parts) part.dispose();
  mesh.name = 'surface-coast';
  mesh.position.set(centre.x, 0, centre.z);
  group.add(mesh);
  return mesh;
}

// Vessels --------------------------------------------------------------------------------------------------

function coloured(geometry, hex) {
  const c = new THREE.Color(hex);
  const count = geometry.attributes.position.count;
  const colours = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) colours.set([c.r, c.g, c.b], i * 3);
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  geometry.deleteAttribute('uv');
  return geometry;
}

function block(w, h, l, x, y, z, hex) {
  const g = new THREE.BoxGeometry(w, h, l);
  g.translate(x, y, z);
  return coloured(g, hex);
}

function post(radius, y0, y1, x, z, hex) {
  const g = new THREE.CylinderGeometry(radius, radius, y1 - y0, 5, 1, true);
  g.translate(x, (y0 + y1) / 2, z);
  return coloured(g, hex);
}

// Flat-sided hull: transom stern, parallel body, straight raked bow to a point (plan view), from y0 to y1.
function hull(length, beam, y0, y1, bowShare, hex) {
  const half = beam / 2;
  const stern = -length / 2;
  const shoulder = length / 2 - length * bowShare;
  const shape = new THREE.Shape();
  shape.moveTo(-half, -stern);
  shape.lineTo(half, -stern);
  shape.lineTo(half, -shoulder);
  shape.lineTo(0, -length / 2);
  shape.lineTo(-half, -shoulder);
  shape.closePath();
  const g = new THREE.ExtrudeGeometry(shape, {depth: y1 - y0, bevelEnabled: false});
  g.rotateX(-Math.PI / 2);
  g.translate(0, y0, 0);
  return coloured(g.toNonIndexed(), hex);
}

// Each builder returns parts in the vessel frame: bow on +z, waterline at y = 0.
const VESSEL_BUILDERS = {
  // Crew transfer vessel: a 26 m catamaran, dark hulls, flat working deck forward of a white wheelhouse.
  ctv() {
    return [
      hull(26, 2.6, -1.2, 2.0, 0.25, '#2f3438').translate(-3.2, 0, 0),
      hull(26, 2.6, -1.2, 2.0, 0.25, '#2f3438').translate(3.2, 0, 0),
      block(9.0, 1.0, 22, 0, 2.4, -1, '#e2a21a'),
      block(6.6, 2.6, 7.5, 0, 4.2, -1.5, '#e9ecec'),
      block(5.2, 0.9, 5.5, 0, 6.0, -2.0, '#2c3238'),
      block(8.4, 0.9, 0.9, 0, 2.6, 11.4, '#1d1f22'),
      post(0.08, 6.4, 10.0, 0, -3.0, '#d9dcdc')
    ];
  },
  // Small general cargo ship (about 90 m): dark hull, hatch covers, superstructure and funnel aft.
  coaster() {
    return [
      hull(90, 14, -3, 5.5, 0.16, '#24323f'),
      block(13.6, 0.7, 88, 0, 5.4, -1, '#8b2a22'),
      block(11.5, 1.6, 22, 0, 6.6, 18, '#5b6670'),
      block(11.5, 1.6, 22, 0, 6.6, -6, '#5b6670'),
      block(13.4, 9.0, 11, 0, 10.0, -36, '#eceeee'),
      block(16.0, 1.6, 4.2, 0, 15.2, -33.5, '#eceeee'),
      block(2.6, 4.8, 3.0, 0, 16.4, -40, '#2a2c2e'),
      post(0.25, 5.5, 20, 0, 31, '#d9dcdc'),
      post(0.18, 16, 24, 0, -34, '#d9dcdc')
    ];
  },
  // Coastal fishing boat (about 18 m): white hull with a blue band, wheelhouse forward, masts and booms.
  fishing() {
    return [
      hull(18, 5, -1, 2.0, 0.3, '#e7eaea'),
      block(5.1, 0.45, 17, 0, 1.4, -0.4, '#2c5ea8'),
      block(3.6, 2.6, 4.2, 0, 3.3, 2.5, '#eef0f0'),
      block(3.8, 0.3, 4.6, 0, 4.7, 2.5, '#2c5ea8'),
      post(0.1, 2, 10, 0, 5.5, '#c9cccc'),
      post(0.1, 2, 7.5, 0, -6, '#c9cccc')
    ];
  },
  // Survey and supply workboat (about 30 m): high bow, bridge forward, open aft deck with an A-frame.
  workboat() {
    return [
      hull(30, 8, -2, 3.2, 0.24, '#2e4a66'),
      block(7.8, 1.8, 7, 0, 4.1, 9, '#2e4a66'),
      block(7.0, 3.0, 8, 0, 6.2, 5.5, '#eceeee'),
      block(6.0, 1.1, 5.5, 0, 8.2, 6, '#2b3036'),
      post(0.3, 3.2, 9, -3.2, -13.5, '#e0a81c'),
      post(0.3, 3.2, 9, 3.2, -13.5, '#e0a81c'),
      block(7.0, 0.6, 0.6, 0, 9.1, -13.5, '#e0a81c'),
      post(0.1, 8.8, 13.5, 0, 5, '#d9dcdc')
    ];
  }
};

function vesselMesh(name) {
  const parts = VESSEL_BUILDERS[name]().map((part) => (part.index ? part.toNonIndexed() : part));
  for (const part of parts) {
    if (!part.attributes.normal) part.computeVertexNormals();
  }
  const mesh = horizonMesh(new THREE.Mesh(mergeGeometries(parts, false), horizonMaterial()));
  for (const part of parts) part.dispose();
  mesh.name = `vessel-${name}`;
  return mesh;
}

// Where a vessel lies: a crew transfer vessel holds its bow against the nearest turbine's boat landing, others
// steam or lie at plausible distances round the site.
function placeVessel(name, centre, random, farm) {
  const v = vesselMesh(name);
  const group = new THREE.Group();
  group.add(v);
  let speed = 0;
  if (name === 'ctv' && farm?.turbines?.length) {
    const nearest = farm.turbines.reduce((best, t) => {
      const d = Math.hypot(t.x - centre.x, t.z - centre.z);
      return d < best.d ? {t, d} : best;
    }, {t: null, d: Infinity}).t;
    const away = random() * Math.PI * 2;
    const type = TURBINE_TYPES[farm.type];
    const reach = (type.jacketHalf || type.tpDiameter / 2) + 16;
    group.position.set(nearest.x + Math.cos(away) * reach, 0, nearest.z + Math.sin(away) * reach);
    group.rotation.y = Math.atan2(nearest.x - group.position.x, nearest.z - group.position.z);
    return {v: group, ph: random() * 6.28, speed};
  }
  const range = {coaster: [3200, 5200], fishing: [700, 1900], workboat: [450, 1200], ctv: [500, 1200]}[name];
  const a = random() * Math.PI * 2;
  const d = THREE.MathUtils.lerp(range[0], range[1], random());
  group.position.set(centre.x + Math.cos(a) * d, 0, centre.z + Math.sin(a) * d);
  group.rotation.y = random() * Math.PI * 2;
  speed = {coaster: 4.5, fishing: 1.2, workboat: 0, ctv: 0}[name] * (random() < 0.6 ? 1 : 0);
  return {v: group, ph: random() * 6.28, speed};
}

// Navigation buoys ------------------------------------------------------------------------------------------

function buildBuoys(group, centre, random) {
  const buoys = [];
  const cols = [0xf2c200, 0xc62828, 0x2e7d32, 0xf2c200];
  const material = (color) => new THREE.MeshStandardMaterial({color, roughness: 0.5, metalness: 0.05});
  for (let i = 0; i < 5; i++) {
    const a = i * 1.26 + random() * 0.4;
    const d = 70 + random() * 90;
    const b = new THREE.Group();
    const m = material(cols[i % 4]);
    b.add(new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.1, 1.6, 16), m));
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 2.6, 8), m);
    mast.position.y = 2;
    b.add(mast);
    const top = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.8, 12), material(0x222222));
    top.position.y = 3.5;
    b.add(top);
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.16, 8, 6), new THREE.MeshBasicMaterial({color: 0xfff1a8}));
    lamp.position.y = 4.05;
    b.add(lamp);
    b.position.set(centre.x + Math.cos(a) * d, 0, centre.z + Math.sin(a) * d);
    group.add(b);
    buoys.push({b, lamp, ph: random() * 6.28});
  }
  return buoys;
}

// Assembly -------------------------------------------------------------------------------------------------

/** Builds the whole above-water set. time: {value} uniform with the scene time (turns the rotors). */
export function buildSurfaceSet(world, centre, random, {detail = 'medium', time = {value: 0}} = {}) {
  const group = new THREE.Group();
  group.name = 'surface-set';
  const plan = surfacePlan(world, centre);
  group.userData.plan = plan;
  let farm = null;
  if (plan.farm) {
    const windAngle = random() * Math.PI * 2;
    const farmPlan = {...plan.farm, windAngle};
    if (farmPlan.mode === 'distant') {
      // Up- or downwind of the site, so the rows recede from it rather than run past it.
      farmPlan.bearing = windAngle + (random() < 0.5 ? 0 : Math.PI) + (random() - 0.5) * 0.6;
      farmPlan.offset = 2600 + random() * 900;
    }
    farm = buildWindFarm(group, centre, farmPlan, random, {detail, time});
    farm.type = plan.farm.type;
    group.userData.farmCentre = farm.centre.clone();
    group.userData.turbines = farm.turbines.length;
    // Inside a farm the inspected foundation is one of its turbines: draw what stands above the water.
    if (farmPlan.mode === 'inside') farm.site = buildSiteTopside(group, world, plan.farm, farm, time);
  }
  if (plan.coast) buildCoast(group, centre, plan, random, detail);
  const vessels = plan.vessels.map((name) => placeVessel(name, centre, random, farm));
  for (const vessel of vessels) group.add(vessel.v);
  const buoys = plan.buoys ? buildBuoys(group, centre, random) : [];
  return {group, vessels, buoys, plan, farm};
}
