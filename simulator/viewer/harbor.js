// Harbor construction and attached marine colonies, dimensioned from the collision obstacles.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Narrow hinge, swollen umbo, paired valves and a pale growth margin along the shell lip.
function musselValve() {
  const profile = [[0, -1], [.44, -.68], [.76, -.19], [1, .43], [.88, .78], [.48, .96], [0, 1]];
  const shape = new THREE.LatheGeometry(profile.map(([r, y]) => new THREE.Vector2(r, y)), 8);
  const pos = shape.attributes.position;
  const colors = [];
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    const z = pos.getZ(i);
    const seam = Math.max(0, 1 - Math.abs(x) * 3.8);
    pos.setXYZ(i, x + .19 * y * y, y, z * (.84 - seam * .42));
    const lip = y > .75 ? .32 : 0;
    const light = .58 + Math.abs(x) * .34 + lip - seam * .20;
    colors.push(light * (1 + lip * .4), light, light * (1.14 - lip));
  }
  shape.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  shape.computeVertexNormals();
  return shape;
}

// A folded, tapering ribbon bends away from its holdfast and curls back toward the pile.
function weedBlade() {
  const vertices = [];
  const indices = [];
  for (let i = 0; i <= 5; i++) {
    const t = i / 5;
    const w = Math.sin(Math.PI * t) * .9 + .025;
    const bend = Math.sin(t * 4.3) * .65;
    vertices.push(bend - w, .5 - t, t, bend, .5 - t, t + w * .6, bend + w, .5 - t, t);
    if (i === 0) continue;
    const k = i * 3;
    indices.push(k - 3, k, k - 2, k, k + 1, k - 2, k - 2, k + 1, k - 1, k + 1, k + 2, k - 1);
  }
  const shape = new THREE.BufferGeometry();
  shape.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  shape.setIndex(indices);
  shape.computeVertexNormals();
  return shape;
}

function colony(set, ob, seeded) {
  const rng = seeded(ob.name + '-colony');
  const beds = [[], [], []];
  const height = ob.p1[2] - ob.p0[2];
  const middle = (ob.p0[2] + ob.p1[2]) / 2;
  const item = new THREE.Object3D();
  for (let patch = 0; patch < 24; patch++) {
    const randomDepth = Math.max(.1, ob.p0[2]) + rng() * (ob.p1[2] - Math.max(.1, ob.p0[2]));
    const fixed = ob.name === 'Harbor pile A' && patch < 6;
    const depth = fixed ? [1.25, 1.55, 5.8, 6.1, 6.3, 6.55][patch] : randomDepth;
    const bearing = fixed ? 2.65 + (rng() - .5) * .6 : rng() * Math.PI * 2;
    for (let j = 0; j < 5; j++) {
      const phi = bearing + (rng() - .5) * 1.5;
      const zone = depth < 2.4 ? 0 : depth < 8.4 ? 1 : 2;
      let tint;
      if (zone === 0) {
        item.scale.set(.064, .34 + rng() * .23, .032);
        tint = rng() < .5 ? 0x748132 : 0x464f1f;
      } else if (zone === 1) {
        item.scale.set(.054, .105, .047);
        tint = rng() < .4 ? 0x615575 : 0x343d4d;
      } else {
        item.scale.setScalar(.045 + rng() * .04);
        tint = rng() < .6 ? 0xd9c39c : 0xb19680;
      }
      item.position.set(ob.radius * Math.sin(phi), middle - depth + (rng() - .5) * .42, ob.radius * Math.cos(phi));
      item.rotation.set(0, phi, rng() - .5, 'YXZ');
      item.updateMatrix();
      beds[zone].push([item.matrix.clone(), new THREE.Color(tint)]);
    }
  }
  const profile = [[1, 0], [.7, .65], [.53, 1], [.28, .93], [.26, .35]];
  const shapes = [weedBlade(), musselValve(),
    new THREE.LatheGeometry(profile.map(([r, y]) => new THREE.Vector2(r, y)), 7).rotateX(Math.PI / 2)];
  const close = new THREE.Group();
  for (const [i, bed] of beds.entries()) {
    const material = new THREE.MeshStandardMaterial({roughness: i === 1 ? .48 : .85,
      vertexColors: i === 1, side: i === 0 ? THREE.DoubleSide : THREE.FrontSide});
    const relief = new THREE.InstancedMesh(shapes[i], material, bed.length);
    bed.forEach(([matrix, tint], j) => {
      relief.setMatrixAt(j, matrix);
      relief.setColorAt(j, tint);
    });
    relief.userData = {role: 'attached', colliders: [ob.name]};
    close.add(relief);
  }
  const lod = new THREE.LOD();
  lod.position.set(-ob.p0[1], -middle, ob.p0[0]);
  const reliefRange = set.detailName === 'high' ? 6 : 2.5;
  lod.addLevel(close, 0);
  lod.addLevel(new THREE.Group(), reliefRange);
  const eye = new THREE.Vector3();
  // LOD's default distance to the shaft midpoint keeps entire distant bents active near the bed.
  // Use the closest point on the vertical shaft so a camera beside either end still sees relief.
  lod.update = function inspectionRange(camera) {
    camera.getWorldPosition(eye);
    this.worldToLocal(eye);
    eye.y -= THREE.MathUtils.clamp(eye.y, -height / 2, height / 2);
    close.visible = eye.lengthSq() < (reliefRange + ob.radius) ** 2;
    this.levels[1].object.visible = !close.visible;
  };
  set.group.add(lod);
}

