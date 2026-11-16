// Offshore wind farm on the horizon: turbine designs, the farm layout and the instanced meshes that draw it.
//
// Every turbine of a farm is one instance of one merged geometry (foundation, tower, nacelle, spinner and three
// blades, coloured per vertex), so a whole farm costs one draw call per level of detail. The rotor turns in the
// vertex shader (per-instance phase and speed), nothing is updated per frame on the CPU.
//
// Turbines stand kilometres away, beyond the camera's far plane. `horizonMaterial()` draws such props at their
// true size and direction: every vertex further than FARM_REACH is pulled towards the camera along its line of
// sight (a uniform scaling about the eye, which leaves the projected image unchanged), and the aerial haze for
// the distance it was pulled in is added back, so far rows fade into the horizon instead of popping out.
//
// Dimensions are public, typical values for current offshore turbine classes (no make or model); see
// docs/design/wind-farm/README.md.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Vertices further than this (metres) are pulled in along the line of sight; inside the camera's 2600 m far plane.
export const FARM_REACH = 2200;

const COLOURS = Object.freeze({
  tower: '#e6e9e9',
  blade: '#eff1f1',
  nacelle: '#e8ebeb',
  red: '#c3261c',
  yellow: '#efb90a',
  grating: '#3b4045',
  splash: '#2b2924',
  topside: '#d9dcdc',
  topsideDark: '#5a6066'
});

// Turbine classes. hub: hub height above sea; rotor: diameter; tipSpeed: m/s at rated rotation.
export const TURBINE_TYPES = Object.freeze({
  // Current large offshore class on a monopile: tip bands for aviation marking.
  large: Object.freeze({
    hub: 138, rotor: 222, tipSpeed: 86, towerBase: 7.8, towerTop: 5.0, foundation: 'monopile',
    tpDiameter: 7.4, tpTop: 22, nacelle: Object.freeze([7.6, 7.8, 20]), spinner: 6.2, rootDiameter: 4.4,
    maxChord: 5.6, tipBands: true, tilt: 6
  }),
  // Nearshore 8 MW class on a four-legged jacket (Taiwan Strait type).
  jacket: Object.freeze({
    hub: 112, rotor: 167, tipSpeed: 84, towerBase: 6.0, towerTop: 3.9, foundation: 'jacket',
    tpDiameter: 6.2, tpTop: 21, nacelle: Object.freeze([6.4, 6.6, 15]), spinner: 4.8, rootDiameter: 3.4,
    maxChord: 4.3, tipBands: false, tilt: 6, jacketHalf: 9, deckHalf: 9.5
  }),
  // Older 6 MW class on monopiles, used for farms seen from a distance.
  mid: Object.freeze({
    hub: 102, rotor: 154, tipSpeed: 80, towerBase: 6.0, towerTop: 3.9, foundation: 'monopile',
    tpDiameter: 6.0, tpTop: 19, nacelle: Object.freeze([5.6, 6.0, 13.5]), spinner: 4.4, rootDiameter: 3.2,
    maxChord: 4.1, tipBands: false, tilt: 5
  })
});

// Spacing in rotor diameters across and along the prevailing wind (typical 5-8 D offshore).
const SPACING = Object.freeze({across: 5.2, along: 7.0});
const PARKED_SHARE = 0.08;
const NEAR_LOD_RANGE = 1700;

function colour(hex) {
  return new THREE.Color(hex);
}

// Paints a part: per-vertex colour and the rotor flag the shader reads.
function paint(part, hex, spin = 0) {
  const count = part.attributes.position.count;
  const c = colour(hex);
  const colours = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    colours[i * 3] = c.r;
    colours[i * 3 + 1] = c.g;
    colours[i * 3 + 2] = c.b;
  }
  part.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  part.setAttribute('aSpin', new THREE.BufferAttribute(new Float32Array(count).fill(spin), 1));
  part.setAttribute('aBlade', new THREE.BufferAttribute(new Float32Array(count * 4), 4));
  part.setAttribute('aSection', new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  part.deleteAttribute('uv');
  return part;
}

// Open-ended tube between two heights, tapered.
function tube(radiusBottom, radiusTop, y0, y1, segments, hex, open = true) {
  const g = new THREE.CylinderGeometry(radiusTop, radiusBottom, y1 - y0, segments, 1, open);
  g.translate(0, (y0 + y1) / 2, 0);
  return paint(g, hex);
}

function box(w, h, l, x, y, z, hex, spin = 0) {
  const g = new THREE.BoxGeometry(w, h, l);
  g.translate(x, y, z);
  return paint(g, hex, spin);
}

