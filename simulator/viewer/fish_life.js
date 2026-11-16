// Live fish for every site: procedural species bodies, a swimming vertex shader and per-fish school motion.
//
// Presentation only. The server owns each school's centre, velocity and count (state.environment.fish_schools);
// this module decides how the individual fish of a school are spread round that centre, how they swim and how
// they react to the vehicle. Everything that moves a fish's place or heading is written into the instance
// matrices on the CPU, so observation photos (observation_camera.js raycasts the instance matrices) see the fish
// where they are drawn; only the body wave (a few centimetres) lives in the vertex shader.
//
// Look targets come from real working-camera footage (docs/design/underwater-look/README.md): fusiform bodies
// with flat silver flanks that flash white under the lamps, dark backs and pale bellies (countershading), schools
// that hold one heading with about one body length between fish, a travelling body wave whose amplitude grows to
// the tail, and fish that shy away from an approaching vehicle. Distance fade comes from the water optics
// (underwater_lighting.js patches this material like any other MeshStandardMaterial).
//
//   const geometry = fishGeometry('saithe', 'medium');          // unit body, nose +Z, species length in metres
//   const mesh = createFishMesh(geometry, fishMaterial('saithe'), count);
//   const motion = createSchoolMotion(fishList, 'saithe', random);
//   each frame: updateSchoolMotion(motion, mesh, dt, t, placeFish, vehicle);
import * as THREE from 'three';

