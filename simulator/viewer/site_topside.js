// Above-water part of the inspected structure itself (presentation only): the site's jacket or monopile
// continues above the sea to a transition piece and a turbine, as real foundations in a wind farm do.
//
// The scenario (and the server's collision) stops at the leg or transition-piece tops 3 m above the sea; this
// module only adds what stands above that, matched to the scenario's leg positions, batter and radii. The
// vehicle cannot fly above the water, so parts above +0.5 m need no collider. At and below +0.5 m (down to
// SKIN_FLOOR, just under the sea) the only thing added is the splash-zone paint skin on the existing legs and
// transition piece, 0.024 m proud of their collision cylinders (the structures' own mussel lumps stand 0.05 m
// proud); fittings such as the boat landing start above +0.5 m.
//
// Each foundation has its own function (jacketTopside, monopileTopside) so a detailed model can replace one
// without touching the other. Painted steel, gratings and deck plate are separate meshes with CC0 scanned
// textures (topside_materials.js): the platforms are open steel framing under galvanised gratings, so their
// undersides show beams and daylight through the grating instead of a solid dark slab.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {FARM_COLOURS, TURBINE_TYPES, farmParts, siteTurbineMesh} from './wind_farm.js';
import {metreUv, topsideMaterial} from './topside_materials.js';

const {box, member, paint, railing, squareRailing} = farmParts;
const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);          // NED -> three

// Lowest height (m above the sea) of any fitting added here; below it only the paint skin.
export const TOPSIDE_FLOOR = 0.5;
// Lowest point of the splash-zone skin, just under the sea surface so no bare steel shows at the waterline.
export const SKIN_FLOOR = -0.6;
// How far the skin and the sleeves above it stand proud of the scenario's cylinders (m).
export const SKIN_PROUD = 0.024;
const SLEEVE = 0.02;
const WEATHER = Object.freeze({
  fouling: '#34301f',
  splash: '#3a3222',
  stain: '#5b4425',
  rust: '#93552a'
});

function seeded(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Splash zone on a tube: dark fouling at the waterline fading to rust-brown staining, its upper edge ragged as
// the tide line and spray leave it. Open tube along `axis` from the point `base` (at height y0) up to height y1.
function splashZone(base, axis, radius, y0, y1, random) {
  const segments = 24;
  const length = (y1 - y0) / axis.y;
  const g = new THREE.CylinderGeometry(radius, radius, length, segments, 3, true);
  g.translate(0, length / 2, 0);
  paint(g, WEATHER.fouling);
  const position = g.attributes.position;
  const colour = g.attributes.color;
  const phase = random() * 6.28;
  const low = new THREE.Color(WEATHER.fouling);
  const high = new THREE.Color(WEATHER.stain);
  for (let i = 0; i < position.count; i++) {
    const k = position.getY(i) / length;
    const angle = Math.atan2(position.getZ(i), position.getX(i));
    if (k > 0.99) {
      const ragged = 0.35 * Math.sin(angle * 5 + phase) + 0.2 * Math.sin(angle * 11 + phase * 2);
      position.setY(i, length + ragged);
    }
    const c = low.clone().lerp(high, Math.min(1, k * 1.1));
    colour.setXYZ(i, c.r, c.g, c.b);
  }
  g.computeVertexNormals();
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis));
  g.translate(base.x, base.y, base.z);
  return g;
}

const UP = new THREE.Vector3(0, 1, 0);

// Rust streaks running down from a weld or a fitting: thin strips just proud of a tube's surface.
function rustStreaks(x, z, radius, yTop, count, random) {
  const parts = [];
  for (let i = 0; i < count; i++) {
    const angle = random() * Math.PI * 2;
    const length = 1.2 + random() * 3.5;
    const top = yTop - random() * 1.5;
    const g = box(0.12 + random() * 0.12, length, 0.02, 0, top - length / 2, radius + 0.012, WEATHER.rust);
    g.rotateY(-angle + Math.PI / 2);
    g.translate(x, 0, z);
    parts.push(g);
  }
  return parts;
}

// Tilted tube sleeve between two points (legs), painted.
function sleeve(a, b, radius, hex) {
  return member([a.x, a.y, a.z], [b.x, b.y, b.z], radius, 12, hex);
}

