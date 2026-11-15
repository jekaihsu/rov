// Reservoir collision-derived review geometry. Original materials; no photographic textures.
import * as THREE from 'three';
const P = p => new THREE.Vector3(-p[1], -p[2], p[0]);
export const RESERVOIR_CAMERAS = Object.freeze({
  reservoir_overlook: {eye: [-16, -16, -12], target: [8, 4, 0]},
  reservoir_equipment: {eye: [4, -5, -2], target: [7, -3, -.6]}
});
const COLORS = {concrete: 0x7e8075, steel: 0x67544b, wood: 0x514a31,
  white: 0xc8c7b5, orange: 0xc76825, blue: 0x275b83, rope: 0x9d9876, cable: 0xc6ec17, red: 0x9e3429};

export function reservoirMaterial(kind) {
  const material = new THREE.MeshStandardMaterial({color: COLORS[kind.slice(10)], roughness: .9});
  material.userData.structureKind = kind;
  return material;
}

export function buildReservoirPart(set, ob) {
  let geometry;
  if (ob.type === 'box') {
    geometry = new THREE.BoxGeometry(ob.half[1]*2, ob.half[2]*2, ob.half[0]*2);
    geometry.rotateY(-ob.yaw_deg*Math.PI/180);
    geometry.translate(...P(ob.center).toArray());
  } else {
    const a = P(ob.p0);
    const b = P(ob.p1);
    geometry = new THREE.CapsuleGeometry(ob.radius, a.distanceTo(b), 2, set.detailName === 'low' ? 6 : 12);
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()));
    geometry.translate(...a.add(b).multiplyScalar(.5).toArray());
  }
  set.addBatched(ob.kind, geometry, ob.kind, [ob.name], ob.above_water ? 'above' : 'solid', [ob]);
}