// Body profile per species, in body lengths from the nose (s = 0) to the caudal peduncle: [s, half height,
// half width, centre height]. Caudal and other fins are outlines in the mid plane, [s, height] in body lengths.
// Colours are linear-ish albedo of a fresh fish in white light (back, flank, belly, fin); `sheen` is how
// mirror-like the flank is (guanine scales), `spots` a dark speckle on the upper flank.
export const SPECIES = Object.freeze({
  salmon: {
    length: 0.30,
    profile: [[0, 0, 0, 0], [0.03, 0.035, 0.022, 0], [0.1, 0.075, 0.045, -0.004], [0.2, 0.1, 0.058, -0.008],
      [0.33, 0.112, 0.062, -0.01], [0.48, 0.103, 0.055, -0.008], [0.62, 0.08, 0.04, -0.004],
      [0.74, 0.052, 0.024, 0], [0.82, 0.036, 0.014, 0]],
    caudal: [[0.8, 0.032], [0.99, 0.105], [0.93, 0.004], [0.99, -0.1], [0.8, -0.03]],
    dorsal: [[0.3, 0.1], [0.36, 0.165], [0.46, 0.098]],
    adipose: [[0.66, 0.072], [0.69, 0.1], [0.72, 0.058]],
    anal: [[0.62, -0.068], [0.65, -0.112], [0.71, -0.05]],
    pelvic: [[0.47, -0.088], [0.52, -0.12], [0.55, -0.083]],
    pectoral: [[0.17, -0.06], [0.27, -0.1], [0.25, -0.07]],
    colours: {back: [0.018, 0.026, 0.03], flank: [0.17, 0.19, 0.2], belly: [0.34, 0.34, 0.33],
      fin: [0.04, 0.045, 0.045]},
    sheen: 1, spots: 0.55, wave: 0.09, waveLength: 1.05,
  },
  saithe: {
    length: 0.30,
    profile: [[0, 0, 0, 0], [0.03, 0.03, 0.022, 0], [0.1, 0.068, 0.045, -0.004], [0.22, 0.092, 0.056, -0.008],
      [0.36, 0.098, 0.056, -0.008], [0.5, 0.088, 0.048, -0.006], [0.64, 0.066, 0.034, -0.003],
      [0.76, 0.042, 0.02, 0], [0.84, 0.03, 0.012, 0]],
    caudal: [[0.82, 0.028], [0.99, 0.09], [0.95, 0.01], [0.99, -0.085], [0.82, -0.026]],
    dorsal: [[0.24, 0.088], [0.3, 0.14], [0.4, 0.092]],
    dorsal2: [[0.46, 0.086], [0.52, 0.12], [0.62, 0.068]],
    anal: [[0.44, -0.08], [0.5, -0.115], [0.66, -0.06]],
    pelvic: [[0.2, -0.085], [0.24, -0.12], [0.27, -0.085]],
    pectoral: [[0.18, -0.03], [0.3, -0.06], [0.27, -0.035]],
    colours: {back: [0.016, 0.022, 0.016], flank: [0.14, 0.15, 0.145], belly: [0.3, 0.3, 0.29],
      fin: [0.03, 0.035, 0.03]},
    // Pale lateral line along the flank, as in saithe and pollack.
    marks: [{from: 0.12, to: 0.8, upMin: 0.05, upMax: 0.3, colour: [0.22, 0.23, 0.22]}],
    sheen: 0.8, spots: 0, wave: 0.09, waveLength: 1.0,
  },
  fusilier: {
    length: 0.26,
    profile: [[0, 0, 0, 0], [0.03, 0.03, 0.02, 0], [0.1, 0.07, 0.04, -0.002], [0.24, 0.1, 0.05, -0.004],
      [0.4, 0.1, 0.048, -0.004], [0.56, 0.082, 0.04, -0.002], [0.7, 0.054, 0.026, 0], [0.82, 0.032, 0.012, 0]],
    caudal: [[0.8, 0.03], [1.0, 0.12], [0.92, 0.006], [1.0, -0.115], [0.8, -0.028]],
    dorsal: [[0.26, 0.1], [0.34, 0.135], [0.62, 0.075]],
    anal: [[0.5, -0.085], [0.56, -0.11], [0.68, -0.055]],
    pectoral: [[0.17, -0.035], [0.29, -0.065], [0.26, -0.04]],
    // Fusilier: blue back, a yellow stripe along the upper flank, blue-silver flank, pale belly, yellow tail.
    colours: {back: [0.02, 0.05, 0.18], flank: [0.11, 0.17, 0.27], belly: [0.36, 0.34, 0.35], fin: [0.15, 0.2, 0.3]},
    marks: [{from: 0.08, to: 0.86, upMin: 0.35, upMax: 0.75, colour: [0.5, 0.38, 0.03]}],
    finColours: {caudal: [0.55, 0.42, 0.03], dorsal: [0.05, 0.09, 0.22]},
    sheen: 0.35, spots: 0, wave: 0.1, waveLength: 1.0,
  },
  damsel: {
    length: 0.09,
    profile: [[0, 0, 0, 0], [0.04, 0.06, 0.035, 0], [0.12, 0.16, 0.07, 0], [0.3, 0.23, 0.085, 0],
      [0.48, 0.22, 0.075, 0], [0.64, 0.15, 0.05, 0], [0.76, 0.08, 0.025, 0], [0.82, 0.06, 0.015, 0]],
    caudal: [[0.8, 0.055], [0.99, 0.15], [0.94, 0.02], [0.99, -0.14], [0.8, -0.055]],
    dorsal: [[0.18, 0.2], [0.4, 0.28], [0.72, 0.13]],
    anal: [[0.5, -0.2], [0.62, -0.26], [0.74, -0.12]],
    pelvic: [[0.24, -0.2], [0.3, -0.3], [0.34, -0.21]],
    pectoral: [[0.22, -0.02], [0.36, -0.08], [0.33, -0.04]],
    // Damselfish: electric-blue body, yellow belly and tail (blue-yellow damsel).
    colours: {back: [0.02, 0.12, 0.5], flank: [0.05, 0.2, 0.62], belly: [0.7, 0.58, 0.06], fin: [0.04, 0.14, 0.5]},
    marks: [{from: 0.62, to: 1, upMin: -1, upMax: 1, colour: [0.75, 0.6, 0.06]}],
    finColours: {caudal: [0.78, 0.62, 0.06], anal: [0.7, 0.55, 0.06], pelvic: [0.7, 0.55, 0.06]},
    sheen: 0.12, spots: 0, wave: 0.06, waveLength: 1.15,
  },
  butterfly: {
    length: 0.13,
    profile: [[0, 0, 0, 0], [0.05, 0.05, 0.025, 0.02], [0.14, 0.2, 0.05, 0.01], [0.3, 0.32, 0.065, 0],
      [0.48, 0.33, 0.06, 0], [0.64, 0.24, 0.045, 0], [0.76, 0.1, 0.022, 0], [0.82, 0.07, 0.014, 0]],
    caudal: [[0.8, 0.065], [0.98, 0.13], [0.99, 0.0], [0.98, -0.13], [0.8, -0.065]],
    dorsal: [[0.2, 0.28], [0.44, 0.4], [0.74, 0.16]],
    anal: [[0.44, -0.3], [0.6, -0.36], [0.76, -0.14]],
    pectoral: [[0.24, -0.04], [0.36, -0.1], [0.34, -0.06]],
    // Butterflyfish: yellow with a white face and chest, a black bar through the eye and a dark rear patch.
    colours: {back: [0.72, 0.56, 0.05], flank: [0.78, 0.62, 0.08], belly: [0.78, 0.76, 0.66], fin: [0.75, 0.58, 0.05]},
    marks: [{from: 0, to: 0.3, upMin: -1, upMax: 0.1, colour: [0.8, 0.8, 0.76]},
      {from: 0.52, to: 0.72, upMin: 0.3, upMax: 1, colour: [0.04, 0.04, 0.05]}],
    finColours: {dorsal: [0.7, 0.52, 0.05], caudal: [0.8, 0.78, 0.7]},
    sheen: 0.06, spots: 0, eyeBand: true, wave: 0.05, waveLength: 1.2,
  },
  surgeon: {
    length: 0.2,
    profile: [[0, 0, 0, 0], [0.05, 0.08, 0.03, 0.02], [0.15, 0.2, 0.055, 0.01], [0.32, 0.26, 0.065, 0],
      [0.5, 0.24, 0.058, 0], [0.66, 0.16, 0.04, 0], [0.78, 0.07, 0.02, 0], [0.84, 0.05, 0.012, 0]],
    caudal: [[0.82, 0.05], [1.0, 0.16], [0.95, 0.02], [1.0, -0.16], [0.82, -0.05]],
    dorsal: [[0.18, 0.22], [0.3, 0.3], [0.78, 0.1]],
    anal: [[0.4, -0.22], [0.5, -0.29], [0.8, -0.09]],
    pectoral: [[0.22, -0.02], [0.36, -0.09], [0.32, -0.04]],
    // Surgeonfish: dark blue-grey body with a bright yellow spine patch on the tail stalk and a pale tail edge.
    colours: {back: [0.04, 0.05, 0.1], flank: [0.07, 0.09, 0.18], belly: [0.1, 0.12, 0.2], fin: [0.05, 0.07, 0.16]},
    marks: [{from: 0.72, to: 0.86, upMin: -0.6, upMax: 0.6, colour: [0.8, 0.62, 0.05]}],
    finColours: {caudal: [0.1, 0.14, 0.3], dorsal: [0.12, 0.16, 0.35]},
    sheen: 0.08, spots: 0, wave: 0.06, waveLength: 1.1,
  },
});
// Rings along the body and vertices round each ring per render tier. Low keeps the old fish's triangle budget.
const DETAIL = {
  low: {rings: 6, around: 6, fins: false, eyes: false},
  medium: {rings: 10, around: 8, fins: true, eyes: true},
  high: {rings: 13, around: 10, fins: true, eyes: true},
};
const FLANK_EXPONENT = 2.6;          // superellipse cross-section: compressed body with flat, mirror-like flanks
// Flank guanine as a partly metallic reflector: the diffuse albedo of a silver fish is low (dark in footage away
// from the lamps); the white flash comes from the specular reflection of the lamps off the flat flank, and only
// where the flank faces the lamps (scales are not a perfect mirror: moderate roughness). Colours above are linear
// albedo (0.17 linear is about 45 % on screen in white light).
const SHEEN_METALNESS = 0.5;
const SHEEN_ROUGHNESS = 0.38;
const BODY_ROUGHNESS = 0.55;
const PROGRAM_KEY = 'fish-swim-v1';

