// The server's fish schools as drawn fish: species per school and site (fish_kit.js), how the fish of a school are
// spread round the server's centre, the level of detail shared by all schools, and the per-frame update that feeds
// fish_life.js. Presentation only: school centres, counts and velocities stay the server's
// (state.environment.fish_schools); the observation targets keep one entry per school covering every drawn fish.
// Pen schools are drawn denser than the server's count (each server fish stands for a few: a real pen holds tens
// of thousands).
//
// Each school is a group of three instanced meshes: the kit's full model, its distance model and the far cards.
// Every frame the nearest fish of the whole scene get the full model and the next ones the distance model, up to
// the counts of FISH_LOD for the render tier; the rest are cards. Until a species has loaded (and in Node tests)
// the three meshes draw the procedural bodies of fish_life.js.
//
//   const schools = createSharedSchools(group, world, detail, seededRandom);
//   observationTargets.push(...schools.observationTargets);
//   each frame: schools.update(dt, t, camera, state);   // schools.vehicle: the vehicle the fish react to
import * as THREE from 'three';
import {
  createFishMesh, createSchoolMotion, fishGeometry, fishMaterial, replaceFishBody, updateSchoolMotion,
} from './fish_life.js';
import {KIT_SPECIES, fishSite, kitMaterial, loadKitSpecies, schoolKitSpecies, setKitDetail} from './fish_kit.js';
import {penTurn, placePenFish} from './pen_life.js';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
// Level of detail per tier for all schools together: at most `full` fish within `fullRange` metres use the full
// model (about 5,000 triangles), at most `distance` fish within `distanceRange` the distance model (about 700),
// every other fish the crossed cards (16). Worst cases per tier: tools/aquaculture_asset_report.mjs and
// docs/design/fish-kit/README.md. Low draws fewer triangles than the procedural fish it replaces.
export const FISH_LOD = Object.freeze({
  low: {full: 0, distance: 5, fullRange: 0, distanceRange: 8},
  medium: {full: 2, distance: 32, fullRange: 3, distanceRange: 10},
  high: {full: 5, distance: 56, fullRange: 4, distanceRange: 14},
});
const LEVELS = ['full', 'distance', 'card'];
// Pen fish drawn per server fish, per tier (low keeps the previous quarter).
export const PEN_CROWD = Object.freeze({low: 0.25, medium: 2, high: 2.5});
// Farmed fish circle the pen as a thick, slowly turning band: across it (radial), vertically and along it (m).
const PEN_BAND = [3.0, 2.2, 14];
// Individual variation: body size within +-15 % of the school's mean, brightness and hue within a few percent.
const SIZE_SPREAD = 0.15;
const COLOUR_SPREAD = 0.1;
const DRAW_DISTANCE = 55;
// Far cards (beyond the distance LOD range) only need a swimming silhouette; 12 Hz is enough and cuts CPU on pens.
const FAR_CARD_HZ = 12;
// Free-swimming schools of 0.3 m fish: a loose band about 2 m across, 0.8 m deep and 2.4 m along the track, with
// at least this much space between fish centres (about 1.5 body lengths, from net-pen and mackerel footage).
// Larger species spread in proportion to their length.
const SCHOOL_BOX = [2.1, 0.8, 2.4];
const MIN_SPACING = 0.34;
const SCHOOL_BOX_LENGTH = 0.3;
const SCHOOL_TURN_RATE = 0.8;        // rad/s, how fast the drawn school's heading follows the server's velocity
// Tints per server variant: slightly different stock per school, so neighbouring schools do not match exactly.
const VARIANT_TINTS = [0xffffff, 0xf0f2ea, 0xe8edf2];

/** Procedural stand-in drawn until the kit species of a site has loaded. */
export function schoolSpecies(world) {
  const site = fishSite(world);
  if (site === 'pen') return 'salmon';
  if (site === 'reef') return 'fusilier';
  return 'saithe';
}