// Vertical ladder: two stiles and rungs every 0.3 m, from y0 to y1, its face looking along `out`.
function ladder(base, out, y0, y1, hex) {
  const side = new THREE.Vector3(-out.z, 0, out.x).multiplyScalar(0.22);
  const parts = [];
  for (const s of [-1, 1]) {
    const p = base.clone().addScaledVector(side, s);
    parts.push(member([p.x, y0, p.z], [p.x, y1, p.z], 0.03, 4, hex));
  }
  for (let y = y0 + 0.3; y < y1; y += 0.3) {
    const a = base.clone().sub(side);
    const b = base.clone().add(side);
    parts.push(member([a.x, y, a.z], [b.x, y, b.z], 0.015, 3, hex));
  }
  return parts;
}

// Stair flight from a to b (world points), a strip of treads with a hand rail on each side.
function stairFlight(a, b, width, hex) {
  const parts = [];
  const run = b.clone().sub(a);
  const across = new THREE.Vector3(-run.z, 0, run.x).normalize().multiplyScalar(width / 2);
  const steps = Math.max(2, Math.round(run.y / 0.25));
  for (let i = 0; i <= steps; i++) {
    const p = a.clone().addScaledVector(run, i / steps);
    const l = p.clone().sub(across);
    const r = p.clone().add(across);
    parts.push(member([l.x, l.y, l.z], [r.x, r.y, r.z], 0.05, 3, FARM_COLOURS.grating));
  }
  for (const s of [-1, 1]) {
    const l0 = a.clone().addScaledVector(across, s);
    const l1 = b.clone().addScaledVector(across, s);
    parts.push(member([l0.x, l0.y, l0.z], [l1.x, l1.y, l1.z], 0.06, 4, hex));
    parts.push(member([l0.x, l0.y + 1.0, l0.z], [l1.x, l1.y + 1.0, l1.z], 0.03, 4, hex));
  }
  return parts;
}

function siteMesh(parts, name, material) {
  const geometry = mergeGeometries(parts.map(metreUv), false);
  for (const part of parts) part.dispose();
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = name;
  mesh.frustumCulled = false;
  mesh.castShadow = !material.alphaTest;              // a grating's shadow would be a solid slab
  mesh.receiveShadow = true;
  mesh.userData.observationIgnore = true;
  return mesh;
}

/** Adds the painted steel, grating and plate meshes of a topside; returns the painted one. */
function addSiteMeshes(group, name, surfaces, detail) {
  let main = null;
  for (const [kind, parts] of Object.entries(surfaces)) {
    if (!parts.length) continue;
    const mesh = siteMesh(parts, kind === 'paint' ? name : `${name}-${kind}`, topsideMaterial(kind, detail));
    group.add(mesh);
    if (kind === 'paint') main = mesh;
  }
  return main;
}

// Horizontal grating panel (w across x, l across z) with its top at y, centred on (x, z).
function gratingPanel(w, l, x, y, z) {
  const g = new THREE.PlaneGeometry(w, l);
  g.rotateX(-Math.PI / 2);
  g.translate(x, y, z);
  return paint(g, FARM_COLOURS.grating);
}

// Annular grating round a tube, top at y.
function gratingRing(centre, inner, outer, y) {
  const g = new THREE.RingGeometry(inner, outer, 48, 1);
  g.rotateX(-Math.PI / 2);
  g.translate(centre.x, y, centre.z);
  return paint(g, FARM_COLOURS.grating);
}

// Steel framing under a ring platform: radial beams, an outer ring beam that also stands up as the toe plate,
// and knee brackets from the shell. The grating rests on the beams at `y`.
function ringFrame(centre, inner, outer, y, hex) {
  const parts = [];
  for (let i = 0; i < 16; i++) {
    const a = i / 16 * Math.PI * 2;
    const beam = new THREE.BoxGeometry(outer - inner, 0.3, 0.14);
    beam.translate((inner + outer) / 2, y - 0.15, 0);
    beam.rotateY(-a);
    beam.translate(centre.x, 0, centre.z);
    parts.push(paint(beam, hex));
    if (i % 2 === 0) {
      const from = [centre.x + Math.cos(a) * inner, y - 2.2, centre.z + Math.sin(a) * inner];
      const to = [centre.x + Math.cos(a) * (outer - 0.4), y - 0.3, centre.z + Math.sin(a) * (outer - 0.4)];
      parts.push(member(from, to, 0.07, 6, hex));
    }
  }
  const rim = new THREE.CylinderGeometry(outer, outer, 0.45, 48, 1, true);
  rim.translate(centre.x, y - 0.075, centre.z);
  parts.push(paint(rim, hex));
  return parts;
}

