// Harbor construction and attached marine colonies, dimensioned from the collision obstacles.
import * as THREE from 'three';

import {prop} from './harbor_props.js';

function colony(set, ob, seeded) {
  const rng = seeded(ob.name);
  const top = Math.max(-.35, ob.p0[2] + .18);
  const phase = rng() * Math.PI * 2;
  for (let depth = top; depth < ob.p1[2] - .2; depth += (.5 + rng()) * (depth > 7 ? 1.8 : .75)) {
    const angle = phase + depth * 2.4 + rng() * 1.8;
    const size = [30, 60, 100][Math.floor(rng() * 3)];
    const kind = depth < 1.45 ? 'barnacles' : depth < 4.6 ? 'mussels' : 'filaments';
    const species = depth > 7 ? ['barnacles', 'mussels', 'filaments'][Math.floor(rng() * 3)] : kind;
    const name = species === 'filaments' ? 'filaments-ascidians' : species + '-' + size;
    const at = new THREE.Vector3(-ob.p0[1] + ob.radius * Math.sin(angle), -depth,
      ob.p0[0] + ob.radius * Math.cos(angle));
    prop(set, name, at, {radius: ob.radius, obstacles: [ob],
      rotation: new THREE.Quaternion().setFromAxisAngle(UP, angle)});
  }
}

const UP = new THREE.Vector3(0, 1, 0);
// The shared unwrap spans depths -2 to 18 m. Geometry UVs select each shaft's actual interval.
function pileSkin(set) {
  if (typeof document === 'undefined') return set.makeMaterial('pileConcrete');
  const loader = new THREE.TextureLoader();
  const load = suffix => loader.load(new URL('./models/harbor/pile-' + suffix + '.jpg', import.meta.url).href);
  const map = load('color');
  map.colorSpace = THREE.SRGBColorSpace;
  const normalMap = load('normal');
  const orm = load('orm');
  const displacementMap = load('height');
  for (const texture of [map, orm, normalMap, displacementMap]) texture.wrapS = THREE.RepeatWrapping;
  const material = new THREE.MeshStandardMaterial({map, normalMap, roughnessMap: orm,
    aoMap: orm, metalness: 0, displacementMap, displacementScale: .055});
  // Scale only radial relief. The instance stretches vertically to the full pile length.
  material.onBeforeCompile = shader => {
    shader.vertexShader = shader.vertexShader.replace('#include <displacementmap_vertex>',
      'if (abs(objectNormal.y) < .5) {\n#include <displacementmap_vertex>\n}');
  };
  material.userData.structureKind = 'pileConcrete';
  material.addEventListener('dispose', function releaseSkin() {
    map.dispose();
    normalMap.dispose();
    displacementMap.dispose();
    orm.dispose();
  });
  return material;
}

