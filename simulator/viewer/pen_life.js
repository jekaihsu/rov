// Farmed fish for the net pen: the loose circling school layout used instead of the generic tight ball, and the
// mortality lying on the bottom net: the farmed species of fish_kit.js on its side (an original low-poly salmonid
// with countershaded vertex colours until the model has loaded, or where it cannot be).
// Viewer only: school centres, counts and the work objects' positions stay the server's.
import * as THREE from 'three';
import {FARMED_SPECIES, kitDetail, loadKitSpecies} from './fish_kit.js';

// Half height / half width of the body along its length (nose +Z), base length 0.30 m like the generic fish.
const RINGS = [
  [0.135, 0.013, 0.008], [0.105, 0.024, 0.014], [0.06, 0.031, 0.018], [0.01, 0.033, 0.0185],
  [-0.04, 0.028, 0.015], [-0.08, 0.018, 0.009], [-0.108, 0.009, 0.004],
];
const NOSE_Z = 0.15;
// Around each ring: back, upper flanks, lower flanks, belly.
const AROUND = [90, 150, 210, 270, 330, 30].map((deg) => deg * Math.PI / 180);
const LIVE = {back: [0.13, 0.17, 0.17], upper: [0.42, 0.47, 0.47], lower: [0.72, 0.74, 0.72],
  belly: [0.86, 0.86, 0.82], fin: [0.2, 0.22, 0.22]};
const DEAD = {back: [0.3, 0.33, 0.31], upper: [0.47, 0.48, 0.44], lower: [0.6, 0.59, 0.54],
  belly: [0.7, 0.68, 0.62], fin: [0.36, 0.36, 0.32]};
const PEN_CENTRE = new THREE.Vector3(0, 0, 24);
const MORT_SCALE = 2.2;
const MORT_HALF_WIDTH = 0.016 * MORT_SCALE;
// A 0.8 kg mort (the server's mass) is a red sea bream of about 0.35 m. A dead fish lies on its side, bent a little
// along its back (the curve is horizontal once it lies on its side), and has lost its colour: pale and grey.
const MORT_LENGTH = 0.35;
const MORT_BEND = 0.4;
const MORT_TINT = 0xc8c4bc;

function ringColour(palette, index) {
  if (index === 0) return palette.back;
  if (index === 3) return palette.belly;
  return index === 1 || index === 5 ? palette.upper : palette.lower;
}

function pushFin(positions, colours, indices, points, colour) {
  // A flat fin in the body's mid plane, drawn on both sides.
  const base = positions.length / 3;
  for (const point of points) {
    positions.push(0, point[0], point[1]);
    colours.push(...colour);
  }
  for (let i = 1; i < points.length - 1; i++) {
    indices.push(base, base + i, base + i + 1, base, base + i + 1, base + i);
  }
}

