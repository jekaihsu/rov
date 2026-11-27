// Lost hand tools resting on the harbor mud. Geometry is local to each authoritative habitat pose.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

export function harborToolGeometry(variant) {
  const parts = [];
  function bar(x, z, width, length, angle = 0) {
    const shape = new THREE.BoxGeometry(width, .035, length);
    shape.rotateY(angle);
    parts.push(shape.translate(x, .028, z));
  }
  function eye(x, z, radius) {
    const shape = new THREE.TorusGeometry(radius, .022, 6, 16);
    shape.rotateX(Math.PI / 2);
    parts.push(shape.translate(x, .03, z));
  }
  if (variant === 0) {
    // Ring spanner, with two splayed jaws at the opposite end of its shank.
    eye(0, -.21, .067);
    bar(0, 0, .05, .4);
    for (const side of [-1, 1]) bar(side * .039, .212, .034, .104, side * .49);
  } else if (variant === 1) {
    // Folding grapnel with opposed flukes and a crown ring.
    eye(0, -.34, .08);
    bar(0, 0, .083, .59);
    for (const side of [-1, 1]) {
      bar(side * .13, .22, .08, .36, -side * 1.12);
      bar(side * .25, .10, .095, .18, side * .32);
    }
  } else {
    // Abandoned wire lifting sling with a swaged ferrule below each eye.
    for (const side of [-1, 1]) {
      eye(0, side * .32, .092);
      bar(0, side * .20, .064, .089);
    }
    bar(0, 0, .026, .43);
  }
  return mergeGeometries(parts);
}