function schoolOffsets(count, random, spread) {
  const offsets = [];
  for (let i = 0; i < count; i++) {
    let best = null;
    for (let attempt = 0; attempt < 12; attempt++) {
      const candidate = new THREE.Vector3((random() - 0.5) * SCHOOL_BOX[0], (random() - 0.5) * SCHOOL_BOX[1],
        (random() - 0.5) * SCHOOL_BOX[2]).multiplyScalar(spread);
      const spacing = offsets.reduce((nearest, other) => Math.min(nearest, other.distanceTo(candidate)), Infinity);
      if (!best || spacing > best.spacing) best = {candidate, spacing};
      if (spacing >= MIN_SPACING * spread) break;
    }
    offsets.push(best.candidate);
  }
  return offsets;
}

function penOffset(random) {
  return new THREE.Vector3((random() - 0.5) * PEN_BAND[0], (random() - 0.5) * PEN_BAND[1],
    (random() - 0.5) * PEN_BAND[2]);
}

function fishColour(random) {
  const colour = new THREE.Color(1, 1, 1).multiplyScalar(1 + (random() - 0.5) * COLOUR_SPREAD);
  colour.r *= 1 + (random() - 0.5) * COLOUR_SPREAD * 0.5;
  colour.b *= 1 + (random() - 0.5) * COLOUR_SPREAD * 0.5;
  return colour;
}

function levelMesh(body, material, capacity, school, level) {
  const mesh = createFishMesh(body, material, capacity);
  mesh.name = `fish-${school.id}-${level}`;
  mesh.count = 0;
  mesh.visible = false;
  mesh.userData.fishLevel = level;
  mesh.userData.observationEntities = Array.from({length: capacity}, () => ({entity_id: school.id,
    category: 'fish_school'}));
  return mesh;
}

function buildSchool(school, context, random) {
  const {world, detail, lod, bodies} = context;
  const species = schoolKitSpecies(world, school.id);
  const farm = fishSite(world) === 'pen';
  const length = KIT_SPECIES[species].length;
  const count = farm ? Math.ceil(school.count * (PEN_CROWD[detail] || 1)) : school.count;
  const spread = Math.max(1, length / SCHOOL_BOX_LENGTH);
  const offsets = farm ? null : schoolOffsets(count, random, spread);
  const mean = 0.8 + random() * 0.4;
  const fish = Array.from({length: count}, function makeFish(_, i) {
    const offset = farm ? penOffset(random) : offsets[i];
    const phase = random() * Math.PI * 2;
    const scale = mean * (1 + (random() * 2 - 1) * SIZE_SPREAD);
    return {offset, phase, scale, colour: fishColour(random)};
  });
  const tint = VARIANT_TINTS[school.variant % 3] || 0xffffff;
  const material = fishMaterial(bodies.species, tint);
  const capacity = {full: Math.min(count, lod.full), distance: Math.min(count, lod.distance), card: count};
  const group = new THREE.Group();
  group.name = `fish-${school.id}-group`;
  const meshes = {};
  for (const level of LEVELS) {
    if (!capacity[level]) continue;
    meshes[level] = levelMesh(bodies[level], material, capacity[level], school, level);
    group.add(meshes[level]);
  }
  const pos = P(school.pos);
  const stage = {matrices: new Float32Array(count * 16), swim: new Float32Array(count * 3),
    distance: new Float32Array(count), level: new Uint8Array(count)};
  return {id: school.id, species, tint, mesh: group, meshes, fish, farm, pos, target: pos.clone(),
    vel: new THREE.Vector3(0, 0, 0.3), heading: null, stage, visible: true,
    motion: createSchoolMotion(fish, {length}, random)};
}

