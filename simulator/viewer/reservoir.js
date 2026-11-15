// Original reservoir dressing; collision geometry comes from the server, horizon assets from a seeded manifest.
import * as THREE from 'three';

const COLORS = {concrete: 0x817e6b, steel: 0x485651, wood: 0x554332, white: 0xd5d6c7,
  blue: 0x216bb5, orange: 0xe17c32, lime: 0xc5ed26,
  rope: 0x9d9876, cable: 0xc5ed26, red: 0x9e3429};

export function isReservoirKind(kind) {
  return kind?.startsWith('res_') || kind?.startsWith('reservoir_');
}

export function reservoirMaterial(kind) {
  const key = kind.slice(kind.startsWith('reservoir_') ? 10 : 4);
  const material = new THREE.MeshStandardMaterial({color: COLORS[key] || 0x718268, roughness: .87});
  material.userData.structureKind = kind;
  if (key === 'concrete' && typeof document !== 'undefined') {
    const texture = new THREE.TextureLoader().load('models/reservoir/concrete.webp');
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    material.map = texture;
    material.addEventListener('dispose', () => texture.dispose());
  }
  return material;
}

export function buildReservoirSurface(group, detail) {
  const water = new THREE.Mesh(new THREE.PlaneGeometry(800, 800),
    new THREE.MeshStandardMaterial({color: 0x395d46, roughness: .24, metalness: .25}));
  water.rotation.x = -Math.PI / 2;
  water.position.y = .015;
  group.add(water);
  // Decorative landscape never replaces underwater collision geometry.
  const materials = [0x3e5740, 0x496345, 0x526c48].map(color =>
    new THREE.MeshStandardMaterial({color, roughness: 1, flatShading: true}));
  for (let i = 0; i < 15; i++) {
    const bank = (i - 7) * 32;
    const height = 32 + 18 * Math.sin(i * 7) ** 2;
    const hill = new THREE.Mesh(new THREE.SphereGeometry(1, 14, 8), materials[i % 3]);
    hill.position.set(bank, -8, 230 + 18 * Math.sin(i * .7));
    hill.scale.set(57, height, 58);
    group.add(hill);
    const count = detail === 'low' ? 12 : 36;
    const trees = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), materials[(i + 1) % 3], count);
    const matrix = new THREE.Matrix4();
    for (let j = 0; j < count; j++) {
      const a = j * 2.39996;
      const radius = 48 * Math.sqrt((j + .5) / count);
      const x = radius * Math.cos(a);
      const z = radius * Math.sin(a);
      const y = height * Math.sqrt(Math.max(0, 1 - (x / 65) ** 2 - (z / 58) ** 2));
      matrix.compose(new THREE.Vector3(hill.position.x + x, hill.position.y + y + 3, hill.position.z + z),
        new THREE.Quaternion(), new THREE.Vector3(5, 6, 5));
      trees.setMatrixAt(j, matrix);
    }
    group.add(trees);
  }
  const bridge = new THREE.MeshStandardMaterial({color: 0xa3a394, roughness: .9});
  function box(x, y, z, a, b, c) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(a, b, c), bridge);
    mesh.position.set(x, y, z);
    group.add(mesh);
  }
  box(0, 19, 150, 180, 1.4, 6);
  for (let i = -3; i <= 3; i++) box(i * 24, 9, 150, 2, 20, 3);
  for (const z of [147, 153]) box(0, 20.5, z, 180, .6, .3);
}

export function buildReservoirPart(set, ob) {
  const point = p => new THREE.Vector3(-p[1], -p[2], p[0]);
  let geometry;
  if (ob.type === 'box') {
    geometry = new THREE.BoxGeometry(ob.half[1] * 2, ob.half[2] * 2, ob.half[0] * 2);
    geometry.rotateY(-ob.yaw_deg * Math.PI / 180);
    geometry.translate(...point(ob.center).toArray());
    const uv = geometry.attributes.uv;
    const position = geometry.attributes.position;
    const normal = geometry.attributes.normal;
    for (let i = 0; i < uv.count; i++) {
      const vertical = Math.abs(normal.getY(i)) < .5;
      uv.setXY(i, position.getX(i) * .3, (vertical ? position.getY(i) : position.getZ(i)) * .3);
    }
  } else {
    const a = point(ob.p0);
    const b = point(ob.p1);
    geometry = new THREE.CapsuleGeometry(ob.radius, a.distanceTo(b), 2, set.detailName === 'low' ? 6 : 10);
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()));
    geometry.translate(...a.add(b).multiplyScalar(.5).toArray());
  }
  set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
}