function profileAt(profile, s) {
  for (let i = 1; i < profile.length; i++) {
    if (s <= profile[i][0]) {
      const [s0, h0, w0, c0] = profile[i - 1];
      const [s1, h1, w1, c1] = profile[i];
      const k = (s - s0) / Math.max(1e-6, s1 - s0);
      const smooth = k * k * (3 - 2 * k);
      const lerp = (a, b) => a + (b - a) * (0.5 * k + 0.5 * smooth);
      return [lerp(h0, h1), lerp(w0, w1), lerp(c0, c1)];
    }
  }
  const last = profile[profile.length - 1];
  return [last[1], last[2], last[3]];
}

// Ring positions along the body: denser at the head and the tail, where the silhouette bends most.
function ringStations(end, rings) {
  const stations = [];
  for (let i = 1; i <= rings; i++) {
    const u = i / rings;
    stations.push(end * (0.5 - 0.5 * Math.cos(Math.PI * (0.08 + 0.92 * u))) / (0.5 - 0.5 * Math.cos(Math.PI)));
  }
  return stations;
}

function speckle(s, angle) {
  // Deterministic pseudo-random speckle per vertex, for salmonid spots on the back and upper flank.
  const h = Math.sin(s * 91.7 + angle * 47.3) * 43758.5453;
  return h - Math.floor(h);
}

