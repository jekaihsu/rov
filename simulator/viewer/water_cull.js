// Culls presentation-only objects that the water already makes invisible from the current camera.
// Under water every light path to the camera is attenuated by exp(-c L) along its underwater length L and ends in
// the water colour (fx/water_optics.js waterApply); the water background shows exactly that colour. An object whose
// nearest point is so far that exp(-c L) is below 0.1 % on every channel draws the same pixels as the background,
// so skipping it changes nothing on screen. The legacy look uses three's fog instead (linear, or exponential with a
// negative near, fx/silt.js): there an object beyond it in view depth is pure fog colour. An object is hidden only
// when both tests agree.
// Used for the support boat that holds station at the spool for the whole dive (spool_station.js): dozens of draw
// calls and a skinned crew member that the pilot at depth never sees.
import * as THREE from 'three';
import { waterUniforms } from './fx/water_optics.js';

// ln(1000): 0.1 % of the direct signal is left, well below one 8-bit step of any lit surface.
const EXTINCTION = Math.log(1000);
const centre = new THREE.Vector3();
const forward = new THREE.Vector3();

// Bounding sphere of an object in its own local frame (static shape; the object itself may move a little).
export function localBoundingSphere(object) {
  object.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  object.worldToLocal(sphere.center);
  return sphere;
}

// Shortest underwater length of any segment from the eye (below the surface) to a point of the sphere.
function underwaterLength(eye, centreWorld, radius) {
  const nearest = Math.max(0, eye.distanceTo(centreWorld) - radius);
  const top = centreWorld.y + radius;
  if (top <= 0) return nearest;
  // A point above the surface: only the part of the segment below y = 0 counts, at least this share of it.
  return nearest * -eye.y / (top - eye.y);
}

/**
 * True when ``object`` (bounding sphere ``sphere`` from localBoundingSphere) cannot show in this frame because the
 * water hides it. Above water nothing is hidden.
 */
export function hiddenByWater(object, sphere, camera, scene) {
  const eye = camera.position;
  if (eye.y >= 0) return false;
  centre.copy(sphere.center).applyMatrix4(object.matrixWorld);
  const scale = object.matrixWorld.getMaxScaleOnAxis();
  const radius = sphere.radius * scale;
  const c = waterUniforms.uWaterC.value;
  const clearest = Math.min(c.x, c.y, c.z);
  if (!(clearest > 0) || underwaterLength(eye, centre, radius) * clearest < EXTINCTION) return false;
  const fog = scene?.fog;
  if (!fog?.isFog) return true;
  camera.getWorldDirection(forward);
  const depth = centre.sub(eye).dot(forward) - radius;
  // silt.js: a negative near is exponential fog 1 - exp(near * depth); otherwise three's linear fog.
  if (fog.near < 0) return depth * -fog.near > EXTINCTION;
  return depth > fog.far;
}
