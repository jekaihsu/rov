// Inspection fittings in the ship's local metre frame and cambered sections of its fixed-pitch screw.
import * as THREE from 'three';
import {halfBreadth} from './structure_sdf.js';

const POINT = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);

export function bladeGeometry(a, b) {
  const root = POINT(a.p0).lerp(POINT(b.p0), .5);
  const span = POINT(a.p1).sub(POINT(a.p0));
  const radial = span.clone().normalize();
  const chord = POINT(b.p0).sub(POINT(a.p0)).normalize();
  const positions = [];
  const indices = [];
  const sections = 16;
  const samples = 16;
  for (let row = 0; row <= sections; row++) {
    const t = row / sections;
    const center = root.clone().addScaledVector(radial, .3 + (span.length() - .3 + a.radius * .65) * t);
    center.addScaledVector(chord, a.radius * (.68 * t * t - .38));
    const pitch = chord.clone().applyAxisAngle(radial, .47 - .74 * t);
    const normal = radial.clone().cross(pitch);
    const width = a.radius * (.85 + 1.02 * Math.sin(Math.PI * t ** 1.45)) * (1 - .48 * t ** 8);
    for (let i = 0; i < samples; i++) {
      const angle = i * 2 * Math.PI / samples;
      const u = Math.cos(angle);
      const camber = .045 * (1 - u * u) + .032 * Math.sin(angle) * (1 - .45 * t);
      const p = center.clone().addScaledVector(pitch, width * u).addScaledVector(normal, camber);
      positions.push(...p.toArray());
      if (row === sections) continue;
      const j = row * samples + i;
      const next = row * samples + (i + 1) % samples;
      indices.push(j, next, next + samples, j, next + samples, j + samples);
    }
  }
  const end = sections * samples;
  for (let i = 1; i < samples - 1; i++) {
    indices.push(end, end + i, end + i + 1);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

// Each numeral's lower edge denotes height above keel. Short bars mark the intervening 2 dm steps.
const DIGITS = ['abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg', 'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg'];
const STROKES = {a: [0, .09], b: [.026, .07], c: [.026, .025], d: [0, .005],
  e: [-.026, .025], f: [-.026, .07], g: [0, .047]};

export function addInspectionFittings(set, ob, hp, toWorld, boxAt, merged) {
  const groups = new Map();
  const yaw = -ob.yaw_deg * Math.PI / 180;
  for (const side of [-1, 1]) {
    function plate(kind, x, depth, proud, length, height, thickness) {
      const width = halfBreadth(x, depth, hp).hb;
      const c = toWorld(x, side * (width + proud), depth);
      if (!groups.has(kind)) groups.set(kind, []);
      groups.get(kind).push(boxAt(c, new THREE.Vector3(thickness, height, length), yaw));
    }
    const x = -.0875 * hp.length;
    const z = hp.draft * .68;
    plate('intakeShadow', x, z, .012, 1.62, .76, .022);
    for (let i = -8; i <= 8; i++) plate('steelPlate', x + i * .097, z, .043, .027, .76, .042);
    for (const sign of [-1, 1]) {
      plate('steelPlate', x, z + sign * .38, .04, 1.65, .05, .044);
      const bar = x + sign * 1.55;
      plate('steelPlate', bar, z, .015, .76, .065, .028);
      plate('anode', bar, z, .046, .52, .11, .064);
    }
    for (let dm = 2; dm <= (hp.draft + .8) * 10; dm += 2) {
      const depth = hp.draft - dm / 10;
      if (depth > hp.draft - hp.bilge) continue;
      plate('draftPaint', 0, depth - .01, .008, dm % 10 ? .085 : .16, .02, .007);
      if (dm % 10) continue;
      const digits = String(dm / 10);
      for (let k = 0; k < digits.length; k++) {
        for (const segment of DIGITS[Number(digits[k])]) {
          const [dx, dy] = STROKES[segment];
          const horizontal = 'adg'.includes(segment);
          plate('draftPaint', side * (.17 + .08 * k + dx), depth - dy, .008,
            horizontal ? .06 : .012, horizontal ? .012 : .045, .007);
        }
      }
    }
  }
  for (const [kind, parts] of groups) set.add(merged(parts), kind, [ob.name], 'attached');
}