function bodyColour(species, s, up, angle) {
  const {back, flank, belly} = species.colours;
  const toFlank = THREE.MathUtils.smoothstep(up, -0.85, -0.15);
  const toBack = THREE.MathUtils.smoothstep(up, 0.2, 0.75);
  const colour = [0, 1, 2].map((i) => {
    const lower = belly[i] + (flank[i] - belly[i]) * toFlank;
    return lower + (back[i] - lower) * toBack;
  });
  for (const mark of species.marks || []) {
    if (s >= mark.from && s <= mark.to && up >= mark.upMin && up <= mark.upMax) {
      for (let i = 0; i < 3; i++) colour[i] = mark.colour[i];
    }
  }
  if (species.spots && up > 0.05 && speckle(s, angle) < species.spots * 0.45) {
    for (let i = 0; i < 3; i++) colour[i] *= 0.45;
  }
  if (species.eyeBand && s > 0.08 && s < 0.17) {
    for (let i = 0; i < 3; i++) colour[i] *= 0.15;
  }
  // The head and the gill cover read a little darker than the flank in footage.
  if (s < 0.12) {
    for (let i = 0; i < 3; i++) colour[i] *= 0.8;
  }
  return colour;
}

function pushBody(out, species, detail) {
  const {rings, around} = detail;
  const L = species.length;
  const end = species.profile[species.profile.length - 1][0];
  const stations = ringStations(end, rings);
  const base = out.positions.length / 3;
  const noseZ = L / 2;
  out.positions.push(0, 0, noseZ);
  out.colours.push(...bodyColour(species, 0, 0, 0));
  out.sheen.push(0);
  const angles = Array.from({length: around}, (_, k) => Math.PI / 2 + (k / around) * Math.PI * 2);
  for (const s of stations) {
    const [halfHeight, halfWidth, centre] = profileAt(species.profile, s);
    for (const angle of angles) {
      const c = Math.cos(angle);
      const v = Math.sin(angle);
      const x = Math.sign(c) * Math.pow(Math.abs(c), 2 / FLANK_EXPONENT) * halfWidth * L;
      const y = Math.sign(v) * Math.pow(Math.abs(v), 2 / FLANK_EXPONENT) * halfHeight * L + centre * L;
      out.positions.push(x, y, noseZ - s * L);
      out.colours.push(...bodyColour(species, s, v, angle));
      out.sheen.push(species.sheen * Math.max(0, 1 - v * v * 1.4) * THREE.MathUtils.smoothstep(s, 0.06, 0.16));
    }
  }
  const tail = out.positions.length / 3;
  out.positions.push(0, profileAt(species.profile, end)[2] * L, noseZ - end * L - 0.004 * L);
  out.colours.push(...species.colours.fin);
  out.sheen.push(0);
  for (let k = 0; k < around; k++) {
    out.indices.push(base, base + 1 + k, base + 1 + (k + 1) % around);
  }
  for (let r = 0; r < rings - 1; r++) {
    for (let k = 0; k < around; k++) {
      const a = base + 1 + r * around + k;
      const b = base + 1 + r * around + (k + 1) % around;
      out.indices.push(a, a + around, b, b, a + around, b + around);
    }
  }
  const last = base + 1 + (rings - 1) * around;
  for (let k = 0; k < around; k++) {
    out.indices.push(last + k, tail, last + (k + 1) % around);
  }
}

