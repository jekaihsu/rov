// Local metre-scale shapes for the survey subjects in qysim/inspection_finds.py.
// Lit MeshStandard materials, soft vertex colour variation, and enough segments that a close lamp
// reads shell ridges, rope lay and rust flake edges instead of grey low-poly slabs.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

export const FIND_COLORS = {
  grate_fish: 0x9caaa0,
  barnacle: 0xb9b29a,
  scuff: 0x714538,
  shackle: 0x6a5b4a,
  feed: 0x846944,
  anemone_clump: 0xb45d52,
  rope_coil: 0x8a7348,
  shell_bed: 0xc2b39a,
  rust_panel: 0x7a4a32,
};

export const FIND_MATERIAL = {
  grate_fish: {roughness: .55, metalness: .05},
  barnacle: {roughness: .92, metalness: .02},
  scuff: {roughness: .78, metalness: .18},
  shackle: {roughness: .55, metalness: .55},
  feed: {roughness: .95, metalness: 0},
  anemone_clump: {roughness: .7, metalness: 0},
  rope_coil: {roughness: .88, metalness: 0},
  shell_bed: {roughness: .86, metalness: .04},
  rust_panel: {roughness: .82, metalness: .22},
};

function tintGeometry(geometry, base, spread = .12) {
  const count = geometry.attributes.position.count;
  const colors = new Float32Array(count * 3);
  const color = new THREE.Color(base);
  for (let i = 0; i < count; i++) {
    const shade = 1 - spread * ((i * 0.17) % 1);
    colors[i * 3] = color.r * shade;
    colors[i * 3 + 1] = color.g * shade;
    colors[i * 3 + 2] = color.b * shade;
  }
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  return geometry;
}

