// Distance LOD for the active render quality.
// The metres below are display distances (how far the camera is from the
// model), not vehicle performance parameters. auto, high and ultra keep the
// authored distances. medium and the performance modes pull the coarser levels
// closer so a smaller GPU draws less geometry. Source grade: estimated.

import { currentQualityMode, onQualityMode } from './render_quality.js';

export function lodDistanceScale(mode) {
  if (mode === 'medium') return 0.7;
  if (mode === 'low' || mode === 'performance') return 0.45;
  return 1;
}

export function scaledLodDistance(metres, mode) {
  return metres * lodDistanceScale(mode);
}

/** Rewrite a THREE.LOD's level distances from the authored metres stored on each object. */
export function bindLodQuality(lod, mode) {
  if (!lod || !lod.levels) return;
  const scale = lodDistanceScale(mode);
  for (const level of lod.levels) {
    const object = level.object;
    if (object.userData.lodBaseDistance == null) {
      object.userData.lodBaseDistance = level.distance;
    }
    level.distance = object.userData.lodBaseDistance * scale;
  }
  lod.levels.sort((a, b) => a.distance - b.distance);
}

/** Apply the current quality now, and again whenever the quality mode changes. */
export function watchLodQuality(lod) {
  bindLodQuality(lod, currentQualityMode());
  onQualityMode((mode) => bindLodQuality(lod, mode));
}

// Falcon and the heavy configuration. Training X1 keeps its own 0 / 12 / 40 m table.
export const FALCON_LOD = Object.freeze([
  Object.freeze({ url: 'models/falcon.glb', distance: 0 }),
  Object.freeze({ url: 'models/falcon_lod1.glb', distance: 16 }),
  Object.freeze({ url: 'models/falcon_lod2.glb', distance: 40 }),
]);

export const HEAVY_LOD = Object.freeze([
  Object.freeze({ url: 'models/bluerov2_heavy.glb', distance: 0 }),
  Object.freeze({ url: 'models/bluerov2_heavy_lod1.glb', distance: 10 }),
  Object.freeze({ url: 'models/bluerov2_heavy_lod2.glb', distance: 28 }),
]);

// Filenames relative to the models directory. The intro passes its own base URL.
// One far level. A middle level did not reduce the skinned mesh (meshopt
// simplify leaves it near 10k triangles) and would add another download.
export const CREW_LOD_FILES = Object.freeze(['worker_lod2.glb']);
export const CREW_LOD_DISTANCES = Object.freeze([18]);