// A flat fin drawn on both sides with its own vertices, so each side has a proper normal. `side` places paired
// fins off the mid plane and tilts them outwards.
function pushFin(out, species, outline, side = 0, colour = species.colours.fin) {
  const L = species.length;
  const noseZ = L / 2;
  for (const facing of [1, -1]) {
    const start = out.positions.length / 3;
    const nx = side ? 0.55 * facing : facing;
    const ny = side ? 0.8 * facing : 0;
    for (const [s, h] of outline) {
      const spread = side ? side * (Math.abs(h) * 0.6 + 0.02) * L : 0;
      out.positions.push(spread, h * L, noseZ - s * L);
      out.normals.set(out.positions.length / 3 - 1, [nx, ny, 0]);
      out.colours.push(...colour);
      out.sheen.push(0);
    }
    for (let i = 1; i < outline.length - 1; i++) {
      if (facing > 0) out.indices.push(start, start + i, start + i + 1);
      else out.indices.push(start, start + i + 1, start + i);
    }
  }
}

function pushEyes(out, species) {
  // A dark disc on each side of the head: in footage the eye is the first detail that makes a fish read.
  const L = species.length;
  const s = 0.075;
  const [halfHeight, halfWidth, centre] = profileAt(species.profile, s);
  const radius = Math.max(0.012, halfHeight * 0.32) * L;
  for (const facing of [1, -1]) {
    const middle = out.positions.length / 3;
    const x = facing * (halfWidth * L + 0.0015 * L);
    out.positions.push(x, centre * L + halfHeight * 0.25 * L, L / 2 - s * L);
    out.normals.set(middle, [facing, 0, 0]);
    out.colours.push(0.02, 0.02, 0.02);
    out.sheen.push(0.6);
    for (let k = 0; k < 5; k++) {
      const a = (k / 5) * Math.PI * 2;
      out.positions.push(x, centre * L + halfHeight * 0.25 * L + Math.sin(a) * radius,
        L / 2 - s * L + Math.cos(a) * radius);
      out.normals.set(middle + 1 + k, [facing, 0, 0]);
      out.colours.push(0.05, 0.05, 0.05);
      out.sheen.push(0.6);
    }
    for (let k = 0; k < 5; k++) {
      const a = middle + 1 + k;
      const b = middle + 1 + (k + 1) % 5;
      if (facing > 0) out.indices.push(middle, b, a);
      else out.indices.push(middle, a, b);
    }
  }
}

/**
 * Body of one species, nose +Z, length `SPECIES[name].length` metres, vertex colours (countershading) and an
 * `aSheen` attribute (how mirror-like each vertex is). Triangles per tier: low about 90, medium about 240,
 * high about 330 (tests/test_fish_life.mjs).
 */
export function fishGeometry(name, detailName = 'medium') {
  const species = SPECIES[name];
  if (!species) throw new Error(`unknown fish species ${name}`);
  const detail = DETAIL[detailName] || DETAIL.medium;
  const out = {positions: [], colours: [], sheen: [], indices: [], normals: new Map()};
  pushBody(out, species, detail);
  const finColour = (key) => species.finColours?.[key] || species.colours.fin;
  pushFin(out, species, species.caudal, 0, finColour('caudal'));
  if (detail.fins) {
    for (const key of ['dorsal', 'dorsal2', 'adipose', 'anal']) {
      if (species[key]) pushFin(out, species, species[key], 0, finColour(key === 'dorsal2' ? 'dorsal' : key));
    }
    for (const key of ['pelvic', 'pectoral']) {
      if (!species[key]) continue;
      pushFin(out, species, species[key], 1, finColour(key));
      pushFin(out, species, species[key], -1, finColour(key));
    }
  } else if (species.dorsal) {
    pushFin(out, species, species.dorsal, 0, finColour('dorsal'));
  }
  if (detail.eyes) pushEyes(out, species);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(out.positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(out.colours, 3));
  geometry.setAttribute('aSheen', new THREE.Float32BufferAttribute(out.sheen, 1));
  geometry.setIndex(out.indices);
  geometry.computeVertexNormals();
  const normal = geometry.attributes.normal;
  for (const [index, value] of out.normals) {
    const length = Math.hypot(...value);
    normal.setXYZ(index, value[0] / length, value[1] / length, value[2] / length);
  }
  geometry.userData.fishSpecies = name;
  return geometry;
}