// The shared unwrap spans depths -2 to 18 m. Geometry UVs select each shaft's actual interval.
function pileSkin(set) {
  if (typeof document === 'undefined') return set.makeMaterial('pileConcrete');
  const loader = new THREE.TextureLoader();
  function load(suffix) {
    const url = new URL('./models/scan/harbor_growth_' + suffix + '.webp', import.meta.url);
    return loader.load(url.href, function sizePileMap(texture) {
      if (set.detailName === 'high') return;
      const canvas = document.createElement('canvas');
      canvas.width = texture.image.width / 2;
      canvas.height = texture.image.height / 2;
      canvas.getContext('2d').drawImage(texture.image, 0, 0, canvas.width, canvas.height);
      texture.image = canvas;
      texture.needsUpdate = true;
    });
  }
  const map = load('c');
  map.colorSpace = THREE.SRGBColorSpace;
  const normalMap = load('n');
  const material = new THREE.MeshStandardMaterial({map, normalMap, roughness: .84});
  material.userData.structureKind = 'pileConcrete';
  material.addEventListener('dispose', function releaseSkin() {
    map.dispose();
    normalMap.dispose();
  });
  return material;
}

function buildPiles(set, piles, seeded) {
  const radial = set.detailName === 'high' ? 24 : 12;
  const parts = [];
  for (const ob of piles) {
    const [north, east, top] = ob.p0;
    const bottom = ob.p1[2];
    const shaft = new THREE.CylinderGeometry(ob.radius, ob.radius, bottom - top, radial, 1);
    shaft.rotateY(seeded(ob.name)() * Math.PI * 2);
    shaft.translate(-east, -(top + bottom) / 2, north);
    const {uv} = shaft.attributes;
    for (let i = 0; i < uv.count; i++) {
      const depth = bottom + (top - bottom) * uv.getY(i);
      uv.setY(i, (18 - depth) / 20);
    }
    parts.push(shaft);
    if (ob.p0[2] > 0) {
      // The cut-off dolphins end underwater. Their capsule crown is exposed to the hull and tether.
      const crown = new THREE.SphereGeometry(ob.radius, 12, 5, 0, Math.PI * 2, 0, Math.PI / 2);
      crown.translate(-ob.p0[1], -ob.p0[2], ob.p0[0]);
      set.addBatched('pile-crowns', crown, 'pileConcrete', [ob.name], 'solid', [ob]);
    }
    colony(set, ob, seeded);
  }
  const mesh = new THREE.Mesh(mergeGeometries(parts), pileSkin(set));
  for (const part of parts) part.dispose();
  mesh.userData = {paintable: true, role: 'solid', colliders: piles.map(ob => ob.name)};
  for (const ob of piles) set.anchor(ob, mesh);
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
  const piles = obstacles.filter(ob => ob.kind === 'pile');
  if (piles.length) buildPiles(set, piles, seeded);
  for (const ob of piles) consumed.add(ob.name);
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

export function chainSegment(set, ob) {
  const start = new THREE.Vector3(-ob.p0[1], -ob.p0[2], ob.p0[0]);
  const end = new THREE.Vector3(-ob.p1[1], -ob.p1[2], ob.p1[0]);
  const direction = end.clone().sub(start);
  const links = Math.max(1, Math.round(direction.length() / .19));
  const step = direction.length() / links;
  const rotation = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  for (let i = 0; i < links; i++) {
    const link = new THREE.TorusGeometry(.073, .018, 4, set.detailName === 'high' ? 12 : 8);
    link.scale(1, step / .12, 1);
    link.rotateY(i % 2 * Math.PI / 2);
    link.applyQuaternion(rotation);
    const c = start.clone().lerp(end, (i + .5) / links);
    link.translate(c.x, c.y, c.z);
    set.addBatched('mooring-chain', link, 'steelPlate', [ob.name], 'solid', [ob]);
  }
}

/** A discarded commercial tyre resting on its side in the mud, on its ring of snaggable contact segments. */
function harborTyre(set, tread) {
  const centre = new THREE.Vector3();
  for (const ob of tread) centre.add(new THREE.Vector3(...ob.p0));
  centre.divideScalar(tread.length);
  const [north, east, depth] = centre.toArray();
  const halfHeight = tread[0].radius;
  const radius = centre.distanceTo(new THREE.Vector3(...tread[0].p0)) + halfHeight;
  // Section from the inner bead, over the sidewall to the shoulder and across the tread.
  const section = [[.51, -.85], [.51, .68], [.57, .95], [.78, 1], [.94, .76], [.99, .53],
    [.99, .22], [.965, .15], [.99, .09], [.99, -.11], [.965, -.17], [.99, -.24],
    [.99, -.58], [.9, -.86], [.65, -.98], [.51, -.85]];
  const profile = section.reverse().map(([r, h]) => new THREE.Vector2(radius * r, halfHeight * h));
  const tyre = new THREE.LatheGeometry(profile, 28);
  tyre.translate(-east, -depth, north);
  set.addBatched('tyre-tread', tyre, 'rubber', tread.map(ob => ob.name), 'solid', tread);
}