function seeded(text) {
  let h = 1779033703 ^ text.length;
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const offsetWorld = new THREE.Vector3();

function freeSchoolPlacer(school) {
  return function placeFreeFish(item, t, position, euler) {
    offsetWorld.copy(item.offset).applyAxisAngle(THREE.Object3D.DEFAULT_UP, school.heading);
    position.copy(school.pos).add(offsetWorld);
    position.y += Math.sin(t * 0.9 + item.phase) * 0.08;
    euler.set(0, school.heading, 0);
  };
}

function penSchoolPlacer(school) {
  const turn = penTurn(school);
  return function placeFarmFish(item, t, position, euler) {
    placePenFish(school, item, t, turn, position, euler);
    euler.z = 0;
  };
}

function steerSchool(school, dt) {
  const speed = Math.hypot(school.vel.x, school.vel.z);
  const wanted = speed > 0.02 ? Math.atan2(school.vel.x, school.vel.z) : school.heading ?? 0;
  if (school.heading === null) {
    school.heading = wanted;
    return;
  }
  const delta = Math.atan2(Math.sin(wanted - school.heading), Math.cos(wanted - school.heading));
  const limit = SCHOOL_TURN_RATE * dt;
  school.heading += Math.max(-limit, Math.min(limit, delta));
}

function vehicleTracker() {
  const position = new THREE.Vector3();
  const previous = new THREE.Vector3();
  const velocity = new THREE.Vector3();
  let known = false;
  return function trackVehicle(state, dt) {
    if (!Array.isArray(state?.pos)) return null;
    position.copy(P(state.pos));
    if (known && dt > 0) velocity.lerp(previous.sub(position).multiplyScalar(-1 / dt), 1 - Math.exp(-dt * 4));
    previous.copy(position);
    known = true;
    return {position, velocity, lamps: (state.rc?.right_switch || 0) > 0};
  };
}

// Sink that keeps each fish's matrix, swim values and distance for the level-of-detail pass.
function stageSink(stage, eye) {
  return {
    eye,
    put(i, distance, item, matrix, swim) {
      matrix.toArray(stage.matrices, i * 16);
      stage.swim[i * 3] = swim[0];
      stage.swim[i * 3 + 1] = swim[1];
      stage.swim[i * 3 + 2] = swim[2];
      stage.distance[i] = distance;
    },
    end() {},
  };
}

/** Level index (0 full, 1 distance, 2 card) per staged fish: nearest first, within the tier's counts and ranges. */
export function assignLevels(entries, lod) {
  entries.sort((a, b) => a.school.stage.distance[a.index] - b.school.stage.distance[b.index]);
  let full = 0;
  let distance = 0;
  for (const {school, index} of entries) {
    const range = school.stage.distance[index];
    let level = 2;
    if (full < lod.full && range < lod.fullRange) {
      level = 0;
      full++;
    } else if (distance < lod.distance && range < lod.distanceRange) {
      level = 1;
      distance++;
    }
    school.stage.level[index] = level;
  }
}

function writeSchool(school) {
  const used = {full: 0, distance: 0, card: 0};
  const {stage} = school;
  for (let i = 0; i < school.fish.length; i++) {
    const level = LEVELS[stage.level[i]];
    const mesh = school.meshes[level];
    const slot = used[level]++;
    const dst = mesh.instanceMatrix.array;
    const src = stage.matrices;
    const from = i * 16;
    const to = slot * 16;
    for (let k = 0; k < 16; k++) dst[to + k] = src[from + k];
    mesh.geometry.attributes.aSwim.setXYZ(slot, stage.swim[i * 3], stage.swim[i * 3 + 1], stage.swim[i * 3 + 2]);
    mesh.setColorAt(slot, school.fish[i].colour);
  }
  for (const level of LEVELS) {
    const mesh = school.meshes[level];
    if (!mesh) continue;
    mesh.count = used[level];
    mesh.visible = used[level] > 0;
    mesh.instanceMatrix.needsUpdate = true;
    mesh.geometry.attributes.aSwim.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }
}

/** The instanced meshes of a drawn school (full, distance and card levels that exist). */
export function schoolMeshes(school) {
  return LEVELS.map((level) => school.meshes[level]).filter(Boolean);
}

function upgradeSpecies(schools, species) {
  const materials = new Map();
  function material(asset, level, tint) {
    const key = `${level === 'card' ? 'card' : 'model'}:${tint}`;
    if (!materials.has(key)) materials.set(key, kitMaterial(asset, level, tint));
    return materials.get(key);
  }
  return loadKitSpecies(species).then(function swapBodies(asset) {
    for (const school of schools) {
      if (school.species !== species) continue;
      for (const level of LEVELS) {
        const mesh = school.meshes[level];
        if (mesh) replaceFishBody(mesh, asset[level], material(asset, level, school.tint));
      }
    }
    return true;
  }, () => false);
}

/**
 * Drawn fish for the server's schools of `world.habitat.fish_schools`: one group per school, a species per school
 * and site, the swimming / schooling motion of fish_life.js and the shared level of detail. `ready` resolves once
 * the kit models are in place (false where they could not be loaded; the procedural bodies stay).
 */
export function createSharedSchools(group, world, detail, worldSeed) {
  setKitDetail(detail);
  const lod = FISH_LOD[detail] || FISH_LOD.medium;
  const stand = schoolSpecies(world);
  const near = fishGeometry(stand, detail);
  const bodies = {species: stand, full: near, distance: near, card: fishGeometry(stand, 'low')};
  const context = {world, detail, lod, bodies};
  const schools = (world.habitat?.fish_schools || []).map(function makeSchool(school) {
    const built = buildSchool(school, context, seeded(`${school.id}:${worldSeed}`));
    group.add(built.mesh);
    return built;
  });
  const observationTargets = schools.map((school) => ({entity_id: school.id, category: 'fish_school',
    mesh: school.mesh}));
  const entries = schools.flatMap((school) => school.fish.map((_, index) => ({school, index})));
  const visibleEntries = [];
  const byId = new Map(schools.map((school) => [school.id, school]));
  const track = vehicleTracker();
  // Placers are stable per school (heading is read through the school object); allocating them every frame
  // was a measurable GC cost on the pen site.
  for (const school of schools) {
    school.place = school.farm ? penSchoolPlacer(school) : freeSchoolPlacer(school);
    school.farAcc = 0;
  }
  const ready = Promise.all([...new Set(schools.map((school) => school.species))].map(
    (species) => upgradeSpecies(schools, species))).then((results) => results.every(Boolean));
  return {
    schools,
    observationTargets,
    vehicle: null,
    ready,
    update(dt, t, camera, state) {
      const live = state?.environment?.fish_schools || [];
      const vehicle = track(state, dt);
      this.vehicle = vehicle;
      for (const item of live) {
        const school = byId.get(item.id);
        if (!school) continue;
        school.target.copy(P(item.pos));
        school.vel.copy(P(item.vel));
      }
      for (const school of schools) {
        school.dirty = false;
        school.pos.copy(school.target);
        school.visible = school.pos.distanceTo(camera.position) < DRAW_DISTANCE;
        school.mesh.visible = school.visible;
        if (!school.visible) {
          school.uploaded = false;
          continue;
        }
        const near = school.pos.distanceTo(camera.position) < (lod.distanceRange + 4);
        // Always stage once so the first visible frame has valid matrices; then far schools tick at FAR_CARD_HZ.
        if (!near) {
          school.farAcc += dt;
          if (school.staged && school.farAcc < 1 / FAR_CARD_HZ) continue;
          school.farAcc = 0;
        } else {
          school.farAcc = 0;
        }
        steerSchool(school, dt);
        const base = Math.max(school.farm ? 0.3 : 0.15, school.vel.length());
        updateSchoolMotion(school.motion, stageSink(school.stage, camera.position), dt, t, school.place, base,
          vehicle);
        school.staged = true;
        school.dirty = true;
      }
      visibleEntries.length = 0;
      for (const entry of entries) {
        if (entry.school.visible) visibleEntries.push(entry);
      }
      assignLevels(visibleEntries, lod);
      for (const school of schools) {
        // Rewrite whenever motion ran, or the first time the school is visible (levels need a mesh upload).
        if (school.visible && (school.dirty || !school.uploaded)) {
          writeSchool(school);
          school.dirty = false;
          school.uploaded = true;
        }
      }
    },
  };
}