const SWIM_VERTEX_PARS = /* glsl */ `
  attribute vec3 aSwim;
  attribute float aSheen;
  varying float vFishSheen;
  uniform vec4 uFishBody;
  // Lateral offset of the body at this vertex and its slope along the body (travelling wave plus turn bend).
  vec2 fishSwim(vec3 p) {
    float s = clamp((uFishBody.x - p.z) / uFishBody.y, 0.0, 1.0);
    float envelope = uFishBody.z * aSwim.y * (0.18 + 0.82 * s * s);
    float travel = aSwim.x - uFishBody.w * s;
    float bend = aSwim.z * (s - 0.3) * (s - 0.3);
    float lateral = uFishBody.y * (envelope * sin(travel) + bend);
    float dEnvelope = uFishBody.z * aSwim.y * 1.64 * s;
    float dLateral = uFishBody.y * (dEnvelope * sin(travel) - envelope * uFishBody.w * cos(travel) +
      2.0 * aSwim.z * (s - 0.3));
    return vec2(lateral, -dLateral / uFishBody.y);
  }
`;
const SWIM_NORMAL = /* glsl */ `
  #include <beginnormal_vertex>
  vec2 fishWave = fishSwim(position);
  objectNormal = normalize(vec3(objectNormal.x, objectNormal.y, objectNormal.z - fishWave.y * objectNormal.x));
`;
const SWIM_POSITION = /* glsl */ `
  #include <begin_vertex>
  transformed.x += fishSwim(position).x;
  vFishSheen = aSheen;
`;
const SHEEN_FRAGMENT = /* glsl */ `
  #include <metalnessmap_fragment>
  metalnessFactor = mix(metalnessFactor, ${SHEEN_METALNESS.toFixed(3)}, vFishSheen);
`;
const SHEEN_ROUGH = /* glsl */ `
  #include <roughnessmap_fragment>
  roughnessFactor = mix(roughnessFactor, ${SHEEN_ROUGHNESS.toFixed(3)}, vFishSheen);
`;

function compileFish(shader) {
  shader.uniforms.uFishBody = this.userData.fishBody;
  shader.vertexShader = SWIM_VERTEX_PARS + shader.vertexShader
    .replace('#include <beginnormal_vertex>', SWIM_NORMAL)
    .replace('#include <begin_vertex>', SWIM_POSITION);
  shader.fragmentShader = 'varying float vFishSheen;\n' + shader.fragmentShader
    .replace('#include <metalnessmap_fragment>', SHEEN_FRAGMENT)
    .replace('#include <roughnessmap_fragment>', SHEEN_ROUGH);
}

function fishProgramKey() {
  return PROGRAM_KEY;
}

/** Material for one species: vertex colours, flank sheen and the swimming wave. `tint` multiplies the colours. */
export function fishMaterial(name, tint = 0xffffff) {
  const species = SPECIES[name];
  const material = new THREE.MeshStandardMaterial({color: tint, vertexColors: true, roughness: BODY_ROUGHNESS,
    metalness: 0.04, side: THREE.FrontSide});
  const wave = (Math.PI * 2) / species.waveLength;
  material.userData.fishBody = {value: new THREE.Vector4(species.length / 2, species.length, species.wave, wave)};
  material.onBeforeCompile = compileFish;
  material.customProgramCacheKey = fishProgramKey;
  return material;
}

/** Instanced mesh with its own per-fish swim attribute (phase, amplitude, bend) over a shared body. */
export function createFishMesh(body, material, count) {
  const geometry = new THREE.BufferGeometry();
  for (const [key, attribute] of Object.entries(body.attributes)) geometry.setAttribute(key, attribute);
  geometry.setIndex(body.index);
  geometry.boundingBox = null;
  const swim = new THREE.InstancedBufferAttribute(new Float32Array(count * 3), 3);
  swim.setUsage(THREE.DynamicDrawUsage);
  for (let i = 0; i < count; i++) swim.setXYZ(i, i * 2.39996, 1, 0);
  geometry.setAttribute('aSwim', swim);
  geometry.userData.fishSpecies = body.userData.fishSpecies;
  const mesh = new THREE.InstancedMesh(geometry, material, count);
  mesh.frustumCulled = false;
  mesh.userData.fish = true;
  return mesh;
}