/** Salmonid body with forked tail, dorsal, adipose and anal fins; about 110 triangles. `bend` curves a carcass. */
export function salmonGeometry(palette = LIVE, bend = 0) {
  const positions = [0, 0, NOSE_Z];
  const colours = [...palette.upper];
  const indices = [];
  for (const [z, halfHeight, halfWidth] of RINGS) {
    AROUND.forEach((angle, k) => {
      // The belly is fuller than the back: lower the widest point a little.
      positions.push(Math.cos(angle) * halfWidth, Math.sin(angle) * halfHeight - 0.15 * halfHeight, z);
      colours.push(...ringColour(palette, k));
    });
  }
  for (let k = 0; k < 6; k++) indices.push(0, 1 + k, 1 + (k + 1) % 6);
  for (let ring = 0; ring < RINGS.length - 1; ring++) {
    for (let k = 0; k < 6; k++) {
      const a = 1 + ring * 6 + k;
      const b = 1 + ring * 6 + (k + 1) % 6;
      indices.push(a, a + 6, b, b, a + 6, b + 6);
    }
  }
  pushFin(positions, colours, indices, [[0.008, -0.106], [0.04, -0.158], [0, -0.136], [-0.04, -0.158],
    [-0.01, -0.106]], palette.fin);
  pushFin(positions, colours, indices, [[0.025, 0.02], [0.052, -0.005], [0.024, -0.03]], palette.fin);
  pushFin(positions, colours, indices, [[0.014, -0.07], [0.024, -0.085], [0.011, -0.088]], palette.fin);
  pushFin(positions, colours, indices, [[-0.026, -0.045], [-0.045, -0.066], [-0.018, -0.082]], palette.fin);
  if (bend) {
    // Curved in the dorso-ventral plane, which is the horizontal plane once the carcass lies on its side.
    for (let i = 0; i < positions.length; i += 3) positions[i + 1] += bend * positions[i + 2] * positions[i + 2];
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

/** Slightly different silver per school, so the ring of fish is not one flat colour. */
export function salmonMaterial(variant = 0) {
  const tint = [0xffffff, 0xf2f4ea, 0xe9eef2][variant % 3];
  return new THREE.MeshStandardMaterial({color: tint, vertexColors: true, metalness: .3, roughness: .42});
}

/**
 * One fish's place in a pen school: along the swimming circle (m of arc), across it and vertically. Farmed
 * salmon circle the pen as a long loose band rather than a ball.
 */
export function penFishOffset(random) {
  return new THREE.Vector3((random() - .5) * 5, (random() - .5) * 2.6, (random() - .5) * 13);
}

const radial = new THREE.Vector3();

/**
 * Position and heading of a pen fish at time t: the school centre swept along its circle round the pen by the
 * fish's arc offset, heading along the tangent. `turn` is +1 or -1 (which way the school circles).
 */
export function placePenFish(school, fish, t, turn, position, euler) {
  radial.copy(school.pos).sub(PEN_CENTRE);
  radial.y = 0;
  const radius = Math.max(4, radial.length() + fish.offset.x);
  const angle = Math.atan2(radial.x, radial.z) + turn * fish.offset.z / radius;
  const weave = Math.sin(t * .9 + fish.phase);
  position.set(PEN_CENTRE.x + Math.sin(angle) * (radius + weave * .25),
    school.pos.y + fish.offset.y + Math.sin(t * .6 + fish.phase * 1.7) * .15,
    PEN_CENTRE.z + Math.cos(angle) * (radius + weave * .25));
  const heading = angle + turn * Math.PI / 2;
  euler.set(0, heading + Math.sin(t * 5 + fish.phase) * .06, Math.sin(t * 4 + fish.phase) * .03);
}

/** Which way a pen school circles, from the server velocity; counter-clockwise (the server's sense) when still. */
export function penTurn(school) {
  radial.copy(school.pos).sub(PEN_CENTRE);
  const tangential = radial.z * school.vel.x - radial.x * school.vel.z;
  return Math.abs(tangential) < 1e-4 ? -1 : Math.sign(tangential);
}

function hashAngle(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296 * Math.PI * 2;
}

function layMort(geometry, object, bend) {
  // Curved in the dorso-ventral plane, which is the horizontal plane once the carcass lies on its side.
  const position = geometry.attributes.position;
  for (let i = 0; i < position.count; i++) position.setY(i, position.getY(i) + bend * position.getZ(i) ** 2);
  geometry.rotateZ(Math.PI / 2);
  geometry.rotateY(hashAngle(object.id || ''));
  geometry.computeBoundingBox();
  geometry.translate(0, -(object.radius || .15) - geometry.boundingBox.min.y, 0);
  geometry.computeBoundingSphere();
  return geometry;
}

function dressKitMort(mesh, object, asset) {
  // The full model on medium and high, the distance model on low (render tier of the scene, fish_kit.js).
  const source = kitDetail() === 'low' ? asset.distance : asset.full;
  const geometry = source.clone();
  const scale = MORT_LENGTH / asset.length;
  geometry.scale(scale, scale, scale);
  mesh.geometry.dispose();
  mesh.geometry = layMort(geometry, object, MORT_BEND);
  const map = asset.map.clone();
  mesh.material.map = map;
  mesh.material.addEventListener('dispose', function releaseMap() {
    map.dispose();
  });
  mesh.material.vertexColors = false;
  mesh.material.color.set(MORT_TINT);
  mesh.material.alphaTest = .5;
  mesh.material.side = THREE.DoubleSide;
  mesh.material.metalness = .05;
  mesh.material.roughness = .65;
  mesh.material.needsUpdate = true;
  mesh.userData.mortSpecies = asset.id;
}

/**
 * Turn a work-object mesh into a dead fish lying on its side at the bottom of its collision sphere: the procedural
 * salmonid at once, the farmed species' model once it has loaded. Resolves true once the model is in place.
 */
export function dressMort(mesh, object) {
  mesh.geometry.dispose();
  const geometry = salmonGeometry(DEAD, 1.1);
  geometry.scale(MORT_SCALE, MORT_SCALE, MORT_SCALE);
  geometry.rotateZ(Math.PI / 2);
  geometry.rotateY(hashAngle(object.id || ''));
  geometry.translate(0, MORT_HALF_WIDTH - (object.radius || .15), 0);
  mesh.geometry = geometry;
  mesh.material.color.set(0xffffff);
  mesh.material.vertexColors = true;
  mesh.material.metalness = .1;
  mesh.material.roughness = .6;
  mesh.material.needsUpdate = true;
  mesh.userData.mort = true;
  return loadKitSpecies(FARMED_SPECIES).then(function swapMort(asset) {
    dressKitMort(mesh, object, asset);
    return true;
  }, () => false);
}
