// Coral reef look: colony shapes for the server's coral entities, their muted colours, and viewer-only reef
// dressing (rubble, small low colonies, a few site-attached reef fish of three species, drawn and swum by
// fish_life.js). All shapes are original procedural work.
//
// The server owns where colonies stand and their collision capsule (radius 0.45 x scale, height scale); every
// colony style below fills roughly that envelope. Dressing has no collision and stays under 0.25 m, except the
// fish, which hover above colonies.
//
//   const style = reefCoralStyle(entity);                     // 0..5, stable per entity
//   const geometry = reefCoralGeometry(style, 'medium');      // unit size, instances scale it
//   mesh.setColorAt(i, reefCoralTint(entity));
//   const dressing = installReefDressing(group, world, 'medium');   // null when the site is not a reef
//   dressing?.update(timeSeconds);
import * as THREE from 'three';
import {createFishMesh, createSchoolMotion, fishGeometry, fishMaterial, updateSchoolMotion} from './fish_life.js';

export const CORAL_STYLES = ['massive', 'branching', 'table', 'fan', 'sponge', 'finger'];
// Colony colours as they look in white light. Browns, olives and lavenders keep some contrast in blue-green
// daylight; the reds and oranges of fans and sponges read dark at depth and only show under the lamps.
const TINTS = {
  massive: [0x8e7848, 0x70804c, 0x9a885e, 0x7a7088],
  branching: [0x967c46, 0x78884c, 0x7e7698, 0xa48858],
  table: [0x84744a, 0x688258, 0x96845c],
  fan: [0xb03c24, 0x903a84, 0xc87a22],
  sponge: [0xc86822, 0xbca030, 0x7c48a0, 0xa0342c],
  finger: [0x988c56, 0x809458, 0x927084],
};
// Dead coral rubble and turf-covered hard ground round each colony: darker than the coral sand.
const RUBBLE_TINTS = [0x7d7966, 0x67644f, 0x525840, 0x5e5645, 0x959079];
const FISH_TINTS = [0xd8b830, 0x5aa7a0, 0xd9742c, 0x3a3f46];
const COUNTS = {
  low: {rubble: 360, recruits: 0, fish: 18},
  medium: {rubble: 640, recruits: 96, fish: 42},
  high: {rubble: 1100, recruits: 192, fish: 72},
};
// Underwater daylight is diffuse: a colony's flanks are lit almost as well as its top. Vertex normals are
// tilted towards the surface by this much so the shapes do not read as black silhouettes on bright sand.
const NORMAL_LIFT = 0.9;
const UP = new THREE.Vector3(0, 1, 0);