// Square deck framing: deep perimeter girders and a grid of secondary beams under the grating.
function deckFrame(half, y, hex) {
  const parts = [];
  for (const s of [-1, 1]) {
    parts.push(box(half * 2, 0.9, 0.4, 0, y + 0.45, s * (half - 0.2), hex));
    parts.push(box(0.4, 0.9, half * 2, s * (half - 0.2), y + 0.45, 0, hex));
  }
  for (let k = 1; k < 6; k++) {
    const at = -half + k * half / 3;
    parts.push(box(half * 2 - 0.8, 0.55, 0.22, 0, y + 0.6, at, hex));
    parts.push(box(0.22, 0.55, half * 2 - 0.8, at, y + 0.6, 0, hex));
  }
  return parts;
}

// Jacket ---------------------------------------------------------------------------------------------------

/** Jacket legs from the scenario: top (three.js, at the scenario's leg top) and the unit vector up the leg. */
export function jacketLegs(world) {
  return (world?.obstacles || []).filter((ob) => ob.kind === 'jacket_leg').map(function leg(ob) {
    const a = P(ob.p0);
    const b = P(ob.p1);
    const top = a.y > b.y ? a : b;
    const bottom = a.y > b.y ? b : a;
    return {top, up: top.clone().sub(bottom).normalize(), radius: ob.radius};
  });
}

function onLeg(leg, y) {
  return leg.top.clone().addScaledVector(leg.up, (y - leg.top.y) / leg.up.y);
}

/**
 * The jacket above its scenario leg tops: legs on the same batter up to a square deck with railings, braces,
 * a boat landing with a ladder and a stair to the deck, a short transition piece. Returns the deck's top.
 */
