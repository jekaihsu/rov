/** Place distance-field scene assets; authored LODs share one collision field and coordinate frame. */
import * as THREE from 'three';
import {loadGLTF} from './glb.js';

const cache = new Map();

export function placeSceneModel(ob, worldGroup, mapPosition, detail) {
  const holder = new THREE.Group();
  const angle = ob.heading_deg * Math.PI / 180;
  mapPosition(ob.origin, holder.position);
  holder.rotation.y = Math.atan2(-Math.cos(angle), -Math.sin(angle));
  worldGroup.add(holder);
  let url = ob.model;
  if (url === 'models/wreck_chenjiao.glb' && detail !== 'high') {
    url = url.replace('.glb', detail === 'low' ? '_lod2.glb' : '_lod1.glb');
  }
  if (!cache.has(url)) {
    cache.set(url, loadGLTF(url).catch((error) => {
      cache.delete(url);
      console.warn('model', url, error?.message || error);
      return null;
    }));
  }
  cache.get(url).then((gltf) => {
    if (!gltf || holder.parent !== worldGroup) return;
    const model = gltf.scene.clone(true);
    model.traverse((object) => {
      if (!object.isMesh) return;
      object.userData.paintable = true;
      object.castShadow = false;
      object.receiveShadow = true;
      object.frustumCulled = true;
    });
    holder.add(model);
  });
}
