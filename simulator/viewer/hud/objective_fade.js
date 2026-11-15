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
