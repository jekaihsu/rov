// Local metre-scale shapes for the survey subjects in qysim/inspection_finds.py.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

export const FIND_COLORS = {grate_fish: 0x9caaa0, barnacle: 0xb9b29a, scuff: 0x714538, shackle: 0x57483d, feed: 0x846944};

export function findGeometry(kind) {
  const parts = [];
  if (kind === 'grate_fish') {
    const body = new THREE.SphereGeometry(1, 10, 6);
    body.scale(.009, .042, .13);
    const tail = new THREE.ConeGeometry(.048, .083, 3);
    tail.rotateX(Math.PI / 2);
    tail.scale(.15, 1, 1);
    tail.translate(0, 0, -.14);
    return mergeGeometries([body, tail]);
  }
  if (kind === 'shackle') {
    const bow = new THREE.TorusGeometry(.28, .045, 7, 20, Math.PI * 1.65);
    bow.rotateX(-1.32);
    bow.scale(1, 1, 1.4);
    bow.translate(0, .08, 0);
    return bow;
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
      part = new THREE.LatheGeometry(profile.map(([x, y]) => new THREE.Vector2(x * size, y * size)), 7);
      part.rotateZ(-Math.PI / 2);
      part.translate(0, b * .24 + .08 * Math.sin(a * 6), a * 1.6);
    } else if (kind === 'feed') {
      part = new THREE.DodecahedronGeometry(.042 + .01 * Math.cos(i));
      part.translate(a * .53, .13 * (1 - r), b * .41);
    } else {
      part = new THREE.CircleGeometry(1, 5);
      part.rotateX(Math.PI / 2);
      part.scale(.008 + .022 * (1 - r), 1, .12 + .22 * (1 - r));
      part.translate(b * .23 + a * .12, -.002 * Math.sin(i), a * 1.4);
    }
    parts.push(part.index ? part.toNonIndexed() : part);
  }
  return mergeGeometries(parts);
}

// A holdfast on a rope or net supports several soft, ribbon-like blades (not square patches).
export function attachedKelp() {
  const positions = [];
  const indices = [];
  for (let blade = 0; blade < 11; blade++) {
    const angle = blade * 2.39996 + 0.15 * Math.sin(blade);
    const length = .48 + .42 * (.5 + .5 * Math.sin(blade * 1.7));
    const base = positions.length / 3;
    for (let step = 0; step <= 14; step++) {
      const t = step / 14;
      const curl = angle + .55 * t + 0.2 * Math.sin(2.4 * t + blade);
      const reach = (.15 + .38 * length) * t;
      const width = (.03 + .08 * Math.sin(Math.PI * t)) * (1 - .92 * t ** 6);
      for (const side of [-1, 0, 1]) {
        const wave = side * width * (1 + .22 * Math.sin(9 * t + blade * 1.3));
        positions.push(reach * Math.cos(curl) - wave * Math.sin(curl),
          length * t * (1 - .32 * t) + (side === 0 ? width * .22 : 0),
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