// School motion
// Reaction distances (m) and rates (1/s). Assumed from footage: fish keep about 1 m from a working vehicle
// (crowded farm fish pass within 0.5-1 m) and dart when it closes quickly (V4, trout pen clip); none of this is
// measured behaviour.
const AVOID_RADIUS = 1.0;
const AVOID_RADIUS_LAMPS = 0.4;      // extra distance with the lamps on (pen fish shy from lights, server too)
const AVOID_GAIN = 0.9;
const AVOID_OUT_RATE = 4.0;
const AVOID_BACK_RATE = 0.45;
const STARTLE_SPEED = 0.35;          // approach speed (m/s) that turns a slow avoid into a dart
const STARTLE_DECAY = 1.6;
const HEADING_RATE = 2.2;            // how fast a fish's heading follows its swimming direction

/**
 * Per-fish motion state for a school. `fish` is the list the caller places ({offset, phase, scale}); the state
 * adds a slow wander, an avoid displacement and a startle level, and keeps heading and tail-beat phase.
 */
export function createSchoolMotion(fish, speciesName, random = Math.random) {
  const species = SPECIES[speciesName];
  return {
    species,
    fish: fish.map(function initialState(item) {
      return {
        item,
        wander: [random() * 6.28, random() * 6.28, random() * 6.28, 0.25 + random() * 0.35],
        avoid: new THREE.Vector3(),
        startle: 0,
        heading: null,
        pitch: 0,
        tail: random() * Math.PI * 2,
        turn: 0,
        // Small individual tilt so a school is not a set of perfectly level copies.
        tilt: (random() - 0.5) * 0.12,
        position: new THREE.Vector3(),
      };
    }),
  };
}

const placed = new THREE.Vector3();
const placedEuler = new THREE.Euler();
const away = new THREE.Vector3();
const local = new THREE.Vector3();
const matrix = new THREE.Matrix4();
const rotation = new THREE.Quaternion();
const scaleVector = new THREE.Vector3();
const motionEuler = new THREE.Euler(0, 0, 0, 'YXZ');

function wanderOffset(state, t, length, target) {
  const [a, b, c, rate] = state.wander;
  // Lateral, vertical and along-track drift of about half a body length round the fish's slot in the school.
  target.set(Math.sin(t * rate + a) * 0.55 * length, Math.sin(t * rate * 0.7 + b) * 0.25 * length,
    Math.sin(t * rate * 0.6 + c) * 0.8 * length);
  return target;
}

function wanderVelocity(state, t, length, target) {
  const [a, b, c, rate] = state.wander;
  target.set(Math.cos(t * rate + a) * 0.55 * length * rate, Math.cos(t * rate * 0.7 + b) * 0.25 * length * rate * 0.7,
    Math.cos(t * rate * 0.6 + c) * 0.8 * length * rate * 0.6);
  return target;
}

function angleDelta(from, to) {
  return Math.atan2(Math.sin(to - from), Math.cos(to - from));
}

function avoidVehicle(state, position, vehicle, dt) {
  // Push the fish out of a sphere round the vehicle, quickly outwards and slowly back to its slot.
  let push = 0;
  if (vehicle) {
    away.copy(state.position).sub(vehicle.position);
    const distance = Math.max(away.length(), 0.05);
    const radius = AVOID_RADIUS + (vehicle.lamps ? AVOID_RADIUS_LAMPS : 0);
    if (distance < radius) {
      push = (radius - distance) * AVOID_GAIN;
      away.multiplyScalar(push / distance);
      const closing = vehicle.velocity ? vehicle.velocity.dot(away) / Math.max(push, 1e-3) : 0;
      if (closing > STARTLE_SPEED || distance < radius * 0.5) state.startle = 1;
    }
  }
  if (!push) away.set(0, 0, 0);
  const rate = push ? AVOID_OUT_RATE : AVOID_BACK_RATE;
  state.avoid.lerp(away, 1 - Math.exp(-rate * dt));
  state.startle = Math.max(0, state.startle - STARTLE_DECAY * dt);
  position.add(state.avoid);
}

const instanceColour = new THREE.Color();

function writeInstance(mesh, index, item) {
  mesh.setMatrixAt(index, matrix);
  mesh.geometry.attributes.aSwim.setXYZ(index, swimValue[0], swimValue[1], swimValue[2]);
  if (item.colour && mesh.instanceColor) mesh.setColorAt(index, instanceColour.setHex(item.colour));
}

function finishMesh(mesh, count) {
  mesh.count = count;
  mesh.instanceMatrix.needsUpdate = true;
  mesh.geometry.attributes.aSwim.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
}