// A cylinder member between two points (jacket legs and braces, crane posts).
function member(a, b, radius, segments, hex) {
  const from = new THREE.Vector3(...a);
  const to = new THREE.Vector3(...b);
  const length = from.distanceTo(to);
  const g = new THREE.CylinderGeometry(radius, radius, length, segments, 1, true);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize());
  g.applyQuaternion(q);
  g.translate((from.x + to.x) / 2, (from.y + to.y) / 2, (from.z + to.z) / 2);
  return paint(g, hex);
}

// Railing silhouette round a platform: a top and a knee rail, with posts on the detailed model.
function railing(radius, y, sides, detailed, hex) {
  const parts = [tube(radius, radius, y + 1.0, y + 1.1, sides, hex)];
  if (!detailed) return parts;
  parts.push(tube(radius, radius, y + 0.5, y + 0.56, sides, hex));
  for (let i = 0; i < sides; i++) {
    const a = (i + 0.5) / sides * Math.PI * 2;
    parts.push(box(0.08, 1.1, 0.08, Math.cos(a) * radius, y + 0.55, Math.sin(a) * radius, hex));
  }
  return parts;
}

// Square railing round a jacket deck.
function squareRailing(half, y, detailed, hex) {
  const parts = [];
  const rails = detailed ? [0.53, 1.05] : [1.05];
  for (const height of rails) {
    parts.push(box(half * 2, 0.07, 0.07, 0, y + height, half, hex));
    parts.push(box(half * 2, 0.07, 0.07, 0, y + height, -half, hex));
    parts.push(box(0.07, 0.07, half * 2, half, y + height, 0, hex));
    parts.push(box(0.07, 0.07, half * 2, -half, y + height, 0, hex));
  }
  return parts;
}

function monopileFoundation(type, detailed) {
  const r = type.tpDiameter / 2;
  const segments = detailed ? 14 : 6;
  const deckY = type.tpTop;
  const parts = [
    tube(r, r, -4, deckY, segments, COLOURS.yellow),
    tube(r + 0.04, r + 0.04, -1.2, 1.4, segments, COLOURS.splash),
    // Access platform: a dark grating ring round the top of the transition piece.
    tube(r + 3.4, r + 3.4, deckY - 0.5, deckY, 8, COLOURS.grating, false),
    ...railing(r + 3.3, deckY, 8, detailed, COLOURS.yellow)
  ];
  if (detailed) {
    // Boat landing (two vertical fender tubes) and the platform davit.
    parts.push(member([-1.1, -2, r + 0.9], [-1.1, deckY - 3, r + 0.9], 0.22, 5, COLOURS.yellow));
    parts.push(member([1.1, -2, r + 0.9], [1.1, deckY - 3, r + 0.9], 0.22, 5, COLOURS.yellow));
    parts.push(member([r + 2.2, deckY, 0], [r + 2.2, deckY + 4.2, 0], 0.18, 5, COLOURS.yellow));
    parts.push(member([r + 2.2, deckY + 4.2, 0], [r + 2.2, deckY + 4.6, 2.6], 0.12, 4, COLOURS.yellow));
  }
  return parts;
}

// Four-legged jacket, battered legs and X braces above the water, a square deck and a short transition piece.
function jacketFoundation(type, detailed) {
  const segments = detailed ? 6 : 4;
  const base = type.jacketHalf;
  const top = type.jacketHalf * 0.72;
  const deckY = type.tpTop - 3;
  const parts = [];
  const corners = [[1, 1], [1, -1], [-1, -1], [-1, 1]];
  const at = (corner, y) => {
    const half = THREE.MathUtils.lerp(base, top, (y + 6) / (deckY + 6));
    return [corner[0] * half, y, corner[1] * half];
  };
  for (const corner of corners) parts.push(member(at(corner, -6), at(corner, deckY), 0.95, segments, COLOURS.yellow));
  for (const corner of corners) parts.push(member(at(corner, -1.2), at(corner, 1.4), 1.0, segments, COLOURS.splash));
  for (let i = 0; i < 4; i++) {
    const a = corners[i];
    const b = corners[(i + 1) % 4];
    parts.push(member(at(a, 2.5), at(b, 2.5), 0.5, segments, COLOURS.yellow));
    parts.push(member(at(a, 2.5), at(b, deckY - 1), 0.45, segments, COLOURS.yellow));
    parts.push(member(at(b, 2.5), at(a, deckY - 1), 0.45, segments, COLOURS.yellow));
  }
  const deck = type.deckHalf;
  parts.push(box(deck * 2, 1.2, deck * 2, 0, deckY + 0.6, 0, COLOURS.yellow));
  parts.push(box(deck * 2 - 0.4, 0.5, deck * 2 - 0.4, 0, deckY - 0.2, 0, COLOURS.grating));
  parts.push(...squareRailing(deck - 0.1, deckY + 1.2, detailed, COLOURS.yellow));
  const r = type.tpDiameter / 2;
  parts.push(tube(r, r, deckY + 1.2, type.tpTop, detailed ? 14 : 6, COLOURS.yellow));
  if (detailed) {
    parts.push(box(2.4, 2.6, 1.6, deck - 2.4, deckY + 2.5, -deck + 1.6, COLOURS.topside));
    parts.push(member([deck - 1.5, deckY + 1.2, deck - 1.5], [deck - 1.5, deckY + 6, deck - 1.5], 0.2, 5,
      COLOURS.yellow));
  }
  return parts;
}