export function jacketTopside(group, legs, random, detail = 'medium') {
  const type = TURBINE_TYPES.jacket;
  const deckY = type.tpTop - 3;
  const yellow = FARM_COLOURS.yellow;
  const parts = [];
  const centre = legs.reduce((sum, leg) => sum.add(leg.top), new THREE.Vector3()).divideScalar(legs.length);
  centre.y = 0;
  // Order the legs round the centre so braces join neighbours.
  legs.sort((a, b) => Math.atan2(a.top.z - centre.z, a.top.x - centre.x) -
    Math.atan2(b.top.z - centre.z, b.top.x - centre.x));
  for (const leg of legs) {
    const r = leg.radius + SLEEVE;
    parts.push(splashZone(onLeg(leg, SKIN_FLOOR), leg.up, leg.radius + SKIN_PROUD, SKIN_FLOOR, 2.4, random));
    parts.push(sleeve(onLeg(leg, 2.3), onLeg(leg, deckY), r, yellow));
    const node = onLeg(leg, deckY - 1.6);
    parts.push(...rustStreaks(node.x, node.z, r, deckY - 1.2, 3, random));
  }
  for (let i = 0; i < legs.length; i++) {
    const a = legs[i];
    const b = legs[(i + 1) % legs.length];
    parts.push(sleeve(onLeg(a, 3.4), onLeg(b, 3.4), 0.32, yellow));
    parts.push(sleeve(onLeg(a, deckY - 1.6), onLeg(b, deckY - 1.6), 0.32, yellow));
    parts.push(sleeve(onLeg(a, 3.4), onLeg(b, deckY - 1.6), 0.28, yellow));
    parts.push(sleeve(onLeg(b, 3.4), onLeg(a, deckY - 1.6), 0.28, yellow));
  }
  // Deck: overhanging square platform framed in girders, galvanised grating, railing; a container-sized store
  // on a diamond-plate laydown area.
  const reach = Math.max(...legs.map((leg) => Math.hypot(onLeg(leg, deckY).x - centre.x, onLeg(leg, deckY).z -
    centre.z)));
  const half = reach / Math.SQRT2 + 2.6;
  const deck = [...deckFrame(half, deckY, yellow),
    ...squareRailing(half - 0.05, deckY + 0.9, true, yellow),
    box(2.4, 2.6, 6.0, half - 2.0, deckY + 2.2, 0, FARM_COLOURS.topside)];
  const grating = [gratingPanel(half * 2 - 0.3, half * 2 - 0.3, 0, deckY + 0.9, 0)];
  const plate = [box(4.2, 0.03, 8.0, half - 2.4, deckY + 0.93, 0, FARM_COLOURS.grating)];
  // Transition piece up to the tower flange, closed underneath (seen through the grating).
  const tp = new THREE.CylinderGeometry(type.tpDiameter / 2, type.tpDiameter / 2 + 0.2, type.tpTop - deckY - 0.9,
    24, 1, true);
  tp.translate(0, (deckY + 0.9 + type.tpTop) / 2, 0);
  deck.push(paint(tp, yellow));
  const tpFloor = new THREE.CircleGeometry(type.tpDiameter / 2 + 0.2, 24);
  tpFloor.rotateX(Math.PI / 2);
  tpFloor.translate(0, deckY + 0.88, 0);
  deck.push(paint(tpFloor, yellow));
  for (const g of [...deck, ...grating, ...plate]) g.translate(centre.x, 0, centre.z);
  parts.push(...deck);
  parts.push(...rustStreaks(centre.x, centre.z, type.tpDiameter / 2 + 0.2, type.tpTop - 0.4, 4, random));
  // Boat landing on the first leg's outer face: fender tubes and a ladder up to a rest platform, a stair to
  // the deck.
  const leg = legs[0];
  const out = onLeg(leg, 3).sub(centre).setY(0).normalize();
  const foot = onLeg(leg, 3).addScaledVector(out, leg.radius + 1.1);
  const side = new THREE.Vector3(-out.z, 0, out.x);
  for (const s of [-0.7, 0.7]) {
    const p = foot.clone().addScaledVector(side, s);
    parts.push(member([p.x, 0.6, p.z], [p.x, 7.2, p.z], 0.2, 8, yellow));
    parts.push(splashZone(new THREE.Vector3(p.x, 0.6, p.z), UP, 0.205, 0.6, 1.8, random));
  }
  parts.push(...ladder(foot.clone().addScaledVector(out, -0.35), out, 0.8, 7.0, yellow));
  // Rest platform at the ladder head, then a stair along the outside of one deck edge (the deck is square to
  // the axes, like the scenario's legs).
  const sx = Math.sign(out.x) || 1;
  const sz = Math.sign(out.z) || 1;
  const rest = new THREE.Vector3(foot.x, 7.0, (foot.z + centre.z + sz * (half + 0.7)) / 2);
  const restLength = Math.abs(rest.z - foot.z) * 2 + 2.0;
  grating.push(gratingPanel(2.4, restLength, rest.x, 7.1, rest.z));
  for (const s of [-1.15, 1.15]) parts.push(box(0.12, 0.25, restLength, rest.x + s, 6.98, rest.z, yellow));
  const start = new THREE.Vector3(centre.x + sx * (half - 1.0), 7.1, centre.z + sz * (half + 0.7));
  const end = new THREE.Vector3(start.x - sx * 9.0, deckY + 0.95, start.z);
  parts.push(...stairFlight(start, end, 0.9, yellow));
  const mesh = addSiteMeshes(group, 'site-jacket-topside', {paint: parts, grating, plate}, detail);
  return {mesh, centre, top: type.tpTop};
}

// Monopile -------------------------------------------------------------------------------------------------

/**
 * The transition piece above the scenario's top: splash zone, yellow shell up to the tower flange, the main
 * access platform with railing and davit, a ladder from the boat landing. Returns the flange height.
 */