/** Writes every fish into one instanced mesh, at its own index. */
export function meshSink(mesh) {
  return {
    put(i, distance, item) {
      writeInstance(mesh, i, item);
    },
    end(total) {
      finishMesh(mesh, total);
    },
  };
}

/**
 * Near / far level of detail for big schools: fish within `split` metres of the eye go to `near` (full body, at
 * most near.instanceMatrix.count of them), the rest to `far` (cheap body). Both meshes are drawn every frame.
 */
export function lodSink(near, far, eye, split) {
  let nearCount = 0;
  let farCount = 0;
  const nearLimit = near.instanceMatrix.count;
  return {
    put(i, distance, item) {
      if (distance < split && nearCount < nearLimit) {
        writeInstance(near, nearCount, item);
        nearCount++;
      } else {
        writeInstance(far, farCount, item);
        farCount++;
      }
    },
    end() {
      finishMesh(near, nearCount);
      finishMesh(far, farCount);
      nearCount = 0;
      farCount = 0;
    },
    eye,
  };
}

const swimValue = [0, 1, 0];

/**
 * Move one school's instances. `placeFish(item, t, position, euler)` gives the fish's slot (school layout,
 * server centre) and base heading; `base` is the school's speed through the water (m/s). `vehicle` is
 * {position, velocity, lamps} in three space or null. `target` is an instanced mesh or a sink (meshSink,
 * lodSink); it receives the instance matrices, swim attributes and per-fish colours.
 */
export function updateSchoolMotion(motion, target, dt, t, placeFish, base, vehicle) {
  const sink = target.isInstancedMesh ? meshSink(target) : target;
  const step = Math.max(0, Math.min(dt, 0.1));
  motion.fish.forEach(function moveFish(state, i) {
    const {item} = state;
    const length = motion.species.length * item.scale;
    placeFish(item, t, placed, placedEuler);
    const baseHeading = placedEuler.y;
    wanderOffset(state, t, length, local);
    local.applyAxisAngle(THREE.Object3D.DEFAULT_UP, baseHeading);
    placed.add(local);
    const first = state.heading === null;
    state.position.copy(placed);
    avoidVehicle(state, placed, vehicle, step);
    state.position.copy(placed);
    // Swimming direction: the school's track plus the fish's own drift and avoid displacement.
    wanderVelocity(state, t, length, local);
    // A fish pushed aside by the vehicle also turns away from it: the avoid displacement in the fish's frame.
    const avoidLateral = state.avoid.x * Math.cos(baseHeading) - state.avoid.z * Math.sin(baseHeading);
    const lateral = local.x + avoidLateral * 1.5;
    const along = Math.max(0.12, base) + local.z;
    const wanted = baseHeading + Math.atan2(lateral, along);
    if (first) state.heading = wanted;
    const change = angleDelta(state.heading, wanted) * (1 - Math.exp(-HEADING_RATE * (1 + 3 * state.startle) * step));
    state.heading += change;
    state.turn += ((step > 0 ? change / step : 0) - state.turn) * (1 - Math.exp(-6 * step));
    // Positive rotation about X turns the nose (+Z) down, so climbing fish get a negative pitch.
    state.pitch = -Math.atan2(local.y, along) * 0.9 + state.tilt;
    // Tail beat from swimming speed in body lengths per second (Bainbridge: f = (4 U / L + 4) / 3).
    const speed = Math.hypot(lateral, along) * (1 + 2.5 * state.startle);
    const frequency = Math.min(9, (4 * speed / length + 4) / 3);
    state.tail = (state.tail + Math.PI * 2 * frequency * step) % (Math.PI * 200);
    const amplitude = 1 + 0.5 * state.startle;
    const bend = THREE.MathUtils.clamp(-state.turn * 0.35, -0.6, 0.6);
    swimValue[0] = state.tail;
    swimValue[1] = amplitude;
    swimValue[2] = bend;
    // Fish bank into turns (top towards the inside of the turn).
    const roll = THREE.MathUtils.clamp(-state.turn * 0.35, -0.4, 0.4) + state.tilt * 0.5;
    rotation.setFromEuler(motionEuler.set(state.pitch, state.heading, roll));
    matrix.compose(placed, rotation, scaleVector.setScalar(item.scale));
    sink.put(i, sink.eye ? placed.distanceTo(sink.eye) : 0, item);
  });
  sink.end(motion.fish.length);
}