// Long, crisp nacelle box on the tower top; the rotor hub sits ahead of it on +z (upwind).
function nacelleParts(type, detailed) {
  const [w, h, l] = type.nacelle;
  const y = type.hub + 0.25;
  const front = l * 0.26;
  const parts = [box(w, h, l, 0, y, front - l / 2, COLOURS.nacelle)];
  // Eased leading edges: a slightly narrower front block, so the nose steps in rather than rounding off.
  parts.push(box(w * 0.86, h * 0.9, 1.0, 0, y, front + 0.5, COLOURS.nacelle));
  if (detailed) {
    // Rear roof platform (helicopter hoisting area) and a cooler on top.
    parts.push(box(w * 0.92, 0.18, l * 0.3, 0, y + h / 2 + 0.6, front - l * 0.82, COLOURS.grating));
    parts.push(box(w * 0.5, 1.3, l * 0.16, 0, y + h / 2 + 0.65, front - l * 0.46, COLOURS.nacelle));
  }
  return {parts, hubZ: front + 1.0 + type.spinner * 0.25};
}

// Spinner: a short hub ring and a pointed nose cone (rotor frame: axis +z, origin at the blade root plane).
function spinnerParts(type, detailed) {
  const r = type.spinner / 2;
  const segments = detailed ? 12 : 6;
  const ring = new THREE.CylinderGeometry(r, r * 0.92, type.spinner * 0.55, segments, 1, true);
  ring.rotateX(Math.PI / 2);
  ring.translate(0, 0, -type.spinner * 0.12);
  const cone = new THREE.ConeGeometry(r, type.spinner * 0.95, segments, 1, true);
  cone.rotateX(Math.PI / 2);
  cone.translate(0, 0, type.spinner * 0.15 + type.spinner * 0.475);
  return [paint(ring, COLOURS.nacelle, 1), paint(cone, COLOURS.nacelle, 1)];
}

// Blade planform along the span s (0 at the root flange, 1 at the tip). Round root cylinder, a smooth
// transition to the maximum chord at 20 % span, then a long convex taper to a thin tip. The leading edge stays
// nearly straight and the trailing edge carries the change of chord, sweeping back towards the tip, so from the
// front each blade reads as a slightly curved sabre. Thickness ratio: 100 % (round) at the root, 36 % at the
// maximum chord, 16 % at the tip.
const ROOT_END = 0.04;
const MAX_CHORD_AT = 0.2;

function chordAt(s, type) {
  const tip = 0.1 * type.maxChord;
  if (s <= ROOT_END) return type.rootDiameter;
  if (s <= MAX_CHORD_AT) {
    const k = THREE.MathUtils.smoothstep(s, ROOT_END, MAX_CHORD_AT);
    return THREE.MathUtils.lerp(type.rootDiameter, type.maxChord, k);
  }
  const k = (s - MAX_CHORD_AT) / (1 - MAX_CHORD_AT);
  return tip + (type.maxChord - tip) * (1 - k) ** 1.3;
}

function thicknessAt(s) {
  if (s <= ROOT_END) return 1;
  if (s <= MAX_CHORD_AT) return THREE.MathUtils.lerp(1, 0.36, THREE.MathUtils.smoothstep(s, ROOT_END, MAX_CHORD_AT));
  if (s <= 0.5) return THREE.MathUtils.lerp(0.36, 0.21, (s - MAX_CHORD_AT) / 0.3);
  return THREE.MathUtils.lerp(0.21, 0.16, (s - 0.5) / 0.5);
}

