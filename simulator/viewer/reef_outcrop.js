// Faceted limestone faces cut into the capsule supplied by the server. The
// long axis and both ends follow that collision surface, including overhangs.
import * as THREE from 'three';
import {SCAN_TILE, scanTexture} from './scan_materials.js';

const UP = new THREE.Vector3(0, 1, 0);

export function outcropGeometry(a, b, radius, radial) {
  const length = a.distanceTo(b);
  const middle = a.clone().lerp(b, .5);
  const rotation = new THREE.Quaternion().setFromUnitVectors(UP, b.clone().sub(a).normalize());
  const profile = [];

  // Sample the straight section as well as the ends so strata interrupt the
  // silhouette. The same metre-scale variation crosses the seam of each ring.
  for (let i = 0; i <= 4; i++) {
    const angle = -Math.PI / 2 + i * Math.PI / 8;
    profile.push(new THREE.Vector2(radius * Math.cos(angle), -length / 2 + radius * Math.sin(angle)));
  }
  const rings = Math.ceil(length / .73);
  for (let i = 1; i < rings; i++) {
    profile.push(new THREE.Vector2(radius, length * (i / rings - .5)));
  }
  for (let i = 0; i <= 4; i++) {
    const angle = i * Math.PI / 8;
    profile.push(new THREE.Vector2(radius * Math.cos(angle), length / 2 + radius * Math.sin(angle)));
  }
  const geometry = new THREE.LatheGeometry(profile, radial);
  const pos = geometry.attributes.position;
  const v = new THREE.Vector3();
  const normal = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    normal.set(v.x, v.y - THREE.MathUtils.clamp(v.y, -length / 2, length / 2), v.z).normalize();
    v.applyQuaternion(rotation).add(middle);
    const strata = Math.sin(4 * v.y + .8 * v.z) * Math.sin(2 * v.z + 1.5 * v.x);
    v.addScaledVector(normal.applyQuaternion(rotation), -.06 + .09 * strata);
    pos.setXYZ(i, v.x, v.y, v.z);
  }
  const facets = geometry.toNonIndexed();
  geometry.dispose();
  facets.computeVertexNormals();
  const points = facets.attributes.position;
  const normals = facets.attributes.normal;
  const uv = facets.attributes.uv;
  const colours = new Float32Array(points.count * 3);
  const tint = new THREE.Color();
  for (let i = 0; i < points.count; i++) {
    v.fromBufferAttribute(points, i);
    // Planar projection per facet keeps the intertidal rock scan at its real
    // metre scale, including across vertical joints and the arch underside.
    normal.fromBufferAttribute(normals, i);
    let u = v.x;
    let w = v.y;
    if (Math.abs(normal.y) > Math.max(Math.abs(normal.x), Math.abs(normal.z))) w = v.z;
    else if (Math.abs(normal.x) > Math.abs(normal.z)) u = v.z;
    uv.setXY(i, u / SCAN_TILE.rockbed, w / SCAN_TILE.rockbed);
    const crust = .5 + .5 * Math.sin(v.x * 1.9 + v.y * 3.3 + .7 * Math.sin(v.z * 2.1));
    const sand = Math.max(0, normals.getY(i)) * (.45 + crust * .35);
    tint.setRGB(.28 + .42 * crust + .29 * sand, .35 + .23 * crust + .37 * sand, .32 + .22 * crust + .29 * sand);
    tint.toArray(colours, i * 3);
  }
  facets.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
  return facets;
}

/** Reuse the site's licensed intertidal stone scan on the new exposed faces. */
export function dressOutcrop(material, detail) {
  const size = detail === 'high' ? 0 : 512;
  material.color.setHex(0xf2e7cf);
  material.vertexColors = true;
  material.map = scanTexture('rockbed_c', {size}, function assignColour(texture) {
    material.map = texture;
  });
  if (detail !== 'low') {
    material.normalMap = scanTexture('rockbed_n', {size}, function assignNormal(texture) {
      material.normalMap = texture;
    });
  }
  return material;
}
