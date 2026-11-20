// Harbor pile bents and shoreside silhouettes. All submerged dimensions come from world obstacles.
import * as THREE from 'three';

function pileRow(set, piles, seeded) {
  const first = piles[0];
  const height = first.p1[2] - first.p0[2];
  const sides = set.detailName === 'high' ? 24 : 12;
  const shape = new THREE.CylinderGeometry(first.radius, first.radius, height, sides, 9);
  const uv = shape.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * Math.PI * 2 * first.radius, uv.getY(i) * height);
  // Vertex colours mark the tidal and subtidal communities even on the lowest quality tier.
  // Rotation per shaft changes which flank of each irregular band faces the inspection lane.
  const position = shape.attributes.position;
  const colors = [];
  const color = new THREE.Color();
  for (let i = 0; i < position.count; i++) {
    const phi = Math.atan2(position.getX(i), position.getZ(i));
    const depth = first.p0[2] + height / 2 - position.getY(i);
    const boundary = depth + .4 * Math.sin(3 * phi) + .2 * Math.cos(phi + depth);
    color.setHex(0xf1ebe0);
    if (boundary > -.4 && boundary < 1.7) color.setHex(0x708247);
    if (boundary >= 1.7 && boundary < 6.3) color.setHex(0x706f65);
    if (boundary >= 6.3 && boundary < 10) color.setHex(0xb4a991);
    colors.push(color.r, color.g, color.b);
  }
  shape.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const material = set.makeMaterial('pileConcrete');
  material.vertexColors = true;
  const mesh = new THREE.InstancedMesh(shape, material, piles.length);
  mesh.userData = {paintable: true, role: 'solid', colliders: piles.map(ob => ob.name)};
  const shells = [];
  for (const [index, ob] of piles.entries()) {
    const [north, east, top] = ob.p0;
    const rng = seeded(ob.name);
    const matrix = new THREE.Matrix4().makeRotationY(rng() * 2 * Math.PI);
    matrix.setPosition(-east, -top - height / 2, north);
    mesh.setMatrixAt(index, matrix);
    mesh.setColorAt(index, new THREE.Color().setScalar(.72 + rng() * .28));
    set.anchor(ob, mesh);
    // Broad patches of weed and mussels near the tide line, chalky barnacles farther down.
    for (let patch = 0; patch < 9; patch++) {
      const depth = rng() ** 1.6 * (height + top - .5);
      const azimuth = rng() * 2 * Math.PI;
      for (let j = 0; j < 7; j++) {
        const phi = azimuth + (rng() - .5) * 1.4;
        const y = -Math.max(.03, depth + rng() - .5);
        const color = y > -2 ? 0x59602a : y > -8 ? 0x30332e : 0x938776;
        const scale = y > -2 ? [.045, .23, .024] : [.045, .075, .034];
        const item = new THREE.Object3D();
        item.position.set(-east + ob.radius * Math.sin(phi), y, north + ob.radius * Math.cos(phi));
        item.rotation.set(0, phi, rng() - .5, 'YXZ');
        item.scale.set(...scale).multiplyScalar(.6 + .4 * rng());
        item.updateMatrix();
        shells.push({matrix: item.matrix, color});
      }
    }
  }
  set.group.add(mesh);
  // Only render millimetre/centimetre-scale relief in inspection range; the depth bands remain at distance.
  const relief = new THREE.InstancedMesh(new THREE.OctahedronGeometry(1), set.makeMaterial('rock'), shells.length);
  relief.userData = {role: 'attached', colliders: mesh.userData.colliders};
  shells.forEach(({matrix, color}, i) => {
    relief.setMatrixAt(i, matrix);
    relief.setColorAt(i, new THREE.Color(color));
  });
  relief.computeBoundingSphere();
  set.group.add(relief);
  return relief;
}

export function harborStructures(set, obstacles, consumed, seeded, boxAt) {
  if (!obstacles.some(ob => ob.kind === 'quay')) return;
  const piles = obstacles.filter(ob => ob.kind === 'pile');
  const rows = new Map();
  for (const ob of piles) {
    const key = ob.p0[1];
    if (!rows.has(key)) rows.set(key, []);
    rows.get(key).push(ob);
    consumed.add(ob.name);
  }
  for (const row of rows.values()) {
    const relief = pileRow(set, row, seeded);
    const center = relief.boundingSphere.center;
    relief.onBeforeRender = function selectDetail(renderer, scene, camera) {
      relief.count = camera.position.distanceTo(center) < 27 ? relief.instanceMatrix.count : 0;
    };
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
    for (const dx of [-4, 4]) block(metal, x + dx, 4, 60.96, 3.2, 3.8, .15);
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

/** A discarded commercial tyre resting on its side in the mud, within its server box. */
export function harborTyre(set, ob) {
  const [radius, , halfHeight] = ob.half;
  const [north, east, depth] = ob.center;
  // Section from the inner bead, over the sidewall to the shoulder and across the tread.
  const section = [[.51, -.85], [.51, .68], [.57, .95], [.78, 1], [.94, .76], [.99, .53],
    [.99, .22], [.965, .15], [.99, .09], [.99, -.11], [.965, -.17], [.99, -.24],
    [.99, -.58], [.9, -.86], [.65, -.98], [.51, -.85]];
  const profile = section.reverse().map(([r, h]) => new THREE.Vector2(radius * r, halfHeight * h));
  const tyre = new THREE.LatheGeometry(profile, 28);
  tyre.translate(-east, -depth, north);
  set.add(tyre, 'rubber', [ob.name], 'solid', [ob]);
}