// Leading edge ahead of the pitch axis (m): half the root diameter on the round root, about 27 % of the
// chord at the maximum chord, then a nearly straight line to the tip.
function leadingEdgeAt(s, type) {
  const atMax = 0.27 * type.maxChord;
  if (s <= ROOT_END) return type.rootDiameter / 2;
  if (s <= MAX_CHORD_AT) {
    const k = THREE.MathUtils.smoothstep(s, ROOT_END, MAX_CHORD_AT);
    return THREE.MathUtils.lerp(type.rootDiameter / 2, atMax, k);
  }
  const k = (s - MAX_CHORD_AT) / (1 - MAX_CHORD_AT);
  return THREE.MathUtils.lerp(atMax, 0.4 * chordAt(1, type), k);
}

// Section point at angle phi (0 at the leading edge): [u along the chord from the leading edge, half thickness],
// per unit chord. A symmetric aerofoil (NACA 4-digit form, thin trailing edge) blended into a circle at the
// round root.
function sectionPoint(phi, thickness) {
  const u = (1 - Math.cos(phi)) / 2;
  const naca = 5 * thickness * (0.2969 * Math.sqrt(u) - 0.126 * u - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1015 * u ** 4);
  const round = THREE.MathUtils.smoothstep(thickness, 0.4, 1.0);
  return [u, THREE.MathUtils.lerp(naca * Math.sign(Math.sin(phi)), 0.5 * Math.sin(phi), round)];
}

// Span stations, dense at the root transition and the tip, with doubled stations at the colour changes of the
// tip bands so the bands stay crisp.
const NEAR_STATIONS = Object.freeze([0, 0.02, 0.04, 0.07, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
  0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.94, 0.97, 0.99, 1]);
const FAR_STATIONS = Object.freeze([0, 0.04, 0.12, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92, 1]);

function bladeStations(detailed, bands) {
  const stations = (detailed ? NEAR_STATIONS : FAR_STATIONS).map((s) => ({s, hex: COLOURS.blade}));
  if (!bands) return stations;
  // Aviation marking: red, white, red over the outer part of the blade (about 6 m each on a 108 m blade).
  const edges = [[0.835, COLOURS.blade, COLOURS.red], [0.89, COLOURS.red, COLOURS.blade],
    [0.945, COLOURS.blade, COLOURS.red]];
  const out = stations.filter((station) => station.s < edges[0][0]);
  for (let i = 0; i < edges.length; i++) {
    const [s, before, after] = edges[i];
    out.push({s, hex: before});
    out.push({s, hex: after});
    const next = i + 1 < edges.length ? edges[i + 1][0] : 1.01;
    for (const station of stations) {
      if (station.s > s && station.s < next) out.push({s: station.s, hex: after});
    }
  }
  return out;
}

