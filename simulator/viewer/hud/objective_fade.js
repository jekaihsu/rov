// Objective marks (checkpoint rings) are world objects; when one projects onto the bottom read-outs it fades back
// so the numbers stay readable (hud/safe_zones.js). Presentation only.
import * as THREE from 'three';
import {readoutFade} from './safe_zones.js';

const projected = new THREE.Vector3();

// position: world position of the mark; radius: its world radius (m); viewport: the 3D view element.
export function objectiveFade(position, radius, camera, viewport) {
  projected.copy(position).project(camera);
  if (projected.z > 1 || projected.z < -1) return 1;
  const rect = viewport.getBoundingClientRect();
  const x = rect.left + (projected.x + 1) / 2 * rect.width;
  const y = rect.top + (1 - projected.y) / 2 * rect.height;
  const distance = Math.max(0.1, camera.position.distanceTo(position));
  const focal = rect.height / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2);
  return readoutFade(x, y, radius / distance * focal);
}

const WIRE_OPACITY = 0.07;

// A site-work mark is a ring and a wire sphere around its point. When the camera stands inside or right at the
// ring (the first objectives of some sites sit on the start position) the ring crosses the picture as a broad
// translucent band, so the mark fades out between 1.4 m and 0.4 m outside the ring. Presentation only.
// mark: {g, mat, wire} from the viewer's objective markers; mat.opacity must already hold this frame's value.
export function objectiveNearFade(mark, radius, camera) {
  const outside = camera.position.distanceTo(mark.g.position) - radius;
  const fade = THREE.MathUtils.smoothstep(outside, 0.4, 1.4);
  mark.mat.opacity *= fade;
  mark.wire.opacity = WIRE_OPACITY * fade;
  return fade;
}