export function monopileTopside(group, world, random, detail = 'medium') {
  const type = TURBINE_TYPES.large;
  const obstacles = world?.obstacles || [];
  const piece = obstacles.find((ob) => ob.kind === 'transition_piece');
  const a = P(piece.p0);
  const b = P(piece.p1);
  const top = a.y > b.y ? a : b;
  const r = piece.radius + SLEEVE;
  const flange = type.tpTop;
  const yellow = FARM_COLOURS.yellow;
  const skinBase = new THREE.Vector3(top.x, SKIN_FLOOR, top.z);
  const parts = [splashZone(skinBase, UP, piece.radius + SKIN_PROUD, SKIN_FLOOR, 2.2, random)];
  const shell = new THREE.CylinderGeometry(r, r, flange - 2.1, 32, 1, true);
  shell.translate(top.x, (flange + 2.1) / 2, top.z);
  parts.push(paint(shell, yellow));
  const cap = new THREE.CylinderGeometry(r, r, 0.3, 32);
  cap.translate(top.x, flange - 0.15, top.z);
  parts.push(paint(cap, yellow));
  // Main access platform at the flange: radial beams and knee brackets under a galvanised grating ring, toe
  // plate, railing, davit crane.
  const deckTop = flange - 0.85;
  parts.push(...ringFrame(top, r, r + 2.5, deckTop, yellow));
  const grating = [gratingRing(top, r + 0.02, r + 2.48, deckTop)];
  const rails = railing(r + 2.45, flange - 0.85, 24, true, yellow);
  for (const g of rails) g.translate(top.x, 0, top.z);
  parts.push(...rails);
  parts.push(...rustStreaks(top.x, top.z, r, flange - 1.3, 6, random));
  // Boat landing: the scenario's fender tubes end 2.5 m above the sea; continue them and the ladder.
  const landings = obstacles.filter((ob) => ob.kind === 'boat_landing' && Math.abs(ob.p0[2] - ob.p1[2]) > 2);
  let out = new THREE.Vector3(1, 0, 0);
  if (landings.length) {
    const mid = landings.reduce((sum, ob) => sum.add(P(ob.p0)), new THREE.Vector3()).divideScalar(landings.length);
    out = mid.clone().sub(top).setY(0).normalize();
    for (const ob of landings) {
      const p = P(ob.p0);
      const upper = Math.max(P(ob.p0).y, P(ob.p1).y);
      parts.push(member([p.x, upper - 0.05, p.z], [p.x, 6.5, p.z], 0.2, 8, yellow));
    }
  }
  const foot = top.clone().setY(0).addScaledVector(out, r + 0.5);
  parts.push(...ladder(foot, out, 3.3, flange - 0.9, yellow));
  const davitBase = top.clone().setY(0).addScaledVector(out.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.6),
    r + 1.8);
  parts.push(member([davitBase.x, flange - 0.8, davitBase.z], [davitBase.x, flange + 4.2, davitBase.z], 0.16, 8,
    yellow));
  const jib = davitBase.clone().addScaledVector(out, 2.4);
  parts.push(member([davitBase.x, flange + 4.1, davitBase.z], [jib.x, flange + 4.6, jib.z], 0.1, 6, yellow));
  const mesh = addSiteMeshes(group, 'site-monopile-topside', {paint: parts, grating}, detail);
  return {mesh, centre: top.clone().setY(0), top: flange};
}

// Assembly -------------------------------------------------------------------------------------------------

/**
 * Builds the site's own topside and its turbine for an inside-farm plan. farm: buildWindFarm's result
 * (facing gives the rotor direction). Returns null when the site has no foundation of the planned type.
 */
export function buildSiteTopside(group, world, plan, farm, time, detail = 'medium') {
  const random = seeded(String(world?.scenario?.key || 'site').length * 7919 + 17);
  let site = null;
  if (plan.type === 'jacket') {
    const legs = jacketLegs(world);
    if (legs.length < 3) return null;
    site = jacketTopside(group, legs, random, detail);
  } else {
    if (!(world?.obstacles || []).some((ob) => ob.kind === 'transition_piece')) return null;
    site = monopileTopside(group, world, random, detail);
  }
  const type = TURBINE_TYPES[plan.type];
  const omega = type.tipSpeed * 0.9 / (type.rotor / 2);
  const turbine = {x: site.centre.x, z: site.centre.z, yaw: farm.facing + 0.03, phase: random() * 6.28, omega};
  const mesh = siteTurbineMesh(plan.type, site.top, turbine, time);
  group.add(mesh);
  return {...site, turbine: mesh};
}