// One blade along +y in the rotor frame: lofted aerofoil sections, twisted 13 degrees at the root to 0 at the
// tip, leading edge on +x (the rotor turns clockwise seen from upwind), tip swept slightly back and pre-bent
// upwind (+z) by 4.5 % of the radius. aBlade holds each vertex's point on the pitch axis (xyz) and 1 (w),
// aSection the section's twist, half chord and half thickness: the vertex shader keeps far blades at least
// about a pixel wide in both directions.
function bladeGeometry(type, detailed) {
  const radius = type.rotor / 2;
  const root = type.spinner * 0.42;
  const length = radius - root;
  const sides = detailed ? 12 : 6;
  const stations = bladeStations(detailed, type.tipBands);
  const positions = [];
  const axes = [];
  const sections = [];
  const colours = [];
  const index = [];
  for (const station of stations) {
    const s = station.s;
    // The very tip closes to a rounded point rather than ending in an open section.
    const chord = chordAt(s, type) * (s >= 1 ? 0.35 : 1);
    const thickness = thicknessAt(s);
    const lead = leadingEdgeAt(s, type);
    const twist = THREE.MathUtils.degToRad(13 * (1 - s) ** 1.6);
    const sweep = -radius * 0.012 * Math.max(0, (s - 0.55) / 0.45) ** 2;
    const bend = radius * 0.045 * s * s;
    const y = root + s * length;
    const c = colour(station.hex);
    for (let k = 0; k < sides; k++) {
      const [u, half] = sectionPoint((k / sides) * Math.PI * 2, thickness);
      const x = lead - u * chord;
      const z = half * chord;
      positions.push(x * Math.cos(twist) - z * Math.sin(twist) + sweep, y,
        x * Math.sin(twist) + z * Math.cos(twist) + bend);
      axes.push(sweep, y, bend, 1);
      sections.push(twist, chord / 2, Math.max(thickness * chord / 2, 0.01));
      colours.push(c.r, c.g, c.b);
    }
  }
  for (let i = 0; i + 1 < stations.length; i++) {
    if (stations[i].s === stations[i + 1].s) continue;
    for (let k = 0; k < sides; k++) {
      const a = i * sides + k;
      const b = i * sides + (k + 1) % sides;
      index.push(a, a + sides, b, b, a + sides, b + sides);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
  g.setAttribute('aSpin', new THREE.Float32BufferAttribute(new Array(positions.length / 3).fill(1), 1));
  g.setAttribute('aBlade', new THREE.Float32BufferAttribute(axes, 4));
  g.setAttribute('aSection', new THREE.Float32BufferAttribute(sections, 3));
  g.setIndex(index);
  g.computeVertexNormals();
  return g;
}

// Pitch bearing: a flange ring where each blade root enters the hub, at the spinner's surface.
function pitchBearing(type, detailed) {
  const r = type.rootDiameter / 2 * 1.14;
  const g = new THREE.CylinderGeometry(r, r, 0.45, detailed ? 16 : 6, 1, true);
  g.translate(0, type.spinner * 0.47, 0);
  return paint(g, COLOURS.nacelle, 1);
}

function rotorParts(type, detailed) {
  const parts = spinnerParts(type, detailed);
  const blade = bladeGeometry(type, detailed);
  const bearing = pitchBearing(type, detailed);
  for (let b = 0; b < 3; b++) {
    for (const part of [blade, bearing]) {
      const copy = part.clone();
      copy.rotateZ(b * Math.PI * 2 / 3);
      if (part === blade) rotateBladeAxes(copy, b * Math.PI * 2 / 3);
      parts.push(copy);
    }
  }
  blade.dispose();
  bearing.dispose();
  return parts;
}

// rotateZ moves positions and normals; the pitch-axis points in aBlade must turn with them.
function rotateBladeAxes(geometry, angle) {
  const axes = geometry.attributes.aBlade;
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  for (let i = 0; i < axes.count; i++) {
    const x = axes.getX(i);
    const y = axes.getY(i);
    axes.setXY(i, c * x - s * y, s * x + c * y);
  }
}

/**
 * One turbine as a single geometry (turbine frame: base at sea level, rotor facing +z).
 * foundation: false leaves out the foundation, for a tower standing on a site's own structure.
 */
export function turbineGeometry(type, detailed, {foundation = true} = {}) {
  const jacket = type.foundation === 'jacket';
  const below = jacket ? jacketFoundation(type, detailed) : monopileFoundation(type, detailed);
  const nacelle = nacelleParts(type, detailed);
  const towerTop = type.hub - type.nacelle[1] / 2 + 0.2;
  const tower = tube(type.towerBase / 2, type.towerTop / 2, type.tpTop, towerTop, detailed ? 14 : 6, COLOURS.tower);
  const parts = [...(foundation ? below : []), tower, ...nacelle.parts, ...rotorParts(type, detailed)];
  const merged = mergeGeometries(parts, false);
  for (const part of foundation ? parts : [...below, ...parts]) part.dispose();
  merged.userData.hub = new THREE.Vector3(0, type.hub, nacelle.hubZ);
  return merged;
}

/** Offshore substation: a jacket with a two-storey topside, one per farm. */
export function substationGeometry() {
  const parts = [];
  const half = 13;
  for (const [x, z] of [[1, 1], [1, -1], [-1, -1], [-1, 1]]) {
    parts.push(member([x * half * 1.15, -6, z * half * 1.15], [x * half, 20, z * half], 1.0, 6, COLOURS.yellow));
    parts.push(member([x * half * 1.12, -1.2, z * half * 1.12], [x * half * 1.1, 1.4, z * half * 1.1], 1.05, 6,
      COLOURS.splash));
  }
  parts.push(box(34, 8, 26, 0, 24, 0, COLOURS.topside));
  parts.push(box(30, 7, 22, 0, 31.5, 0, COLOURS.topside));
  parts.push(box(34.4, 0.6, 26.4, 0, 20.3, 0, COLOURS.topsideDark));
  parts.push(box(10, 3, 8, -9, 36.5, 4, COLOURS.topsideDark));
  parts.push(member([12, 35, -8], [12, 44, -8], 0.6, 6, COLOURS.yellow));
  parts.push(member([12, 44, -8], [3, 47, -8], 0.35, 4, COLOURS.yellow));
  const merged = mergeGeometries(parts, false);
  for (const part of parts) part.dispose();
  return merged;
}

// Seeded layout ------------------------------------------------------------------------------------------

/**
 * Turbine positions of a farm (three.js metres, relative to the site centre).
 * plan: {type, mode: 'inside'|'distant', anchor: {x, z}, windAngle, offset?}
 * Returns [{x, z, yaw, phase, omega}], plus the substation position.
 */
export function farmLayout(plan, random) {
  const type = TURBINE_TYPES[plan.type];
  const across = SPACING.across * type.rotor;
  const along = SPACING.along * type.rotor;
  const wind = plan.windAngle;
  // Unit vectors: `up` points into the wind, `side` along a row.
  const up = {x: Math.cos(wind), z: Math.sin(wind)};
  const side = {x: -up.z, z: up.x};
  const inside = plan.mode === 'inside';
  const rows = inside ? [-1, 5] : [0, 5];
  const cols = inside ? [-3, 4] : [-4, 4];
  // The farm recedes away from the site: rows run downwind of the anchor for an inside farm, or start at
  // `offset` metres along `bearing` for a distant one.
  const origin = inside ? {x: plan.anchor.x, z: plan.anchor.z} : {
    x: Math.cos(plan.bearing) * plan.offset, z: Math.sin(plan.bearing) * plan.offset
  };
  // b runs against `up`, so rows recede from the site when b's sign is opposite to bearing · up.
  const facing = inside ? 1 : Math.cos(plan.bearing) * up.x + Math.sin(plan.bearing) * up.z;
  const rowSign = facing > 0 ? -1 : 1;
  const slope = 0.35 + random() * 0.4;
  const turbines = [];
  let substation = null;
  const middleRow = Math.round((rows[0] + rows[1]) / 2);
  for (let row = rows[0]; row <= rows[1]; row++) {
    const stagger = (row & 1) ? 0.5 : 0;
    for (let col = cols[0]; col <= cols[1]; col++) {
      if (inside && row === 0 && col === 0) continue;
      // An irregular outline: the far corner is cut on a slant, as farm boundaries follow lease lines.
      if (col > cols[1] - Math.floor((row - rows[0]) * slope)) continue;
      const a = (col + stagger) * across + (random() - 0.5) * across * 0.08;
      const b = rowSign * row * along + (random() - 0.5) * along * 0.06;
      const x = origin.x + side.x * a - up.x * b;
      const z = origin.z + side.z * a - up.z * b;
      if (!substation && row === middleRow && col === 1) {
        substation = {x, z, yaw: Math.atan2(side.x, side.z)};
        continue;
      }
      const parked = random() < PARKED_SHARE;
      const tip = type.tipSpeed * (0.82 + random() * 0.18);
      const omega = parked ? 0.01 + random() * 0.02 : tip / (type.rotor / 2);
      // Rotors face the wind, each yawed a few degrees off as it tracks the local direction.
      const yaw = Math.atan2(up.x, up.z) + THREE.MathUtils.degToRad((random() - 0.5) * 8);
      turbines.push({x, z, yaw, phase: random() * Math.PI * 2, omega});
    }
  }
  return {turbines, substation, spacing: {across, along}};
}

// Material ---------------------------------------------------------------------------------------------

const hazeUniform = {value: new THREE.Vector4()};
const pixelUniform = {value: 0.001};
const bufferSize = new THREE.Vector2();

// Distant props share the daylight's aerial haze (fx/daylight.js publishes it on the scene each frame); the
// rotor shader also needs the size of a pixel (tangent of its angle) for this camera.
function syncHaze(renderer, scene, camera) {
  const haze = scene?.userData?.daylightHaze;
  if (haze) hazeUniform.value.set(haze.colour.x, haze.colour.y, haze.colour.z, haze.rate);
  else hazeUniform.value.set(0, 0, 0, 0);
  if (camera?.isPerspectiveCamera) {
    renderer.getDrawingBufferSize(bufferSize);
    pixelUniform.value = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / Math.max(1, bufferSize.y);
  }
}

const VERTEX_HEADER = /* glsl */ `
  uniform float uFarmReach;
  varying float vFarmExtra;
  #ifdef FARM_ROTOR
  uniform float uFarmTime;
  uniform vec3 uRotorHub;
  uniform float uRotorTilt;
  uniform float uFarmPixel;
  attribute float aSpin;
  attribute vec2 aRotor;
  attribute vec4 aBlade;
  attribute vec3 aSection;
  vec3 farmRotate(vec3 v) {
    float a = aRotor.x - uFarmTime * aRotor.y;
    float c = cos(a);
    float s = sin(a);
    v.xy = vec2(c * v.x - s * v.y, s * v.x + c * v.y);
    float ct = cos(uRotorTilt);
    float st = sin(uRotorTilt);
    return vec3(v.x, ct * v.y + st * v.z, -st * v.y + ct * v.z);
  }
  #endif
`;

const VERTEX_NORMAL = /* glsl */ `
  #include <beginnormal_vertex>
  #ifdef FARM_ROTOR
  if (aSpin > 0.5) objectNormal = farmRotate(objectNormal);
  #endif
`;

// Blades: far away a blade is thinner than a pixel and breaks up into dots. Each section is widened along its
// chord and its thickness, about its pitch axis (aBlade.xyz), until it is at least about 1.7 pixels across at
// the hub's distance: a smooth function of distance that leaves near blades untouched.
const VERTEX_BEGIN = /* glsl */ `
  #include <begin_vertex>
  #ifdef USE_INSTANCING
  mat4 farmModel = modelMatrix * instanceMatrix;
  #else
  mat4 farmModel = modelMatrix;
  #endif
  #ifdef FARM_ROTOR
  if (aSpin > 0.5) {
    if (aBlade.w > 0.5) {
      float hubDistance = distance((farmModel * vec4(uRotorHub, 1.0)).xyz, cameraPosition);
      float minHalf = 0.85 * uFarmPixel * hubDistance;
      vec2 radial = normalize(aBlade.xy);
      vec3 tangent = vec3(radial.y, -radial.x, 0.0);
      vec3 chordDir = cos(aSection.x) * tangent + vec3(0.0, 0.0, sin(aSection.x));
      vec3 thickDir = -sin(aSection.x) * tangent + vec3(0.0, 0.0, cos(aSection.x));
      vec3 off = transformed - aBlade.xyz;
      float alongChord = dot(off, chordDir);
      float alongThick = dot(off, thickDir);
      vec3 rest = off - chordDir * alongChord - thickDir * alongThick;
      float chordGrow = max(1.0, minHalf / aSection.y);
      float thickGrow = max(1.0, minHalf / aSection.z);
      transformed = aBlade.xyz + rest + chordDir * alongChord * chordGrow + thickDir * alongThick * thickGrow;
    }
    transformed = uRotorHub + farmRotate(transformed);
  }
  #endif
  {
    vec3 farmWorld = (farmModel * vec4(transformed, 1.0)).xyz;
    float farmDistance = distance(farmWorld, cameraPosition);
    float farmScale = min(1.0, uFarmReach / max(farmDistance, 1.0));
    vec3 farmNear = cameraPosition + (farmWorld - cameraPosition) * farmScale;
    transformed = (inverse(farmModel) * vec4(farmNear, 1.0)).xyz;
    vFarmExtra = farmDistance - farmDistance * farmScale;
  }
`;

const FRAGMENT_HEADER = /* glsl */ `
  uniform vec4 uFarmHaze;
  varying float vFarmExtra;
`;

// Haze for the part of the path the vertex was pulled in by; the water optics add the rest (same colour).
const FRAGMENT_HAZE = /* glsl */ `
  gl_FragColor.rgb = mix(gl_FragColor.rgb, uFarmHaze.rgb, 1.0 - exp(-vFarmExtra * uFarmHaze.w));
  #include <tonemapping_fragment>
`;

/**
 * Lit, vertex-coloured material for props on the horizon. rotor: {time, hub, tilt} turns the rotor vertices.
 */
export function horizonMaterial(rotor = null) {
  const material = new THREE.MeshStandardMaterial({vertexColors: true, roughness: 0.6, metalness: 0});
  const uniforms = {uFarmReach: {value: FARM_REACH}, uFarmHaze: hazeUniform};
  if (rotor) {
    material.defines = {FARM_ROTOR: ''};
    Object.assign(uniforms, {uFarmTime: rotor.time, uRotorHub: {value: rotor.hub.clone()},
      uRotorTilt: {value: THREE.MathUtils.degToRad(rotor.tilt)}, uFarmPixel: pixelUniform});
  }
  material.userData.horizonUniforms = uniforms;
  material.onBeforeCompile = function compileHorizon(shader) {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = VERTEX_HEADER + shader.vertexShader
      .replace('#include <beginnormal_vertex>', VERTEX_NORMAL)
      .replace('#include <begin_vertex>', VERTEX_BEGIN);
    shader.fragmentShader = FRAGMENT_HEADER + shader.fragmentShader
      .replace('#include <tonemapping_fragment>', FRAGMENT_HAZE);
  };
  material.customProgramCacheKey = function horizonProgramKey() {
    return rotor ? 'horizon-rotor-v3' : 'horizon-v3';
  };
  return material;
}

/** Prepares a mesh for the horizon: never culled (it moves in the shader), no shadows, haze synced. */
export function horizonMesh(mesh) {
  mesh.frustumCulled = false;
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.onBeforeRender = syncHaze;
  mesh.userData.observationIgnore = true;
  return mesh;
}

function instanced(geometry, material, list) {
  const rotor = new Float32Array(list.length * 2);
  const matrix = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const one = new THREE.Vector3(1, 1, 1);
  const mesh = new THREE.InstancedMesh(geometry, material, list.length);
  list.forEach(function place(turbine, i) {
    q.setFromAxisAngle(up, turbine.yaw);
    matrix.compose(new THREE.Vector3(turbine.x, 0, turbine.z), q, one);
    mesh.setMatrixAt(i, matrix);
    rotor[i * 2] = turbine.phase;
    rotor[i * 2 + 1] = turbine.omega;
  });
  geometry.setAttribute('aRotor', new THREE.InstancedBufferAttribute(rotor, 2));
  mesh.instanceMatrix.needsUpdate = true;
  return horizonMesh(mesh);
}

/**
 * Builds a farm into `group` around `centre`. detail 'low' draws every turbine with the simple model.
 * time: a {value} uniform with the scene time in seconds. Returns {turbines, substation, centre}.
 */
export function buildWindFarm(group, centre, plan, random, {detail = 'medium', time}) {
  const type = TURBINE_TYPES[plan.type];
  const layout = farmLayout(plan, random);
  const world = layout.turbines.map((t) => ({...t, x: t.x + centre.x, z: t.z + centre.z}));
  const nearRange = detail === 'low' ? -1 : NEAR_LOD_RANGE;
  const near = world.filter((t) => Math.hypot(t.x - centre.x, t.z - centre.z) < nearRange);
  const far = world.filter((t) => Math.hypot(t.x - centre.x, t.z - centre.z) >= nearRange);
  const meshes = [];
  for (const [list, detailed] of [[near, true], [far, false]]) {
    if (!list.length) continue;
    const geometry = turbineGeometry(type, detailed);
    const material = horizonMaterial({time, hub: geometry.userData.hub, tilt: type.tilt});
    const mesh = instanced(geometry, material, list);
    mesh.name = detailed ? 'wind-farm-near' : 'wind-farm-far';
    group.add(mesh);
    meshes.push(mesh);
  }
  let substation = null;
  if (layout.substation) {
    const s = layout.substation;
    const mesh = horizonMesh(new THREE.Mesh(substationGeometry(), horizonMaterial()));
    mesh.name = 'wind-farm-substation';
    mesh.position.set(s.x + centre.x, 0, s.z + centre.z);
    mesh.rotation.y = s.yaw;
    group.add(mesh);
    substation = mesh;
  }
  const middle = world.reduce((sum, t) => sum.add(new THREE.Vector3(t.x, 0, t.z)), new THREE.Vector3())
    .divideScalar(Math.max(1, world.length));
  const facing = Math.atan2(Math.cos(plan.windAngle), Math.sin(plan.windAngle));
  return {turbines: world, meshes, substation, centre: middle, type, facing};
}

/**
 * The turbine on top of a site's own foundation (no foundation of its own), standing at `top` metres.
 * turbine: {x, z, yaw, phase, omega} in world metres.
 */
export function siteTurbineMesh(typeName, top, turbine, time) {
  const type = {...TURBINE_TYPES[typeName], tpTop: top};
  const geometry = turbineGeometry(type, true, {foundation: false});
  const material = horizonMaterial({time, hub: geometry.userData.hub, tilt: type.tilt});
  const mesh = instanced(geometry, material, [turbine]);
  mesh.name = 'site-turbine';
  return mesh;
}

// Part builders and paint for other horizon props (site_topside.js): vertex-coloured, merged by the caller.
export const FARM_COLOURS = COLOURS;
export const farmParts = Object.freeze({tube, box, member, railing, squareRailing, paint});