function pileRow(set, piles, seeded, material) {
  const geometry = new THREE.CylinderGeometry(1, 1, 1, set.detailName === 'high' ? 32 : 18, set.detailName === 'high' ? 36 : 9);
  const uv = geometry.attributes.uv;
  const top = piles[0].p0[2];
  const bottom = piles[0].p1[2];
  for (let i = 0; i < uv.count; i++) {
    const depth = bottom + (top - bottom) * uv.getY(i);
    uv.setX(i, uv.getX(i) * Math.max(1, Math.round(piles[0].radius / .15)));
    uv.setY(i, (18 - depth) / 20);
  }
  const mesh = new THREE.InstancedMesh(geometry, material, piles.length);
  mesh.userData = {paintable: true, role: 'solid', colliders: piles.map(ob => ob.name)};
  const item = new THREE.Object3D();
  for (const [i, ob] of piles.entries()) {
    const height = ob.p1[2] - ob.p0[2];
    item.position.set(-ob.p0[1], -ob.p0[2] - height / 2, ob.p0[0]);
    item.scale.set(ob.radius, height, ob.radius);
    item.rotation.y = seeded(ob.name)() * Math.PI * 2;
    item.updateMatrix();
    mesh.setMatrixAt(i, item.matrix);
    set.anchor(ob, mesh);
    if (ob.p0[2] > 0) {
      // The cut-off dolphins end underwater. Their capsule crown is exposed to the hull and tether.
      const crown = new THREE.SphereGeometry(ob.radius, 12, 5, 0, Math.PI * 2, 0, Math.PI / 2);
      crown.translate(-ob.p0[1], -ob.p0[2], ob.p0[0]);
      set.addBatched('pile-crowns', crown, 'pileConcrete', [ob.name], 'solid', [ob]);
    }
    colony(set, ob, seeded);
  }
  set.group.add(mesh);
}
export function harborStructures(set, obstacles, consumed, seeded, boxAt) {
  if (set.world.scenario?.key !== 'harbor_inspection') return;
  const makeMaterial = set.makeMaterial;
  set.makeMaterial = function harborMaterial(kind) {
    if (kind === 'fenderMarker' || kind === 'quayRunoff') {
      const color = kind === 'fenderMarker' ? 0xc6a34c : 0x924a27;
      const paint = new THREE.MeshStandardMaterial({color, roughness: .93});
      paint.userData.structureKind = kind;
      return paint;
    }
    const material = makeMaterial(kind);
    if (kind === 'rubber' && !material.map) material.color.setHex(0x353732);
    return material;
  };
  if (!obstacles.some(ob => ob.kind === 'quay')) return;
  const tread = obstacles.filter(ob => ob.kind === 'tyre_tread');
  if (tread.length) {
    harborTyre(set, tread);
    for (const ob of tread) consumed.add(ob.name);
  }
  const parted = obstacles.find(ob => ob.name === 'Hawser tail 0');
  if (parted) {
    // The far end of the tail disappears inside the inner pile. Show the parted lay on the exposed end.
    along(set, 'parted-hawser', parted, .74, 1, true);
    consumed.add(parted.name);
  }
  const debris = obstacles.find(ob => ob.name === 'Harbor mooring block');
  if (debris) {
    const point = new THREE.Vector3(-debris.point[1], -debris.point[2], debris.point[0]);
    prop(set, 'crab-pot', point, {scale: new THREE.Vector3(1, .65, 1), obstacles: [debris]});
    consumed.add(debris.name);
  }
  const piles = obstacles.filter(ob => ob.kind === 'pile');
  const rows = new Map();
  for (const ob of piles) {
    const key = [ob.p0[2], ob.p1[2], ob.radius].join();
    if (!rows.has(key)) rows.set(key, []);
    rows.get(key).push(ob);
    consumed.add(ob.name);
  }
  if (rows.size) {
    const skin = pileSkin(set);
    for (const row of rows.values()) pileRow(set, row, seeded, skin);
  }
  const solids = [];
  const metal = [];
  const roof = [];
  function block(parts, x, y, z, w, h, d) {
    parts.push(boxAt(new THREE.Vector3(x, y, z), new THREE.Vector3(w, h, d), 0));
  }
  function girder(a, b, width, depth) {
    const start = new THREE.Vector3(...a);
    const end = new THREE.Vector3(...b);
    const delta = end.clone().sub(start);
    const shape = new THREE.BoxGeometry(width, delta.length(), depth);
    shape.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize()));
    const c = start.lerp(end, .5);
    metal.push(shape.translate(c.x, c.y, c.z));
  }
  const face = [];
  for (const fender of obstacles.filter(ob => ob.kind === 'fender')) {
    const [north, east] = fender.p0;
    // Narrow ochre wear indicators sit proud of the black rubber on its seaward arc.
    for (const y of [-.52, -.72]) {
      const stripe = new THREE.CylinderGeometry(fender.radius + .018, fender.radius + .018,
        .085, 12, 1, true, Math.PI * .72, Math.PI * .56);
      stripe.translate(-east, y, north);
      set.addBatched('rub-face', stripe, 'fenderMarker', [fender.name], 'attached', []);
    }
    for (const y of [-1.25, .7]) {
      const band = new THREE.CylinderGeometry(fender.radius + .012, fender.radius + .012, .09, 16, 1, true);
      band.translate(-east, y, north);
      set.addBatched('fender-straps', band, 'steelPlate', [fender.name], 'attached', []);
    }
  }
  const stain = [];
  const joint = [];
  for (let y = -17; y <= 2; y += 2.5) {
    block(joint, 0, y, 41.985, 70, .045, .026);
    for (let x = -33 + (Math.round(y * 2) % 2) * 1.6; x < 35; x += 4) {
      block(joint, x, y + 1.25, 41.983, .041, 2.5, .032);
    }
  }
  for (let x = -28.8; x <= 31.2; x += 5) {
    const rim = new THREE.TorusGeometry(.25, .047, 5, 16);
    face.push(rim.translate(x, -.38, 41.955));
    const bore = new THREE.CircleGeometry(.24, 16);
    bore.rotateY(Math.PI);
    joint.push(bore.translate(x, -.38, 41.958));
    for (let i = 0; i < 5; i++) {
      const len = .35 + .77 * Math.abs(Math.sin(x + i));
      block(stain, x + (i - 2) * .064, -.57 - len / 2, 41.975, .065, len, .024);
    }
  }
  for (const [parts, kind] of [[face, 'steelPlate'], [joint, 'rubber'], [stain, 'quayRunoff']]) {
    for (const part of parts) set.addBatched('quay-' + kind, part, kind, ['Quay'], 'attached', []);
  }
  // Quayside wheel stops, portal crane legs, trolley rails and the machinery house.
  block(solids, 0, 1.92, 68.4, 70, .22, 13);
  for (let x = -32; x <= 32; x += 4) block(solids, x, 2.32, 43.2, 3.2, .43, .42);
  // A spare hawser in loose turns on the apron beside an existing bollard.
  for (let turn = 0; turn < 5; turn++) {
    const line = new THREE.TorusGeometry(.58 - turn * .055, .028, 5, 26);
    line.rotateX(Math.PI / 2);
    line.scale(1.45, 1, 1);
    roof.push(line.translate(-5, 2.14 + turn * .015, 44.6));
  }
  for (const x of [-24, 24]) {
    for (const side of [-3.6, 3.6]) {
      for (const z of [48, 59]) {
        girder([x + side, 2, z], [x + side * .8, 15, z], .42, .52);
      }
      girder([x + side * .8, 15, 48], [x + side * .8, 15, 59], .55, .7);
      girder([x + side * .8, 15, 48], [x + side * .8, 23, 49], .38, .4);
      girder([x + side * .8, 23, 49], [x + side * .8, 16, 36], .15, .16);
      girder([x + side * .8, 23, 49], [x + side * .8, 15, 59], .18, .18);
      girder([x + side * .8, 15, 60], [x + side * .8, 16, 32], .38, .65);
    }
    for (const z of [48, 59]) {
      girder([x - 3, 15, z], [x + 3, 15, z], .55, .6);
      girder([x - 3.4, 7.2, z], [x + 3, 15, z], .25, .28);
    }
    for (let z = 34; z < 59; z += 2) {
      girder([x - 2.85, 16, z], [x + 2.85, 16, z + 2], .12, .14);
    }
    block(roof, x + 2.6, 14.8, 45, 1.7, 1.8, 2.3);
    block(metal, x + 2.6, 14.95, 43.82, 1.45, .76, .07);
    // Trolley and twin hoist falls, with an empty spreader parked off the quay.
    const outreach = x < 0 ? 38 : 43;
    block(roof, x, 15.8, outreach, 5.9, .62, 1.7);
    for (const side of [-1.8, 1.8]) {
      girder([x + side, 15.5, outreach], [x + side, 8.2, outreach], .06, .06);
    }
    block(metal, x, 8.1, outreach, 5.4, .36, 1.35);
    block(metal, x, 16, 32, 6, .45, .5);
    block(roof, x, 16.4, 55, 7.2, 2.1, 5.6);
    block(metal, x, 23, 49, 6, .55, .55);
  }
  for (const x of [-20, 6, 24]) {
    block(solids, x, 5.2, 67, 16, 6.4, 12);
    for (const sign of [-1, 1]) {
      const panel = new THREE.BoxGeometry(8.5, .22, 12.6);
      panel.rotateZ(-sign * .13);
      roof.push(panel.translate(x + sign * 4, 8.94, 67));
    }
    for (let dx = -7; dx <= 7; dx += .7) block(metal, x + dx, 6.8, 60.96, .07, 2.6, .12);
    block(roof, x, 5.92, 60.1, 14, .16, 2.1);
    for (const dx of [-4, 4]) block(metal, x + dx, 4, 60.96, 3.2, 3.8, .15);
  }
  const skyline = seeded('inland-skyline');
  for (let x = -100; x <= 100; x += 4) {
    const h = 5 + skyline() ** 2 * 21;
    block(solids, x, h / 2, 86 + skyline() * 9, 3 + skyline() * 4, h, 5);
  }
  for (const [parts, material] of [[solids, 'concrete'], [metal, 'steelPlate'], [roof, 'ladder']]) {
    for (const part of parts) set.addBatched('yard-' + material, part, material, [], 'above', []);
  }
}

