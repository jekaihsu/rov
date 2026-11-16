/** Place distance-field scene assets; authored LODs share one collision field and coordinate frame.
 * Chenjiao uses distance LODs; Korean Castle uses the selected quality tier.
 * Menu backgrounds load the middle tier so the wreck silhouette stays legible. */
import * as THREE from 'three';
import {loadGLTF} from './glb.js';

const cache = new Map();

// Distances in metres from the camera: high detail first, then mid, then far.
const WRECK_LOD_DISTANCES = [0, 40, 100];
const WRECK_BASE = 'models/wreck_chenjiao.glb';
const LOD_MODELS = new Set([WRECK_BASE, 'models/korean_castle.glb']);

function modelUrl(ob, detail = 'high') {
  if (!LOD_MODELS.has(ob.model)) return ob.model;
  return wreckLodUrls(ob.model)[{high: 0, medium: 1, low: 2}[detail] ?? 0];
}

function wreckLodUrls(base = WRECK_BASE) {
  if (!base.endsWith('.glb')) return [base];
  const stem = base.slice(0, -4);
  return [`${stem}.glb`, `${stem}_lod1.glb`, `${stem}_lod2.glb`];
}

function loadCached(url) {
  if (!cache.has(url)) {
    cache.set(url, loadGLTF(url).catch((error) => {
      cache.delete(url);
      console.warn('model', url, error?.message || error);
      return null;
    }));
  }
  return cache.get(url);
}

function markMeshes(root) {
  root.traverse((object) => {
    if (!object.isMesh) return;
    object.userData.paintable = true;
    object.castShadow = false;
    object.receiveShadow = true;
    object.frustumCulled = true;
  });
}

function holderFor(ob, worldGroup, mapPosition) {
  const holder = new THREE.Group();
  const angle = ob.heading_deg * Math.PI / 180;
  mapPosition(ob.origin, holder.position);
  holder.rotation.y = Math.atan2(-Math.cos(angle), -Math.sin(angle));
  worldGroup.add(holder);
  return holder;
}

/** Menu / background: farthest authored LOD (cheap), unless the model is a large wreck —
 * then use the mid LOD so the site card still reads as a ship inside the menu fog.
 * `stillCurrent` (optional) aborts a stale async load when the menu has already switched scenes. */
export function placeSceneModelLow(ob, worldGroup, mapPosition, stillCurrent = null) {
  const holder = holderFor(ob, worldGroup, mapPosition);
  const url = modelUrl(ob, 'medium');
  loadCached(url).then((gltf) => {
    if (stillCurrent && !stillCurrent()) {
      holder.removeFromParent();
      return;
    }
    if (!gltf || holder.parent !== worldGroup) return;
    const model = gltf.scene.clone(true);
    markMeshes(model);
    holder.add(model);
  });
  return holder;
}

export function placeSceneModel(ob, worldGroup, mapPosition, _detail = 'medium') {
  // Preserve Chenjiao's distance LODs and Korean Castle's quality-tier selection.
  const holder = holderFor(ob, worldGroup, mapPosition);
  if (ob.model !== WRECK_BASE) {
    loadCached(modelUrl(ob, _detail)).then((gltf) => {
      if (!gltf || holder.parent !== worldGroup) return;
      const model = gltf.scene.clone(true);
      markMeshes(model);
      holder.add(model);
    });
    return holder;
  }
  const lod = new THREE.LOD();
  lod.name = 'WreckChenjiaoLOD';
  holder.add(lod);
  const urls = ['high', 'medium', 'low'].map(detail => modelUrl(ob, detail));
  Promise.all(urls.map(loadCached)).then((gltfs) => {
    if (holder.parent !== worldGroup) return;
    for (let index = 0; index < urls.length; index++) {
      const gltf = gltfs[index];
      if (!gltf) continue;
      const model = gltf.scene.clone(true);
      markMeshes(model);
      lod.addLevel(model, WRECK_LOD_DISTANCES[index] ?? index * 40);
    }
  });
  return holder;
}

export {WRECK_LOD_DISTANCES, wreckLodUrls, modelUrl};