export function findGeometry(kind) {
  const parts = [];
  if (kind === 'grate_fish') {
    const body = new THREE.SphereGeometry(1, 12, 8);
    body.scale(.009, .042, .13);
    const tail = new THREE.ConeGeometry(.048, .083, 4);
    tail.rotateX(Math.PI / 2);
    tail.scale(.15, 1, 1);
    tail.translate(0, 0, -.14);
    return tintGeometry(mergeGeometries([body, tail]), FIND_COLORS.grate_fish, .08);
  }
  if (kind === 'shackle') {
    const bow = new THREE.TorusGeometry(.28, .045, 10, 28, Math.PI * 1.65);
    bow.rotateX(-1.32);
    bow.scale(1, 1, 1.4);
    bow.translate(0, .08, 0);
    const pin = new THREE.CylinderGeometry(.035, .035, .42, 10);
    pin.rotateZ(Math.PI / 2);
    pin.translate(0, .08, .05);
    return tintGeometry(mergeGeometries([bow, pin]), FIND_COLORS.shackle, .1);
  }
  if (kind === 'anemone_clump') {
    for (let i = 0; i < 14; i++) {
      const theta = i * 2.39996;
      const r = .12 * Math.sqrt((i + .5) / 14);
      const stem = new THREE.CylinderGeometry(.018, .028, .16 + .08 * Math.sin(i), 8);
      stem.translate(r * Math.cos(theta), .1, r * Math.sin(theta));
      const crown = new THREE.SphereGeometry(.055 + .02 * Math.sin(i * 1.7), 10, 8);
      crown.scale(1, .55, 1);
      crown.translate(r * Math.cos(theta), .2 + .04 * Math.sin(i), r * Math.sin(theta));
      parts.push(stem.index ? stem.toNonIndexed() : stem);
      parts.push(crown.index ? crown.toNonIndexed() : crown);
    }
    return tintGeometry(mergeGeometries(parts), FIND_COLORS.anemone_clump, .16);
  }
  if (kind === 'rope_coil') {
    for (let turn = 0; turn < 5; turn++) {
      const torus = new THREE.TorusGeometry(.16 + turn * .05, .028, 8, 24);
      torus.rotateX(Math.PI / 2);
      torus.translate(0, .03 * turn, 0);
      parts.push(torus.index ? torus.toNonIndexed() : torus);
    }
    const bitter = new THREE.CylinderGeometry(.025, .025, .35, 8);
    bitter.rotateZ(.9);
    bitter.translate(.22, .08, .05);
    parts.push(bitter.index ? bitter.toNonIndexed() : bitter);
    return tintGeometry(mergeGeometries(parts), FIND_COLORS.rope_coil, .1);
  }
  if (kind === 'shell_bed') {
    for (let i = 0; i < 18; i++) {
      const theta = i * 2.39996;
      const r = .42 * Math.sqrt((i + .5) / 18);
      const shell = new THREE.SphereGeometry(.05 + .03 * Math.sin(i), 10, 6);
      shell.scale(1, .28, .7);
      shell.rotateY(theta);
      shell.translate(r * Math.cos(theta), .02, r * Math.sin(theta));
      parts.push(shell.index ? shell.toNonIndexed() : shell);
    }
    return tintGeometry(mergeGeometries(parts), FIND_COLORS.shell_bed, .14);
  }
  if (kind === 'rust_panel') {
    const plate = new THREE.BoxGeometry(1.1, .04, .55, 1, 1, 1);
    plate.translate(0, .02, 0);
    const flake = new THREE.BoxGeometry(.35, .03, .22);
    flake.rotateZ(.35);
    flake.translate(.25, .05, .08);
    return tintGeometry(mergeGeometries([plate, flake]), FIND_COLORS.rust_panel, .18);
  }
  const count = kind === 'feed' ? 100 : 58;
  for (let i = 0; i < count; i++) {
    const theta = i * 2.39996;
    const r = Math.sqrt((i + .5) / count);
    const a = r * Math.cos(theta);
    const b = r * Math.sin(theta);
    let part;
    if (kind === 'barnacle') {
      const size = .023 + .032 * (.5 + .5 * Math.sin(16 * i));
      const profile = [[1, 0], [.7, .7], [.42, .92], [.23, .3]];
      part = new THREE.LatheGeometry(profile.map(([x, y]) => new THREE.Vector2(x * size, y * size)), 8);
      part.rotateZ(-Math.PI / 2);
      part.translate(0, b * .24 + .08 * Math.sin(a * 6), a * 1.6);
    } else if (kind === 'feed') {
      part = new THREE.DodecahedronGeometry(.042 + .01 * Math.cos(i));
      part.translate(a * .53, .13 * (1 - r), b * .41);
    } else {
      part = new THREE.CircleGeometry(1, 6);
      part.rotateX(Math.PI / 2);
      part.scale(.008 + .022 * (1 - r), 1, .12 + .22 * (1 - r));
      part.translate(b * .23 + a * .12, -.002 * Math.sin(i), a * 1.4);
    }
    parts.push(part.index ? part.toNonIndexed() : part);
  }
  return tintGeometry(mergeGeometries(parts), FIND_COLORS[kind] || 0x888888, .12);
}

// A holdfast on a rope or net supports several broad blades. Each one twists around its midrib.
export function attachedKelp() {
  const positions = [];
  const indices = [];
  for (let blade = 0; blade < 9; blade++) {
    const angle = blade * 2.39996;
    const length = .52 + .4 * (.5 + .5 * Math.sin(blade * 1.7));
    const base = positions.length / 3;
    for (let step = 0; step <= 10; step++) {
      const t = step / 10;
      const curl = angle + .75 * t;
      const reach = (.2 + .4 * length) * t;
      const width = (.035 + .09 * Math.sin(Math.PI * t)) * (1 - .94 * t ** 7);
      for (const side of [-1, 0, 1]) {
        const wave = side * width * (1 + .18 * Math.sin(15 * t + blade));
        positions.push(reach * Math.cos(curl) - wave * Math.sin(curl),
          length * t * (1 - .36 * t) + (side === 0 ? width * .28 : 0),
          reach * Math.sin(curl) + wave * Math.cos(curl));
      }
      if (!step) continue;
      for (let j = 0; j < 2; j++) {
        const i = base + step * 3 + j;
        indices.push(i - 3, i, i - 2, i, i + 1, i - 2);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

export function findMaterial(kind, uniforms) {
  const tone = FIND_COLORS[kind] || 0x888888;
  const opts = FIND_MATERIAL[kind] || {roughness: .9, metalness: .05};
  return new THREE.MeshStandardMaterial({
    color: tone,
    vertexColors: true,
    roughness: opts.roughness,
    metalness: opts.metalness,
  });
}