function along(set, name, ob, length, repeats, reverse = false) {
  const [a, b] = reverse ? [ob.p1, ob.p0] : [ob.p0, ob.p1];
  const start = new THREE.Vector3(-a[1], -a[2], a[0]);
  const end = new THREE.Vector3(-b[1], -b[2], b[0]);
  const direction = end.clone().sub(start);
  const scale = new THREE.Vector3(1, direction.length() / (length * repeats), 1);
  const rotation = new THREE.Quaternion().setFromUnitVectors(UP, direction.normalize());
  for (let i = 0; i < repeats; i++) {
    const asset = name === 'chain-links' && !i && ob.name.endsWith('2') ? 'shackle-chain' : name;
    prop(set, asset, start.clone().lerp(end, i / repeats), {rotation, scale, obstacles: [ob]});
  }
}

export function chainSegment(set, ob) {
  const length = new THREE.Vector3(...ob.p0).distanceTo(new THREE.Vector3(...ob.p1));
  along(set, 'chain-links', ob, .60, Math.max(1, Math.round(length / .60)));
}

function harborTyre(set, tread) {
  const centre = new THREE.Vector3();
  for (const ob of tread) centre.add(new THREE.Vector3(-ob.p0[1], -ob.p0[2], ob.p0[0]));
  prop(set, 'discarded-tyre', centre.divideScalar(tread.length), {obstacles: tread});
}
