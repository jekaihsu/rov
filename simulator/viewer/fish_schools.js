// The server's fish schools as drawn fish: species per site, how the fish of a school are spread round the
// server's centre, and the per-frame update that feeds fish_life.js. Presentation only: school centres, counts
// and velocities stay the server's (state.environment.fish_schools); the observation targets keep one entry
// per school with every instance, as before. Pen schools are drawn denser than the server's count (each server
// fish stands for a few: a real pen holds tens of thousands) with a near / far level of detail.
//
//   const schools = createSharedSchools(group, world, detail, seededRandom);
//   observationTargets.push(...schools.observationTargets);
//   each frame: schools.update(dt, t, camera, state);   // schools.vehicle: the vehicle the fish react to
import * as THREE from 'three';
import {
  createFishMesh, createSchoolMotion, fishGeometry, fishMaterial, lodSink, updateSchoolMotion,
} from './fish_life.js';
import {penTurn, placePenFish} from './pen_life.js';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
// Pen fish drawn per server fish, per tier. Low keeps the previous quarter (and its single cheap body); medium and
// high draw a dense band, with the full body only within PEN_NEAR_SPLIT metres of the camera and at most
// PEN_NEAR_CAPACITY fish per school (triangle budget: tools/aquaculture_asset_report.mjs).
const PEN_CROWD = {low: 0.25, medium: 2, high: 2.5};
const PEN_NEAR_SPLIT = 6;
const PEN_NEAR_CAPACITY = 24;
const PEN_SCALE = 2;
// Farmed salmon circle the pen as a thick, slowly turning band: across it (radial), vertically and along it (m).
const PEN_BAND = [3.0, 2.2, 14];
// Individual variation: body size within +-15 % of the school's mean, brightness and hue within a few percent.
const SIZE_SPREAD = 0.15;
const COLOUR_SPREAD = 0.1;
const DRAW_DISTANCE = 55;
// Free-swimming schools: a loose band about 2 m across, 0.8 m deep and 2.4 m along the track, with at least
// this much space between fish centres (about 1.5 body lengths, from net-pen and mackerel footage).
const SCHOOL_BOX = [2.1, 0.8, 2.4];
const MIN_SPACING = 0.34;
const SCHOOL_TURN_RATE = 0.8;        // rad/s, how fast the drawn school's heading follows the server's velocity
// Tints per server variant: slightly different stock per school, so neighbouring schools do not match exactly.
const VARIANT_TINTS = [0xffffff, 0xf0f2ea, 0xe8edf2];

/** Species drawn for a world's server schools. */
export function schoolSpecies(world) {
  if (String(world?.scenario?.key || '').startsWith('aquaculture_pen')) return 'salmon';
  if ((world?.biome || world?.habitat?.biome) === 'reef') return 'fusilier';
  return 'saithe';
}

function schoolOffsets(count, random) {
  const offsets = [];
  for (let i = 0; i < count; i++) {
    let best = null;
    for (let attempt = 0; attempt < 12; attempt++) {
      const candidate = new THREE.Vector3((random() - 0.5) * SCHOOL_BOX[0], (random() - 0.5) * SCHOOL_BOX[1],
        (random() - 0.5) * SCHOOL_BOX[2]);
      const spacing = offsets.reduce((nearest, other) => Math.min(nearest, other.distanceTo(candidate)), Infinity);
      if (!best || spacing > best.spacing) best = {candidate, spacing};
      if (spacing >= MIN_SPACING) break;
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
  return colour.getHex();
}

function namedMesh(geometry, material, count, school, name) {
  const mesh = createFishMesh(geometry, material, count);
  mesh.name = name;
  mesh.userData.observationEntities = Array.from({length: count}, () => ({entity_id: school.id,
    category: 'fish_school'}));
  return mesh;
}

function buildSchool(school, detail, bodies, species, random) {
  const farm = species === 'salmon';
  const count = farm ? Math.ceil(school.count * (PEN_CROWD[detail] || 1)) : school.count;
  const offsets = farm ? null : schoolOffsets(count, random);
  const mean = 0.8 + random() * 0.4;
  const fish = Array.from({length: count}, function makeFish(_, i) {
    const offset = farm ? penOffset(random) : offsets[i];
    const phase = random() * Math.PI * 2;
    const size = mean * (1 + (random() * 2 - 1) * SIZE_SPREAD);
    return {offset, phase, scale: size * (farm ? PEN_SCALE : 1), colour: fishColour(random)};
  });
  const material = fishMaterial(species, VARIANT_TINTS[school.variant % 3] || 0xffffff);
  const lod = farm && bodies.far !== bodies.near;
  const near = namedMesh(bodies.near, material, lod ? Math.min(PEN_NEAR_CAPACITY, count) : count, school,
    `fish-${school.id}`);
  let mesh = near;
  let far = null;
  if (lod) {
    far = namedMesh(bodies.far, material, count, school, `fish-${school.id}-far`);
    mesh = new THREE.Group();
    mesh.name = `fish-${school.id}-group`;
    mesh.add(near, far);
  }
  for (const part of far ? [near, far] : [near]) {
    for (let i = 0; i < part.count; i++) part.setColorAt(i, new THREE.Color(fish[i].colour));
  }
  const pos = P(school.pos);
  return {id: school.id, mesh, near, far, fish, farm, pos, target: pos.clone(), vel: new THREE.Vector3(0, 0, 0.3),
    heading: null, motion: createSchoolMotion(fish, species, random)};
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

/**
 * Drawn fish for the server's schools of `world.habitat.fish_schools`: one instanced mesh per school (the same
 * draw calls as before), a species per site and the swimming / schooling motion of fish_life.js.
 */
export function createSharedSchools(group, world, detail, worldSeed) {
  const species = schoolSpecies(world);
  const near = fishGeometry(species, detail);
  const bodies = {near, far: detail === 'low' ? near : fishGeometry(species, 'low')};
  const schools = (world.habitat?.fish_schools || []).map(function makeSchool(school) {
    const built = buildSchool(school, detail, bodies, species, seeded(`${school.id}:${worldSeed}`));
    group.add(built.mesh);
    return built;
  });
  // A pen school with level of detail is a group of two meshes: the observation code checks every instance of it.
  const observationTargets = schools.map((school) => ({entity_id: school.id, category: 'fish_school',
    mesh: school.mesh, instanceIds: school.far ? undefined : school.fish.map((_, i) => i)}));
  const track = vehicleTracker();
  return {
    schools,
    observationTargets,
    vehicle: null,
    update(dt, t, camera, state) {
      const live = state?.environment?.fish_schools || [];
      const vehicle = track(state, dt);
      this.vehicle = vehicle;
      for (const school of schools) {
        const server = live.find((item) => item.id === school.id);
        if (server) {
          school.target.copy(P(server.pos));
          school.vel.copy(P(server.vel));
        }
        school.pos.copy(school.target);
        school.mesh.visible = school.pos.distanceTo(camera.position) < DRAW_DISTANCE;
        if (!school.mesh.visible) continue;
        steerSchool(school, dt);
        const place = school.farm ? penSchoolPlacer(school) : freeSchoolPlacer(school);
        const base = Math.max(school.farm ? 0.3 : 0.15, school.vel.length());
        const target = school.far ? lodSink(school.near, school.far, camera.position, PEN_NEAR_SPLIT) : school.near;
        updateSchoolMotion(school.motion, target, dt, t, place, base, vehicle);
      }
    },
  };
}