function hashText(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

function randomFrom(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6D2B79F5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Colony style for a coral entity: the server variant picks a pair of styles, the id picks one of the two. */
export function reefCoralStyle(entity) {
  const pairs = [[0, 5], [1, 3], [2, 4]];
  const pair = pairs[Math.abs(entity.variant || 0) % 3];
  // Reef-building forms dominate; fans and sponges are the minority that brings colour under the lamps.
  const second = hashText(String(entity.id)) % 100 < 38;
  return pair[second ? 1 : 0];
}

/** Per-colony colour: a palette entry for its style with a little brightness variation. */
export function reefCoralTint(entity, target = new THREE.Color()) {
  const palette = TINTS[CORAL_STYLES[reefCoralStyle(entity)]];
  const h = hashText(`tint:${entity.id}`);
  target.setHex(palette[h % palette.length]);
  return target.multiplyScalar(0.85 + ((h >>> 8) % 100) / 100 * 0.3);
}

/** Colony material; only the flat sea fans (style 3) need both faces, the other shapes are closed surfaces. */
export function reefCoralMaterial(style = 0) {
  return new THREE.MeshStandardMaterial({color: 0xffffff, vertexColors: true, roughness: .95, metalness: 0,
    side: CORAL_STYLES[style] === 'fan' ? THREE.DoubleSide : THREE.FrontSide});
}

function shapeBuilder() {
  return {positions: [], colours: [], indices: []};
}

function addVertex(shape, x, y, z, shade) {
  shape.positions.push(x, y, z);
  shape.colours.push(shade, shade, shade);
  return shape.positions.length / 3 - 1;
}

function finishShape(shape) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(shape.positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(shape.colours, 3));
  geometry.setIndex(shape.indices);
  geometry.computeVertexNormals();
  return liftNormals(geometry);
}

function liftNormals(geometry) {
  const normal = geometry.attributes.normal;
  const lifted = new THREE.Vector3();
  for (let i = 0; i < normal.count; i++) {
    lifted.fromBufferAttribute(normal, i);
    lifted.y += NORMAL_LIFT;
    lifted.normalize();
    normal.setXYZ(i, lifted.x, lifted.y, lifted.z);
  }
  return geometry;
}

const tubeAxis = new THREE.Vector3();
const tubeSide = new THREE.Vector3();
const tubeOther = new THREE.Vector3();

/** A tapered tube along `path` (Vector3 list) with one radius and one shade per point, closed by a rounded tip. */
function addTube(shape, path, radii, shades, sides) {
  const rings = [];
  for (let i = 0; i < path.length; i++) {
    const from = path[Math.max(0, i - 1)];
    const to = path[Math.min(path.length - 1, i + 1)];
    tubeAxis.copy(to).sub(from).normalize();
    tubeSide.crossVectors(tubeAxis, Math.abs(tubeAxis.y) > .95 ? new THREE.Vector3(1, 0, 0) : UP).normalize();
    tubeOther.crossVectors(tubeAxis, tubeSide);
    const ring = [];
    for (let k = 0; k < sides; k++) {
      const angle = k / sides * Math.PI * 2;
      const x = Math.cos(angle) * radii[i];
      const y = Math.sin(angle) * radii[i];
      ring.push(addVertex(shape, path[i].x + tubeSide.x * x + tubeOther.x * y,
        path[i].y + tubeSide.y * x + tubeOther.y * y, path[i].z + tubeSide.z * x + tubeOther.z * y, shades[i]));
    }
    rings.push(ring);
  }
  for (let i = 0; i < rings.length - 1; i++) {
    for (let k = 0; k < sides; k++) {
      const a = rings[i][k];
      const b = rings[i][(k + 1) % sides];
      const c = rings[i + 1][k];
      const d = rings[i + 1][(k + 1) % sides];
      shape.indices.push(a, b, c, b, d, c);
    }
  }
  const last = path.length - 1;
  const tipAt = path[last].clone().addScaledVector(tubeAxis, radii[last] * .8);
  const tip = addVertex(shape, tipAt.x, tipAt.y, tipAt.z, shades[last]);
  for (let k = 0; k < sides; k++) shape.indices.push(rings[last][k], rings[last][(k + 1) % sides], tip);
}

/** Boulder or brain coral: a lumpy dome whose grooves are a darker shade. */
function massiveShape(detail, random) {
  const geometry = new THREE.SphereGeometry(1, detail === 'low' ? 10 : 16, detail === 'low' ? 6 : 10);
  const position = geometry.attributes.position;
  const colours = new Float32Array(position.count * 3);
  const phase = [random() * 6, random() * 6, random() * 6];
  for (let i = 0; i < position.count; i++) {
    const x = position.getX(i);
    const y = position.getY(i);
    const z = position.getZ(i);
    const swell = .1 * Math.sin(x * 4.1 + phase[0]) * Math.sin(z * 3.7 + phase[1]);
    const lump = 1 + swell + .07 * Math.sin(y * 6 + phase[2]);
    const groove = .5 + .5 * Math.sin(x * 17 + Math.sin(z * 9 + phase[0]) * 2.2) * Math.sin(z * 15 + y * 11 + phase[1]);
    // Wider at the base, flat on the sand.
    const height = Math.max(-.25, y);
    position.setXYZ(i, x * .5 * lump * (1 + .12 * (1 - height)), (height + .25) * .62 * lump, z * .5 * lump);
    const shade = (.72 + .5 * groove) * (.75 + .35 * Math.max(0, y));
    colours.set([shade, shade, shade], i * 3);
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  geometry.deleteAttribute('uv');
  geometry.computeVertexNormals();
  return liftNormals(geometry);
}

function addCoralBranch(shape, start, direction, length, radius, depth, sides, random) {
  const end = start.clone().addScaledVector(direction, length);
  end.y = Math.min(end.y, .96);
  const tipShade = depth === 0 ? 1.25 : 1.0;
  addTube(shape, [start, end], [radius, radius * .74], [depth >= 2 ? .7 : .9, tipShade], sides);
  if (depth <= 0) return;
  // Each fork leans away from its parent in a random plane and keeps growing towards the light.
  const side = new THREE.Vector3(random() - .5, 0, random() - .5).normalize();
  for (const sign of [1, -1]) {
    const lean = (.35 + random() * .3) * sign;
    const fork = direction.clone().addScaledVector(side, lean).add(new THREE.Vector3(0, .25, 0)).normalize();
    addCoralBranch(shape, end, fork, length * (.6 + random() * .25), radius * .72, depth - 1, sides, random);
  }
}

/** Staghorn thicket: a few stout stems that fork twice, pale at the growing tips. */
function branchingShape(detail, random) {
  const shape = shapeBuilder();
  const sides = detail === 'low' ? 4 : 5;
  const stems = detail === 'low' ? 6 : 5;
  for (let i = 0; i < stems; i++) {
    const azimuth = i / stems * Math.PI * 2 + random() * .6;
    const out = new THREE.Vector3(Math.cos(azimuth), 0, Math.sin(azimuth));
    const start = out.clone().multiplyScalar(.1 + .1 * random());
    const direction = out.clone().multiplyScalar(.35 + .3 * random()).add(new THREE.Vector3(0, 1, 0)).normalize();
    addCoralBranch(shape, start, direction, .3 + .1 * random(), .075, detail === 'low' ? 1 : 2, sides, random);
  }
  return finishShape(shape);
}

/** Table coral: a stout trunk under a thin, slightly dished plate with an uneven pale rim. */
function tableShape(detail, random) {
  const shape = shapeBuilder();
  const segments = detail === 'low' ? 10 : 16;
  addTube(shape, [new THREE.Vector3(0, 0, 0), new THREE.Vector3(.01, .28, 0), new THREE.Vector3(.03, .5, .01)],
    [.2, .12, .17], [.6, .7, .8], detail === 'low' ? 5 : 7);
  const radii = [.14, .33, .5, .56];
  const heights = [.52, .57, .615, .6];
  const shades = [.85, 1.0, 1.1, 1.45];
  const wobble = Array.from({length: segments}, () => .86 + random() * .28);
  for (const side of [1, -1]) {
    const rings = radii.map((radius, r) => Array.from({length: segments}, (_, k) => {
      const angle = k / segments * Math.PI * 2;
      const reach = radius * (r < 2 ? 1 : wobble[k]);
      const ridge = side > 0 ? 1 + .12 * Math.sin(k * Math.PI) * (r % 2) : .5;
      return addVertex(shape, .03 + Math.cos(angle) * reach, heights[r] - (side > 0 ? 0 : .035),
        .01 + Math.sin(angle) * reach, (side > 0 ? shades[r] : .5) * ridge);
    }));
    for (let r = 0; r < rings.length - 1; r++) {
      for (let k = 0; k < segments; k++) {
        const a = rings[r][k];
        const b = rings[r][(k + 1) % segments];
        const c = rings[r + 1][k];
        const d = rings[r + 1][(k + 1) % segments];
        if (side > 0) shape.indices.push(a, b, c, b, d, c);
        else shape.indices.push(a, c, b, b, c, d);
      }
    }
    const centre = addVertex(shape, .03, heights[0] - (side > 0 ? .01 : .035), .01, side > 0 ? .85 : .5);
    for (let k = 0; k < segments; k++) {
      if (side > 0) shape.indices.push(centre, rings[0][(k + 1) % segments], rings[0][k]);
      else shape.indices.push(centre, rings[0][k], rings[0][(k + 1) % segments]);
    }
  }
  return finishShape(shape);
}

function addFanBranch(shape, base, angle, length, width, depth, plane, random) {
  const direction = new THREE.Vector3().copy(plane).multiplyScalar(Math.sin(angle));
  direction.addScaledVector(UP, Math.cos(angle));
  const across = new THREE.Vector3().copy(plane).multiplyScalar(Math.cos(angle)).addScaledVector(UP, -Math.sin(angle));
  const end = base.clone().addScaledVector(direction, length);
  if (end.y > .96) end.y = .96;
  const shade = 1.25 - .12 * depth;
  const a = addVertex(shape, base.x - across.x * width, base.y - across.y * width, base.z - across.z * width, shade);
  const b = addVertex(shape, base.x + across.x * width, base.y + across.y * width, base.z + across.z * width, shade);
  const c = addVertex(shape, end.x - across.x * width * .6, end.y - across.y * width * .6,
    end.z - across.z * width * .6, shade + .1);
  const d = addVertex(shape, end.x + across.x * width * .6, end.y + across.y * width * .6,
    end.z + across.z * width * .6, shade + .1);
  shape.indices.push(a, b, c, b, d, c);
  if (depth <= 0) return;
  const spread = .38 + random() * .2;
  addFanBranch(shape, end, angle - spread, length * .74, width * .62, depth - 1, plane, random);
  addFanBranch(shape, end, angle + spread * (.7 + random() * .5), length * .74, width * .62, depth - 1, plane, random);
  if (depth < 3) return;
  addFanBranch(shape, end, angle + (random() - .5) * .2, length * .8, width * .62, depth - 2, plane, random);
}

/** Sea fans: flat branching fans standing at different azimuths from one holdfast. */
function fanShape(detail, random) {
  const shape = shapeBuilder();
  const fans = detail === 'low' ? 2 : 3;
  for (let i = 0; i < fans; i++) {
    const azimuth = i * Math.PI / fans + random() * .4;
    const plane = new THREE.Vector3(Math.cos(azimuth), 0, Math.sin(azimuth));
    const base = plane.clone().multiplyScalar((i - (fans - 1) / 2) * .1);
    const depth = detail === 'low' ? 3 : 4;
    addFanBranch(shape, base, (random() - .5) * .3, .24 + .05 * random(), .022, depth, plane, random);
  }
  addTube(shape, [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, .1, 0)], [.1, .05], [.6, .8], 5);
  return finishShape(shape);
}

/** Tube sponges: open vases with a dark inside. */
function spongeShape(detail, random) {
  const shape = shapeBuilder();
  const sides = detail === 'low' ? 6 : 9;
  const tubes = [[0, 0, .82, .2], [.24, .08, .56, .15], [-.14, .22, .4, .13], [-.2, -.2, .3, .11]];
  for (const [x, z, height, radius] of tubes.slice(0, detail === 'low' ? 3 : 4)) {
    const lean = (random() - .5) * .12;
    const levels = [[0, radius * .62, .7], [height * .5, radius, 1], [height, radius * .9, 1.25],
      [height * .96, radius * .62, .55], [height * .45, radius * .25, .18]];
    const rings = levels.map(([y, r, shade]) => Array.from({length: sides}, (_, k) => {
      const angle = k / sides * Math.PI * 2;
      const bump = 1 + .08 * Math.sin(k * 2.3 + y * 9);
      return addVertex(shape, x + lean * y + Math.cos(angle) * r * bump, y, z + Math.sin(angle) * r * bump, shade);
    }));
    for (let r = 0; r < rings.length - 1; r++) {
      for (let k = 0; k < sides; k++) {
        const a = rings[r][k];
        const b = rings[r][(k + 1) % sides];
        const c = rings[r + 1][k];
        const d = rings[r + 1][(k + 1) % sides];
        shape.indices.push(a, c, b, b, c, d);
      }
    }
  }
  return finishShape(shape);
}

/** Finger coral: a clump of upright rounded lobes of different heights. */
function fingerShape(detail, random) {
  const shape = shapeBuilder();
  const sides = detail === 'low' ? 5 : 6;
  const count = detail === 'low' ? 7 : 11;
  for (let i = 0; i < count; i++) {
    const azimuth = i * 2.39996;
    const reach = .34 * Math.sqrt((i + .3) / count);
    const height = (.85 - reach * 1.1) * (.75 + random() * .3);
    const out = new THREE.Vector3(Math.cos(azimuth), 0, Math.sin(azimuth));
    const foot = out.clone().multiplyScalar(reach);
    const top = foot.clone().addScaledVector(out, .08 * random()).setY(height);
    const middle = foot.clone().lerp(top, .5);
    const radius = .075 + .03 * random();
    addTube(shape, [foot, middle, top], [radius * 1.15, radius, radius * .8], [.7, .95, 1.3], sides);
  }
  return finishShape(shape);
}

const SHAPES = [massiveShape, branchingShape, tableShape, fanShape, spongeShape, fingerShape];

/** Unit-size colony geometry (base at the origin, about 0.9 wide and 0.6-1 tall) with shade in vertex colours. */
export function reefCoralGeometry(style, detail = 'medium') {
  const index = Math.abs(style) % SHAPES.length;
  return SHAPES[index](detail, randomFrom(977 + index * 131));
}

/** Seabed height (three.js y) at a NED north / east from the world's terrain grid, matching its triangles. */
export function terrainHeight(world, north, east) {
  const terrain = world.terrain;
  if (!terrain) return -(world.seabed_depth || 0);
  const [rows, columns] = terrain.size;
  const n = Math.min(rows - 1.0001, Math.max(0, (north - terrain.origin[0]) / terrain.spacing));
  const e = Math.min(columns - 1.0001, Math.max(0, (east - terrain.origin[1]) / terrain.spacing));
  const row = Math.floor(n);
  const column = Math.floor(e);
  const fn = n - row;
  const fe = e - column;
  const a = terrain.depths[row][column];
  const b = terrain.depths[row + 1][column];
  const c = terrain.depths[row][column + 1];
  const d = terrain.depths[row + 1][column + 1];
  const depth = fn + fe <= 1 ? a + fn * (b - a) + fe * (c - a) : d + (1 - fn) * (c - d) + (1 - fe) * (b - d);
  return -depth;
}

/** A rounded cobble: 20 faces with shared, lifted normals so it shades as a worn lump, not as a crystal. */
function rubbleGeometry() {
  const source = new THREE.IcosahedronGeometry(1, 0);
  const shape = shapeBuilder();
  const seen = new Map();
  const position = source.attributes.position;
  for (let i = 0; i < position.count; i++) {
    const key = [position.getX(i), position.getY(i), position.getZ(i)].map((v) => v.toFixed(3)).join(',');
    if (!seen.has(key)) {
      const lump = .8 + .4 * Math.abs(Math.sin(seen.size * 2.1));
      seen.set(key, addVertex(shape, position.getX(i) * lump, position.getY(i) * .5 * lump + .3,
        position.getZ(i) * .85 * lump, .85 + .3 * Math.max(0, position.getY(i))));
    }
    shape.indices.push(seen.get(key));
  }
  source.dispose();
  return finishShape(shape);
}

function scatterRubble(group, world, corals, count, random) {
  const mesh = new THREE.InstancedMesh(rubbleGeometry(),
    new THREE.MeshStandardMaterial({color: 0xffffff, vertexColors: true, roughness: 1}), count);
  const matrix = new THREE.Matrix4();
  const rotation = new THREE.Quaternion();
  const euler = new THREE.Euler();
  const scale = new THREE.Vector3();
  const colour = new THREE.Color();
  for (let i = 0; i < count; i++) {
    // An apron of broken coral round each colony; every colony gets some, the count cycles through them.
    const anchor = corals[i % corals.length];
    const distance = anchor.scale * (.3 + 1.5 * random() * random());
    const bearing = random() * Math.PI * 2;
    const north = anchor.pos[0] + Math.cos(bearing) * distance;
    const east = anchor.pos[1] + Math.sin(bearing) * distance;
    const size = .03 + random() * random() * .09;
    scale.set(size * (.7 + random() * .8), size * (.5 + random() * .6), size * (.7 + random() * .8));
    rotation.setFromEuler(euler.set((random() - .5) * .5, random() * Math.PI * 2, (random() - .5) * .5));
    matrix.compose(new THREE.Vector3(-east, terrainHeight(world, north, east) - size * .25, north), rotation, scale);
    mesh.setMatrixAt(i, matrix);
    colour.setHex(RUBBLE_TINTS[Math.floor(random() * RUBBLE_TINTS.length)]).multiplyScalar(.8 + random() * .35);
    mesh.setColorAt(i, colour);
  }
  mesh.name = 'reef-rubble';
  mesh.receiveShadow = true;
  group.add(mesh);
}

function scatterRecruits(group, world, corals, count, random) {
  // Young colonies under 0.3 m beside the big ones, so a colony reads as a patch of reef; one draw call a shape.
  const styles = [0, 5, 1, 2];
  styles.forEach((style, s) => {
    const share = Math.floor(count / styles.length);
    if (!share) return;
    const mesh = new THREE.InstancedMesh(reefCoralGeometry(style, 'low'), reefCoralMaterial(style), share);
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const colour = new THREE.Color();
    for (let i = 0; i < share; i++) {
      const anchor = corals[(i * styles.length + s) % corals.length];
      const distance = anchor.scale * .5 + .2 + random() * random() * 1.6;
      const bearing = random() * Math.PI * 2;
      const north = anchor.pos[0] + Math.cos(bearing) * distance;
      const east = anchor.pos[1] + Math.sin(bearing) * distance;
      const size = .14 + random() * .16;
      rotation.setFromAxisAngle(UP, random() * Math.PI * 2);
      matrix.compose(new THREE.Vector3(-east, terrainHeight(world, north, east) - .01, north), rotation,
        new THREE.Vector3(size, size, size));
      mesh.setMatrixAt(i, matrix);
      const palette = TINTS[CORAL_STYLES[style]];
      colour.setHex(palette[Math.floor(random() * palette.length)]).multiplyScalar(.85 + random() * .3);
      mesh.setColorAt(i, colour);
    }
    mesh.name = `reef-recruits-${s}`;
    group.add(mesh);
  });
}

// Site-attached reef fish by species (fish_life.js bodies): small damselfish, butterflyfish and surgeonfish in
// the tints of FISH_TINTS. One instanced mesh per species, all named 'reef-fish'.
const REEF_SPECIES = [
  {name: 'damsel', tints: [1, 2], share: 0.5},
  {name: 'butterfly', tints: [0], share: 0.25},
  {name: 'surgeon', tints: [3, 1], share: 0.25},
];

function reefFish(group, corals, count, random, detail) {
  // Site-attached fish hold station over the larger colonies in small groups.
  const homes = corals.slice().sort((a, b) => b.scale - a.scale).slice(0, Math.max(3, Math.ceil(count / 1.75)));
  const colour = new THREE.Color();
  const schools = [];
  let placed = 0;
  REEF_SPECIES.forEach(function buildSpecies(kind, k) {
    const share = k === REEF_SPECIES.length - 1 ? count - placed : Math.round(count * kind.share);
    if (share <= 0) return;
    const mesh = createFishMesh(fishGeometry(kind.name, detail === 'high' ? 'medium' : 'low'),
      fishMaterial(kind.name), share);
    const fish = [];
    for (let i = 0; i < share; i++) {
      const home = homes[(placed + i) % homes.length];
      fish.push({
        home: new THREE.Vector3(-home.pos[1], -home.pos[2] + home.scale * (.8 + random() * .7), home.pos[0]),
        radius: home.scale * (.3 + random() * .7), speed: (.25 + random() * .5) * (random() < .5 ? -1 : 1),
        phase: random() * Math.PI * 2, scale: .8 + random() * .6,
      });
      const tint = FISH_TINTS[kind.tints[i % kind.tints.length]];
      mesh.setColorAt(i, colour.setHex(tint).multiplyScalar(.85 + random() * .3));
    }
    placed += share;
    mesh.name = 'reef-fish';
    mesh.userData.observationIgnore = true;
    group.add(mesh);
    schools.push({mesh, fish, motion: createSchoolMotion(fish, kind.name, random)});
  });
  return schools;
}

// Station keeping: a slow loop with pauses round the home colony, not a steady orbit.
function placeReefFish(item, time, position, euler) {
  const angle = time * item.speed + item.phase;
  const drift = angle + .6 * Math.sin(angle * 1.7 + item.phase);
  position.set(item.home.x + Math.cos(drift) * item.radius,
    item.home.y + Math.sin(time * .8 + item.phase * 3) * .08, item.home.z + Math.sin(drift) * item.radius * .8);
  const heading = Math.atan2(-Math.sin(drift), Math.cos(drift) * .8) + (item.speed < 0 ? Math.PI : 0);
  euler.set(0, heading, 0);
}

function moveReefFish(reef, time, vehicle = null) {
  const step = reef.last === null ? 0 : Math.max(0, Math.min(0.1, time - reef.last));
  reef.last = time;
  for (const school of reef.schools) {
    updateSchoolMotion(school.motion, school.mesh, step, time, placeReefFish, 0.12, vehicle);
  }
}

/**
 * Add reef dressing for a world whose habitat is a reef; returns {update(timeSeconds)} or null elsewhere.
 * Deterministic per world seed; nothing here has collision or is reported to the server.
 */
export function installReefDressing(group, world, detail = 'medium') {
  const biome = world?.biome || world?.habitat?.biome;
  const corals = (world?.habitat?.entities || []).filter((entity) => entity.kind === 'coral');
  if (biome !== 'reef' || !corals.length) return null;
  const counts = COUNTS[detail] || COUNTS.medium;
  const random = randomFrom(hashText(`reef:${world.world_seed ?? ''}`));
  scatterRubble(group, world, corals, counts.rubble, random);
  scatterRecruits(group, world, corals, counts.recruits, random);
  const reef = {schools: reefFish(group, corals, counts.fish, random, detail), last: null};
  moveReefFish(reef, 0);
  return {
    // `vehicle` ({position, velocity, lamps} in three space) is optional: without it fish do not react.
    update(timeSeconds, vehicle = null) {
      moveReefFish(reef, timeSeconds, vehicle);
    },
  };
}
